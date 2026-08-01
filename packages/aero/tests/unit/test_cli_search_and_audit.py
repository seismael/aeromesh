"""Unit tests for amx search and amx audit CLI commands in cli.py."""

import pytest
from pathlib import Path
from aero.presentation.cli import main

CLEAN_MANIFEST = """{
  "manifest_version": "3.0.0",
  "identity": { "id": "test-sec-agent", "name": "Test Security Agent", "version": "1.0.0" },
  "capabilities": { "domain": "Security", "tags": ["security", "audit"], "short_description": "Clean manifest for CLI audit test", "evaluation_trigger": "Security audit" },
  "cognitive_runtime": { "persona": "Auditor", "success_criteria": "Audited" },
  "requirements": { "providers": [] }
}"""

def test_cli_search():
    exit_code = main(["search", "postgres database tuner"])
    assert exit_code == 0

def test_cli_audit():
    import shutil
    tmp_path = Path.cwd() / ".test_tmp_cli_audit"
    tmp_path.mkdir(exist_ok=True)
    try:
        fpath = tmp_path / "test-sec-agent.json"
        fpath.write_text(CLEAN_MANIFEST, encoding="utf-8")

        exit_code = main(["audit", str(fpath)])
        assert exit_code == 0
    finally:
        if tmp_path.exists():
            shutil.rmtree(tmp_path, ignore_errors=True)
