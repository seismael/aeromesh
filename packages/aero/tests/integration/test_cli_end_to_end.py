"""End-to-End Integration Tests for Aero Agent Engine (packages/aero)."""

import json
import os
import shutil
import pytest
from aero.presentation.cli import main

VALID_DAM_V3_MANIFEST = {
    "manifest_version": "0.1.0",
    "identity": {
        "id": "integration-test-agent",
        "name": "Integration Test PostgreSQL Agent",
        "version": "1.0.0",
        "author": "AeroMesh Core Team",
        "license": "MIT"
    },
    "capabilities": {
        "domain": "Database Engineering",
        "tags": ["postgres", "test"],
        "short_description": "Integration test agent for query optimization.",
        "evaluation_trigger": "Use when running end to end integration tests."
    },
    "cognitive_runtime": {
        "driver": "Driver.LangGraph",
        "persona": "You are a Database Specialist.",
        "success_criteria": "Must produce verified SQL DDL optimization scripts."
    },
    "requirements": {
        "providers": [
            {
                "type": "mcp",
                "id": "postgres-mcp",
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-postgres"]
            },
            {
                "type": "credential",
                "id": "TEST_DB_CONNECT_STRING",
                "kind": "connection_string"
            }
        ]
    }
}

@pytest.fixture
def workspace_tmp_dir():
    """Creates a temporary workspace directory inside packages/aero/tests/scratch."""
    scratch_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "scratch")
    )
    os.makedirs(scratch_dir, exist_ok=True)
    yield scratch_dir
    shutil.rmtree(scratch_dir, ignore_errors=True)

def test_amx_version_command(capsys):
    exit_code = main(["version"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "aero / amx version 0.1.0" in captured.out

def test_amx_validate_command_success(workspace_tmp_dir):
    manifest_file = os.path.join(workspace_tmp_dir, "valid_agent.json")
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(VALID_DAM_V3_MANIFEST, f)

    exit_code = main(["validate", manifest_file])
    assert exit_code == 0

def test_amx_validate_command_schema_error(workspace_tmp_dir):
    invalid_manifest = VALID_DAM_V3_MANIFEST.copy()
    invalid_manifest.pop("manifest_version")  # Missing required field
    manifest_file = os.path.join(workspace_tmp_dir, "invalid_agent.json")
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(invalid_manifest, f)

    exit_code = main(["validate", manifest_file])
    assert exit_code == 10  # ExitCode.SCHEMA_VIOLATION

def test_amx_run_command_end_to_end_success(workspace_tmp_dir, monkeypatch):
    manifest_file = os.path.join(workspace_tmp_dir, "valid_agent.json")
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(VALID_DAM_V3_MANIFEST, f)

    monkeypatch.setenv("TEST_DB_CONNECT_STRING", "postgresql://user:pass@localhost:5432/testdb")

    exit_code = main(["run", manifest_file, "Optimize query SELECT * FROM users", "--non-interactive"])
    assert exit_code == 0

def test_amx_run_command_missing_vault_key_failure(workspace_tmp_dir, monkeypatch):
    manifest_file = os.path.join(workspace_tmp_dir, "valid_agent.json")
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(VALID_DAM_V3_MANIFEST, f)

    monkeypatch.delenv("TEST_DB_CONNECT_STRING", raising=False)

    exit_code = main(["run", manifest_file, "Optimize query", "--non-interactive"])
    assert exit_code == 20  # ExitCode.VAULT_KEY_MISSING
