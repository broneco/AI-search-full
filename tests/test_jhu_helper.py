"""Local helper ownership/idempotency/retry policy with a fake Docker CLI."""
import json
import subprocess
import time

import pytest

from app.providers.jhu_secrets import JHUConnectionError
from scripts.vpn_spike.lifecycle import ForwardHealth, Lifecycle
from scripts.vpn_spike.manager import CONFIG, OWNER, ROLE, HelperManager


IDENTIFIER = 'a' * 64


class Docker:
    def __init__(self):
        self.container = None
        self.calls = []
        self.status = dict(state='ready', code=None, attempts=1, generation=1,
                           updated_at=time.time(), protocol_version=2)
        self.others = b''

    def __call__(self, args, **kwargs):
        self.calls.append((args, kwargs))
        command = args[1:]
        code, output = 0, b''
        if command[0] == 'inspect':
            if self.container:
                output = (' '.join(json.dumps(item) for item in self.container)).encode()
            else:
                code = 1
        elif command[0] == 'ps':
            output = self.others
        elif command[0] == 'run':
            labels = {}
            for i, arg in enumerate(command):
                if arg == '--label':
                    key, value = command[i+1].split('=', 1)
                    labels[key] = value
            self.container = (IDENTIFIER, True, labels)
            output = IDENTIFIER.encode()
        elif command[0] == 'exec' and 'cat' in command:
            output = json.dumps(self.status).encode()
        elif command[0] == 'rm':
            self.container = None
        return subprocess.CompletedProcess(args, code, output, b'')


def payload():
    return dict(profile='synthetic-profile', vpn_username='synthetic-vpn-user',
                vpn_password='synthetic-vpn-password', target_ip='192.0.2.1', target_port=11434)


def test_start_is_idempotent_and_bootstrap_secrets_are_stdin_only(tmp_path):
    docker = Docker()
    manager = HelperManager(tmp_path, docker)
    calls = []
    manager.start('fingerprint', lambda: calls.append(1) or payload())
    assert manager.start('fingerprint', lambda: pytest.fail('Do not re-read credentials'))['state'] == 'ready'
    assert calls == [1]
    assert sum(args[1] == 'run' for args, _ in docker.calls) == 1
    for args, _ in docker.calls:
        assert 'synthetic-vpn-password' not in ' '.join(args)
        assert '--env' not in args and '--privileged' not in args
        if '--publish' in args:
            assert args[args.index('--publish')+1] == '127.0.0.1::18081'
    bootstrap = [kw['input'] for args, kw in docker.calls if args[-1] == 'bootstrap']
    assert len(bootstrap) == 1 and 'api_password' not in json.loads(bootstrap[0])


def test_vault_failure_does_not_create_a_container(tmp_path):
    docker = Docker()

    def fail(): raise JHUConnectionError('jhu_secret_missing')

    with pytest.raises(JHUConnectionError, match='jhu_secret_missing'):
        HelperManager(tmp_path, docker).start('fingerprint', fail)
    assert not any(args[1] == 'run' for args, _ in docker.calls)


def test_stop_uses_owned_immutable_id_and_is_idempotent(tmp_path):
    docker = Docker()
    manager = HelperManager(tmp_path, docker)
    manager.start('fingerprint', payload)
    manager.stop()
    manager.stop()
    mutations = [args for args, _ in docker.calls if args[1] in {'stop', 'rm'}]
    assert len(mutations) == 2 and all(args[-1] == IDENTIFIER for args in mutations)


def test_foreign_container_is_never_stopped_or_bootstrapped(tmp_path):
    docker = Docker()
    docker.container = (IDENTIFIER, True, {ROLE:'v1', OWNER:'someone-else'})
    manager = HelperManager(tmp_path, docker)
    for action in (manager.status, manager.stop, lambda: manager.start('x', payload)):
        with pytest.raises(JHUConnectionError, match='jhu_helper_foreign_owner'):
            action()
    assert all(args[1] == 'inspect' for args, _ in docker.calls)


def test_changed_configuration_requires_explicit_restart(tmp_path):
    docker = Docker()
    manager = HelperManager(tmp_path, docker)
    manager.start('first', payload)
    with pytest.raises(JHUConnectionError, match='jhu_helper_restart_required'):
        manager.start('changed', payload)


def test_other_workspace_prevents_second_session(tmp_path):
    docker = Docker()
    docker.others = b'foreign-container-id'
    with pytest.raises(JHUConnectionError, match='jhu_helper_other_workspace_active'):
        HelperManager(tmp_path, docker).start('x', lambda: pytest.fail('No secret read'))


def test_stale_status_is_not_reported_ready(tmp_path):
    docker = Docker()
    manager = HelperManager(tmp_path, docker)
    manager.start('x', payload)
    docker.status['updated_at'] = time.time() - 31
    assert manager.status()['code'] == 'vpn_status_stale'


def test_authentication_and_certificate_failures_are_terminal():
    for code, state in [('vpn_auth_failed', 'auth_failed'), ('vpn_certificate_failed', 'degraded')]:
        lifecycle = Lifecycle()
        lifecycle.connecting()
        assert lifecycle.failed(code) is None
        assert lifecycle.state == state and lifecycle.attempts == 1


def test_transient_retry_budget_is_bounded_even_after_ready():
    lifecycle = Lifecycle()
    for expected_delay in (2, 5, None):
        lifecycle.connecting()
        lifecycle.ready()
        assert lifecycle.failed('vpn_disconnected') == expected_delay
    assert lifecycle.attempts == 3 and lifecycle.generation == 3
    with pytest.raises(ValueError, match='retry_budget_exhausted'):
        lifecycle.connecting()


def test_health_withdraws_ready_but_transient_rekey_does_not_consume_retry_budget():
    lifecycle = Lifecycle()
    lifecycle.connecting()
    health = ForwardHealth()
    assert not health.observe(lifecycle, True)
    assert lifecycle.generation == 1
    for _ in range(2):
        assert not health.observe(lifecycle, False)
        assert lifecycle.state == 'degraded' and lifecycle.code == 'vpn_upstream_unavailable'
    assert not health.observe(lifecycle, True)
    assert lifecycle.state == 'ready' and lifecycle.code is None
    assert lifecycle.generation == lifecycle.attempts == 1
    for _ in range(2):
        assert not health.observe(lifecycle, False)
    assert health.observe(lifecycle, False)
    assert lifecycle.state == 'degraded'


def test_initial_upstream_failure_never_publishes_ready():
    lifecycle = Lifecycle()
    lifecycle.connecting()
    health = ForwardHealth()
    assert not health.observe(lifecycle, False)
    assert lifecycle.state == 'degraded' and lifecycle.generation == 0
    assert not health.initialized


def test_failed_bootstrap_removes_only_the_new_container(tmp_path):
    docker = Docker()

    def run(args, **kwargs):
        result = docker(args, **kwargs)
        if args[-1] == 'bootstrap':
            result.returncode = 1
        return result

    with pytest.raises(JHUConnectionError, match='jhu_docker_operation_failed'):
        HelperManager(tmp_path, run).start('x', payload)
    assert docker.container is None
    assert any(args[1:4] == ['rm', '-f', IDENTIFIER] for args, _ in docker.calls)


def test_unsuccessful_stop_is_not_reported_disabled(tmp_path):
    docker = Docker()

    def run(args, **kwargs):
        if args[1] == 'rm':
            return subprocess.CompletedProcess(args, 1, b'', b'private-error-details')
        return docker(args, **kwargs)

    manager = HelperManager(tmp_path, run)
    manager.start('x', payload)
    with pytest.raises(JHUConnectionError, match='jhu_helper_stop_failed'):
        manager.stop()


def test_cli_rejects_other_tenant_before_docker_or_vault(monkeypatch, capsys):
    import jhu_connection
    monkeypatch.setattr('sys.argv', ['jhu_connection.py', 'status', '--tenant', 'dolphin'])
    monkeypatch.setattr(jhu_connection, 'HelperManager', lambda *_: pytest.fail('No Docker'))
    assert jhu_connection.main() == 1
    assert 'jhu_helper_tenant_invalid' in capsys.readouterr().out


def test_cli_restart_vault_failure_keeps_existing_helper(monkeypatch, tmp_path, capsys):
    import jhu_connection
    from test_vpn_spike import PROFILE
    profile = tmp_path/'Client.ovpn'
    profile.write_text(PROFILE)
    monkeypatch.setattr('sys.argv', ['jhu_connection.py', 'restart', '--profile', str(profile),
                                  '--endpoint', 'http://192.0.2.1:11434'])
    monkeypatch.setattr(jhu_connection, 'HelperManager', lambda *_: type('Manager', (), {
        'stop': lambda _: pytest.fail('Vault failure must preserve the old session')})())

    def fail(*_): raise JHUConnectionError('jhu_vault_unreachable')

    monkeypatch.setattr(jhu_connection, 'key_vault_resolver', fail)
    assert jhu_connection.main() == 1
    assert 'jhu_vault_unreachable' in capsys.readouterr().out
