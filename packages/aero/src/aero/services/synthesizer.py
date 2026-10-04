"""LLM-driven JIT agent manifest synthesis (always real — no synthetic fallback)."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.domain.models import AgentManifest
from aero.infrastructure.parser import ManifestParser, strict_json
from aero.domain.paths import get_aeromesh_home
from aero.infrastructure.attestation import canonicalize, sha256_hex
from aero.services.trust import atomic_write

SYSTEM_PROMPT = (
    "You are an agent-designer. Given a user goal, output ONLY a valid JSON object "
    "conforming to the AeroMesh declarative-agent manifest schema with fields: "
    'manifest_version ("0.1.0"), identity{id,name,version}, capabilities{domain,tags,'
    "short_description,evaluation_trigger}, cognitive_runtime{persona,success_criteria}, "
    "requirements{providers:[]}. The identity.id must be a lowercase kebab-case slug. "
    "This authors a tool-free draft only. providers MUST remain []. No credential, tool, filesystem, or sub-agent access is available. The persona must answer the goal using the supplied information in the "
    "current session — do not create files or delegate to subagents unless the goal "
    "explicitly requires it. Do not include explanations or markdown fences."
)


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Decode an embedded object with correct JSON string/escape handling."""
    if not isinstance(text, str):
        return None
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            _, end = decoder.raw_decode(text[index:])
            result = strict_json(text[index : index + end])
            if isinstance(result, dict):
                return result
        except (ValueError, AeroMeshDomainError):
            continue
    return None


def manifest_to_dict(manifest: AgentManifest) -> Dict[str, Any]:
    """Serialize the supported schema without leaking dataclass-only defaults."""
    raw = asdict(manifest)
    data = {"manifest_version": raw["manifest_version"]}
    for block in ("identity", "capabilities", "cognitive_runtime"):
        data[block] = {
            key: value for key, value in raw[block].items() if value is not None
        }
    provider_keys = {
        "credential": {"type", "id", "kind", "fallback_action"},
        "mcp": {
            "type",
            "id",
            "transport",
            "command",
            "args",
            "allowed_domains",
            "uri",
            "required_tools",
            "image",
            "credential_bindings",
        },
        "sub_agent": {"type", "id", "agent_id", "agent_sha256", "delegation_purpose"},
    }
    for provider in raw["providers"]:
        supported = provider_keys.get(provider["type"], {"type", "id"})
        unsupported = [
            key
            for key, value in provider.items()
            if key not in supported
            and value not in (None, [], {})
            and not (key == "kind" and value == "credential")
        ]
        if unsupported:
            raise AeroMeshDomainError(
                f"Unsupported provider fields: {', '.join(unsupported)}",
                ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                ExitCode.SCHEMA_VIOLATION,
            )
    if raw.get("swarm_topology") and any(
        raw["swarm_topology"].get(key) is not None
        for key in ("consensus_threshold", "routing_key")
    ):
        raise AeroMeshDomainError(
            "Unsupported swarm topology behavior.",
            ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
            ExitCode.SCHEMA_VIOLATION,
        )
    if (
        raw.get("observability")
        and raw["observability"].get("trace_level", "info") != "info"
    ):
        raise AeroMeshDomainError(
            "Unsupported trace_level; configure native runtime tracing explicitly.",
            ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
            ExitCode.SCHEMA_VIOLATION,
        )
    data["requirements"] = {
        "providers": [
            {
                key: value
                for key, value in provider.items()
                if key in provider_keys.get(provider["type"], {"type", "id"})
                and value is not None
            }
            for provider in raw["providers"]
        ]
    }
    if raw.get("swarm_topology"):
        data["swarm_topology"] = {"pattern": raw["swarm_topology"]["pattern"]}
    if raw.get("observability"):
        data["observability"] = {
            key: value
            for key, value in raw["observability"].items()
            if value is not None and key != "trace_level"
        }
    return data


def persist_draft(data: Dict[str, Any]) -> Path:
    """Persist content-addressed authoring output; persistence grants no trust."""
    raw = canonicalize(data)
    path = get_aeromesh_home() / "drafts" / f"{sha256_hex(raw)}.json"
    atomic_write(path, raw)
    return path


class JitSynthesizer:
    """Synthesizes a DAM v0.1 manifest for a goal using a real LLM.

    There is no synthetic/template fallback: without a live provider key,
    synthesis raises a clear error. Test doubles are injected from test code.
    """

    def __init__(self, parser: Optional[ManifestParser] = None, model: Any = None):
        self.parser = parser or ManifestParser()
        self.model = model

    def _get_model(self) -> Any:
        if self.model is not None:
            return self.model
        from aero.services.deepagents_runner import resolve_model

        return resolve_model()

    def synthesize(self, goal: str, max_retries: int = 3) -> AgentManifest:
        if not isinstance(goal, str) or not goal.strip() or not 1 <= max_retries <= 5:
            raise AeroMeshDomainError(
                "Synthesis requires a nonempty goal and 1–5 attempts.",
                ErrorCode.AMX_ERR_JIT_BUILD_FAILED,
                ExitCode.JIT_BUILD_FAILED,
            )
        return self._synthesize_via_llm(goal, max_retries)

    def _synthesize_via_llm(self, goal: str, max_retries: int) -> AgentManifest:
        model = self._get_model()
        last_error = None
        for attempt in range(1, max_retries + 1):
            user_prompt = f"Goal: {goal}"
            if last_error:
                user_prompt += (
                    f"\nPrevious attempt failed schema validation: {last_error}"
                )
            response = model.invoke([("system", SYSTEM_PROMPT), ("human", user_prompt)])
            text = getattr(response, "content", str(response))
            data = extract_json(text)
            if data is None:
                last_error = "response contained no JSON object"
                continue
            try:
                manifest = self.parser.validate_dict(data)
                if manifest.providers:
                    raise AeroMeshDomainError(
                        "Generated drafts must be tool-free; capabilities require explicit authoring and approval.",
                        ErrorCode.AMX_ERR_JIT_BUILD_FAILED,
                        ExitCode.JIT_BUILD_FAILED,
                    )
                self.last_manifest_path = persist_draft(data)
                return manifest
            except AeroMeshDomainError as e:
                last_error = str(e)

        raise AeroMeshDomainError(
            f"JIT synthesis failed after {max_retries} attempts: {last_error}",
            ErrorCode.AMX_ERR_JIT_BUILD_FAILED,
            ExitCode.JIT_BUILD_FAILED,
        )
