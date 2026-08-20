"""LLM-driven JIT agent manifest synthesis (LLM-first with template fallback)."""

import json
import re
from typing import Any, Dict, Optional

from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.domain.models import AgentManifest
from aero.infrastructure.parser import ManifestParser

SYSTEM_PROMPT = (
    "You are an agent-designer. Given a user goal, output ONLY a valid JSON object "
    "conforming to the AeroMesh DAM v0.1 declarative-agent manifest schema with fields: "
    "manifest_version (\"0.1.0\"), identity{id,name,version}, capabilities{domain,tags,"
    "short_description,evaluation_trigger}, cognitive_runtime{persona,success_criteria}, "
    "requirements{providers:[]}. The identity.id must be a lowercase kebab-case slug. "
    "Do not include explanations or markdown fences."
)


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract the first JSON object from an LLM response (strips code fences)."""
    if not text:
        return None
    # Strip ```json ... ``` fences
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    # Find the first balanced {...} block
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


class JitSynthesizer:
    """Synthesizes a DAM v0.1 manifest for a goal, preferring the LLM and falling back
    to a deterministic template when no live provider key is available."""

    def __init__(self, parser: Optional[ManifestParser] = None, adapter: Any = None):
        self.parser = parser or ManifestParser()
        self.adapter = adapter

    def _is_live(self) -> bool:
        if self.adapter is None:
            return False
        key = (getattr(self.adapter, "api_key", "") or "").lower()
        if not key:
            return False
        return not any(token in key for token in ("mock", "test", "fake"))

    def synthesize(self, goal: str, max_retries: int = 3) -> AgentManifest:
        if self._is_live():
            try:
                return self._synthesize_via_llm(goal, max_retries)
            except AeroMeshDomainError:
                raise
        return self._template_manifest(goal)

    def _synthesize_via_llm(self, goal: str, max_retries: int) -> AgentManifest:
        last_error = None
        for attempt in range(1, max_retries + 1):
            user_prompt = f"Goal: {goal}"
            if last_error:
                user_prompt += f"\nPrevious attempt failed schema validation: {last_error}"
            response = self.adapter.complete_prompt(SYSTEM_PROMPT, user_prompt)
            data = extract_json(response)
            if data is None:
                last_error = "response contained no JSON object"
                continue
            try:
                return self.parser.validate_dict(data)
            except AeroMeshDomainError as e:
                last_error = str(e)

        raise AeroMeshDomainError(
            f"JIT synthesis failed after {max_retries} attempts: {last_error}",
            ErrorCode.AMX_ERR_JIT_BUILD_FAILED,
            ExitCode.JIT_BUILD_FAILED,
        )

    def _template_manifest(self, goal: str) -> AgentManifest:
        """Deterministic fallback manifest for offline/no-key operation."""
        slug = re.sub(r"[^a-z0-9]+", "-", goal.lower()).strip("-")[:30] or "agent"
        agent_id = f"jit-{slug}"
        raw_dict = {
            "manifest_version": "0.1.0",
            "identity": {
                "id": agent_id,
                "name": f"JIT Synthesized Agent ({agent_id})",
                "version": "0.1.0",
                "author": "AeroEngine JIT Synthesizer",
                "license": "MIT",
            },
            "capabilities": {
                "domain": "Dynamic Multi-Domain",
                "tags": ["jit", "dynamic", "auto-generated"],
                "short_description": f"Auto-generated JIT agent for intent: {goal}",
                "evaluation_trigger": goal,
            },
            "cognitive_runtime": {
                "persona": f"You are a specialized autonomous agent created for: {goal}",
                "success_criteria": f"Goal criteria met: {goal}",
                "driver": "Driver.LangGraph",
                "memory_policy": "CVM_LRU_PAGING",
            },
            "requirements": {"providers": []},
        }
        return self.parser.validate_dict(raw_dict)
