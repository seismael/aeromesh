"""Local HTTP(S) egress proxy enforcing ``allowed_domains`` on subprocess traffic.

Runs in-process on 127.0.0.1 and is injected into MCP tool subprocesses via
``HTTP_PROXY``/``HTTPS_PROXY`` so their outbound HTTP(S) calls are gated by the
agent's declared allowlist (CONNECT tunneling for HTTPS, best-effort for HTTP).
"""

import socket
import socketserver
import threading
from typing import List, Optional
from urllib.parse import urlparse

from aero.infrastructure.sandbox import NetworkSandboxFirewall


class _ProxyHandler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            self.request.settimeout(20)
            data = self.request.recv(65536)
            if not data:
                return
            first_line = data.split(b"\r\n", 1)[0].decode("latin-1", "replace")
            parts = first_line.split(" ")
            if len(parts) < 2:
                return
            method, target = parts[0].upper(), parts[1]
            if method == "CONNECT":
                self._tunnel(target)
            else:
                self._forward_http(method, target, data)
        except Exception:
            pass

    def _allowed(self, host: str) -> bool:
        return self.server.firewall.is_domain_allowed(host)

    def _tunnel(self, target: str):
        host, _, port = target.partition(":")
        port = int(port) if port else 443
        if not self._allowed(host):
            self.request.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\n")
            return
        try:
            upstream = socket.create_connection((host, port), timeout=10)
        except OSError:
            self.request.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            return
        self.request.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        self._relay(self.request, upstream)

    @staticmethod
    def _relay(a: socket.socket, b: socket.socket):
        def pump(src, dst):
            try:
                while True:
                    chunk = src.recv(65536)
                    if not chunk:
                        break
                    dst.sendall(chunk)
            except OSError:
                pass
            finally:
                try:
                    dst.shutdown(socket.SHUT_WR)
                except OSError:
                    pass

        t1 = threading.Thread(target=pump, args=(a, b), daemon=True)
        t2 = threading.Thread(target=pump, args=(b, a), daemon=True)
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

    def _forward_http(self, method: str, target: str, data: bytes):
        if target.startswith("http://") or target.startswith("https://"):
            url = target
        else:
            host = self._host_header(data)
            if not host:
                self.request.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                return
            url = f"http://{host}{target}"
        host = urlparse(url).hostname or ""
        if not self._allowed(host):
            self.request.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\n")
            return
        try:
            import urllib.request

            req = urllib.request.Request(url, method=method)
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read()
            status = getattr(resp, "status", 200)
            header = f"HTTP/1.1 {status} OK\r\nContent-Length: {len(body)}\r\n\r\n".encode()
            self.request.sendall(header + body)
        except Exception:
            self.request.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")

    def _host_header(self, data: bytes) -> Optional[str]:
        for line in data.split(b"\r\n"):
            if line.lower().startswith(b"host:"):
                return line.split(b":", 1)[1].strip().decode("latin-1", "replace")
        return None


class LocalEgressProxy:
    """Starts/stops a local filtering proxy and exposes proxy env vars."""

    def __init__(self, allowed_domains: Optional[List[str]] = None):
        self.firewall = NetworkSandboxFirewall(allowed_domains=allowed_domains)
        self._server: Optional[socketserver.ThreadingTCPServer] = None
        self._thread: Optional[threading.Thread] = None
        self.port: Optional[int] = None

    def start(self) -> int:
        self._server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _ProxyHandler)
        self._server.firewall = self.firewall  # type: ignore[attr-defined]
        self._server.daemon_threads = True
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self.port

    def stop(self):
        if self._server is not None:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
            self._server = None

    def proxy_env(self) -> dict:
        addr = f"http://127.0.0.1:{self.port}"
        return {
            "HTTP_PROXY": addr,
            "HTTPS_PROXY": addr,
            "http_proxy": addr,
            "https_proxy": addr,
            "ALL_PROXY": addr,
        }
