"""Unit tests for Guardian Security Scanner in aero.infrastructure.guardian."""

import pytest
from aero.infrastructure.guardian import GuardianSecurityScanner

CLEAN_MANIFEST = """{
  "manifest_version": "0.1.0",
  "identity": { "id": "secure-agent", "name": "Secure Agent", "version": "1.0.0" },
  "capabilities": { "domain": "Security", "tags": ["sec"], "short_description": "Clean manifest", "evaluation_trigger": "Test" },
  "cognitive_runtime": { "persona": "Tester", "success_criteria": "Pass" },
  "requirements": { "providers": [] }
}"""

HARDCODED_MANIFEST = """{
  "manifest_version": "0.1.0",
  "identity": { "id": "leaky-agent", "name": "Leaky Agent", "version": "1.0.0" },
  "capabilities": { "domain": "Security", "tags": ["sec"], "short_description": "Leaky manifest", "evaluation_trigger": "Test" },
  "cognitive_runtime": { "persona": "Tester", "success_criteria": "Pass" },
  "requirements": { "providers": [{ "type": "credential", "id": "ghp_1234567890abcdef" }] }
}"""

def test_guardian_scanner_clean():
    scanner = GuardianSecurityScanner()
    res = scanner.scan_manifest_content(CLEAN_MANIFEST)
    assert res["is_secure"] is True
    assert len(res["sha256_attestation"]) == 64

def test_guardian_scanner_hardcoded_key():
    scanner = GuardianSecurityScanner()
    res = scanner.scan_manifest_content(HARDCODED_MANIFEST)
    assert res["is_secure"] is False
    assert any("CRITICAL" in i for i in res["issues"])
