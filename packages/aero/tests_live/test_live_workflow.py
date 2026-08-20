"""Live workflow test: two real DeepSeek agents composed into a DWM workflow."""

import json
import os

import pytest

from aero.domain.paths import get_aeromesh_agents_dir
from aero.infrastructure.parser import WorkflowParser
from aero.services.workflow_runner import WorkflowExecutionDriver


def _install_agent(agent_id: str, persona: str):
    agents_dir = get_aeromesh_agents_dir()
    agents_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "manifest_version": "0.1.0",
        "identity": {"id": agent_id, "name": agent_id, "version": "1.0.0"},
        "capabilities": {
            "domain": "General",
            "tags": ["live"],
            "short_description": "Live workflow test agent.",
            "evaluation_trigger": "test",
        },
        "cognitive_runtime": {
            "persona": persona,
            "success_criteria": "reply",
        },
        "requirements": {"providers": []},
    }
    (agents_dir / f"{agent_id}.json").write_text(json.dumps(manifest))


@pytest.mark.live
def test_live_workflow_two_steps():
    if not os.environ.get("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY not set; skipping live test")

    _install_agent("live-a", "Reply with exactly: A")
    _install_agent("live-b", "Reply with exactly: B")

    workflow = WorkflowParser().validate_dict(
        {
            "workflow_version": "0.1.0",
            "identity": {"id": "live-wf", "name": "Live WF", "version": "1.0.0"},
            "steps": [
                {"id": "a", "agent_id": "live-a", "intent": "Reply A"},
                {
                    "id": "b",
                    "agent_id": "live-b",
                    "intent": "Reply B, having seen: {a}",
                    "depends_on": ["a"],
                },
            ],
            "output": "b",
        }
    )

    driver = WorkflowExecutionDriver(workflow)
    result = driver.execute("run the two steps")
    assert set(result["outputs"].keys()) == {"a", "b"}
    assert result["verified_result"]
