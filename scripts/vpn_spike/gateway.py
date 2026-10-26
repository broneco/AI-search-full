"""Capability-protected fixed-upstream API gateway. No open proxy or raw logs."""
import hmac
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import socket
import threading
import time

ALLOWED = {('GET', '/api/tags'), ('POST', '/api/show'), ('POST', '/api/generate'), ('POST', '/api/embed')}
MAX_REQUEST = 2_000_000
MAX_RESPONSE = 16_000_000
UPSTREAM_DEADLINE = 300


class GatewayServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False

    def __init__(self, address, key, status_path: Path, upstream_factory=http.client.HTTPConnection):
        self.key, self.status_path = key, status_path
        self.upstream_factory = upstream_factory
        self.slots = threading.BoundedSemaphore(4)
        self.active_lock = threading.Lock()
        self.active = set()
        self.forwarded = {path: 0 for _, path in ALLOWED}
        super().__init__(address, GatewayHandler)

    def status(self):
        status = json.loads(self.status_path.read_text())
        if not isinstance(status, dict):
            raise ValueError('invalid_status')
        return status

    def require_ready(self):
        status = self.status()
        age = time.time() - float(status['updated_at'])
        if status.get('state') != 'ready' or not math.isfinite(age) or not 0 <= age <= 30:
            raise ValueError('upstream_unavailable')

    def track(self, connection):
        with self.active_lock:
            self.require_ready()
            self.active.add(connection)

    def untrack(self, connection):
        with self.active_lock:
            self.active.discard(connection)

    def record_forward(self, path):
        with self.active_lock:
            self.forwarded[path] += 1

    def metrics(self):
        with self.active_lock:
            return dict(active_requests=len(self.active), forwarded=dict(self.forwarded))

    def abort_upstreams(self):
        """Interrupt socket reads when the supervisor withdraws VPN readiness."""
        with self.active_lock:
            active = list(self.active)
        for connection in active:
            self.abort_connection(connection)

    @staticmethod
    def abort_connection(connection):
        with connection._jhu_close_lock:
            sock = connection.sock
            try:
                if sock is not None:
                    sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            finally:
                # makefile() retains an I/O reference to a socket. Explicitly
                # transfer ownership, with one closer per descriptor.
                if sock is not None:
                    descriptor = sock.detach()
                    if descriptor != -1:
                        socket.close(descriptor)
                connection.close()

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            try:
                request.sendall(b'HTTP/1.1 429 Too Many Requests\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            finally:
                request.close()
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def handle_error(self, request, client_address):
        pass  # Never dump body/header-bearing tracebacks.


class GatewayHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *_):
        pass

    def reply(self, status, body=b'', error=False):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection', 'close')
        if error:
            self.send_header('X-JHU-Gateway-Error', 'connection_unavailable')
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def do_GET(self): self.handle_api()
    def do_POST(self): self.handle_api()
    def do_CONNECT(self): self.reply(405)
    def do_DELETE(self): self.reply(405)
    def do_PUT(self): self.reply(405)

    def handle_api(self):
        if not hmac.compare_digest(self.headers.get('X-JHU-Connection', '').encode(), self.server.key.encode()):
            self.reply(403)
            return
        if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) > 1:
            self.reply(400)
            return
        if (self.command, self.path) not in ALLOWED and (self.command, self.path) != ('GET', '/_jhu/health'):
            self.reply(405)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 <= length <= MAX_REQUEST or (self.command == 'POST' and not length):
                self.reply(413)
                return
            body = self.rfile.read(length) if length else None
            if body is not None and len(body) != length:
                self.reply(400)
                return
            # Consume the bounded request before a readiness rejection. Closing
            # with unread body bytes can turn the intended 503 into a TCP reset.
            status = self.server.status()
            if self.path == '/_jhu/health':
                self.reply(200, json.dumps({**status, **self.server.metrics()}).encode())
                return
            self.server.require_ready()
            # The upstream is always the inherited-VPN-fd forward, never a user URL.
            connection = self.server.upstream_factory('127.0.0.1', 18080, timeout=3)
            connection._jhu_close_lock = threading.Lock()
            deadline = None
            try:
                connection.connect()
                connection.auto_open = 0  # Never reconnect after cancellation.
                # Blocking makefile reads can be interrupted by shutdown on
                # Windows as well as Linux. A bounded watchdog owns the overall
                # upstream deadline, independent of partial response traffic.
                connection.sock.settimeout(None)
                self.server.track(connection)
                deadline = threading.Timer(UPSTREAM_DEADLINE, self.server.abort_connection, args=(connection,))
                deadline.daemon = True
                deadline.start()
                connection.request(self.command, self.path, body=body, headers={
                    'Authorization': self.headers.get('Authorization', ''), 'Content-Type': 'application/json'})
                self.server.record_forward(self.path)
                response = connection.getresponse()
                if 300 <= response.status < 400:
                    self.reply(502, error=True)
                    return
                content = response.read(MAX_RESPONSE + 1)
                if len(content) > MAX_RESPONSE:
                    self.reply(502, error=True)
                    return
                self.reply(response.status, content)
            finally:
                if deadline is not None:
                    deadline.cancel()
                self.server.untrack(connection)
                with connection._jhu_close_lock:
                    connection.close()
        except (ValueError, KeyError, TypeError, AttributeError, OSError, http.client.HTTPException):
            self.reply(503, error=True)
