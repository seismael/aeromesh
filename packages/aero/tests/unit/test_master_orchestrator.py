"""Unit tests for AeroMasterOrchestrator Facade Service."""

import os
import json
import pytest
from aero.services.orchestrator import AeroMasterOrchestrator

REGISTRY_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "registry")
)

def test_master_orchestrator_auto_detect_single_agent(monkeypatch):
    monkeypatch.setenv("DB_CONNECT_STRING", "postgresql://admin:secret@localhost:5432/db")
    agent_path = os.path.join(REGISTRY_DIR, "agents", "postgres-performance-tuner.json")
    
    orchestrator = AeroMasterOrchestrator()
    res = orchestrator.dispatch(agent_path, intent="Analyze query SELECT 1", non_interactive=True)
    
    assert res["mode"] == "AGENT"
    assert res["result"]["manifest"].identity.id == "postgres-performance-tuner"

def test_master_orchestrator_auto_detect_pipeline(monkeypatch):
    monkeypatch.setenv("DB_CONNECT_STRING", "postgresql://admin:secret@localhost:5432/db")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_mock_token_123")
    
    agent1 = os.path.join(REGISTRY_DIR, "agents", "postgres-performance-tuner.json")
    agent2 = os.path.join(REGISTRY_DIR, "agents", "enterprise-security-auditor.json")
    
    orchestrator = AeroMasterOrchestrator()
    res = orchestrator.dispatch([agent1, agent2], intent="Tune query and audit secrets", non_interactive=True)
    
    assert res["mode"] == "PIPELINE"
    assert res["result"]["pipeline_status"] == "COMPLETED_GUARANTEED"
    assert res["result"]["steps_executed"] == 2

def test_master_orchestrator_auto_detect_workflow(monkeypatch):
    monkeypatch.setenv("DB_CONNECT_STRING", "postgresql://admin:secret@localhost:5432/db")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_mock_token_123")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    monkeypatch.setenv("KUBECONFIG_DATA", "apiVersion: v1...")
    
    wf_path = os.path.join(REGISTRY_DIR, "workflows", "daily_enterprise_audit.json")
    
    orchestrator = AeroMasterOrchestrator()
    res = orchestrator.dispatch(wf_path, non_interactive=True)
    
    assert res["mode"] == "WORKFLOW"
    assert res["result"]["status"] == "COMPLETED_SUCCESSFULLY"


def test_master_orchestrator_hybrid_goal_dispatch(monkeypatch):
    """Regression: a hybrid goal (known agent + unknown clause) must not crash."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-mock-key")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_mock_token_123")

    orchestrator = AeroMasterOrchestrator()
    res = orchestrator.dispatch(
        "Audit workspace secrets and generate custom executive PDF summary",
        non_interactive=True,
    )

    assert res["mode"] == "PIPELINE"
    assert res["result"]["steps_executed"] >= 2
    agent_ids = [s["agent_id"] for s in res["result"]["pipeline_results"]]
    assert "enterprise-security-auditor" in agent_ids
    assert any(aid.startswith("jit-") for aid in agent_ids)
