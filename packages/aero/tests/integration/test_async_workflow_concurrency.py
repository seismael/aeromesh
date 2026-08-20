"""Integration tests for Non-Blocking Async DAG Concurrency in AeroWorkflowEngine."""

import os
import json
import asyncio
import time
import pytest
from aero.services.workflow import AeroWorkflowEngine
from aero.presentation.cli import main

REGISTRY_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "registry", "agents")
)

CONCURRENT_WORKFLOW = {
    "workflow_version": "1.0.0",
    "identity": {
        "id": "concurrent-async-test-workflow",
        "name": "Concurrent Non-Blocking Async Test Workflow"
    },
    "steps": [
        {
            "id": "step-slow-db",
            "agent_id": "postgres-performance-tuner",
            "intent": "Analyze slow query"
        },
        {
            "id": "step-fast-sec",
            "agent_id": "enterprise-security-auditor",
            "intent": "Audit secrets"
        },
        {
            "id": "step-devops-dependent",
            "agent_id": "multicloud-devops-orchestrator",
            "intent": "Deploy to EKS",
            "depends_on": ["step-slow-db"]
        }
    ]
}

@pytest.fixture
def workspace_scratch_dir():
    scratch_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "scratch")
    )
    os.makedirs(scratch_dir, exist_ok=True)
    yield scratch_dir

@pytest.mark.asyncio
async def test_async_workflow_concurrency_execution(workspace_scratch_dir, monkeypatch):
    monkeypatch.setenv("AEROMESH_HOME", workspace_scratch_dir)
    monkeypatch.setenv("DB_CONNECT_STRING", "postgresql://admin:secret@localhost:5432/db")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_mock_token_1234567890")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    monkeypatch.setenv("KUBECONFIG_DATA", "apiVersion: v1...")

    workflow_file = os.path.join(workspace_scratch_dir, "concurrent_wf.json")
    with open(workflow_file, "w", encoding="utf-8") as f:
        json.dump(CONCURRENT_WORKFLOW, f)

    engine = AeroWorkflowEngine()
    start_time = time.time()
    res = await engine.execute_workflow_async(workflow_file, non_interactive=True, enable_diagnostics=True)
    duration = time.time() - start_time

    assert res["status"] == "COMPLETED_SUCCESSFULLY"
    assert res["steps_executed"] == 3
    # Verify non-blocking async execution completed fast
    assert duration < 5.0


def test_workflow_error_propagates_without_hanging(workspace_scratch_dir, monkeypatch):
    """A failing step must propagate its error and release dependents (no deadlock)."""
    monkeypatch.setenv("AEROMESH_HOME", workspace_scratch_dir)
    monkeypatch.setenv("DB_CONNECT_STRING", "postgresql://admin:secret@localhost:5432/db")
    # Deliberately leave GITHUB_TOKEN unset so the security step fails.
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    monkeypatch.setenv("KUBECONFIG_DATA", "apiVersion: v1...")

    wf = {
        "workflow_version": "1.0.0",
        "identity": {"id": "failing-wf", "name": "Failing Workflow"},
        "steps": [
            {
                "id": "step-sec",
                "agent_id": "enterprise-security-auditor",
                "intent": "Audit secrets",
            },
            {
                "id": "step-devops",
                "agent_id": "multicloud-devops-orchestrator",
                "intent": "Deploy to EKS",
                "depends_on": ["step-sec"],
            },
        ],
    }
    wf_file = os.path.join(workspace_scratch_dir, "failing_wf.json")
    with open(wf_file, "w", encoding="utf-8") as f:
        json.dump(wf, f)

    engine = AeroWorkflowEngine()

    async def _run():
        return await asyncio.wait_for(
            engine.execute_workflow_async(wf_file, non_interactive=True), timeout=10
        )

    from aero.domain.errors import AeroMeshDomainError

    with pytest.raises(AeroMeshDomainError):
        asyncio.run(_run())
