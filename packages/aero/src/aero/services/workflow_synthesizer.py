"""LLM-driven JIT workflow synthesis (always real — no synthetic fallback)."""

import json
from typing import Any, Optional

from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.domain.models import WorkflowManifest
from aero.infrastructure.parser import WorkflowParser
from aero.services.discovery import AeroDiscoveryEngine
from aero.services.synthesizer import extract_json

SYSTEM_PROMPT = (
    "You are a workflow designer for AeroMesh. Given a user goal and a catalog of "
    "available verified agents, output ONLY a valid JSON object conforming to the "
    "AeroMesh DWM v0.1 workflow schema with fields: "
    'workflow_version ("0.1.0"), identity{id,name,version,description}, '
    "steps[{id,agent_id,intent,depends_on}], output. "
    "Rules: (1) choose agent_id values ONLY from the provided catalog; "
    "(2) identity.id must be a lowercase kebab-case slug; "
    "(3) use depends_on to express ordering — steps with no shared dependency run in parallel; "
    "(4) use {step_id} placeholders in intent to pass an upstream step's result downstream; "
    "(5) set output to the id of the final step. "
    "Do not include explanations or markdown fences."
)


class WorkflowSynthesizer:
    """Synthesizes a DWM v0.1 workflow for a goal using a real LLM, grounded on the
    available agent catalog. There is no template fallback: without a live provider
    key, synthesis raises a clear error.
    """

    def __init__(
        self,
        parser: Optional[WorkflowParser] = None,
        model: Any = None,
        discovery: Optional[AeroDiscoveryEngine] = None,
    ):
        self.parser = parser or WorkflowParser()
        self.model = model
        self.discovery = discovery or AeroDiscoveryEngine()

    def _get_model(self) -> Any:
        if self.model is not None:
            return self.model
        from aero.services.deepagents_runner import resolve_model

        return resolve_model()

    def _catalog(self) -> str:
        records = self.discovery.build_registry_index()
        entries = [
            {
                "id": r.id,
                "name": r.name,
                "domain": r.domain,
                "short_description": r.short_description,
                "evaluation_trigger": r.evaluation_trigger,
            }
            for r in records
        ]
        return json.dumps(entries, indent=2)

    def synthesize(self, goal: str, max_retries: int = 3) -> WorkflowManifest:
        model = self._get_model()
        catalog = self._catalog()
        last_error = None
        for _ in range(1, max_retries + 1):
            user_prompt = f"Goal: {goal}\n\nAvailable verified agents:\n{catalog}"
            if last_error:
                user_prompt += f"\nPrevious attempt failed validation: {last_error}"
            response = model.invoke([("system", SYSTEM_PROMPT), ("human", user_prompt)])
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
            f"JIT workflow synthesis failed after {max_retries} attempts: {last_error}",
            ErrorCode.AMX_ERR_JIT_BUILD_FAILED,
            ExitCode.JIT_BUILD_FAILED,
        )
