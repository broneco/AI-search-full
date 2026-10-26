"""Probe input/transport policy only; no real secrets, VPN or cloud access."""
import pytest

from probe_jhu_vpn import container_command
from scripts.vpn_spike.bridge import bridge_command
from scripts.vpn_spike.profile import failure_code, validated_profile
from scripts.publication.jhu import safe_name

PROFILE = '''client
dev tun
proto udp
remote vpn.example.test 1194
auth-user-pass
auth-nocache
verify-x509-name vpn.example.test name
comp-lzo
<ca>
-----BEGIN CERTIFICATE-----
YWJj
-----END CERTIFICATE-----
</ca>
'''


def test_profile_preserves_security_and_overrides_only_local_packet_io():
    result = validated_profile(PROFILE + 'persist-tun\n')
    assert 'verify-x509-name vpn.example.test name' in result
    assert 'comp-lzo\n' in result and '<ca>\n' in result
    assert 'auth-nocache' in result and 'auth-user-pass /run/probe/auth' in result
    assert 'dev-node unix:/opt/probe/bridge.py' in result
    assert 'route-noexec' in result and 'ifconfig-noexec' in result
    assert 'persist-tun' not in result  # Recreate the userspace stack on reconnect.


@pytest.mark.parametrize('extra', [
    'up /evil', 'plugin /evil', 'config /evil', 'script-security 3', 'management 0.0.0.0 9000',
    'dev-node /dev/net/tun', 'setenv LD_PRELOAD /evil', 'auth-user-pass /private',
    'log /private', 'ca /private', '<key>', 'remote other.example.test 1194',
])
def test_profile_rejects_hooks_files_and_overrides(extra):
    with pytest.raises(ValueError):
        validated_profile(PROFILE + extra + '\n')


@pytest.mark.parametrize('directive', ['verify-x509-name vpn.example.test name\n', 'auth-nocache\n', '</ca>\n'])
def test_profile_requires_identity_and_closed_ca(directive):
    with pytest.raises(ValueError):
        validated_profile(PROFILE.replace(directive, ''))


def test_bridge_exposes_only_fixed_target_and_minimal_environment():
    command, env = bridge_command(dict(TUNTAP_DEV_TYPE='tun', TUNTAP_SOCKET_FD='7',
        ifconfig_local='192.0.2.2', PROBE_TARGET_IP='192.0.2.123', PROBE_TARGET_PORT='11434',
        PASSWORD='synthetic-secret', LD_PRELOAD='/untrusted'))
    assert command == ['/usr/local/bin/tunsocks', '-L', '127.0.0.1:18080:192.0.2.123:11434']
    assert env['VPNFD'] == '7' and 'PASSWORD' not in env and 'LD_PRELOAD' not in env
    assert '-S' not in command and '-D' not in command  # No host stack / arbitrary SOCKS proxy.


def test_container_has_no_privileged_host_network_or_secret_arguments():
    command = container_command('test', 'offline')
    assert '--cap-drop' in command and 'ALL' in command
    assert '--read-only' in command and '--network' in command and 'none' in command
    assert '--privileged' not in command and '--device' not in command and '--env' not in command
    assert '--publish' not in command and '-p' not in command


@pytest.mark.parametrize('name', ['Client.ovpn', 'tenants/jhu/CLIENT.OVPN', 'vpn.auth'])
def test_private_vpn_files_cannot_be_exported(name):
    assert not safe_name(name)


@pytest.mark.parametrize('line,expected', [
    ('AUTH_FAILED,sensitive peer details', 'vpn_auth_failed'),
    ('VERIFY X509NAME ERROR: private certificate identity', 'vpn_certificate_failed'),
    ('VERIFY ERROR: private certificate identity', 'vpn_certificate_failed'),
    ('TLS Error: private server details', 'vpn_tls_failed'),
    ('Options error: private file path', 'vpn_options_failed'),
    ('unrecognized sensitive text', None),
])
def test_log_errors_never_expose_peer_or_credential_text(line, expected):
    assert failure_code(line) == expected


def test_empty_server_identity_rejected():
    with pytest.raises(ValueError):
        validated_profile(PROFILE.replace('verify-x509-name vpn.example.test name', 'verify-x509-name "" name'))


def test_probe_vault_failure_preserves_safe_error_code(monkeypatch, capsys):
    import probe_jhu_vpn
    from app.providers.jhu_secrets import JHUConnectionError
    monkeypatch.setattr('sys.argv', ['probe_jhu_vpn.py', 'live', '--profile', 'unused.ovpn'])

    def fail(_): raise JHUConnectionError('jhu_secret_missing')

    monkeypatch.setattr(probe_jhu_vpn, 'payload_for', fail)
    assert probe_jhu_vpn.main() == 1
    assert 'jhu_secret_missing' in capsys.readouterr().out
