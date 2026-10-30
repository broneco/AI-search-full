"""Local/ACA helper supervisor with private container-local bootstrap.

Control plane uses Docker exec/signals; the bounded API gateway is separate.
"""
import http.client
import ipaddress
import json
import os
import re
import secrets
from pathlib import Path
import signal
import socketserver
import subprocess
import sys
import threading
import time

from lifecycle import ForwardHealth, Lifecycle
from profile import failure_code, validated_profile
from gateway import GatewayServer

RUNTIME = Path('/run/probe')


class LivenessHandler(socketserver.BaseRequestHandler):
    def handle(self):
        pass  # TCP process probe only: no metadata, proxy or secret-bearing response.


class LivenessServer(socketserver.TCPServer):
    allow_reuse_address = True


def write_json(name: str, data: dict) -> None:
    path = RUNTIME / name
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data), encoding='utf-8')
    os.chmod(temp, 0o600)
    temp.replace(path)


def bootstrap() -> None:
    data = sys.stdin.buffer.read(192_001)
    if len(data) > 192_000 or (RUNTIME/'bootstrap.json').exists() or (RUNTIME/'client.conf').exists():
        raise ValueError('bootstrap_rejected')
    payload = validated_bootstrap(json.loads(data))
    write_json('bootstrap.json', payload)


def validated_bootstrap(payload) -> dict:
    if not isinstance(payload, dict):
        raise ValueError('bootstrap_rejected')
    if set(payload) != {'profile', 'vpn_username', 'vpn_password', 'target_ip', 'target_port', 'gateway_key'}:
        raise ValueError('bootstrap_rejected')
    if not re.fullmatch(r'[a-f0-9]{64}', payload['gateway_key']):
        raise ValueError('bootstrap_rejected')
    validated_profile(payload['profile'])
    ipaddress.IPv4Address(payload['target_ip'])
    if type(payload['target_port']) is not int or not 1 <= payload['target_port'] <= 65535:
        raise ValueError('bootstrap_rejected')
    for key in ('vpn_username', 'vpn_password'):
        value = payload[key]
        if not isinstance(value, str) or not value or len(value) > 25_000 or any(c in value for c in '\r\n\x00'):
            raise ValueError('bootstrap_rejected')
    return dict(payload)


def stop_child(process) -> None:
    if process is not None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
            except ProcessLookupError:
                pass


def forward_responds() -> bool:
    """No model/API secrets: prove TCP response, not model authorization/quality."""
    connection = http.client.HTTPConnection('127.0.0.1', 18080, timeout=2)
    try:
        connection.request('GET', '/api/tags')
        return connection.getresponse().status in {200, 401}
    except (OSError, http.client.HTTPException):
        return False
    finally:
        connection.close()


def serve(cloud_loader=None, cloud_context=None) -> None:
    os.umask(0o077)
    stop, reconnect = threading.Event(), threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGUSR1, lambda *_: reconnect.set())
    lifecycle = Lifecycle()
    tls_channels = 0
    recovery_causes = {}

    def report():
        write_json('status.json', dict(lifecycle.public(), updated_at=time.time(),
                                      protocol_version=2, tls_channels=tls_channels,
                                      recovery_causes=dict(recovery_causes),
                                      **({'context': cloud_context} if cloud_context else {})))
        if gateway is not None and lifecycle.state != 'ready':
            gateway.abort_upstreams()

    process = None
    gateway = None
    liveness = None
    report()
    try:
        if cloud_loader is not None:
            # Process health is independent of vault/VPN health. A terminal
            # bootstrap error stays visible; ACA must not retry credentials.
            gateway = GatewayServer(('127.0.0.1', 18081), secrets.token_hex(32), RUNTIME/'status.json')
            threading.Thread(target=gateway.serve_forever, daemon=True).start()
            # Platform TCP probes target the replica IP, not its loopback.
            # Keep model traffic on loopback and use a separate no-data port.
            liveness = LivenessServer(('0.0.0.0', 18082), LivenessHandler)
            threading.Thread(target=liveness.serve_forever, daemon=True).start()
            try:
                payload = validated_bootstrap(cloud_loader())
            except Exception:
                lifecycle.state, lifecycle.code = 'degraded', 'vpn_cloud_bootstrap_failed'
                report()
                print('{"code":"vpn_cloud_bootstrap_failed"}', flush=True)
                stop.wait()
                return
        else:
            deadline = time.monotonic() + 120
            while not (RUNTIME/'bootstrap.json').exists():
                if stop.wait(.1) or time.monotonic() > deadline:
                    return
            payload = validated_bootstrap(json.loads((RUNTIME/'bootstrap.json').read_text(encoding='utf-8')))
            (RUNTIME/'bootstrap.json').unlink()
        key = payload.pop('gateway_key')
        (RUNTIME/'gateway.key').write_text(key)
        if gateway is None:
            gateway = GatewayServer(('0.0.0.0', 18081), key, RUNTIME/'status.json')
            threading.Thread(target=gateway.serve_forever, daemon=True).start()
        else:
            gateway.key = key
        config = validated_profile(payload.pop('profile'))
        # All reconnects go through the bounded supervisor instead of OpenVPN's
        # unlimited soft-restart loop. auth-nocache still re-reads tmpfs auth.
        config += 'remap-usr1 SIGTERM\n'
        (RUNTIME/'client.conf').write_text(config)
        (RUNTIME/'auth').write_text(payload.pop('vpn_username') + '\n' + payload.pop('vpn_password') + '\n')
        while not stop.is_set():
            reconnect.clear()
            lifecycle.connecting()
            report()
            ready = threading.Event()
            forward_health = ForwardHealth()
            errors: list[str] = []

            def drain(stream):
                nonlocal tls_channels
                for line in stream:
                    if 'Control Channel: TLS' in line:
                        tls_channels += 1
                    if 'Initialization Sequence Completed' in line:
                        ready.set()
                    code = failure_code(line)
                    if code and not errors:
                        errors.append(code)

            process = subprocess.Popen(['openvpn', '--config', str(RUNTIME/'client.conf'),
                '--setenv', 'PROBE_TARGET_IP', payload['target_ip'],
                '--setenv', 'PROBE_TARGET_PORT', str(payload['target_port'])],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
            reader = threading.Thread(target=drain, args=(process.stdout,), daemon=True)
            reader.start()
            started, next_health = time.monotonic(), 0.0
            code = 'vpn_disconnected'
            while not stop.wait(.2):
                if errors:
                    code = errors[0]
                    break
                if process.poll() is not None or reconnect.is_set():
                    break
                now = time.monotonic()
                if not forward_health.initialized and now - started > 75:
                    code = 'vpn_handshake_timeout'
                    break
                if ready.is_set() and now >= next_health:
                    healthy = forward_responds()
                    next_health = now + (10 if healthy else .5)
                    restart = forward_health.observe(lifecycle, healthy)
                    report()
                    if restart:
                        code = 'vpn_upstream_unavailable'
                        break
            # Withdraw readiness and unblock API sockets before waiting for VPN
            # child cleanup. Submitted model requests are never replayed.
            lifecycle.state = 'disabled' if stop.is_set() else 'degraded'
            lifecycle.code = None if stop.is_set() else code
            report()
            stop_child(process)
            reader.join(timeout=2)
            process = None
            if stop.is_set():
                break
            recovery_causes[code] = recovery_causes.get(code, 0) + 1
            delay = lifecycle.failed(code)
            report()
            if delay is None:
                # Terminal failure: keep metadata visible until explicit stop/restart.
                # Remove credentials immediately, not just when the container exits.
                for name in ('auth', 'client.conf'):
                    (RUNTIME/name).unlink(missing_ok=True)
                stop.wait()
                break
            if stop.wait(delay):
                break
    except Exception:
        lifecycle.state, lifecycle.code = 'degraded', 'vpn_service_failed'
        report()
    finally:
        if gateway is not None:
            lifecycle.state = 'disabled' if stop.is_set() else 'degraded'
            report()
        stop_child(process)
        if gateway is not None:
            gateway.shutdown()
            gateway.server_close()
        if liveness is not None:
            liveness.shutdown()
            liveness.server_close()
        for name in ('bootstrap.json', 'bootstrap.tmp', 'auth', 'client.conf', 'gateway.key'):
            (RUNTIME/name).unlink(missing_ok=True)
        if stop.is_set() or lifecycle.state == 'disabled':
            lifecycle.state = 'disabled'
        report()


if __name__ == '__main__':
    try:
        if sys.argv[1:] == ['serve']:
            serve()
        elif sys.argv[1:] == ['bootstrap']:
            bootstrap()
        elif sys.argv[1:] == ['cloud']:
            from cloud import cloud_config, load_payload
            # Configuration validation is also done inside the bounded loader,
            # so a bad config cannot create a platform-driven retry storm.
            config = {}
            def cloud_payload():
                config.update(cloud_config())
                context.update(config['context'])
                return load_payload(config)
            context = {}
            serve(cloud_payload, context)
        else:
            raise ValueError('invalid_mode')
    except Exception:
        print('{"code":"vpn_service_control_failed"}')
        sys.exit(1)
