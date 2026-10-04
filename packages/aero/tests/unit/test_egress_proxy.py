"""Tests for the local egress proxy (CONNECT tunneling with domain allowlisting)."""

import socket
import threading
import time
import http.client
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from aero.infrastructure.egress_proxy import LocalEgressProxy


@contextmanager
def _http_origin():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            requests.append(self.path)
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header(
                    "Location", f"http://localhost:{self.server.server_port}/private"
                )
                self.end_headers()
                return
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"missing")

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            requests.append((body, dict(self.headers)))
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.send_header("X-Origin", "preserved")
            self.end_headers()
            self.wfile.write(body)

    origin = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=origin.serve_forever, daemon=True)
    thread.start()
    try:
        yield origin.server_port, requests
    finally:
        origin.shutdown()
        origin.server_close()
        thread.join(timeout=2)


def test_http_preserves_payload_authorization_content_type_and_response(monkeypatch):
    # The forwarding client must not inherit a parent process's proxy settings.
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    with _http_origin() as (port, requests):
        proxy = LocalEgressProxy(["127.0.0.1"])
        proxy.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", proxy.port, timeout=5)
            payload = b'{"message":"complete body"}'
            conn.request(
                "POST",
                f"http://127.0.0.1:{port}/echo",
                body=payload,
                headers={
                    "Authorization": "Bearer test-only",
                    "Content-Type": "application/json",
                },
            )
            response = conn.getresponse()
            assert response.status == 201
            assert response.getheader("Content-Type") == "application/json"
            assert response.getheader("X-Origin") == "preserved"
            assert response.read() == payload
            assert requests[0][0] == payload
            assert requests[0][1]["Authorization"] == "Bearer test-only"
            assert requests[0][1]["Content-Type"] == "application/json"
            conn.close()
        finally:
            proxy.stop()


def test_redirect_is_not_followed_and_next_destination_is_checked():
    with _http_origin() as (port, requests):
        proxy = LocalEgressProxy(["127.0.0.1"])
        proxy.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", proxy.port, timeout=5)
            conn.request("GET", f"http://127.0.0.1:{port}/redirect")
            response = conn.getresponse()
            assert response.status == 302
            location = response.getheader("Location")
            response.read()
            conn.close()
            assert requests == ["/redirect"]
            conn = http.client.HTTPConnection("127.0.0.1", proxy.port, timeout=5)
            conn.request("GET", location)
            assert conn.getresponse().status == 403
            assert requests == ["/redirect"]
            conn.close()
        finally:
            proxy.stop()


def test_http_error_status_and_body_are_preserved():
    with _http_origin() as (port, _):
        proxy = LocalEgressProxy(["127.0.0.1"])
        proxy.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", proxy.port, timeout=5)
            conn.request("GET", f"http://127.0.0.1:{port}/missing")
            response = conn.getresponse()
            assert response.status == 404
            assert response.read() == b"missing"
            conn.close()
        finally:
            proxy.stop()


@pytest.mark.parametrize(
    "headers",
    [
        b"Content-Length: 2\r\nContent-Length: 3\r\n",
        b"Content-Length: -1\r\n",
        b"Transfer-Encoding: chunked\r\nContent-Length: 3\r\n",
        b"Content-Length: 999999999\r\n",
    ],
)
def test_rejects_ambiguous_or_unbounded_request_body(headers):
    proxy = LocalEgressProxy(["127.0.0.1"])
    proxy.start()
    try:
        with socket.create_connection(("127.0.0.1", proxy.port), timeout=3) as conn:
            conn.sendall(
                b"POST http://127.0.0.1:1/x HTTP/1.1\r\n" + headers + b"\r\nabc"
            )
            status = int(conn.recv(1024).split(b" ")[1])
            assert status in (400, 413, 501)
    finally:
        proxy.stop()


def _start_echo_server():
    """Returns the port of a single-shot TCP echo server."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]

    def run():
        conn, _ = srv.accept()
        data = conn.recv(1024)
        conn.sendall(data)  # echo
        conn.close()
        srv.close()

    threading.Thread(target=run, daemon=True).start()
    return port


def test_proxy_allows_connect_to_allowed_domain():
    echo_port = _start_echo_server()
    proxy = LocalEgressProxy(allowed_domains=["127.0.0.1"])
    proxy.start()
    try:
        s = socket.create_connection(("127.0.0.1", proxy.port), timeout=5)
        s.sendall(f"CONNECT 127.0.0.1:{echo_port} HTTP/1.1\r\n\r\n".encode())
        resp = s.recv(1024).decode("latin-1")
        assert "200" in resp

        s.sendall(b"hello-through-proxy")
        echoed = s.recv(1024)
        assert echoed == b"hello-through-proxy"
        s.close()
    finally:
        proxy.stop()


def test_proxy_blocks_connect_to_disallowed_domain():
    proxy = LocalEgressProxy(allowed_domains=["127.0.0.1"])
    proxy.start()
    try:
        s = socket.create_connection(("127.0.0.1", proxy.port), timeout=5)
        s.sendall(b"CONNECT evil.com:443 HTTP/1.1\r\n\r\n")
        resp = s.recv(1024).decode("latin-1")
        assert "403" in resp
        s.close()
    finally:
        proxy.stop()


def test_proxy_env_contains_http_and_https():
    proxy = LocalEgressProxy(allowed_domains=["x.com"])
    proxy.start()
    try:
        env = proxy.proxy_env()
        assert env["HTTP_PROXY"] == f"http://127.0.0.1:{proxy.port}"
        assert env["HTTPS_PROXY"] == f"http://127.0.0.1:{proxy.port}"
        assert env["NO_PROXY"] == "" and env["no_proxy"] == ""
    finally:
        proxy.stop()


def test_incomplete_request_cannot_keep_worker_forever(monkeypatch):
    monkeypatch.setattr("aero.infrastructure.egress_proxy._MAX_REQUEST_SECONDS", 0.1)
    proxy = LocalEgressProxy(["127.0.0.1"])
    proxy.start()
    try:
        started = time.monotonic()
        with socket.create_connection(("127.0.0.1", proxy.port), timeout=2) as conn:
            conn.sendall(b"GET http://127.0.0.1:1/")
            assert conn.recv(1024) == b""
        assert time.monotonic() - started < 1
    finally:
        proxy.stop()
