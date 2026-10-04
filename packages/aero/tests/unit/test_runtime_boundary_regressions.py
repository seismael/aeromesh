"""Production boundaries that must also hold for nested agent invocations."""

import asyncio
from dataclasses import replace

import pytest
from langchain_core.messages import AIMessage
from langgraph.errors import GraphRecursionError
from langgraph.graph import START, StateGraph

from aero.domain.errors import AeroMeshDomainError
from aero.infrastructure.parser import ManifestParser
from aero.services import deepagents_runner as runtime
from aero.services.receipt import make_receipt


def manifest(**capabilities):
    return ManifestParser().validate_dict(
        {
            "manifest_version": "1.0.0",
            "identity": {"id": "bounded", "name": "Bounded", "version": "1.0.0"},
            "capabilities": {
                "domain": "test",
                "tags": [],
                "short_description": "test",
                "evaluation_trigger": "test",
                **capabilities,
            },
            "cognitive_runtime": {"persona": "test", "success_criteria": "test"},
            "requirements": {"providers": []},
            "observability": {"max_execution_steps": 2},
        }
    )


@pytest.mark.parametrize("payload", ["1e309", "-1e309", '{"nested":[1e309]}'])
def test_output_contract_rejects_nonfinite_exponent_overflow(payload):
    with pytest.raises(AeroMeshDomainError, match="output contract"):
        runtime._validate_output(
            manifest(output_contract={}), {"messages": [AIMessage(content=payload)]}
        )


@pytest.mark.parametrize("payload", ["1e309", "-1e309", '{"nested":[1e309]}'])
def test_input_contract_rejects_nonfinite_exponent_overflow(payload):
    with pytest.raises(AeroMeshDomainError, match="input contract"):
        runtime._validate_input(
            manifest(input_contract={"type": ["number", "object"]}), payload
        )


@pytest.mark.parametrize("parent_limit,child_limit", [(20, 2), (2, 20)])
def test_delegated_graph_enforces_tighter_parent_or_child_step_limit(
    parent_limit, child_limit
):
    calls = []

    def repeat(state):
        calls.append(True)
        return state

    graph = StateGraph(dict)
    graph.add_node("repeat", repeat)
    graph.add_edge(START, "repeat")
    graph.add_edge("repeat", "repeat")
    child = manifest()
    child = replace(
        child,
        observability=replace(child.observability, max_execution_steps=child_limit),
    )
    # The native graph performs the counting and termination; this test bypasses
    # model/network construction without mocking the scheduler or its limits.
    owner = object.__new__(runtime.DeepAgentsExecutionDriver)
    runnable = owner._child_runnable(child, graph.compile())
    with pytest.raises(GraphRecursionError):
        asyncio.run(
            runnable.ainvoke(
                {"messages": [{"content": "task"}]},
                config={"recursion_limit": parent_limit},
            )
        )
    assert len(calls) == min(parent_limit, child_limit)


def test_failed_cleanup_cannot_produce_successful_execution_receipt():
    receipt = make_receipt(
        execution_id="execution",
        session_id="session",
        artifact_sha256="a" * 64,
        status="failed",
        started_at=0,
        development=False,
        result={"execution_success": True, "output_valid": True},
        error=RuntimeError("Cleanup failed"),
    )
    assert receipt["execution_success"] is False
    assert receipt["status"] == "failed"
    assert receipt["output_valid"] is True


def test_driver_attempts_all_finalizers_and_reports_failed_cleanup():
    completed = []

    def broken():
        completed.append("broken")
        raise RuntimeError("sensitive cleanup detail")

    owner = object.__new__(runtime.DeepAgentsExecutionDriver)
    owner._closed = False
    owner._loop = None
    owner._cleanup_callbacks = [
        lambda: completed.append("first"),
        broken,
        lambda: completed.append("last"),
    ]
    with pytest.raises(AeroMeshDomainError, match="cleanup could not be confirmed") as error:
        owner.close()
    assert completed == ["last", "broken", "first"]
    assert "sensitive cleanup detail" not in str(error.value)
    owner.close()
    assert completed == ["last", "broken", "first"]


def test_constructor_preserves_primary_error_and_reports_cleanup_failure(monkeypatch):
    completed = []

    def broken_cleanup():
        completed.append(True)
        raise OSError("private daemon detail")

    def broken_compile(owner, *args):
        owner._cleanup_callbacks.append(broken_cleanup)
        raise ValueError("initial construction failure")

    monkeypatch.setattr(runtime.DeepAgentsExecutionDriver, "_compile", broken_compile)
    child = manifest()
    child = replace(
        child,
        cognitive_runtime=replace(child.cognitive_runtime, checkpoint_policy="DISABLED"),
    )
    with pytest.warns(RuntimeWarning, match="cleanup could not be confirmed"):
        with pytest.raises(ValueError, match="initial construction failure") as error:
            runtime.DeepAgentsExecutionDriver(child, development=True)
    assert completed == [True]
    assert "cleanup could not be confirmed" in error.value.__notes__[0]
    assert "private daemon detail" not in error.value.__notes__[0]
