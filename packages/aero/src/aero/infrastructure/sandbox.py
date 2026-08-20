"""Network Sandbox Firewall Engine for DAM v0.1 allowed_domains Enforcement."""

from urllib.parse import urlparse
from typing import List, Optional
from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode


class NetworkSandboxFirewall:
    """Enforces domain allowlisting rules declared in agent manifests to prevent unauthorized data exfiltration."""

    def __init__(self, allowed_domains: Optional[List[str]] = None):
        self.allowed_domains = allowed_domains or []

    def _extract_domain(self, url_or_domain: str) -> str:
        """Extracts normalized hostname from URL or raw domain string."""
        target = url_or_domain.strip()
        if (
            target.startswith("http://")
            or target.startswith("https://")
            or "://" in target
        ):
            parsed = urlparse(target)
            hostname = parsed.hostname or target
        else:
            # Strip port and path if present
            hostname = target.split("/")[0].split(":")[0]

        return hostname.lower()

    def is_domain_allowed(self, url_or_domain: str) -> bool:
        """Validates if target hostname matches allowed_domains policies."""
        if not self.allowed_domains:
            return True  # Open default if no restrictions specified

        if "*" in self.allowed_domains:
            return True

        target_host = self._extract_domain(url_or_domain)

        for pattern in self.allowed_domains:
            pattern_clean = pattern.strip().lower()

            # Strip scheme if declared in pattern
            if "://" in pattern_clean:
                pattern_clean = urlparse(pattern_clean).hostname or pattern_clean
            pattern_clean = pattern_clean.split("/")[0].split(":")[0]

            # Exact match
            if target_host == pattern_clean:
                return True

            # Wildcard domain match (e.g. *.postgresql.org)
            if pattern_clean.startswith("*."):
                suffix = pattern_clean[2:]
                if target_host.endswith("." + suffix) or target_host == suffix:
                    return True

        return False

    def validate_network_request(self, url_or_domain: str) -> str:
        """Validates target domain against allowlist policy, raising AMX_ERR_SECURITY_VIOLATION if unauthorized."""
        if not self.is_domain_allowed(url_or_domain):
            target_host = self._extract_domain(url_or_domain)
            raise AeroMeshDomainError(
                f"Network request to unauthorized target '{target_host}' violates sandbox allowlist policy.",
                ErrorCode.AMX_ERR_DOMAIN_BLOCKED,
                ExitCode.DOMAIN_BLOCKED,
            )
        return self._extract_domain(url_or_domain)
