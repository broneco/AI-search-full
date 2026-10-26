"""Bounded isolated probe. JSON stdin contains secrets; stdout is metadata only."""
import base64
import http.client
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import threading
import time

from profile import failure_code, validated_profile


def emit(**fields):
    print(json.dumps(fields), flush=True)


def stop(process):
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


def offline():
    """Observe an actual TCP SYN on the VPN fd with Docker network disabled."""
    from bridge import bridge_command
    assert os.getuid() != 0 and not Path('/dev/net/tun').exists()
    capabilities = next(line for line in Path('/proc/self/status').read_text().splitlines()
                        if line.startswith('CapEff:'))
    assert int(capabilities.split()[1], 16) == 0
    version = subprocess.check_output(['openvpn', '--version'], text=True).splitlines()[0]
    parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
    env = dict(TUNTAP_SOCKET_FD=str(child.fileno()), TUNTAP_DEV_TYPE='tun',
               ifconfig_local='192.0.2.2', PROBE_TARGET_IP='192.0.2.123',
               PROBE_TARGET_PORT='11434')
    command, clean_env = bridge_command(env)
    process = subprocess.Popen(command, env=clean_env, pass_fds=[child.fileno()],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               start_new_session=True)
    child.close()
    client = None
    try:
        for _ in range(50):
            try:
                client = socket.create_connection(('127.0.0.1', 18080), timeout=.2)
                break
            except OSError:
                time.sleep(.1)
        if client is None:
            raise RuntimeError('forward_not_started')
        parent.settimeout(5)
        packet = parent.recv(65535)
        assert packet[0] >> 4 == 4 and packet[9] == 6
        assert socket.inet_ntoa(packet[16:20]) == '192.0.2.123'
        header = (packet[0] & 15) * 4
        assert int.from_bytes(packet[header+2:header+4], 'big') == 11434
        assert packet[header+13] & 2  # TCP SYN, through VPN fd, not host TCP.
        emit(stage='offline', passed=True, non_root=True, capabilities=0,
             tun_device=False, tcp_syn_via_vpn_fd=True, openvpn=version)
    finally:
        if client:
            client.close()
        parent.close()
        stop(process)


def call_api(path, auth, body=None, timeout=180):
    conn = http.client.HTTPConnection('127.0.0.1', 18080, timeout=timeout)
    try:
        conn.request('GET' if body is None else 'POST', path,
                     body=None if body is None else json.dumps(body).encode(),
                     headers={'Authorization': auth, 'Content-Type': 'application/json'})
        response = conn.getresponse()
        if response.status != 200:
            raise RuntimeError(f'api_http_{response.status}')
        raw = response.read(8_000_001)
        if len(raw) > 8_000_000:
            raise RuntimeError('api_response_limit')
        return json.loads(raw)
    finally:
        conn.close()


def wait_forward():
    for _ in range(50):
        try:
            with socket.create_connection(('127.0.0.1', 18080), timeout=.1):
                return
        except OSError:
            time.sleep(.1)
    raise RuntimeError('forward_not_ready')


def live(payload):
    config = validated_profile(payload['profile'])
    negative = payload.get('negative_name', False)
    if negative:
        config = re.sub(r'^verify-x509-name .*$', 'verify-x509-name probe-invalid.example name',
                        config, flags=re.MULTILINE)
    if payload.get('rekey'):
        config = re.sub(r'^reneg-sec .*\n', '', config, flags=re.MULTILINE) + 'reneg-sec 15\n'
    target = str(ipaddress.IPv4Address(payload['target_ip']))
    port = int(payload['target_port'])
    if not 1 <= port <= 65535:
        raise ValueError('Invalid port')
    for key in ('vpn_username', 'vpn_password', 'api_username', 'api_password'):
        if not payload[key] or any(c in payload[key] for c in '\r\n\x00'):
            raise ValueError('Invalid credentials')
    runtime = Path('/run/probe')
    runtime.mkdir(mode=0o700, exist_ok=True)
    os.umask(0o077)
    (runtime / 'auth').write_text(payload['vpn_username'] + '\n' + payload['vpn_password'] + '\n')
    (runtime / 'client.conf').write_text(config)
    auth = 'Basic ' + base64.b64encode(
        (payload['api_username'] + ':' + payload['api_password']).encode()).decode()
    ready, failure = threading.Event(), []
    control_channels = []
    # Read all logs without retaining or echoing peer-controlled/raw contents.
    def drain(stream):
        for line in stream:
            if 'Control Channel: TLS' in line:
                control_channels.append(time.monotonic())
            if 'Options error:' in line:
                # Report directive name only, never its arguments or raw OpenVPN log.
                match = re.search(r'client\.conf:\d+: ([a-z-]+)', line)
                if match:
                    emit(stage='options', directive=match.group(1))
                else:
                    emit(stage='options', flags=re.findall(r'--([a-z][a-z-]+)', line),
                         missing_file='No such file' in line, denied='Permission denied' in line,
                         compression='compression' in line.lower(),
                         unix='unix' in line.lower())
            if 'Initialization Sequence Completed' in line:
                ready.set()
            code = failure_code(line)
            if code and code not in failure:
                failure.append(code)
    process = None
    started = time.monotonic()
    try:
        process = subprocess.Popen(['openvpn', '--config', str(runtime/'client.conf'),
                                    '--setenv', 'PROBE_TARGET_IP', target,
                                    '--setenv', 'PROBE_TARGET_PORT', str(port)],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, start_new_session=True)
        threading.Thread(target=drain, args=(process.stdout,), daemon=True).start()
        deadline = time.monotonic() + 75
        while not ready.wait(.2):
            if process.poll() is not None or failure or time.monotonic() > deadline:
                if negative and 'vpn_certificate_failed' in failure:
                    emit(stage='negative_certificate_name', passed=True)
                    return
                raise RuntimeError(failure[0] if failure else 'vpn_handshake_incomplete')
        if negative:
            raise RuntimeError('negative_certificate_unexpected_success')
        emit(stage='vpn_ready', elapsed_ms=round((time.monotonic()-started)*1000))
        if payload.get('handshake_only'):
            return
        # OpenVPN reports ready just before the child finishes starting its listener.
        # Waiting for a local socket is not a retry of an API/model request.
        wait_forward()
        tags = call_api('/api/tags', auth, timeout=15)
        names = {entry['name'] for entry in tags.get('models', [])}
        if not {payload['model'], payload['embedding_model']} <= names:
            raise RuntimeError('requested_model_missing')
        emit(stage='inventory', model_count=len(names))
        for model in (payload['model'], payload['embedding_model']):
            result = call_api('/api/show', auth, {'model': model}, timeout=15)
            if not isinstance(result, dict) or not result:
                raise RuntimeError('invalid_model_metadata')
        for attempt in range(2):
            start = time.monotonic()
            result = call_api('/api/generate', auth, {
                'model': payload['model'], 'prompt': 'Napiš jednu krátkou větu v češtině o knihovně.',
                'stream': False, 'options': {'num_predict': 48}})
            if not isinstance(result.get('response'), str) or not result['response'].strip():
                raise RuntimeError('empty_generation')
            emit(stage='generate', attempt=attempt+1, model=payload['model'],
                 elapsed_ms=round((time.monotonic()-start)*1000),
                 total_duration_ns=result.get('total_duration'), load_duration_ns=result.get('load_duration'))
        start = time.monotonic()
        result = call_api('/api/embed', auth, {'model': payload['embedding_model'],
                          'input': ['search_document: Knihovna půjčuje studentům učebnice.',
                                    'search_query: Kde si půjčím učebnici?'], 'truncate': False})
        vectors = result.get('embeddings', [])
        if (len(vectors) != 2 or not vectors[0] or len(vectors[0]) != len(vectors[1])
                or not all(type(v) in (int, float) and math.isfinite(v) for row in vectors for v in row)):
            raise RuntimeError('invalid_embedding')
        emit(stage='embed', dimensions=len(vectors[0]), count=len(vectors),
             elapsed_ms=round((time.monotonic()-start)*1000))
        if payload.get('rekey'):
            deadline = time.monotonic() + 55
            while len(control_channels) < 2 and time.monotonic() < deadline:
                if failure or process.poll() is not None:
                    raise RuntimeError('rekey_failed')
                time.sleep(.2)
            if len(control_channels) < 2:
                raise RuntimeError('rekey_not_observed')
            call_api('/api/tags', auth, timeout=15)
            emit(stage='rekey', passed=True, established_tls_channels=len(control_channels))
        if payload.get('reconnect'):
            ready.clear()
            failure.clear()
            start = time.monotonic()
            process.send_signal(signal.SIGUSR1)
            if not ready.wait(75) or failure:
                raise RuntimeError('reconnect_failed')
            wait_forward()
            call_api('/api/tags', auth, timeout=15)
            emit(stage='reconnect', passed=True, elapsed_ms=round((time.monotonic()-start)*1000))
        emit(stage='live', passed=True)
    finally:
        stop(process)
        for name in ('auth', 'client.conf'):
            (runtime/name).unlink(missing_ok=True)
        try:
            peak = int(Path('/sys/fs/cgroup/memory.peak').read_text())
            cpu = dict(line.split() for line in Path('/sys/fs/cgroup/cpu.stat').read_text().splitlines())
            emit(stage='resources', memory_peak_bytes=peak, cpu_usage_usec=int(cpu['usage_usec']))
        except (OSError, ValueError, KeyError):
            emit(stage='resources', available=False)


if __name__ == '__main__':
    try:
        if sys.argv[1:] == ['offline']:
            offline()
        elif sys.argv[1:] == ['live']:
            live(json.loads(sys.stdin.buffer.readline(256_001)))
        else:
            raise ValueError('Invalid mode')
    except Exception as exc:
        # Never echo input or exception messages except our controlled error codes.
        code = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        if not code.replace('_', '').isalnum():
            code = type(exc).__name__
        emit(stage='error', code=code)
        sys.exit(1)
