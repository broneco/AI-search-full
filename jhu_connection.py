"""Explicit local JHU helper lifecycle. Does not import app Settings or connect SQL."""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

from app.core.tenant_identity import tenant_config_name
from app.providers.jhu_secrets import JHUConnectionError, SecretReferences, key_vault_resolver
from scripts.vpn_spike.manager import HelperManager
from scripts.vpn_spike.profile import validated_profile

ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'status', 'stop', 'restart', 'reconnect', 'check-secrets'])
    parser.add_argument('--tenant', default='jhu')
    parser.add_argument('--vault', default='ju-ai-search-kv-prod')
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--endpoint', help='Non-secret upstream HTTP URL, not a proxy URL')
    parser.add_argument('--wait', action='store_true')
    args = parser.parse_args()
    try:
        if tenant_config_name(args.tenant) != 'jhu':
            raise JHUConnectionError('jhu_helper_tenant_invalid')
        manager = HelperManager(ROOT)
        references = SecretReferences('ju-ai-search-vpn-username-prod', 'ju-ai-search-vpn-password-prod',
                                      'ju-ai-search-jhu-api-username-prod', 'ju-ai-search-jhu-api-password-prod')
        if args.action == 'check-secrets':
            with key_vault_resolver(args.vault, references) as resolver:
                resolver.vpn_credentials()
                resolver.api_credentials()
            result = dict(state='configured', source='key_vault', secret_count=4)
        elif args.action == 'status':
            result = manager.status()
        elif args.action == 'stop':
            result = manager.stop()
        elif args.action == 'reconnect':
            result = manager.reconnect()
            if args.wait:
                result = manager.wait_ready(after_generation=result['generation'])
        else:
            if args.profile is None:
                raise JHUConnectionError('jhu_profile_required')
            profile = args.profile.read_text(encoding='utf-8-sig')
            validated_profile(profile)
            endpoint = args.endpoint or os.environ.get('JHU_LLM_ENDPOINT')
            if not endpoint:
                from dotenv import dotenv_values
                # Endpoint only. Old plaintext credentials never participate in this mode.
                endpoint = (dotenv_values(ROOT/'.env.local').get('JHU_LLM_ENDPOINT')
                            or dotenv_values(ROOT/'.env.jhu-model').get('JHU_LLM_ENDPOINT'))
            url = urlsplit(endpoint or '')
            if (url.scheme != 'http' or url.username or url.password or url.query or url.fragment
                    or url.path not in {'', '/'}):
                raise JHUConnectionError('jhu_endpoint_invalid')
            target, port = str(ipaddress.IPv4Address(url.hostname)), url.port or 80
            fingerprint = hashlib.sha256(json.dumps([2, profile, target, port, args.vault,
                references.__dict__], sort_keys=True).encode()).hexdigest()

            def load_payload():
                with key_vault_resolver(args.vault, references) as resolver:
                    pair = resolver.vpn_credentials()
                return dict(profile=profile, target_ip=target, target_port=port,
                            vpn_username=pair.username, vpn_password=pair.password)

            if args.action == 'restart':
                # A vault outage must not tear down the still-working old session.
                prepared = load_payload()
                manager.stop()
                result = manager.start(fingerprint, lambda: prepared)
            else:
                result = manager.start(fingerprint, load_payload)
            if args.wait:
                result = manager.wait_ready()
        print(json.dumps(result))
        return 0 if result['state'] in {'ready', 'connecting', 'disabled', 'configured'} else 1
    except JHUConnectionError as exc:
        print(json.dumps(dict(state='degraded', code=exc.code)))
        return 1
    except Exception:
        print(json.dumps(dict(state='degraded', code='jhu_configuration_invalid')))
        return 1


if __name__ == '__main__':
    sys.exit(main())
