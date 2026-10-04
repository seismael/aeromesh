"""Bounded HTTP proxy for cooperative development tools only.

A host process can ignore proxy variables; this is not a security boundary.
Trusted tools instead use the network-disabled container backend. Redirects are
returned to the client without following them, so each new request is checked.
"""

from __future__ import annotations

import http.client
import io
import re
import select
import socket
import socketserver
import threading
import time
from urllib.parse import urlsplit

from aero.infrastructure.sandbox import NetworkSandboxFirewall

_MAX_LINE = 8192
_MAX_HEADERS = 65536
_MAX_BODY = 16 * 1024 * 1024
_IO_TIMEOUT = 10
_MAX_REQUEST_SECONDS = 60
_MAX_TUNNEL_SECONDS = 60
_HOP_HEADERS = {
    "connection",
    "proxy-connection",
    "proxy-authorization",
    "proxy-authenticate",
    "keep-alive",
    "transfer-encoding",
    "te",
    "trailer",
    "upgrade",
}
_TOKEN = re.compile(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+\Z")


class _RequestError(Exception):
    def __init__(self, status: int):
        self.status = status


class _ProxyHandler(socketserver.StreamRequestHandler):
    # An unbuffered input avoids swallowing initial TLS bytes after CONNECT.
    rbufsize = 0

    def _expire(self) -> None:
        for sock in (self.request, self._upstream_socket):
            if sock is not None:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def _error(self, code: int) -> None:
        reason = http.client.responses.get(code, "Proxy Error")
        try:
            self.request.sendall(
                f"HTTP/1.1 {code} {reason}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".encode()
            )
        except OSError:
            pass

    def _read_headers(self):
        raw = bytearray()
        for _ in range(100):
            line = self.rfile.readline(_MAX_LINE + 1)
            if len(line) > _MAX_LINE or len(raw) + len(line) > _MAX_HEADERS:
                raise _RequestError(431)
            if line == b"\r\n":
                raw.extend(line)
                return http.client.parse_headers(io.BytesIO(raw))
            if (
                not line.endswith(b"\r\n")
                or b":" not in line
                or not _TOKEN.fullmatch(line.split(b":", 1)[0])
            ):
                raise _RequestError(400)
            if any(char < 32 and char != 9 for char in line[:-2]):
                raise _RequestError(400)
            raw.extend(line)
        raise _RequestError(431)

    def handle(self) -> None:
        self.request.settimeout(_IO_TIMEOUT)
        self._upstream_socket = None
        timer = threading.Timer(_MAX_REQUEST_SECONDS, self._expire)
        timer.daemon = True
        timer.start()
        self.server.track(self.request)
        try:
            line = self.rfile.readline(_MAX_LINE + 1)
            if not line:
                return
            if len(line) > _MAX_LINE:
                raise _RequestError(414)
            parts = line.rstrip(b"\r\n").split(b" ")
            if (
                len(parts) != 3
                or not _TOKEN.fullmatch(parts[0])
                or parts[2] not in (b"HTTP/1.0", b"HTTP/1.1")
            ):
                raise _RequestError(400)
            method, target = parts[0].decode("ascii"), parts[1].decode("ascii")
            headers = self._read_headers()
            lengths = headers.get_all("Content-Length", [])
            if len(lengths) > 1 or (lengths and not lengths[0].isascii()):
                raise _RequestError(400)
            if headers.get("Transfer-Encoding"):
                # Reject ambiguous framing and unsupported streaming uploads.
                raise _RequestError(400 if lengths else 501)
            if lengths and not re.fullmatch(r"[0-9]+", lengths[0]):
                raise _RequestError(400)
            length = int(lengths[0]) if lengths else 0
            if length > _MAX_BODY:
                raise _RequestError(413)
            if len(headers.get_all("Host", [])) > 1:
                raise _RequestError(400)
            if method == "CONNECT":
                if length:
                    raise _RequestError(400)
                self._tunnel(target)
            else:
                self._forward_http(method, target, headers, length)
        except _RequestError as exc:
            self._error(exc.status)
        except (ValueError, UnicodeError, http.client.HTTPException):
            self._error(400)
        except (TimeoutError, OSError):
            self._error(502)
        finally:
            timer.cancel()
            self.server.untrack(self.request)

    def _tunnel(self, target: str) -> None:
        parsed = urlsplit("//" + target)
        if (
            not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise _RequestError(400)
        port = parsed.port or 443
        if not self.server.firewall.is_domain_allowed(parsed.hostname):
            raise _RequestError(403)
        with socket.create_connection(
            (parsed.hostname, port), timeout=_IO_TIMEOUT
        ) as upstream:
            self._upstream_socket = upstream
            upstream.settimeout(_IO_TIMEOUT)
            self.server.track(upstream)
            try:
                self.request.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                self._relay(self.request, upstream)
            finally:
                self.server.untrack(upstream)

    @staticmethod
    def _relay(client: socket.socket, upstream: socket.socket) -> None:
        deadline = time.monotonic() + _MAX_TUNNEL_SECONDS
        last_activity = time.monotonic()
        readers = [client, upstream]
        while readers and time.monotonic() < deadline:
            remaining = min(
                deadline - time.monotonic(),
                _IO_TIMEOUT - (time.monotonic() - last_activity),
            )
            if remaining <= 0:
                return
            readable, _, _ = select.select(readers, [], [], remaining)
            if not readable:
                return
            for source in readable:
                data = source.recv(65536)
                destination = upstream if source is client else client
                if not data:
                    readers.remove(source)
                    destination.shutdown(socket.SHUT_WR)
                    continue
                destination.sendall(data)
                last_activity = time.monotonic()

    @staticmethod
    def _hop_headers(headers) -> set[str]:
        return _HOP_HEADERS | {
            token.strip().lower()
            for value in headers.get_all("Connection", [])
            for token in value.split(",")
        }

    def _forward_http(self, method: str, target: str, headers, length: int) -> None:
        if target.startswith("/"):
            if target.startswith("//") or not headers.get("Host"):
                raise _RequestError(400)
            target = "http://" + headers["Host"] + target
        parsed = urlsplit(target)
        if (
            parsed.scheme != "http"
            or not parsed.hostname
            or parsed.fragment
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise _RequestError(400)
        if not self.server.firewall.is_domain_allowed(parsed.hostname):
            raise _RequestError(403)
        if headers.get("Expect", "").lower() == "100-continue":
            self.request.sendall(b"HTTP/1.1 100 Continue\r\n\r\n")
        body = bytearray()
        while len(body) < length:
            part = self.rfile.read(min(65536, length - len(body)))
            if not part:
                raise _RequestError(400)
            body.extend(part)
        # HTTPConnection ignores global proxy environment and never follows redirects.
        connection = http.client.HTTPConnection(
            parsed.hostname, parsed.port or 80, timeout=_IO_TIMEOUT
        )
        try:
            path = parsed.path or "/"
            if parsed.query:
                path += "?" + parsed.query
            connection.putrequest(
                method, path, skip_host=True, skip_accept_encoding=True
            )
            connection.putheader("Host", parsed.netloc)
            hop_headers = self._hop_headers(headers) | {
                "host",
                "content-length",
                "expect",
            }
            for key, value in headers.items():
                if key.lower() not in hop_headers:
                    connection.putheader(key, value)
            if length or headers.get("Content-Length"):
                connection.putheader("Content-Length", str(length))
            connection.putheader("Connection", "close")
            connection.endheaders(bytes(body) if body else None)
            self._upstream_socket = connection.sock
            self.server.track(self._upstream_socket)
            response = connection.getresponse()
            # Buffer a bounded response to ensure one unambiguous message frame,
            # including origins that use chunked encoding or close-delimited data.
            payload = response.read(_MAX_BODY + 1)
            if len(payload) > _MAX_BODY:
                raise _RequestError(502)
            if method != "HEAD" and response.length not in (None, 0):
                raise _RequestError(502)  # truncated Content-Length body
            reason = http.client.responses.get(response.status, "Response")
            output = bytearray(f"HTTP/1.1 {response.status} {reason}\r\n".encode())
            skip = self._hop_headers(response.headers) | {"content-length"}
            for key, value in response.getheaders():
                if key.lower() not in skip:
                    if "\r" in value or "\n" in value:
                        raise _RequestError(502)
                    output.extend(f"{key}: {value}\r\n".encode("latin-1"))
            # HEAD metadata describes the GET entity; preserve that header.
            entity_length = (
                response.getheader("Content-Length") if method == "HEAD" else None
            )
            if entity_length is not None and not re.fullmatch(r"[0-9]+", entity_length):
                raise _RequestError(502)
            output.extend(
                f"Content-Length: {entity_length or len(payload)}\r\nConnection: close\r\n\r\n".encode()
            )
            self.request.sendall(output + payload)
        except (http.client.HTTPException, OSError) as exc:
            raise _RequestError(502) from exc
        finally:
            if self._upstream_socket is not None:
                self.server.untrack(self._upstream_socket)
            connection.close()


class _ProxyServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, firewall):
        self.firewall = firewall
        self._slots = threading.BoundedSemaphore(32)
        self._lock = threading.Lock()
        self._active: set[socket.socket] = set()
        super().__init__(("127.0.0.1", 0), _ProxyHandler)

    def track(self, sock):
        with self._lock:
            self._active.add(sock)

    def untrack(self, sock):
        with self._lock:
            self._active.discard(sock)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()

    def close_connections(self):
        with self._lock:
            for sock in self._active:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass


class LocalEgressProxy:
    """Own a loopback proxy for one cooperative development tool's allowlist."""

    def __init__(self, allowed_domains: list[str] | None = None):
        self.firewall = NetworkSandboxFirewall(allowed_domains=allowed_domains)
        self._server: _ProxyServer | None = None
        self._thread: threading.Thread | None = None
        self.port: int | None = None

    def start(self) -> int:
        if self._server is not None:
            return self.port
        self._server = _ProxyServer(self.firewall)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self.port

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.close_connections()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._server = None
        self._thread = None
        self.port = None

    def proxy_env(self) -> dict[str, str]:
        if self.port is None:
            raise RuntimeError("Start the proxy before obtaining its environment.")
        address = f"http://127.0.0.1:{self.port}"
        return {
            "HTTP_PROXY": address,
            "HTTPS_PROXY": address,
            "http_proxy": address,
            "https_proxy": address,
            "ALL_PROXY": address,
            "all_proxy": address,
            "NO_PROXY": "",
            "no_proxy": "",
        }
