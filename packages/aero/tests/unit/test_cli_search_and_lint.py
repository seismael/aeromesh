"""Tests for search and the explicit manifest lint interface."""

import pytest
from pathlib import Path
from aero.presentation.cli import main

CLEAN_MANIFEST = """{
  "manifest_version": "1.0.0",
  "identity": { "id": "test-sec-agent", "name": "Test Security Agent", "version": "1.0.0" },
  "capabilities": { "domain": "Security", "tags": ["security", "audit"], "short_description": "Clean manifest for CLI audit test", "evaluation_trigger": "Security audit" },
  "cognitive_runtime": { "persona": "Auditor", "success_criteria": "Audited" },
  "requirements": { "providers": [] }
}"""

def test_cli_search():
    exit_code = main(["search", "postgres database tuner"])
    assert exit_code == 0

def test_cli_lint(tmp_path, capsys):
    import json

    fpath = tmp_path / "test-sec-agent.json"
    fpath.write_text(CLEAN_MANIFEST, encoding="utf-8")
    assert main(["lint", str(fpath)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["passed_checks"] is True
    assert "not establish" in result["scope"]
