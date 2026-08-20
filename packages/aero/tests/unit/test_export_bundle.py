"""Unit tests for amx export-bundle CLI command and GuardianSecurityScanner.export_bundle."""

import pytest
from pathlib import Path
from aero.infrastructure.guardian import GuardianSecurityScanner
from aero.presentation.cli import main

MANIFEST_TEXT = """{
  "manifest_version": "3.0.0",
  "identity": { "id": "export-test-agent", "name": "Export Test Agent", "version": "1.0.0" },
  "capabilities": { "domain": "Security", "tags": ["sec"], "short_description": "Export test", "evaluation_trigger": "Test" },
  "cognitive_runtime": { "persona": "Auditor", "success_criteria": "Done" },
  "requirements": { "providers": [] }
}"""

def test_export_bundle_logic():
    scanner = GuardianSecurityScanner()
    bundle = scanner.export_bundle(MANIFEST_TEXT)

    assert bundle["bundle_version"] == "1.0.0"
    assert bundle["agent_id"] == "export-test-agent"
    assert bundle["attestation"].startswith("sha256:")

def test_cli_export_bundle_command():
    import shutil
    tmp_path = Path.cwd() / ".test_tmp_export"
    tmp_path.mkdir(exist_ok=True)
    try:
        fpath = tmp_path / "export-test-agent.json"
        fpath.write_text(MANIFEST_TEXT, encoding="utf-8")

        exit_code = main(["export-bundle", str(fpath)])
        assert exit_code == 0
    finally:
        if tmp_path.exists():
            shutil.rmtree(tmp_path, ignore_errors=True)
