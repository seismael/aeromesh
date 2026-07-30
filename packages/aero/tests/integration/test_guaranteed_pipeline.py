"""Integration tests for Deterministic Guaranteed Agent Pipeline (DGAP) Engine."""

import os
import pytest
from aero.presentation.cli import main
from aero.services.pipeline import DeterministicPipelineOrchestrator

REGISTRY_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "registry", "agents")
)

def test_deterministic_guaranteed_3_agent_pipeline(monkeypatch):
    agent1 = os.path.join(REGISTRY_DIR, "postgres-performance-tuner.json")
    agent2 = os.path.join(REGISTRY_DIR, "enterprise-security-auditor.json")
    agent3 = os.path.join(REGISTRY_DIR, "multicloud-devops-orchestrator.json")

    # Set mock credentials required for non-interactive execution
    monkeypatch.setenv("DB_CONNECT_STRING", "postgresql://admin:secret@localhost:5432/db")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_mock_token_123")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    monkeypatch.setenv("KUBECONFIG_DATA", "apiVersion: v1...")

    orchestrator = DeterministicPipelineOrchestrator()
    res = orchestrator.execute_pipeline(
        [agent1, agent2, agent3],
        initial_intent="Optimize database queries and deploy to EKS",
        non_interactive=True,
        enable_diagnostics=True,
    )

    assert res["pipeline_status"] == "COMPLETED_GUARANTEED"
    assert res["steps_executed"] == 3
    assert len(res["pipeline_results"]) == 3
    assert res["pipeline_results"][0]["agent_id"] == "postgres-performance-tuner"
    assert res["pipeline_results"][1]["agent_id"] == "enterprise-security-auditor"
    assert res["pipeline_results"][2]["agent_id"] == "multicloud-devops-orchestrator"

def test_amx_pipeline_cli_command(monkeypatch, capsys):
    agent1 = os.path.join(REGISTRY_DIR, "postgres-performance-tuner.json")
    agent2 = os.path.join(REGISTRY_DIR, "enterprise-security-auditor.json")

    monkeypatch.setenv("DB_CONNECT_STRING", "postgresql://admin:secret@localhost:5432/db")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_mock_token_123")

    exit_code = main([
        "pipeline",
        agent1,
        agent2,
        "--intent", "Tune query and audit secrets",
        "--non-interactive",
        "--diagnostics"
    ])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Executed Deterministic Guaranteed Pipeline" in captured.out
    assert "Step 1 [postgres-performance-tuner]" in captured.out
    assert "Step 2 [enterprise-security-auditor]" in captured.out
