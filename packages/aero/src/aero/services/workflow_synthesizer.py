"""LLM-driven JIT workflow synthesis (always real — no synthetic fallback)."""

import json
from typing import Any, Optional

from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.domain.models import WorkflowManifest
from aero.infrastructure.parser import WorkflowParser, ManifestParser
from aero.infrastructure.attestation import canonicalize, sha256_hex
from aero.services import trust
from aero.services.discovery import AeroDiscoveryEngine
from aero.services.synthesizer import extract_json, persist_draft

SYSTEM_PROMPT = (
    "You are a workflow designer for AeroMesh. Given a user goal and a catalog of "
    "available verified agents, output ONLY a valid JSON object conforming to the "
    "AeroMesh DWM v1 workflow schema with fields: "
    'workflow_version ("1.0.0"), identity{id,name,version,description}, '
    "steps[{id,agent_id,intent,depends_on}], output. "
    "Rules: (1) choose agent_id values ONLY from the provided catalog; "
    "(2) identity.id must be a lowercase kebab-case slug; "
    "(3) use depends_on to express ordering — steps with no shared dependency run in parallel; "
    "(4) use {input} for the workflow input and {step_id} only for explicitly listed direct dependencies; "
    "(5) set output to the id of the final step. "
    "Do not include explanations or markdown fences."
)


class WorkflowSynthesizer:
    """Synthesizes a DWM v1 workflow for a goal using a real LLM, grounded on the
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

    def _catalog(self):
        entries = {}
        for record in self.discovery.build_registry_index():
            try:
                raw = trust.require_trusted_manifest(record.path, expected_id=record.id)
                manifest = ManifestParser().validate_dict(raw)
            except AeroMeshDomainError:
                continue
            entries[record.id] = {
                "id": manifest.identity.id,
                "name": manifest.identity.name,
                "domain": manifest.capabilities.domain,
                "short_description": manifest.capabilities.short_description,
                "evaluation_trigger": manifest.capabilities.evaluation_trigger,
                "agent_sha256": sha256_hex(canonicalize(raw)),
            }
        return entries

    def synthesize(self, goal: str, max_retries: int = 3) -> WorkflowManifest:
        if not isinstance(goal, str) or not goal.strip() or not 1 <= max_retries <= 5:
            raise AeroMeshDomainError(
                "Workflow synthesis requires a nonempty goal and 1–5 attempts.",
                ErrorCode.AMX_ERR_JIT_BUILD_FAILED,
                ExitCode.JIT_BUILD_FAILED,
            )
        catalog = self._catalog()
        if not catalog:
            raise AeroMeshDomainError(
                "Workflow synthesis requires at least one explicitly trusted agent.",
                ErrorCode.AMX_ERR_DISCOVERY_NO_MATCH,
                ExitCode.DISCOVERY_NO_MATCH,
            )
        model = self._get_model()
        last_error = None
        for _ in range(1, max_retries + 1):
            user_prompt = f"Goal: {goal}\n\nAvailable verified agents:\n{json.dumps(list(catalog.values()))}"
            if last_error:
                user_prompt += f"\nPrevious attempt failed validation: {last_error}"
            response = model.invoke([("system", SYSTEM_PROMPT), ("human", user_prompt)])
            text = getattr(response, "content", str(response))
            data = extract_json(text)
            if data is None:
                last_error = "response contained no JSON object"
                continue
            try:
                self.parser.validate_dict(data)
                for step in data["steps"]:
                    if step["agent_id"] not in catalog:
                        raise AeroMeshDomainError(
                            "Generated workflow references an agent outside the verified catalog.",
                            ErrorCode.AMX_ERR_JIT_BUILD_FAILED,
                            ExitCode.JIT_BUILD_FAILED,
                        )
                    step["agent_sha256"] = catalog[step["agent_id"]]["agent_sha256"]
                manifest = self.parser.validate_dict(data)
                self.last_manifest_path = persist_draft(data)
                return manifest
            except AeroMeshDomainError as e:
                last_error = str(e)

        raise AeroMeshDomainError(
            f"JIT workflow synthesis failed after {max_retries} attempts: {last_error}",
            ErrorCode.AMX_ERR_JIT_BUILD_FAILED,
            ExitCode.JIT_BUILD_FAILED,
        )
