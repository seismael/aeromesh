"""Regression coverage for runtime contracts and preventive invocation limits."""

from typing import ClassVar
from dataclasses import replace

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from aero.domain.errors import AeroMeshDomainError
from aero.infrastructure.parser import ManifestParser
from aero.services import deepagents_runner as runtime


class ObservedModel(BaseChatModel):
    answer: str = "I could not complete the audit."
    calls: ClassVar[list] = []
    max_tokens: int = 128

    @property
    def _llm_type(self):
        return "observed-offline"

    def bind_tools(self, tools, **kwargs):
        return self.bind(**kwargs)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls.append((messages, kwargs))
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=self.answer))]
        )


def manifest(**updates):
    data = {
        "manifest_version": "1.0.0",
        "identity": {"id": "runtime-check", "name": "Runtime", "version": "1.0.0"},
        "capabilities": {
            "domain": "Audit",
            "tags": [],
            "short_description": "Audit",
            "evaluation_trigger": "Audit",
        },
        "cognitive_runtime": {
            "persona": "Audit the supplied evidence.",
            "success_criteria": "Produce three independently verified findings.",
        },
        "requirements": {"providers": []},
    }
    for section, values in updates.items():
        data.setdefault(section, {}).update(values)
    return ManifestParser().validate_dict(data)


def driver(m=None, model=None, **kwargs):
    return runtime.DeepAgentsExecutionDriver(
        m or manifest(),
        model=model or ObservedModel(),
        mcp_tools=[],
        development=True,
        checkpointer=InMemorySaver(),
        store=InMemoryStore(),
        **kwargs,
    )


def test_noncompletion_is_not_task_success_and_criteria_reach_model():
    ObservedModel.calls = []
    d = driver()
    try:
        result = d.execute("Audit this input")
        assert result["execution_success"] is True
        assert result["success_criteria_met"] is None
        assert result["task_assessment"] == "unverified"
        assert result["output_valid"] is None
        assert "three independently verified" in str(ObservedModel.calls[0][0])
    finally:
        d.close()


def test_input_contract_is_validated_before_model_call():
    ObservedModel.calls = []
    d = driver(
        manifest(
            capabilities={
                "input_contract": {"type": "object", "required": ["repository"]}
            }
        )
    )
    try:
        with pytest.raises(AeroMeshDomainError, match="input contract"):
            d.execute("not JSON")
        assert ObservedModel.calls == []
    finally:
        d.close()


def test_output_contract_uses_deterministic_schema_validation():
    contract = {
        "type": "object",
        "required": ["count"],
        "properties": {"count": {"type": "integer"}},
    }
    d = driver(
        manifest(capabilities={"output_contract": contract}),
        ObservedModel(answer='{"count":"wrong type"}'),
    )
    try:
        with pytest.raises(AeroMeshDomainError, match="output contract"):
            d.execute("Return data")
    finally:
        d.close()
    d = driver(
        manifest(capabilities={"output_contract": contract}),
        ObservedModel(answer='{"count":3}'),
    )
    try:
        result = d.execute("Return data")
        assert result["output_valid"] is True
        assert result["structured_output"] == {"count": 3}
        assert result["success_criteria_met"] is None
    finally:
        d.close()


def test_checkpoint_disabled_never_opens_persistent_backends(monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail("disabled checkpoints must not open persistent storage")

    monkeypatch.setattr(runtime, "build_async_checkpointer", forbidden)
    monkeypatch.setattr(runtime, "build_async_store", forbidden)
    d = runtime.DeepAgentsExecutionDriver(
        manifest(cognitive_runtime={"checkpoint_policy": "DISABLED"}),
        model=ObservedModel(),
        mcp_tools=[],
        development=True,
    )
    try:
        assert d.execute("task")["execution_success"] is True
    finally:
        d.close()


def test_empty_answer_is_execution_failure():
    d = driver(model=ObservedModel(answer=""))
    try:
        with pytest.raises(AeroMeshDomainError, match="empty"):
            d.execute("task")
    finally:
        d.close()


def test_model_selection_rejects_ambiguous_provider_configuration(monkeypatch):
    # Test the real resolver, because tests/conftest intentionally replaces the facade.
    monkeypatch.delenv("AEROMESH_MODEL", raising=False)
    for key in runtime.PROVIDER_ENV_VARS.values():
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(AeroMeshDomainError, match="AEROMESH_MODEL"):
        runtime.resolve_configured_model(
            {"OPENAI_API_KEY": "offline", "DEEPSEEK_API_KEY": "offline"}
        )


def test_budget_prevents_model_call_before_estimate_exceeds_limit():
    ObservedModel.calls = []
    m = manifest(
        observability={
            "cost_limit_usd": 0.000001,
            "max_output_tokens": 128,
            "max_model_calls": 2,
            "input_price_per_million": 1,
            "output_price_per_million": 1,
        }
    )
    d = driver(m)
    try:
        with pytest.raises(AeroMeshDomainError, match="budget"):
            d.execute("task")
        assert ObservedModel.calls == []
    finally:
        d.close()


def test_constructor_closes_partial_storage_on_failure(monkeypatch):
    closed = []

    class Connection:
        async def close(self):
            closed.append("connection")

    class Backend:
        conn = Connection()

    async def checkpoint():
        return Backend()

    async def broken_store():
        raise RuntimeError("storage failure")

    monkeypatch.setattr(runtime, "build_async_checkpointer", checkpoint)
    monkeypatch.setattr(runtime, "build_async_store", broken_store)
    with pytest.raises(RuntimeError, match="storage failure"):
        runtime.DeepAgentsExecutionDriver(
            manifest(), model=ObservedModel(), mcp_tools=[], development=True
        )
    assert closed == ["connection"]


def test_explicit_budget_allows_affordable_capped_calls():
    ObservedModel.calls = []
    m = manifest(
        observability={
            "cost_limit_usd": 1.0,
            "max_output_tokens": 128,
            "max_model_calls": 2,
            "input_price_per_million": 1,
            "output_price_per_million": 1,
        }
    )
    d = driver(m)
    try:
        result = d.execute("task")
        assert len(ObservedModel.calls) == 1
        assert ObservedModel.calls[0][1]["max_tokens"] == 128
        assert 0 < result["usage"]["estimated_cost_usd"] < 1
        assert result["usage"]["billing_guarantee"] is False
    finally:
        d.close()


def test_input_union_contract_preserves_valid_plain_text():
    d = driver(
        manifest(
            capabilities={
                "input_contract": {"oneOf": [{"type": "string"}, {"type": "object"}]}
            }
        )
    )
    try:
        assert d.execute("plain task text")["execution_success"] is True
    finally:
        d.close()


@pytest.mark.parametrize("side", ["input", "output"])
def test_unresolvable_contract_reference_is_a_domain_error(side):
    valid = manifest()
    invalid = replace(
        valid,
        capabilities=replace(
            valid.capabilities,
            **{f"{side}_contract": {"$ref": "#/definitions/missing"}},
        ),
    )
    with pytest.raises(AeroMeshDomainError, match="contract"):
        d = driver(invalid, model=ObservedModel(answer="{}"))
        try:
            d.execute("{}")
        finally:
            d.close()
