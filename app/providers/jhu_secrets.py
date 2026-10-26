"""Explicit, narrow Key Vault reads. Importing this module does no I/O.

Independent of Settings: local SQL/auth/cloud secrets are never loaded here.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field
import re
from typing import Iterator, Literal, Protocol

from azure.core.exceptions import (
    ClientAuthenticationError, HttpResponseError, ResourceNotFoundError,
    ServiceRequestError, ServiceResponseError,
)


class JHUConnectionError(Exception):
    """A fixed code is safe for logs/status; Azure exceptions are never echoed."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class CredentialPair:
    username: str = field(repr=False)
    password: str = field(repr=False)

    def __post_init__(self):
        if any(not isinstance(v, str) or not v or len(v) > 25_000
               or any(c in v for c in '\r\n\x00') for v in (self.username, self.password)):
            raise JHUConnectionError('jhu_secret_invalid')


@dataclass(frozen=True)
class SecretReferences:
    vpn_username: str
    vpn_password: str
    api_username: str
    api_password: str

    def __post_init__(self):
        values = [self.vpn_username, self.vpn_password, self.api_username, self.api_password]
        if len(set(values)) != 4 or not all(re.fullmatch(r'[A-Za-z0-9-]{1,127}', v) for v in values):
            raise JHUConnectionError('jhu_secret_reference_invalid')


class SecretReader(Protocol):
    def get_secret(self, name: str): ...


@dataclass(frozen=True)
class APISecretReferences:
    api_username: str
    api_password: str

    def __post_init__(self):
        values = [self.api_username, self.api_password]
        if len(set(values)) != 2 or not all(re.fullmatch(r'[A-Za-z0-9-]{1,127}', v) for v in values):
            raise JHUConnectionError('jhu_secret_reference_invalid')


class JHUSecretResolver:
    """No env fallback, bulk vault listing, background refresh or secret cache."""

    def __init__(self, client: SecretReader, references: SecretReferences | APISecretReferences):
        self._client, self.references = client, references

    def _read(self, name: str) -> str:
        try:
            value = self._client.get_secret(name).value
        except ResourceNotFoundError:
            raise JHUConnectionError('jhu_secret_missing') from None
        except ClientAuthenticationError:
            raise JHUConnectionError('jhu_vault_authentication_failed') from None
        except (ServiceRequestError, ServiceResponseError, TimeoutError, ConnectionError):
            raise JHUConnectionError('jhu_vault_unreachable') from None
        except HttpResponseError as exc:
            code = ('jhu_vault_forbidden' if exc.status_code == 403 else
                    'jhu_vault_authentication_failed' if exc.status_code == 401 else
                    'jhu_vault_unavailable')
            raise JHUConnectionError(code) from None
        except Exception:
            raise JHUConnectionError('jhu_vault_unavailable') from None
        if not isinstance(value, str) or not value:
            raise JHUConnectionError('jhu_secret_invalid')
        return value

    def vpn_credentials(self) -> CredentialPair:
        if isinstance(self.references, APISecretReferences):
            raise JHUConnectionError('jhu_vpn_credentials_not_configured')
        return CredentialPair(self._read(self.references.vpn_username), self._read(self.references.vpn_password))

    def api_credentials(self) -> CredentialPair:
        pair = CredentialPair(self._read(self.references.api_username), self._read(self.references.api_password))
        if ':' in pair.username:
            raise JHUConnectionError('jhu_secret_invalid')
        return pair


@contextmanager
def key_vault_resolver(vault: str, references: SecretReferences | APISecretReferences,
                      identity: Literal['azure_cli', 'managed_identity'] = 'azure_cli') -> Iterator[JHUSecretResolver]:
    if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9-]{1,22}[a-zA-Z0-9]', vault or ''):
        raise JHUConnectionError('jhu_vault_name_invalid')
    # An explicit identity choice avoids accidentally using unrelated env credentials.
    from azure.identity import AzureCliCredential, ManagedIdentityCredential
    from azure.keyvault.secrets import SecretClient
    if identity == 'azure_cli':
        credential = AzureCliCredential(process_timeout=10)
    elif identity == 'managed_identity':
        credential = ManagedIdentityCredential()
    else:
        raise JHUConnectionError('jhu_identity_invalid')
    with credential:
        with SecretClient(vault_url=f'https://{vault}.vault.azure.net', credential=credential,
                          logging_enable=False, retry_total=0, connection_timeout=5, read_timeout=10) as client:
            yield JHUSecretResolver(client, references)
