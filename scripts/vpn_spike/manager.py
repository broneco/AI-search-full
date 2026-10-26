"""Idempotent local Docker lifecycle; only immutable IDs with our owner label mutate."""
import hashlib
import json
from pathlib import Path
import re
import secrets
import subprocess
import time

from app.providers.jhu_secrets import JHUConnectionError
from scripts.vpn_spike.runtime import container_command

ROLE = 'ai-search.jhu-helper'
OWNER = 'ai-search.owner'
CONFIG = 'ai-search.config'
PROTOCOL = 'ai-search.jhu-protocol'
TARGET = 'ai-search.jhu-target'


class HelperManager:
    def __init__(self, root: Path, run=subprocess.run):
        self.owner = hashlib.sha256(str(root.resolve()).casefold().encode()).hexdigest()[:16]
        self.name = 'ai-search-jhu-' + self.owner
        self.run = run

    def docker(self, args: list[str], *, data: bytes | None = None, timeout: int = 20, check=True):
        try:
            result = self.run(['docker', *args], input=data, capture_output=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired):
            raise JHUConnectionError('jhu_docker_unavailable') from None
        if check and result.returncode:
            raise JHUConnectionError('jhu_docker_operation_failed')
        return result

    def inspect(self):
        # Selected fields only: never return image/runtime env or Docker secrets.
        result = self.docker(['inspect', '--format',
            '{{json .Id}} {{json .State.Running}} {{json .Config.Labels}}', self.name], check=False)
        if result.returncode:
            self.docker(['version', '--format', '{{.Server.Version}}'])
            return None
        try:
            decoder = json.JSONDecoder()
            remaining = result.stdout.decode().strip()
            values = []
            for _ in range(3):
                value, index = decoder.raw_decode(remaining)
                values.append(value)
                remaining = remaining[index:].lstrip()
            identifier, running, labels = values
            if not re.fullmatch(r'[a-f0-9]{64}', identifier):
                raise ValueError()
            if labels.get(ROLE) != 'v1' or labels.get(OWNER) != self.owner:
                raise JHUConnectionError('jhu_helper_foreign_owner')
            return dict(id=identifier, running=running, labels=labels)
        except (ValueError, TypeError, AttributeError, UnicodeError):
            raise JHUConnectionError('jhu_helper_metadata_invalid') from None

    def status(self) -> dict:
        existing = self.inspect()
        if not existing:
            return dict(state='disabled', code=None, attempts=0, generation=0)
        result = self.docker(['exec', existing['id'], 'cat', '/run/probe/status.json'], check=False)
        if result.returncode:
            return dict(state='degraded', code='vpn_service_stopped', attempts=0, generation=0)
        try:
            record = json.loads(result.stdout)
            if record['state'] not in {'disabled', 'connecting', 'ready', 'degraded', 'auth_failed'}:
                raise ValueError()
            code = record['code']
            if code is not None and not re.fullmatch(r'vpn_[a-z_]+', code):
                raise ValueError()
            output = {key: record[key] for key in ('state', 'code', 'attempts', 'generation')}
            if record['protocol_version'] != 2 or any(type(output[key]) is not int for key in ('attempts', 'generation')):
                raise ValueError()
            if record['state'] == 'ready' and time.time() - float(record['updated_at']) > 30:
                output.update(state='degraded', code='vpn_status_stale')
            return output
        except (ValueError, KeyError, TypeError):
            raise JHUConnectionError('jhu_helper_metadata_invalid') from None

    def start(self, fingerprint: str, load_payload) -> dict:
        existing = self.inspect()
        if existing:
            if existing['labels'].get(CONFIG) != fingerprint:
                raise JHUConnectionError('jhu_helper_restart_required')
            return self.status()
        others = self.docker(['ps', '-aq', '--filter', f'label={ROLE}=v1']).stdout.strip()
        if others:
            raise JHUConnectionError('jhu_helper_other_workspace_active')
        # Fetch only VPN credentials, before creating a container. Failure creates nothing.
        payload = load_payload()
        command = container_command(self.name, 'service')
        command[2:2] = ['--detach', '--label', f'{ROLE}=v1', '--label', f'{OWNER}={self.owner}',
                        '--label', f'{CONFIG}={fingerprint}', '--label', f'{PROTOCOL}=2',
                        '--label', f"{TARGET}={payload['target_ip']}:{payload['target_port']}",
                        '--publish', '127.0.0.1::18081', '--entrypoint', 'python']
        command[-1:] = ['/opt/probe/service.py', 'serve']
        created = self.docker(command[1:], check=False)
        if created.returncode:
            # A concurrent start may have won the atomic Docker name reservation.
            existing = self.inspect()
            if existing and existing['labels'].get(CONFIG) == fingerprint:
                return self.status()
            raise JHUConnectionError('jhu_helper_start_failed')
        identifier = created.stdout.decode().strip()
        if not re.fullmatch(r'[a-f0-9]{64}', identifier):
            raise JHUConnectionError('jhu_helper_metadata_invalid')
        try:
            payload = dict(payload, gateway_key=secrets.token_hex(32))
            self.docker(['exec', '-i', identifier, 'python', '/opt/probe/service.py', 'bootstrap'],
                        data=json.dumps(payload).encode())
        except BaseException:
            self.docker(['rm', '-f', identifier], check=False)
            raise
        return dict(state='connecting', code=None, attempts=0, generation=0)

    def stop(self) -> dict:
        existing = self.inspect()
        if existing:
            self.docker(['stop', '--time', '10', existing['id']], check=False)
            self.docker(['rm', '-f', existing['id']], check=False)
            remaining = self.docker(['inspect', '--format', '{{.Id}}', existing['id']], check=False)
            if remaining.returncode == 0:
                raise JHUConnectionError('jhu_helper_stop_failed')
            self.docker(['version', '--format', '{{.Server.Version}}'])
        return dict(state='disabled', code=None, attempts=0, generation=0)

    def reconnect(self) -> dict:
        existing = self.inspect()
        current = self.status()
        if not existing or current['state'] != 'ready':
            raise JHUConnectionError('jhu_helper_not_ready')
        self.docker(['kill', '--signal', 'USR1', existing['id']])
        return dict(state='connecting', code=None, attempts=current['attempts'], generation=current['generation'])

    def wait_ready(self, timeout: float = 90, after_generation: int = 0) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status = self.status()
            if status['state'] == 'ready' and status['generation'] > after_generation:
                return status
            if (status['state'] == 'auth_failed' or status['code'] in {
                    'vpn_certificate_failed', 'vpn_options_failed', 'vpn_profile_invalid', 'vpn_service_failed'}
                    or (status['state'] == 'degraded' and status['attempts'] >= 3)):
                return status
            time.sleep(.3)
        raise JHUConnectionError('jhu_helper_start_timeout')
