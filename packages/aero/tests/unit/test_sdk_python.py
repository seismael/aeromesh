"""Unit tests for AeroKernel in packages/sdk-python."""

import json

import pytest
import sys
from pathlib import Path

# Add sdk-python/src to sys.path for testing
sdk_path = Path(__file__).resolve().parents[4] / "packages" / "sdk-python" / "src"
if str(sdk_path) not in sys.path:
    sys.path.insert(0, str(sdk_path))

from aeromesh import AeroKernel

def test_aerokernel_sdk():
    kernel = AeroKernel()
    kernel.orchestrator.runner.vault.override_env["DB_CONNECT_STRING"] = "postgresql://localhost:5432/test"

    res = kernel.run_agent("registry/agents/postgres-performance-tuner.json", "Analyze slow query", non_interactive=True)
    assert res["mode"] == "AGENT"
    assert "result" in res


def test_aerokernel_run_workflow(tmp_path):
    from aero.domain.paths import get_aeromesh_agents_dir

    agents_dir = get_aeromesh_agents_dir()
    agents_dir.mkdir(parents=True, exist_ok=True)

    def _agent(aid):
        return {
            "manifest_version": "0.1.0",
            "identity": {"id": aid, "name": aid, "version": "1.0.0"},
            "capabilities": {
                "domain": "T", "tags": ["t"], "short_description": "d",
                "evaluation_trigger": "e",
            },
            "cognitive_runtime": {"persona": "p", "success_criteria": "s"},
            "requirements": {"providers": []},
        }

    for aid in ("sdk-a", "sdk-b"):
        (agents_dir / f"{aid}.json").write_text(json.dumps(_agent(aid)))

    wf = tmp_path / "wf.json"
    wf.write_text(json.dumps({
        "workflow_version": "0.1.0",
        "identity": {"id": "sdk-wf", "name": "W", "version": "1.0.0"},
        "steps": [
            {"id": "a", "agent_id": "sdk-a", "intent": "x"},
            {"id": "b", "agent_id": "sdk-b", "intent": "y", "depends_on": ["a"]},
        ],
        "output": "b",
    }))

    kernel = AeroKernel()
    res = kernel.run_workflow(str(wf), "go")
    assert res["workflow_id"] == "sdk-wf"
    assert set(res["result"]["outputs"].keys()) == {"a", "b"}
