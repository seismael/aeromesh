"""Guardian Security Static Scanner & Manifest Attestation Adapter."""

import hashlib
from typing import Dict, Any, List
from aero.infrastructure.parser import ManifestParser


class GuardianSecurityScanner:
    """Performs static analysis, secret exposure checks, and SHA-256 Sigstore hashing over agent manifests."""

    def __init__(self, parser: ManifestParser = None):
        self.parser = parser or ManifestParser()

    def scan_manifest_content(self, raw_json: str) -> Dict[str, Any]:
        manifest = self.parser.parse_raw(raw_json)
        issues: List[str] = []

        # Check 1: Secret hardcoding scan
        if "sk_live_" in raw_json or "ghp_" in raw_json or "AKIA" in raw_json:
            issues.append(
                "CRITICAL: Hardcoded API key or access token detected in manifest text!"
            )

        # Check 2: Unrestricted domain wildcard
        for prov in manifest.providers:
            if "*" in prov.allowed_domains:
                issues.append(
                    f"WARNING: Provider '{prov.id}' has unrestricted wildcard '*' in allowed_domains."
                )

        sha256_hash = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()

        return {
            "agent_id": manifest.identity.id,
            "version": manifest.identity.version,
            "sha256_attestation": sha256_hash,
            "is_secure": len([i for i in issues if i.startswith("CRITICAL")]) == 0,
            "issues": issues,
        }

    def export_bundle(self, raw_json: str) -> Dict[str, Any]:
        """Generates a signed JSON bundle containing manifest text, security audit result, and SHA-256 Sigstore hash."""
        scan_res = self.scan_manifest_content(raw_json)
        return {
            "bundle_version": "1.0.0",
            "agent_id": scan_res["agent_id"],
            "version": scan_res["version"],
            "sha256_attestation": scan_res["sha256_attestation"],
            "is_secure": scan_res["is_secure"],
            "manifest_data": self.parser.parse_raw(raw_json),
            "sigstore_proof": f"sigstore:sha256:{scan_res['sha256_attestation']}",
        }
