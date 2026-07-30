"""Integration & Deep Resilience Stress Tests for AeroMasterOrchestrator."""

import os
import json
import time
import pytest
from concurrent.futures import ThreadPoolExecutor
from aero.services.orchestrator import AeroMasterOrchestrator
from aero.domain.errors import AeroMeshDomainError, ErrorCode

REGISTRY_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "registry")
)

@pytest.fixture
def workspace_scratch_dir():
    scratch_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "scratch")
    )
    os.makedirs(scratch_dir, exist_ok=True)
    yield scratch_dir

def test_orchestrator_resilience_non_existent_target(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test-mock-key")
    orchestrator = AeroMasterOrchestrator()
    with pytest.raises(AeroMeshDomainError) as exc:
        orchestrator.dispatch("non_existent_agent_9999.json", intent="Do something", non_interactive=True)
    assert exc.value.error_code == ErrorCode.AMX_ERR_DISCOVERY_NO_MATCH

def test_orchestrator_resilience_corrupted_json(workspace_scratch_dir):
    bad_json_file = os.path.join(workspace_scratch_dir, "corrupted.json")
    with open(bad_json_file, "w", encoding="utf-8") as f:
        f.write("{ invalid json content: true ")

    orchestrator = AeroMasterOrchestrator()
    with pytest.raises(AeroMeshDomainError) as exc:
        orchestrator.dispatch(bad_json_file, intent="Do something", non_interactive=True)
    assert exc.value.error_code == ErrorCode.AMX_ERR_SCHEMA_VIOLATION

def test_orchestrator_resilience_missing_intent_for_agent():
    agent_path = os.path.join(REGISTRY_DIR, "agents", "postgres-performance-tuner.json")
    orchestrator = AeroMasterOrchestrator()
    with pytest.raises(AeroMeshDomainError) as exc:
        orchestrator.dispatch(agent_path, intent=None, non_interactive=True)
    assert "Intent string is required" in str(exc.value)

def test_orchestrator_resilience_missing_intent_for_pipeline():
    agent_path = os.path.join(REGISTRY_DIR, "agents", "postgres-performance-tuner.json")
    orchestrator = AeroMasterOrchestrator()
    with pytest.raises(AeroMeshDomainError) as exc:
        orchestrator.dispatch([agent_path], intent=None, non_interactive=True)
    assert "Intent string is required" in str(exc.value)

def test_orchestrator_resilience_workflow_referencing_missing_agent(workspace_scratch_dir):
    bad_wf = {
        "workflow_version": "1.0.0",
        "identity": {"id": "bad-agent-ref", "name": "Bad Agent Ref Workflow"},
        "steps": [{"id": "s1", "agent_id": "non_existent_agent_888", "intent": "Do task"}]
    }
    wf_file = os.path.join(workspace_scratch_dir, "bad_wf.json")
    with open(wf_file, "w", encoding="utf-8") as f:
        json.dump(bad_wf, f)

    orchestrator = AeroMasterOrchestrator()
    with pytest.raises(AeroMeshDomainError) as exc:
        orchestrator.dispatch(wf_file, non_interactive=True)
    assert exc.value.error_code == ErrorCode.AMX_ERR_DISCOVERY_NO_MATCH

def test_orchestrator_resilience_missing_vault_key(monkeypatch):
    monkeypatch.delenv("DB_CONNECT_STRING", raising=False)
    agent_path = os.path.join(REGISTRY_DIR, "agents", "postgres-performance-tuner.json")

    orchestrator = AeroMasterOrchestrator()
    with pytest.raises(AeroMeshDomainError) as exc:
        orchestrator.dispatch(agent_path, intent="Analyze query", non_interactive=True)
    assert exc.value.error_code == ErrorCode.AMX_ERR_VAULT_KEY_MISSING

def test_orchestrator_high_throughput_parallel_stress(monkeypatch):
    # Set required environment keys
    monkeypatch.setenv("DB_CONNECT_STRING", "postgresql://admin:secret@localhost:5432/db")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_mock_token_123")

    wf_path = os.path.join(REGISTRY_DIR, "workflows", "daily_enterprise_audit.json")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    monkeypatch.setenv("KUBECONFIG_DATA", "apiVersion: v1...")

    orchestrator = AeroMasterOrchestrator(max_workers=10)

    def _run_single_dispatch(batch_id: int):
        return orchestrator.dispatch(wf_path, non_interactive=True)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(_run_single_dispatch, i) for i in range(10)]
        results = [f.result() for f in futures]

    total_duration = time.time() - t0
    assert len(results) == 10
    for r in results:
        assert r["mode"] == "WORKFLOW"
        assert r["result"]["status"] == "COMPLETED_SUCCESSFULLY"

    # All 10 parallel workflows must complete in under 5.0 seconds
    assert total_duration < 5.0
