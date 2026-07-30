"""Integration tests for amx install and amx share commands (packages/aero)."""

import os
import json
import pytest
from aero.presentation.cli import main
from aero.domain.paths import get_aeromesh_agents_dir

SAMPLE_MANIFEST = {
    "manifest_version": "3.0.0",
    "identity": {
        "id": "shared-test-agent",
        "name": "Shared Test Agent",
        "version": "1.0.0",
        "author": "AeroMesh Team",
        "license": "MIT"
    },
    "capabilities": {
        "domain": "Sharing & Installing",
        "tags": ["share", "install"],
        "short_description": "Agent for testing install and share commands.",
        "evaluation_trigger": "Use when testing amx install and amx share commands."
    },
    "cognitive_runtime": {
        "driver": "Driver.LangGraph",
        "persona": "You are a test agent.",
        "success_criteria": "Must pass install and share tests."
    },
    "requirements": {
        "providers": []
    }
}

@pytest.fixture
def workspace_scratch_dir():
    scratch_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "scratch")
    )
    os.makedirs(scratch_dir, exist_ok=True)
    yield scratch_dir

def test_amx_install_and_run_from_local_store(workspace_scratch_dir, monkeypatch, capsys):
    # Override AEROMESH_HOME to scratch dir for isolated testing
    monkeypatch.setenv("AEROMESH_HOME", workspace_scratch_dir)
    
    manifest_file = os.path.join(workspace_scratch_dir, "shared_test_agent.json")
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(SAMPLE_MANIFEST, f)

    # 1. Test amx install
    install_exit = main(["install", manifest_file])
    assert install_exit == 0
    
    installed_path = get_aeromesh_agents_dir() / "shared-test-agent.json"
    assert installed_path.exists()

    # 2. Test amx run using ONLY agent_id (from local store)
    run_exit = main(["run", "shared-test-agent", "Test running from local store", "--non-interactive"])
    assert run_exit == 0
    captured = capsys.readouterr()
    assert "shared-test-agent" in captured.out

def test_amx_share_command(workspace_scratch_dir, capsys):
    manifest_file = os.path.join(workspace_scratch_dir, "shared_test_agent.json")
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(SAMPLE_MANIFEST, f)

    share_exit = main(["share", manifest_file])
    assert share_exit == 0
    captured = capsys.readouterr()
    assert "Registry Share Payload" in captured.out
    assert "shared-test-agent" in captured.out
    assert "sha256" in captured.out
