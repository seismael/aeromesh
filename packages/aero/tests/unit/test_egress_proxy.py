"""Tests for the local egress proxy (CONNECT tunneling with domain allowlisting)."""

import socket
import threading
import time

import pytest

from aero.infrastructure.egress_proxy import LocalEgressProxy


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
    finally:
        proxy.stop()
