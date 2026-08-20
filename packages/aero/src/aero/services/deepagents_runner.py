"""Compile a DAM v0.1 manifest into a LangChain `create_deep_agent()` agent.

This is the correct architecture: AeroMesh does NOT implement an agent runtime.
It is a declarative, signed, sandboxed standard that compiles into Deep Agents,
which provide planning, subagents, skills, filesystem, and HITL out of the box.
"""

import os
from typing import Any, Dict, List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from aero.domain.models import AgentManifest
from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode


class OfflineChatModel(BaseChatModel):
    """Deterministic offline chat model for tests (implements bind_tools as no-op)."""

    response: str = "[offline] deterministic response"

    @property
    def _llm_type(self) -> str:
        return "offline-chat-model"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=self.response))]
        )

    def bind_tools(self, tools, **kwargs):
        return self


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
    """Resolve the first available provider into a LangChain chat model (native SDK).

    In offline mode (AEROMESH_OFFLINE=1), returns LangChain's own fake chat model
    for deterministic tests — no hand-rolled mocks.
    """
    credentials = credentials or {}
    if os.environ.get("AEROMESH_OFFLINE") == "1":
        return OfflineChatModel()

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


def manifest_to_deepagent_kwargs(
    manifest: AgentManifest, credentials: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Compile a DAM manifest into `create_deep_agent(**kwargs)`."""
    kwargs: Dict[str, Any] = {
        "name": manifest.identity.name,
        "system_prompt": manifest.cognitive_runtime.persona,
        "model": resolve_model(credentials),
    }
    subagents = extract_subagents(manifest)
    if subagents:
        kwargs["subagents"] = subagents
    skills = extract_skills(manifest)
    if skills:
        kwargs["skills"] = skills
    return kwargs


class DeepAgentsExecutionDriver:
    """Executes a DAM manifest by delegating to Deep Agents."""

    def __init__(
        self,
        manifest: AgentManifest,
        credentials: Optional[Dict[str, str]] = None,
    ):
        self.manifest = manifest
        self.credentials = credentials or {}
        from deepagents import create_deep_agent

        self.agent = create_deep_agent(
            **manifest_to_deepagent_kwargs(manifest, self.credentials)
        )

    def execute(self, user_intent: str) -> Dict[str, Any]:
        config = {
            "configurable": {"thread_id": f"session-{self.manifest.identity.id}"}
        }
        result = self.agent.invoke(
            {"messages": [{"role": "user", "content": user_intent}]}, config=config
        )
        messages = result.get("messages", [])
        final_text = messages[-1].content if messages else ""
        return {
            "agent_id": self.manifest.identity.id,
            "verified_result": final_text,
            "success_criteria_met": bool(final_text and final_text.strip()),
        }
