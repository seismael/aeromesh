"""Compile a DAM v0.1 manifest into a LangChain `create_deep_agent()` agent.

This is the correct architecture: AeroMesh does NOT implement an agent runtime.
It is a declarative, signed, sandboxed standard that compiles into Deep Agents,
which provide planning, subagents, skills, filesystem, and HITL out of the box.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.callbacks import BaseCallbackHandler

from aero.domain.models import AgentManifest
from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.domain.paths import get_aeromesh_home

# Approximate USD price per million tokens (documented estimate, not billing-grade).
PRICE_PER_MILLION = {
    "deepseek-chat": {"input": 0.27, "output": 1.10},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
}
_DEFAULT_PRICE = {"input": 1.00, "output": 4.00}
DEFAULT_MAX_STEPS = 40


class TokenUsageCounter(BaseCallbackHandler):
    """Accumulates input/output token usage across LLM calls."""

    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0

    def on_llm_end(self, response, **kwargs) -> None:
        for gen_list in response.generations:
            for gen in gen_list:
                msg = getattr(gen, "message", None)
                usage = getattr(msg, "usage_metadata", None)
                if usage:
                    self.input_tokens += usage.get("input_tokens", 0)
                    self.output_tokens += usage.get("output_tokens", 0)


def estimate_cost(model_name: Optional[str], counter: TokenUsageCounter) -> float:
    """Estimate USD cost from token usage (approximate, documented)."""
    price = PRICE_PER_MILLION.get(model_name or "", _DEFAULT_PRICE)
    return (
        counter.input_tokens * price["input"]
        + counter.output_tokens * price["output"]
    ) / 1_000_000

# Provider -> langchain "provider:model" string (native SDKs).
PROVIDER_MODEL_STRINGS = {
    "deepseek": "deepseek:deepseek-chat",
    "openai": "openai:gpt-4o",
    "anthropic": "anthropic:claude-3-5-sonnet-20241022",
    "gemini": "google_genai:gemini-2.5-flash",
}

PROVIDER_ENV_VARS = {
    "deepseek": "DEEPSEEK_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


def default_checkpoint_db() -> Path:
    """SQLite file backing the persistent checkpointer (thread/session state)."""
    return get_aeromesh_home() / "checkpoints.sqlite"


def default_store_db() -> Path:
    """SQLite file backing the persistent store (long-term memory)."""
    return get_aeromesh_home() / "memory.sqlite"


async def build_async_checkpointer(db_path: Optional[Path] = None) -> Any:
    """Persistent LangGraph checkpointer (async SQLite) for cross-process resume.

    Async because the agent graph runs via ``ainvoke`` (MCP tools are async-only).
    """
    import aiosqlite

    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    path = db_path or default_checkpoint_db()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(path))
    saver = AsyncSqliteSaver(conn)
    await saver.setup()
    return saver


async def build_async_store(db_path: Optional[Path] = None) -> Any:
    """Persistent LangGraph store (async SQLite) for long-term memory."""
    import aiosqlite

    from langgraph.store.sqlite.aio import AsyncSqliteStore

    path = db_path or default_store_db()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(path))
    store = AsyncSqliteStore(conn)
    await store.setup()
    return store


def resolve_model(credentials: Optional[Dict[str, str]] = None) -> Any:
    """Resolve the first available provider into a real LangChain chat model.

    Always real: raises if no provider key is configured. Test doubles are
    injected from test code (never here).
    """
    credentials = credentials or {}
    last_error = None
    for provider, env_var in PROVIDER_ENV_VARS.items():
        key = credentials.get(env_var) or os.environ.get(env_var)
        if not key:
            continue
        try:
            from langchain.chat_models import init_chat_model

            return init_chat_model(PROVIDER_MODEL_STRINGS[provider], api_key=key)
        except Exception as e:  # noqa: BLE001 — try next provider
            last_error = e
    raise AeroMeshDomainError(
        f"No LLM provider API key configured ({', '.join(PROVIDER_ENV_VARS.values())}); "
        f"last error: {last_error}",
        ErrorCode.AMX_ERR_VAULT_KEY_MISSING,
        ExitCode.VAULT_KEY_MISSING,
    )


def extract_subagents(manifest: AgentManifest) -> List[Dict[str, str]]:
    """Map DAM `sub_agent` providers onto Deep Agents subagents."""
    subagents = []
    for p in manifest.providers:
        if p.type == "sub_agent":
            subagents.append(
                {
                    "name": p.agent_id or p.id,
                    "description": p.delegation_purpose or p.agent_id or p.id,
                    "system_prompt": (
                        f"You are a specialized sub-agent. "
                        f"Purpose: {p.delegation_purpose or p.id}."
                    ),
                }
            )
    return subagents


def extract_skills(manifest: AgentManifest) -> List[str]:
    """Map DAM `skill` providers onto Deep Agents skill directories."""
    return [p.id for p in manifest.providers if p.type == "skill"]


def mcp_connections(
    manifest: AgentManifest,
    credentials: Optional[Dict[str, str]] = None,
    proxy_env: Optional[Dict[str, str]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Pure mapping: DAM `mcp` providers -> MCP connection dicts."""
    connections: Dict[str, Dict[str, Any]] = {}
    for p in manifest.providers:
        if p.type != "mcp":
            continue
        if p.command:  # stdio subprocess
            env = dict(os.environ)
            env.update(credentials or {})
            if proxy_env:
                env.update(proxy_env)
            connections[p.id] = {
                "transport": "stdio",
                "command": p.command,
                "args": p.args or [],
                "env": env,
            }
        elif p.uri and p.transport == "sse":
            connections[p.id] = {"transport": "sse", "url": p.uri}
    return connections


def _required_tool_names(manifest: AgentManifest) -> set:
    names = set()
    for p in manifest.providers:
        if p.type == "mcp" and p.required_tools:
            names.update(p.required_tools)
    return names


def build_mcp_tools(
    manifest: AgentManifest,
    credentials: Optional[Dict[str, str]] = None,
    proxy_env: Optional[Dict[str, str]] = None,
) -> List[Any]:
    """Build real LangChain tools from the manifest's MCP providers.

    A declared MCP tool is a hard requirement: connection failures and missing
    required tools raise a clear error (they are never silently hidden).
    """
    connections = mcp_connections(manifest, credentials, proxy_env)
    if not connections:
        return []
    import asyncio

    from langchain_mcp_adapters.client import MultiServerMCPClient

    async def _build() -> List[Any]:
        client = MultiServerMCPClient(connections=connections)
        try:
            tools = await client.get_tools()
        except Exception as e:  # noqa: BLE001 — surface as a clear domain error
            raise AeroMeshDomainError(
                f"Failed to connect to MCP server(s) [{', '.join(connections)}]: {e}",
                ErrorCode.AMX_ERR_MCP_SPAWN_FAILED,
                ExitCode.MCP_SPAWN_FAILED,
            ) from e

        required = _required_tool_names(manifest)
        if required:
            available = {t.name for t in tools}
            missing = required - available
            if missing:
                raise AeroMeshDomainError(
                    f"MCP server(s) did not provide required tools: {sorted(missing)}",
                    ErrorCode.AMX_ERR_MCP_SPAWN_FAILED,
                    ExitCode.MCP_SPAWN_FAILED,
                )
            tools = [t for t in tools if t.name in required]
        return tools

    return asyncio.run(_build())


def build_rubric(manifest: AgentManifest) -> Optional[str]:
    """Turn a manifest's `output_contract` (JSON Schema) into a grading rubric."""
    contract = getattr(manifest.capabilities, "output_contract", None)
    if not contract:
        return None
    return (
        "The final answer must be a single valid JSON object conforming to this "
        "JSON Schema (respond with ONLY the JSON, no prose):\n" + json.dumps(contract)
    )


def manifest_to_deepagent_kwargs(
    manifest: AgentManifest,
    credentials: Optional[Dict[str, str]] = None,
    tools: Optional[List[Any]] = None,
    model: Any = None,
) -> Dict[str, Any]:
    """Compile a DAM manifest into `create_deep_agent(**kwargs)`."""
    kwargs: Dict[str, Any] = {
        "name": manifest.identity.name,
        "system_prompt": manifest.cognitive_runtime.persona,
        "model": model or resolve_model(credentials),
    }
    subagents = extract_subagents(manifest)
    if subagents:
        kwargs["subagents"] = subagents
    skills = extract_skills(manifest)
    if skills:
        kwargs["skills"] = skills
    if tools:
        kwargs["tools"] = tools
    return kwargs


class DeepAgentsExecutionDriver:
    """Executes a DAM manifest by delegating to Deep Agents (with real MCP tools)."""

    def __init__(
        self,
        manifest: AgentManifest,
        credentials: Optional[Dict[str, str]] = None,
        mcp_tools: Optional[List[Any]] = None,
        model: Any = None,
        checkpointer: Any = None,
        store: Any = None,
    ):
        self.manifest = manifest
        self.credentials = credentials or {}
        self.proxy = None
        proxy_env: Optional[Dict[str, str]] = None

        has_stdio_mcp = any(p.type == "mcp" and p.command for p in manifest.providers)
        if has_stdio_mcp and mcp_tools is None:
            # Route MCP subprocess HTTP(S) through the allowlist egress proxy.
            from aero.infrastructure.egress_proxy import LocalEgressProxy

            allowed = [
                d for p in manifest.providers for d in (p.allowed_domains or [])
            ]
            self.proxy = LocalEgressProxy(allowed_domains=allowed)
            self.proxy.start()
            proxy_env = self.proxy.proxy_env()

        if mcp_tools is None:
            # A declared MCP tool is a hard requirement — failures propagate.
            mcp_tools = build_mcp_tools(
                manifest, self.credentials, proxy_env=proxy_env
            )

        self.rubric = build_rubric(manifest)
        model_instance = model or resolve_model(self.credentials)
        self._model_name = getattr(model_instance, "model_name", None) or getattr(
            model_instance, "model", None
        )

        from deepagents import create_deep_agent

        # Persistence: wire a checkpointer (session resume / HITL) and a store
        # (long-term memory) so Deep Agents' built-in capabilities are available.
        # Defaults are SQLite-backed so state survives process restarts; test code
        # may inject in-memory backends. The graph runs via ``ainvoke`` (MCP tools
        # are async-only), so async SQLite backends live on a driver-lifetime loop.
        self._loop = asyncio.new_event_loop()
        try:
            if checkpointer is None:
                checkpointer = self._loop.run_until_complete(
                    build_async_checkpointer()
                )
            if store is None:
                store = self._loop.run_until_complete(build_async_store())
        except Exception:
            self._loop.close()
            raise
        self.checkpointer = checkpointer
        self.store = store

        kwargs = manifest_to_deepagent_kwargs(
            manifest, self.credentials, tools=mcp_tools, model=model_instance
        )
        if self.rubric:
            from deepagents import RubricMiddleware

            kwargs["middleware"] = [RubricMiddleware(model=model_instance)]

        self.agent = create_deep_agent(
            **kwargs, checkpointer=self.checkpointer, store=self.store
        )

    def execute(
        self, user_intent: str, thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        thread_id = thread_id or f"session-{self.manifest.identity.id}"
        config: Dict[str, Any] = {"configurable": {"thread_id": thread_id}}

        observability = getattr(self.manifest, "observability", None)
        counter = None
        step_limit = DEFAULT_MAX_STEPS
        if observability is not None:
            if observability.max_execution_steps is not None:
                step_limit = observability.max_execution_steps
            if observability.cost_limit_usd is not None:
                counter = TokenUsageCounter()
                config["callbacks"] = [counter]
        config["recursion_limit"] = step_limit

        state = {"messages": [{"role": "user", "content": user_intent}]}
        if self.rubric:
            state["rubric"] = self.rubric
        # Async invocation: langchain-mcp-adapters tools are async-only, so the
        # graph must run on the event loop for tool calls to work. We reuse the
        # driver-lifetime loop so the async SQLite backends stay valid.
        result = self._loop.run_until_complete(self.agent.ainvoke(state, config=config))
        messages = result.get("messages", [])
        final_text = messages[-1].content if messages else ""
        rubric_status = result.get("_rubric_status")
        success = bool(final_text and final_text.strip())
        if self.rubric:
            success = rubric_status == "passed"

        usage = None
        if counter is not None:
            model_name = getattr(self, "_model_name", None)
            cost = estimate_cost(model_name, counter)
            usage = {
                "input_tokens": counter.input_tokens,
                "output_tokens": counter.output_tokens,
                "estimated_cost_usd": round(cost, 6),
            }
            if cost > observability.cost_limit_usd:
                raise AeroMeshDomainError(
                    f"Estimated cost (${cost:.4f}) exceeded budget "
                    f"(${observability.cost_limit_usd:.2f}).",
                    ErrorCode.AMX_ERR_PROVIDER_FAILED,
                    ExitCode.PROVIDER_FAILED,
                )

        return {
            "agent_id": self.manifest.identity.id,
            "thread_id": thread_id,
            "verified_result": final_text,
            "success_criteria_met": success,
            "rubric_status": rubric_status,
            "usage": usage,
        }

    def close(self) -> None:
        """Release resources (SQLite connections, egress proxy, event loop)."""
        if self.proxy is not None:
            try:
                self.proxy.stop()
            except Exception:  # noqa: BLE001 — best-effort cleanup
                pass

        async def _shutdown() -> None:
            # Cancel lingering background tasks (e.g. LangGraph store batching)
            # before closing connections, so nothing is left pending on the loop.
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            for t in tasks:
                t.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            for backend in (self.checkpointer, self.store):
                conn = getattr(backend, "conn", None)
                if conn is not None:
                    await conn.close()

        try:
            self._loop.run_until_complete(_shutdown())
        except Exception:  # noqa: BLE001 — best-effort cleanup
            pass
        try:
            self._loop.close()
        except Exception:  # noqa: BLE001 — best-effort cleanup
            pass
