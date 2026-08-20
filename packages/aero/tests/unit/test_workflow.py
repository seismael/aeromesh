"""Unit tests for DWM workflows: parsing, DAG validation, execution, and trust."""

import copy
import json
from typing import ClassVar, List

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from aero.domain.errors import AeroMeshDomainError
from aero.domain.paths import get_aeromesh_agents_dir
from aero.infrastructure.parser import WorkflowParser
from aero.services import trust
from aero.services.workflow_runner import WorkflowExecutionDriver, render_intent

VALID = {
    "workflow_version": "0.1.0",
    "identity": {"id": "wf", "name": "W", "version": "1.0.0"},
    "steps": [
        {"id": "a", "agent_id": "agent-a", "intent": "x"},
        {"id": "b", "agent_id": "agent-b", "intent": "y", "depends_on": ["a"]},
    ],
    "output": "b",
}

AGENT = (
    '{"manifest_version":"0.1.0",'
    '"identity":{"id":"%s","name":"%s","version":"1.0.0"},'
    '"capabilities":{"domain":"T","tags":["t"],"short_description":"d","evaluation_trigger":"e"},'
    '"cognitive_runtime":{"persona":"p","success_criteria":"s"},'
    '"requirements":{"providers":[]}}'
)


# --- Parser / DAG validation ---

def test_valid_workflow_parses():
    wf = WorkflowParser().validate_dict(VALID)
    assert wf.identity.id == "wf"
    assert [s.id for s in wf.steps] == ["a", "b"]
    assert wf.output == "b"


def test_duplicate_step_ids_rejected():
    data = copy.deepcopy(VALID)
    data["steps"][1]["id"] = "a"
    with pytest.raises(AeroMeshDomainError):
        WorkflowParser().validate_dict(data)


def test_unknown_dependency_rejected():
    data = copy.deepcopy(VALID)
    data["steps"][1]["depends_on"] = ["nope"]
    with pytest.raises(AeroMeshDomainError):
        WorkflowParser().validate_dict(data)


def test_cycle_rejected():
    data = copy.deepcopy(VALID)
    data["steps"][0]["depends_on"] = ["b"]  # a -> b -> a
    with pytest.raises(AeroMeshDomainError):
        WorkflowParser().validate_dict(data)


def test_unknown_output_rejected():
    data = copy.deepcopy(VALID)
    data["output"] = "nope"
    with pytest.raises(AeroMeshDomainError):
        WorkflowParser().validate_dict(data)


# --- Templating ---

def test_render_intent_injects_upstream_results():
    assert render_intent("use {a}", {"a": "X"}) == "use X"
    assert render_intent("no placeholders", {}) == "no placeholders"
    assert render_intent("{a} then {b}", {"a": "1", "b": "2"}) == "1 then 2"


# --- Execution ---

class EchoChatModel(BaseChatModel):
    """Test double: records each intent and echoes it back (test code only)."""

    calls: ClassVar[List[str]] = []

    @property
    def _llm_type(self) -> str:
        return "echo-chat-model"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        last = messages[-1]
        content = getattr(last, "content", str(last))
        EchoChatModel.calls.append(content)
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=f"RESULT[{content}]"))]
        )

    def bind_tools(self, tools, **kwargs):
        return self


def _install_agent(agent_id: str):
    agents_dir = get_aeromesh_agents_dir()
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / f"{agent_id}.json").write_text(AGENT % (agent_id, agent_id))


def test_workflow_execution_and_output_selection(tmp_path):
    _install_agent("agent-a")
    _install_agent("agent-b")
    EchoChatModel.calls = []

    workflow = WorkflowParser().validate_dict(
        {
            "workflow_version": "0.1.0",
            "identity": {"id": "test-wf", "name": "T", "version": "1.0.0"},
            "steps": [
                {"id": "a", "agent_id": "agent-a", "intent": "first task"},
                {
                    "id": "b",
                    "agent_id": "agent-b",
                    "intent": "use {a}",
                    "depends_on": ["a"],
                },
            ],
            "output": "b",
        }
    )

    driver = WorkflowExecutionDriver(workflow, model=EchoChatModel())
    result = driver.execute("root")

    assert set(result["outputs"].keys()) == {"a", "b"}
    assert result["verified_result"] == result["outputs"]["b"]
    # Step b's intent was templated with step a's result before running.
    assert any("use RESULT[first task]" in c for c in EchoChatModel.calls)


# --- Recursive trust ---

def test_verify_workflow_references_rejects_untrusted_agent(tmp_path):
    _install_agent("agent-a")  # resolvable, but no trusted key in the workspace
    workflow = WorkflowParser().validate_dict(
        {
            "workflow_version": "0.1.0",
            "identity": {"id": "wf", "name": "W", "version": "1.0.0"},
            "steps": [{"id": "a", "agent_id": "agent-a", "intent": "x"}],
        }
    )
    ok, reason = trust.verify_workflow_references(workflow)
    assert ok is False
    assert "trusted key" in reason


def test_verify_workflow_references_rejects_missing_agent():
    workflow = WorkflowParser().validate_dict(
        {
            "workflow_version": "0.1.0",
            "identity": {"id": "wf", "name": "W", "version": "1.0.0"},
            "steps": [{"id": "a", "agent_id": "does-not-exist", "intent": "x"}],
        }
    )
    ok, reason = trust.verify_workflow_references(workflow)
    assert ok is False
    assert "not found" in reason
