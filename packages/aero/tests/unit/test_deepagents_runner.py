"""Trust, provenance, delegated contract and failure cleanup integration tests."""

import asyncio
import json
from typing import ClassVar

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from aero.domain.errors import AeroMeshDomainError
from aero.domain.paths import get_aeromesh_agents_dir
from aero.infrastructure.attestation import sha256_hex, canonicalize
from aero.infrastructure.parser import ManifestParser
from aero.services import deepagents_runner as runtime, trust


def raw(agent_id="root", providers=None, contract=None):
    result = {
        "manifest_version": "1.0.0",
        "identity": {"id": agent_id, "name": agent_id, "version": "1.0.0"},
        "capabilities": {
            "domain": "Audit",
            "tags": [],
            "short_description": "Audit",
            "evaluation_trigger": "audit",
        },
        "cognitive_runtime": {
            "persona": "ROOT TASK" if agent_id == "root" else "CHILD RULE",
            "success_criteria": "Evidence must substantiate every claim.",
        },
        "requirements": {"providers": providers or []},
    }
    if contract is not None:
        result["capabilities"]["output_contract"] = contract
    return result


class DelegatingModel(BaseChatModel):
    child_answer: str = '{"count":3}'
    prompts: ClassVar[list] = []
    max_tokens: int = 128

    @property
    def _llm_type(self):
        return "offline-delegation"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.prompts.append(str(messages))
        if "CHILD RULE" in str(messages[0].content):
            response = AIMessage(content=self.child_answer)
        elif not any(isinstance(m, ToolMessage) for m in messages):
            response = AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "delegate",
                        "name": "task",
                        "args": {
                            "description": "Return a count",
                            "subagent_type": "child",
                        },
                    }
                ],
            )
        else:
            response = AIMessage(
                content="Task execution finished; assess the evidence separately."
            )
        return ChatResult(generations=[ChatGeneration(message=response)])


def install(data, sign=False):
    path = get_aeromesh_agents_dir() / (data["identity"]["id"] + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    if sign:
        _, public = trust.generate_and_store_keypair(data["identity"]["id"])
        trust.sign_manifest_file(str(path), data["identity"]["id"])
        trust.trust_key(data["identity"]["id"], str(public))
    return path


def test_unsigned_object_cannot_execute_by_default():
    with pytest.raises(AeroMeshDomainError, match="trusted manifest path"):
        runtime.DeepAgentsExecutionDriver(
            ManifestParser().validate_dict(raw()), model=DelegatingModel(), mcp_tools=[]
        )


@pytest.mark.parametrize(
    "answer,valid", [('{"count":3}', True), ('{"count":"invalid"}', False)]
)
def test_signed_subagent_loads_real_definition_and_checks_its_output(answer, valid):
    DelegatingModel.prompts = []
    child = raw(
        "child",
        contract={
            "type": "object",
            "required": ["count"],
            "properties": {"count": {"type": "integer"}},
        },
    )
    install(child, sign=True)
    parent = raw(
        providers=[
            {
                "type": "sub_agent",
                "id": "child-ref",
                "agent_id": "child",
                "agent_sha256": sha256_hex(canonicalize(child)),
            }
        ]
    )
    path = install(parent, sign=True)
    d = runtime.DeepAgentsExecutionDriver(
        ManifestParser().validate_dict(parent),
        model=DelegatingModel(child_answer=answer),
        approved_manifest_path=str(path),
        checkpointer=InMemorySaver(),
        store=InMemoryStore(),
    )
    try:
        if valid:
            result = d.execute("Delegate to child")
            assert result["execution_success"] is True
            assert result["usage"]["model_calls"] == 3
        else:
            with pytest.raises(AeroMeshDomainError, match="output contract"):
                d.execute("Delegate to child")
        assert any(
            "CHILD RULE" in prompt and "Evidence must substantiate" in prompt
            for prompt in DelegatingModel.prompts
        )
    finally:
        d.close()


def test_revocation_after_compilation_blocks_execution():
    data = raw()
    path = install(data, sign=True)
    d = runtime.DeepAgentsExecutionDriver(
        ManifestParser().validate_dict(data),
        model=DelegatingModel(),
        mcp_tools=[],
        approved_manifest_path=str(path),
        checkpointer=InMemorySaver(),
        store=InMemoryStore(),
    )
    try:
        trust.revoke_key("root")
        with pytest.raises(AeroMeshDomainError, match="REVOKED"):
            d.execute("task")
    finally:
        d.close()


def test_subagent_cycle_is_rejected_in_development():
    parent = raw(
        providers=[{"type": "sub_agent", "id": "child-ref", "agent_id": "child"}]
    )
    child = raw(
        "child", providers=[{"type": "sub_agent", "id": "root-ref", "agent_id": "root"}]
    )
    install(parent)
    install(child)
    with pytest.raises(AeroMeshDomainError, match="cycle"):
        runtime.DeepAgentsExecutionDriver(
            ManifestParser().validate_dict(parent),
            model=DelegatingModel(),
            development=True,
            checkpointer=InMemorySaver(),
            store=InMemoryStore(),
        )


def tool(name):
    def call() -> str:
        """An offline tool."""
        return "ok"

    return StructuredTool.from_function(call, name=name)


def test_required_tools_cannot_be_satisfied_by_the_wrong_server(monkeypatch):
    from langchain_mcp_adapters.client import MultiServerMCPClient

    async def get_tools(self, *, server_name=None):
        return [tool("read")] if server_name == "server-a" else [tool("write")]

    monkeypatch.setattr(MultiServerMCPClient, "get_tools", get_tools)
    m = ManifestParser().validate_dict(
        raw(
            providers=[
                {
                    "type": "mcp",
                    "id": "server-a",
                    "transport": "stdio",
                    "command": "a",
                    "required_tools": ["write"],
                },
                {
                    "type": "mcp",
                    "id": "server-b",
                    "transport": "stdio",
                    "command": "b",
                    "required_tools": ["write"],
                },
            ]
        )
    )
    with pytest.raises(AeroMeshDomainError, match="server-a.*missing required tools"):
        asyncio.run(runtime._load_mcp_tools(m, {}))


def test_identical_tool_names_keep_server_provenance(monkeypatch):
    from langchain_mcp_adapters.client import MultiServerMCPClient

    async def get_tools(self, *, server_name=None):
        return [tool("read")]

    monkeypatch.setattr(MultiServerMCPClient, "get_tools", get_tools)
    m = ManifestParser().validate_dict(
        raw(
            providers=[
                {"type": "mcp", "id": server, "transport": "stdio", "command": server}
                for server in ("a", "b")
            ]
        )
    )
    tools = asyncio.run(runtime._load_mcp_tools(m, {}))
    assert [t.name for t in tools] == ["a__read", "b__read"]
    assert [t.metadata["mcp_provider"] for t in tools] == ["a", "b"]
    assert all(t.invoke({}) == "ok" for t in tools)


def test_mcp_failure_closes_registered_execution_resources(monkeypatch):
    cleaned = []

    def broken(*args, cleanup_callbacks, **kwargs):
        cleanup_callbacks.append(lambda: cleaned.append("container"))
        raise RuntimeError("MCP startup failed")

    monkeypatch.setattr(runtime, "build_mcp_tools", broken)
    with pytest.raises(RuntimeError, match="MCP startup failed"):
        runtime.DeepAgentsExecutionDriver(
            ManifestParser().validate_dict(raw()),
            model=DelegatingModel(),
            development=True,
            checkpointer=InMemorySaver(),
            store=InMemoryStore(),
        )
    assert cleaned == ["container"]


def test_namespaced_tool_name_collision_fails_before_model_binding(monkeypatch):
    from langchain_mcp_adapters.client import MultiServerMCPClient

    async def get_tools(self, *, server_name=None):
        return [tool("c" if server_name == "a__b" else "b__c")]

    monkeypatch.setattr(MultiServerMCPClient, "get_tools", get_tools)
    m = ManifestParser().validate_dict(
        raw(
            providers=[
                {"type": "mcp", "id": server, "transport": "stdio", "command": server}
                for server in ("a__b", "a")
            ]
        )
    )
    with pytest.raises(AeroMeshDomainError, match="collision"):
        asyncio.run(runtime._load_mcp_tools(m, {}))


def test_parent_call_budget_counts_real_subagent_model_calls():
    DelegatingModel.prompts = []
    child = raw("child")
    install(child)
    parent = raw(
        providers=[{"type": "sub_agent", "id": "child-ref", "agent_id": "child"}]
    )
    parent["observability"] = {"max_model_calls": 2}
    d = runtime.DeepAgentsExecutionDriver(
        ManifestParser().validate_dict(parent),
        model=DelegatingModel(),
        development=True,
        checkpointer=InMemorySaver(),
        store=InMemoryStore(),
    )
    try:
        with pytest.raises(AeroMeshDomainError, match="model call budget"):
            d.execute("Delegate to child")
        assert len(DelegatingModel.prompts) == 2
    finally:
        d.close()


class FilesystemBoundaryModel(BaseChatModel):
    host_input: str
    host_output: str
    shell_marker: str
    names: list[str] = []
    results: ClassVar[list] = []
    max_tokens: int = 128

    @property
    def _llm_type(self):
        return "filesystem-boundary-offline"

    def bind_tools(self, tools, **kwargs):
        return self.model_copy(update={"names": [t.name for t in tools]})

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        results = [m for m in messages if isinstance(m, ToolMessage)]
        if results:
            FilesystemBoundaryModel.results = results
            response = AIMessage(content="Boundary test completed.")
        else:
            calls = [
                {
                    "id": "read",
                    "name": "read_file",
                    "args": {"file_path": self.host_input},
                },
                {
                    "id": "write",
                    "name": "write_file",
                    "args": {"file_path": self.host_output, "content": "virtual-only"},
                },
            ]
            if "execute" in self.names:
                calls.append(
                    {
                        "id": "shell",
                        "name": "execute",
                        "args": {"command": f"touch {self.shell_marker}"},
                    }
                )
            response = AIMessage(content="", tool_calls=calls)
        return ChatResult(generations=[ChatGeneration(message=response)])


def test_trusted_native_filesystem_is_virtual_and_cannot_access_host(tmp_path):
    host_input = tmp_path / "host-secret.txt"
    host_input.write_text("HOST-SECRET-MUST-NOT-BE-READ")
    host_output = tmp_path / "host-output.txt"
    shell_marker = tmp_path / "shell-marker"
    data = raw()
    path = install(data, sign=True)
    model = FilesystemBoundaryModel(
        host_input=str(host_input),
        host_output=str(host_output),
        shell_marker=str(shell_marker),
    )
    d = runtime.DeepAgentsExecutionDriver(
        ManifestParser().validate_dict(data),
        model=model,
        approved_manifest_path=str(path),
        checkpointer=InMemorySaver(),
        store=InMemoryStore(),
    )
    try:
        assert (
            d.execute("Exercise virtual filesystem tools")["execution_success"] is True
        )
        assert "HOST-SECRET-MUST-NOT-BE-READ" not in str(
            FilesystemBoundaryModel.results
        )
        assert not host_output.exists()
        assert not shell_marker.exists()
        state = d._loop.run_until_complete(
            d.agent.aget_state(
                {"configurable": {"thread_id": next(iter(d.checkpointer.storage))}}
            )
        )
        assert str(host_output) in state.values["files"]
    finally:
        d.close()
