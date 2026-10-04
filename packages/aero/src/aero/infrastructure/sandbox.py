"""Hostname matching for the cooperative development proxy.

This class validates hostnames, not IP routing or process isolation. Enforcement
against untrusted executables belongs to the network-disabled container backend.
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit

from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode


class NetworkSandboxFirewall:
    """Deny by default; match exact hosts or complete wildcard suffix labels."""

    def __init__(self, allowed_domains: list[str] | None = None):
        self.allowed_domains = list(allowed_domains or [])

    def _extract_domain(self, url_or_domain: str) -> str:
        if (
            not isinstance(url_or_domain, str)
            or not url_or_domain
            or any(ord(char) <= 32 or ord(char) == 127 for char in url_or_domain)
        ):
            return ""
        try:
            # Handle an unbracketed IPv6 literal passed by urlsplit.hostname.
            try:
                return str(ipaddress.ip_address(url_or_domain))
            except ValueError:
                pass
            parsed = urlsplit(
                url_or_domain if "://" in url_or_domain else "//" + url_or_domain
            )
            if (
                parsed.username is not None
                or parsed.password is not None
                or (parsed.scheme and parsed.scheme not in ("http", "https"))
            ):
                return ""
            _ = parsed.port  # validate port syntax and range
            hostname = (parsed.hostname or "").rstrip(".")
            if not hostname:
                return ""
            try:
                return str(ipaddress.ip_address(hostname))
            except ValueError:
                pass
            hostname = hostname.encode("idna").decode("ascii").lower()
            if len(hostname) > 253:
                return ""
            if not all(
                re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in hostname.split(".")
            ):
                return ""
            return hostname
        except (ValueError, UnicodeError):
            return ""

    def is_domain_allowed(self, url_or_domain: str) -> bool:
        target = self._extract_domain(url_or_domain)
        if not target:
            return False
        for pattern in self.allowed_domains:
            if not isinstance(pattern, str):
                continue
            if pattern == "*":
                return True
            wildcard = pattern.startswith("*.")
            allowed = self._extract_domain(pattern[2:] if wildcard else pattern)
            if allowed and (
                target == allowed or (wildcard and target.endswith("." + allowed))
            ):
                return True
        return False

    def validate_network_request(self, url_or_domain: str) -> str:
        target = self._extract_domain(url_or_domain)
        if not self.is_domain_allowed(url_or_domain):
            raise AeroMeshDomainError(
                f"Network request to unauthorized target '{target}' violates the proxy allowlist.",
                ErrorCode.AMX_ERR_DOMAIN_BLOCKED,
                ExitCode.DOMAIN_BLOCKED,
            )
        return target
