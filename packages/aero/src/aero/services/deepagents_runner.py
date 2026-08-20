"""Compile a DAM v0.1 manifest into a LangChain `create_deep_agent()` agent.

This is the correct architecture: AeroMesh does NOT implement an agent runtime.
It is a declarative, signed, sandboxed standard that compiles into Deep Agents,
which provide planning, subagents, skills, filesystem, and HITL out of the box.
"""

import json
import os
from typing import Any, Dict, List, Optional

from aero.domain.models import AgentManifest
from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode

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

        from deepagents import create_deep_agent

        kwargs = manifest_to_deepagent_kwargs(
            manifest, self.credentials, tools=mcp_tools, model=model_instance
        )
        if self.rubric:
            from deepagents import RubricMiddleware

            kwargs["middleware"] = [RubricMiddleware(model=model_instance)]

        self.agent = create_deep_agent(**kwargs)

    def execute(self, user_intent: str) -> Dict[str, Any]:
        config = {
            "configurable": {"thread_id": f"session-{self.manifest.identity.id}"}
        }
        state = {"messages": [{"role": "user", "content": user_intent}]}
        if self.rubric:
            state["rubric"] = self.rubric
        result = self.agent.invoke(state, config=config)
        messages = result.get("messages", [])
        final_text = messages[-1].content if messages else ""
        rubric_status = result.get("_rubric_status")
        success = bool(final_text and final_text.strip())
        if self.rubric:
            success = rubric_status == "passed"
        return {
            "agent_id": self.manifest.identity.id,
            "verified_result": final_text,
            "success_criteria_met": success,
            "rubric_status": rubric_status,
        }
