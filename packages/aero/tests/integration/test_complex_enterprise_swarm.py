"""Integration tests for 5-Agent Enterprise Cloud Migration & Compliance Swarm Workflow."""

import os
import json
import shutil
import pytest
from aero.presentation.cli import main
from aero.domain.paths import get_aeromesh_home

WORKFLOW_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "..", "registry", "workflows", "enterprise-cloud-migration-and-compliance-swarm.json"
    )
)

@pytest.fixture
def workspace_scratch_dir():
    scratch_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "scratch")
    )
    os.makedirs(scratch_dir, exist_ok=True)
    yield scratch_dir
    shutil.rmtree(scratch_dir, ignore_errors=True)

def test_5_agent_complex_swarm_workflow_execution(workspace_scratch_dir, monkeypatch, capsys):
    monkeypatch.setenv("AEROMESH_HOME", os.path.join(workspace_scratch_dir, "aeromesh_test"))
    
    # Set all required credentials for 5 agents upfront
    monkeypatch.setenv("DB_CONNECT_STRING", "postgresql://admin:secret@localhost:5432/db")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_mock_token_1234567890")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_51M0...")
    monkeypatch.setenv("PLAID_CLIENT_SECRET", "secret_plaid_key_123")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-openai-key-123")
    monkeypatch.setenv("PINECONE_API_KEY", "pcsk_pinecone_key_456")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    monkeypatch.setenv("KUBECONFIG_DATA", "apiVersion: v1...")

    exit_code = main(["workflow", "run", WORKFLOW_PATH, "--non-interactive", "--diagnostics"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Executed Workflow 'Enterprise Multi-Cloud System Migration & Full Security Compliance Swarm'" in captured.out
    assert "Step 'step-1-db-tuner'" in captured.out
    assert "Step 'step-2-security-auditor'" in captured.out
    assert "Step 'step-3-fintech-auditor'" in captured.out
    assert "Step 'step-4-ai-vector-architect'" in captured.out
    assert "Step 'step-5-multicloud-devops'" in captured.out
