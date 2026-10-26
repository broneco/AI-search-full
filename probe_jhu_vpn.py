"""Experimental Docker-only JHU connectivity probe; does not import app settings."""
import argparse
import ipaddress
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit
import uuid

from scripts.vpn_spike.profile import validated_profile
from scripts.vpn_spike.runtime import IMAGE, container_command
from app.providers.jhu_secrets import JHUConnectionError, SecretReferences, key_vault_resolver

ROOT = Path(__file__).resolve().parent


def payload_for(args) -> dict:
    # Validate first, before contacting Key Vault. No private profile is copied to disk.
    profile = args.profile.read_text(encoding='utf-8-sig')
    validated_profile(profile)
    from dotenv import dotenv_values
    local = dotenv_values(args.api_env)
    endpoint = urlsplit(local.get('JHU_LLM_ENDPOINT') or '')
    if endpoint.scheme != 'http' or endpoint.username or endpoint.password or endpoint.path not in {'', '/'}:
        raise ValueError('Invalid API endpoint')
    target = str(ipaddress.IPv4Address(endpoint.hostname))
    if endpoint.query or endpoint.fragment:
        raise ValueError('Invalid API endpoint')
    if not args.vault or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in args.vault):
        raise ValueError('Invalid vault')
    references = SecretReferences('ju-ai-search-vpn-username-prod', 'ju-ai-search-vpn-password-prod',
                                  'ju-ai-search-jhu-api-username-prod', 'ju-ai-search-jhu-api-password-prod')
    with key_vault_resolver(args.vault, references) as resolver:
        vpn = resolver.vpn_credentials()
        api = resolver.api_credentials() if args.api_credentials == 'key_vault' else None
    return dict(profile=profile, target_ip=target, target_port=endpoint.port or 80,
                vpn_username=vpn.username, vpn_password=vpn.password,
                api_username=api.username if api else local.get('JHU_LLM_USERNAME'),
                api_password=api.password if api else local.get('JHU_LLM_PASSWORD'),
                model=args.model, embedding_model=args.embedding_model,
                negative_name=args.negative_name, handshake_only=args.handshake_only,
                reconnect=args.reconnect, rekey=args.rekey)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'offline', 'live'])
    parser.add_argument('--profile', type=Path, help='External private .ovpn file')
    parser.add_argument('--vault', default='ju-ai-search-kv-prod')
    parser.add_argument('--api-env', type=Path, default=ROOT/'.env.jhu-model')
    parser.add_argument('--api-credentials', choices=['key_vault', 'env'], default='key_vault',
                        help='Explicit API credential source; never falls back on failure')
    parser.add_argument('--model', default='llama3.2:3b')
    parser.add_argument('--embedding-model', default='nomic-embed-text:latest')
    parser.add_argument('--negative-name', action='store_true', help='Expect server name verification failure')
    parser.add_argument('--handshake-only', action='store_true')
    parser.add_argument('--reconnect', action='store_true', help='Test one deliberate client reconnect')
    parser.add_argument('--rekey', action='store_true', help='Test a short client key renegotiation interval')
    args = parser.parse_args()
    if args.action == 'build':
        return subprocess.run(['docker', 'build', '--tag', IMAGE,
                               str(ROOT/'scripts/vpn_spike')], check=False).returncode
    if args.action == 'live' and args.profile is None:
        parser.error('--profile is required for live mode')
    name = 'ai-search-vpn-probe-' + uuid.uuid4().hex[:12]
    process = None
    try:
        payload = payload_for(args) if args.action == 'live' else {}
        process = subprocess.Popen(container_command(name, args.action), stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = process.communicate((json.dumps(payload)+'\n').encode(), timeout=600)
        # Container stdout is structured metadata; stderr may include local paths. Do not dump it.
        for line in out.decode('utf-8').splitlines():
            record = json.loads(line)
            print(json.dumps(record, ensure_ascii=True))
        if err and process.returncode:
            print(json.dumps({'stage': 'docker', 'code': 'docker_failed', 'exit_code': process.returncode}))
        return process.returncode
    except JHUConnectionError as exc:
        print(json.dumps({'stage': 'host', 'code': exc.code}))
        return 1
    except Exception as exc:
        print(json.dumps({'stage': 'host', 'code': type(exc).__name__}))
        return 1
    finally:
        if process is not None:
            subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=20, check=False)
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)


if __name__ == '__main__':
    sys.exit(main())
