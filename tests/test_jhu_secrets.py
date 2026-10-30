"""Narrow secret resolution without any private env, network or Settings load."""
from types import SimpleNamespace

from azure.core.exceptions import ClientAuthenticationError, HttpResponseError, ResourceNotFoundError, ServiceRequestError
import pytest

from app.providers.jhu_secrets import APISecretReferences, CredentialPair, JHUConnectionError, JHUSecretResolver, SecretReferences, key_vault_resolver


REFERENCES = SecretReferences('vpn-user', 'vpn-password', 'api-user', 'api-password')


class Reader:
    def __init__(self, error=None):
        self.error, self.calls = error, []

    def get_secret(self, name):
        self.calls.append(name)
        if self.error:
            raise self.error
        return SimpleNamespace(value='synthetic-' + name)


def test_backend_reference_scope_cannot_resolve_vpn_credentials():
    reader = Reader()
    resolver = JHUSecretResolver(reader, APISecretReferences('api-user', 'api-password'))
    with pytest.raises(JHUConnectionError, match='jhu_vpn_credentials_not_configured'):
        resolver.vpn_credentials()
    assert reader.calls == []
    resolver.api_credentials()
    assert reader.calls == ['api-user', 'api-password']


def test_vpn_and_api_credentials_are_resolved_separately():
    client = Reader()
    resolver = JHUSecretResolver(client, REFERENCES)
    vpn = resolver.vpn_credentials()
    assert client.calls == ['vpn-user', 'vpn-password']
    assert 'synthetic' not in repr(vpn)
    api = resolver.api_credentials()
    assert client.calls == ['vpn-user', 'vpn-password', 'api-user', 'api-password']
    assert api.username != vpn.username and 'synthetic' not in repr(api)


def http_error(status):
    error = HttpResponseError(message='synthetic-private-server-details')
    error.status_code = status
    return error


@pytest.mark.parametrize('error,code', [
    (ResourceNotFoundError('synthetic-private'), 'jhu_secret_missing'),
    (ClientAuthenticationError('synthetic-private'), 'jhu_vault_authentication_failed'),
    (ServiceRequestError('synthetic-private'), 'jhu_vault_unreachable'),
    (http_error(403), 'jhu_vault_forbidden'), (http_error(401), 'jhu_vault_authentication_failed'),
    (http_error(429), 'jhu_vault_unavailable'), (RuntimeError('synthetic-private'), 'jhu_vault_unavailable'),
])
def test_vault_errors_are_explicit_redacted_and_never_fall_back_to_env(monkeypatch, error, code):
    monkeypatch.setenv('JHU_LLM_USERNAME', 'old-env-user')
    monkeypatch.setenv('JHU_LLM_PASSWORD', 'old-env-password')
    with pytest.raises(JHUConnectionError) as caught:
        JHUSecretResolver(Reader(error), REFERENCES).api_credentials()
    assert caught.value.code == code and str(caught.value) == code
    assert caught.value.__suppress_context__


@pytest.mark.parametrize('value', ['', None, 'line\nbreak', 'nul\x00value'])
def test_invalid_secret_values_rejected_without_values(value):
    with pytest.raises(JHUConnectionError, match='^jhu_secret_invalid$'):
        CredentialPair('user', value)


def test_missing_reference_does_not_infer_another_secret():
    with pytest.raises(JHUConnectionError, match='jhu_secret_reference_invalid'):
        SecretReferences('same', 'same', 'api', 'password')


@pytest.mark.parametrize('identity,expected', [('azure_cli', 'cli'), ('managed_identity', 'mi')])
def test_identity_is_explicit_and_clients_close_without_settings(monkeypatch, identity, expected):
    import azure.identity
    import azure.keyvault.secrets
    calls, closed = [], []

    class Context:
        def __init__(self, label): self.label = label
        def __enter__(self): return self
        def __exit__(self, *_): closed.append(self.label)

    monkeypatch.setattr(azure.identity, 'AzureCliCredential', lambda **kwargs: Context('cli'))
    monkeypatch.setattr(azure.identity, 'ManagedIdentityCredential', lambda **kwargs: Context('mi'))

    def client(**kwargs):
        calls.append(kwargs)
        return Context('client')

    monkeypatch.setattr(azure.keyvault.secrets, 'SecretClient', client)
    with key_vault_resolver('synthetic-jhu-vault', REFERENCES, identity) as resolver:
        assert isinstance(resolver, JHUSecretResolver)
    assert closed == ['client', expected]
    assert calls[0]['retry_total'] == 0 and calls[0]['logging_enable'] is False
    assert calls[0]['vault_url'] == 'https://synthetic-jhu-vault.vault.azure.net'
