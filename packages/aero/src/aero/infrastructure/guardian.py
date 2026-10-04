"""Small manifest lint rules. This is neither a code audit nor certification."""

import hashlib
from typing import Any, Dict
from aero.infrastructure.parser import ManifestParser


class GuardianSecurityScanner:
    def __init__(self, parser=None):
        self.parser = parser or ManifestParser()

    def scan_manifest_content(self, raw_json: str) -> Dict[str, Any]:
        manifest = self.parser.parse_raw(raw_json)
        issues = []
        if any(prefix in raw_json for prefix in ("sk_live_", "ghp_", "AKIA")):
            issues.append(
                "Possible hardcoded credential pattern. Remove inline secrets and use explicit credential bindings."
            )
        for provider in manifest.providers:
            if "*" in provider.allowed_domains:
                issues.append(
                    f"Provider '{provider.id}' requests unrestricted domains."
                )
            if provider.type == "mcp" and provider.command:
                issues.append(
                    f"Provider '{provider.id}' uses a host command, supported only in development mode."
                )
        return {
            "agent_id": manifest.identity.id,
            "version": manifest.identity.version,
            "sha256": hashlib.sha256(raw_json.encode("utf-8")).hexdigest(),
            "passed_checks": not issues,
            "issues": issues,
            "scope": "Heuristic manifest lint only. Passing does not establish safe code, trusted provenance, isolation, or task correctness.",
        }
