"""Real loopback HTTP parser/gateway with a synthetic fixed upstream."""
import http.client
import json
import threading
import time

import pytest

from scripts.vpn_spike.gateway import GatewayServer


@pytest.fixture
def gateway(tmp_path):
    status = tmp_path/'status.json'
    status.write_text(json.dumps(dict(state='ready', protocol_version=2, updated_at=time.time())))
    calls, state = [], dict(status=200, error=False)

    class Upstream:
        def __init__(self, host, port, **kw):
            assert (host, port) == ('127.0.0.1', 18080)
        def request(self, *args, **kw): calls.append((args, kw))
        def connect(self):
            self.sock = type('Socket', (), {'settimeout': lambda *_: None})()
        def getresponse(self):
            if state['error']: raise TimeoutError('private upstream details')
            return type('Response', (), dict(status=state['status'], read=lambda *_: b'{"response":"ok"}'))()
        def close(self): pass

    server = GatewayServer(('127.0.0.1', 0), 'a'*64, status, Upstream)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def request(method, path, *, body=None, headers=None):
        connection = http.client.HTTPConnection(*server.server_address, timeout=3)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()
    yield request, status, calls, state
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_capability_required_before_any_upstream(gateway):
    request, _, calls, _ = gateway
    assert request('GET', '/api/tags')[0] == 403
    assert request('GET', '/api/tags', headers={'X-JHU-Connection':'wrong'})[0] == 403
    assert calls == []


@pytest.mark.parametrize('method,path', [('POST','/api/pull'), ('DELETE','/api/delete'),
    ('CONNECT','example.test:443'), ('GET','http://example.test/api/tags'),
    ('GET','/api/tags?url=example.test'), ('POST','/api/generate/../pull')])
def test_only_allowlisted_paths_and_methods_are_forwarded(gateway, method, path):
    request, _, calls, _ = gateway
    assert request(method, path, headers={'X-JHU-Connection':'a'*64})[0] == 405
    assert calls == []


def test_upstream_is_fixed_and_connection_key_is_not_forwarded(gateway):
    request, _, calls, _ = gateway
    assert request('POST', '/api/generate', body=b'{}', headers={
        'X-JHU-Connection':'a'*64, 'Authorization':'Basic synthetic-api', 'Host':'untrusted.example'})[0] == 200
    assert len(calls) == 1
    args, kw = calls[0]
    assert args == ('POST','/api/generate')
    assert kw['headers'] == {'Authorization':'Basic synthetic-api','Content-Type':'application/json'}


@pytest.mark.parametrize('state_name', ['connecting','degraded','auth_failed'])
def test_unready_state_never_forwards(gateway, state_name):
    request, status, calls, _ = gateway
    status.write_text(json.dumps(dict(state=state_name)))
    assert request('POST','/api/generate', body=b'{}',headers={'X-JHU-Connection':'a'*64})[0] == 503
    assert calls == []


def test_input_limit_and_transfer_encoding_are_rejected(gateway):
    request, _, calls, _ = gateway
    assert request('POST','/api/generate',headers={'X-JHU-Connection':'a'*64,'Content-Length':'3000000'})[0] == 413
    assert request('POST','/api/generate',headers={'X-JHU-Connection':'a'*64,'Transfer-Encoding':'chunked'})[0] == 400
    assert calls == []


def test_redirects_and_timeouts_do_not_retry_or_leak(gateway):
    request, _, calls, state = gateway
    state['status'] = 302
    assert request('GET','/api/tags',headers={'X-JHU-Connection':'a'*64})[0] == 502
    assert len(calls) == 1
    state['error'] = True
    code, body = request('GET','/api/tags',headers={'X-JHU-Connection':'a'*64})
    assert code == 503 and b'private' not in body and len(calls) == 2


def test_stale_ready_status_never_forwards(gateway):
    request,status,calls,_=gateway
    status.write_text(json.dumps(dict(state='ready',updated_at=1)))
    assert request('GET','/api/tags',headers={'X-JHU-Connection':'a'*64})[0] == 503
    assert calls == []


@pytest.mark.parametrize('scenario',['inflight','before_send','deadline'])
def test_supervisor_abort_interrupts_actual_socket_read_without_replay(tmp_path,monkeypatch,scenario):
    from concurrent.futures import ThreadPoolExecutor
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    entered,release=threading.Event(),threading.Event()
    calls=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_): pass
        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            calls.append(1); entered.set(); release.wait(5)
            try:
                self.send_response(200); self.send_header('Content-Length','2'); self.end_headers(); self.wfile.write(b'{}')
            except OSError: pass
    upstream=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    upstream.daemon_threads=True
    threading.Thread(target=upstream.serve_forever,daemon=True).start()
    status=tmp_path/'status.json'
    status.write_text(json.dumps(dict(state='ready',updated_at=time.time())))
    server=GatewayServer(('127.0.0.1',0),'a'*64,status,
        lambda *_a,**_k:http.client.HTTPConnection(*upstream.server_address,timeout=3))
    original_track=server.track
    if scenario=='deadline':
        monkeypatch.setattr('scripts.vpn_spike.gateway.UPSTREAM_DEADLINE',.1)
    if scenario=='before_send':
        def cancel_on_track(connection):
            original_track(connection)
            status.write_text(json.dumps(dict(state='connecting',updated_at=time.time())))
            server.abort_upstreams()
        server.track=cancel_on_track
    threading.Thread(target=server.serve_forever,daemon=True).start()
    def send():
        conn=http.client.HTTPConnection(*server.server_address,timeout=4)
        try:
            conn.request('POST','/api/generate',body=b'{}',headers={'X-JHU-Connection':'a'*64})
            response=conn.getresponse()
            return response.status,response.getheader('X-JHU-Gateway-Error'),response.read()
        finally: conn.close()
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending=pool.submit(send)
            started=time.monotonic()
            if scenario!='before_send':
                assert entered.wait(2)
            if scenario=='inflight':
                status.write_text(json.dumps(dict(state='connecting',updated_at=time.time())))
                started=time.monotonic();server.abort_upstreams()
            assert pending.result(timeout=2) == (503,'connection_unavailable',b'')
            assert time.monotonic()-started < 2 and calls == ([] if scenario=='before_send' else [1])
        release.set()
        server.track=original_track
        status.write_text(json.dumps(dict(state='ready',updated_at=time.time())))
        assert send()[0] == 200 and len(calls) == (1 if scenario=='before_send' else 2)
        assert server.metrics()['forwarded']['/api/generate'] == len(calls)
    finally:
        release.set();server.abort_upstreams();server.shutdown();server.server_close()
        upstream.shutdown();upstream.server_close()
