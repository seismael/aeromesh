"""LLM-driven JIT agent manifest synthesis (always real — no synthetic fallback)."""

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
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
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
        return self._synthesize_via_llm(goal, max_retries)

    def _synthesize_via_llm(self, goal: str, max_retries: int) -> AgentManifest:
        model = self._get_model()
        last_error = None
        for attempt in range(1, max_retries + 1):
            user_prompt = f"Goal: {goal}"
            if last_error:
                user_prompt += f"\nPrevious attempt failed schema validation: {last_error}"
            response = model.invoke(
                [("system", SYSTEM_PROMPT), ("human", user_prompt)]
            )
            text = getattr(response, "content", str(response))
            data = extract_json(text)
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
