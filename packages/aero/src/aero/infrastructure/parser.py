"""DAM v0.1 JSON Schema Validator Infrastructure Adapter."""

import os
import json
import jsonschema
from collections import deque
from typing import Dict, Any
from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.domain.models import (
    AgentManifest,
    AgentIdentity,
    AgentCapabilities,
    CognitiveRuntimeProfile,
    CapabilityProviderRequirement,
    SwarmTopology,
    ObservabilityProfile,
    WorkflowManifest,
    WorkflowIdentity,
    WorkflowStep,
)

SCHEMA_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "..",
        "..",
        "..",
        "schemas",
        "declarative-agent.schema.json",
    )
)

WORKFLOW_SCHEMA_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "..",
        "..",
        "..",
        "schemas",
        "declarative-workflow.schema.json",
    )
)


class ManifestParser:
    """Parses raw manifest text or dict and validates against DAM v0.1 JSON Schema."""

    def __init__(self, schema_path: str = SCHEMA_PATH):
        self.schema_path = schema_path
        self._schema_cache = None

    def _load_schema(self) -> Dict[str, Any]:
        if self._schema_cache is None:
            if not os.path.exists(self.schema_path):
                raise AeroMeshDomainError(
                    f"Schema file not found at '{self.schema_path}'",
                    ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                    ExitCode.SCHEMA_VIOLATION,
                )
            with open(self.schema_path, "r", encoding="utf-8") as f:
                self._schema_cache = json.load(f)
        return self._schema_cache

    def parse_raw(self, raw_json: str) -> AgentManifest:
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            raise AeroMeshDomainError(
                f"Invalid JSON format: {str(e)}",
                ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                ExitCode.SCHEMA_VIOLATION,
            )
        return self.validate_dict(data)

    def parse_file(self, file_path: str) -> AgentManifest:
        if not os.path.exists(file_path):
            raise AeroMeshDomainError(
                f"Manifest file not found: '{file_path}'",
                ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                ExitCode.SCHEMA_VIOLATION,
            )
        with open(file_path, "r", encoding="utf-8") as f:
            return self.parse_raw(f.read())

    def validate_dict(self, data: Dict[str, Any]) -> AgentManifest:
        schema = self._load_schema()
        try:
            jsonschema.validate(instance=data, schema=schema)
        except jsonschema.ValidationError as e:
            raise AeroMeshDomainError(
                f"Manifest failed DAM v0.1 schema assertion: {e.message}",
                ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                ExitCode.SCHEMA_VIOLATION,
            )

        identity_data = data["identity"]
        identity = AgentIdentity(
            id=identity_data["id"],
            name=identity_data["name"],
            version=identity_data["version"],
            author=identity_data.get("author"),
            license=identity_data.get("license", "MIT"),
            funding=identity_data.get("funding"),
        )

        caps_data = data["capabilities"]
        caps = AgentCapabilities(
            domain=caps_data["domain"],
            tags=caps_data["tags"],
            short_description=caps_data["short_description"],
            evaluation_trigger=caps_data["evaluation_trigger"],
            sub_domain=caps_data.get("sub_domain"),
            input_contract=caps_data.get("input_contract"),
            output_contract=caps_data.get("output_contract"),
        )

        runtime_data = data["cognitive_runtime"]
        runtime = CognitiveRuntimeProfile(
            persona=runtime_data["persona"],
            success_criteria=runtime_data["success_criteria"],
            driver=runtime_data.get("driver", "Driver.LangGraph"),
            memory_policy=runtime_data.get("memory_policy", "CVM_LRU_PAGING"),
            checkpoint_policy=runtime_data.get("checkpoint_policy", "ON_STEP"),
        )

        providers = []
        for prov_data in data.get("requirements", {}).get("providers", []):
            providers.append(
                CapabilityProviderRequirement(
                    type=prov_data["type"],
                    id=prov_data["id"],
                    kind=prov_data.get("kind", "credential"),
                    transport=prov_data.get("transport"),
                    command=prov_data.get("command"),
                    args=prov_data.get("args", []),
                    allowed_domains=prov_data.get("allowed_domains", []),
                    uri=prov_data.get("uri"),
                    required_tools=prov_data.get("required_tools", []),
                    fallback_action=prov_data.get("fallback_action"),
                    isolation=prov_data.get("isolation"),
                    agent_id=prov_data.get("agent_id"),
                    delegation_purpose=prov_data.get("delegation_purpose"),
                )
            )

        swarm_topology = None
        if "swarm_topology" in data:
            st = data["swarm_topology"]
            swarm_topology = SwarmTopology(
                pattern=st.get("pattern", "hierarchical"),
                consensus_threshold=st.get("consensus_threshold"),
                routing_key=st.get("routing_key"),
            )

        observability = None
        if "observability" in data:
            obs = data["observability"]
            observability = ObservabilityProfile(
                trace_level=obs.get("trace_level", "info"),
                cost_limit_usd=obs.get("cost_limit_usd"),
                max_execution_steps=obs.get("max_execution_steps"),
            )

        return AgentManifest(
            manifest_version=data["manifest_version"],
            identity=identity,
            capabilities=caps,
            cognitive_runtime=runtime,
            providers=providers,
            swarm_topology=swarm_topology,
            observability=observability,
        )


class WorkflowParser:
    """Parses a DWM v0.1 workflow manifest and validates against its schema."""

    def __init__(self, schema_path: str = WORKFLOW_SCHEMA_PATH):
        self.schema_path = schema_path
        self._schema_cache = None

    def _load_schema(self) -> Dict[str, Any]:
        if self._schema_cache is None:
            if not os.path.exists(self.schema_path):
                raise AeroMeshDomainError(
                    f"Workflow schema not found at '{self.schema_path}'",
                    ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                    ExitCode.SCHEMA_VIOLATION,
                )
            with open(self.schema_path, "r", encoding="utf-8") as f:
                self._schema_cache = json.load(f)
        return self._schema_cache

    def parse_raw(self, raw_json: str) -> WorkflowManifest:
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            raise AeroMeshDomainError(
                f"Invalid JSON format: {str(e)}",
                ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                ExitCode.SCHEMA_VIOLATION,
            )
        return self.validate_dict(data)

    def parse_file(self, file_path: str) -> WorkflowManifest:
        if not os.path.exists(file_path):
            raise AeroMeshDomainError(
                f"Workflow file not found: '{file_path}'",
                ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                ExitCode.SCHEMA_VIOLATION,
            )
        with open(file_path, "r", encoding="utf-8") as f:
            return self.parse_raw(f.read())

    def validate_dict(self, data: Dict[str, Any]) -> WorkflowManifest:
        schema = self._load_schema()
        try:
            jsonschema.validate(instance=data, schema=schema)
        except jsonschema.ValidationError as e:
            raise AeroMeshDomainError(
                f"Workflow failed DWM v0.1 schema assertion: {e.message}",
                ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                ExitCode.SCHEMA_VIOLATION,
            )

        identity_data = data["identity"]
        identity = WorkflowIdentity(
            id=identity_data["id"],
            name=identity_data["name"],
            version=identity_data["version"],
            author=identity_data.get("author"),
            license=identity_data.get("license", "MIT"),
            description=identity_data.get("description"),
        )

        steps = [
            WorkflowStep(
                id=s["id"],
                agent_id=s["agent_id"],
                intent=s["intent"],
                depends_on=s.get("depends_on", []),
            )
            for s in data["steps"]
        ]

        self._validate_dag(steps, data.get("output"))

        return WorkflowManifest(
            workflow_version=data["workflow_version"],
            identity=identity,
            steps=steps,
            output=data.get("output"),
        )

    @staticmethod
    def _validate_dag(steps, output) -> None:
        ids = {s.id for s in steps}
        if len(ids) != len(steps):
            raise AeroMeshDomainError(
                "Workflow steps must have unique ids.",
                ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                ExitCode.SCHEMA_VIOLATION,
            )

        dependents = {s.id: [] for s in steps}
        indegree = {s.id: 0 for s in steps}
        for step in steps:
            for dep in step.depends_on:
                if dep not in ids:
                    raise AeroMeshDomainError(
                        f"Step '{step.id}' depends on unknown step '{dep}'.",
                        ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                        ExitCode.SCHEMA_VIOLATION,
                    )
                dependents[dep].append(step.id)
                indegree[step.id] += 1

        # Cycle detection via Kahn's topological sort.
        queue = deque([sid for sid, deg in indegree.items() if deg == 0])
        seen = 0
        while queue:
            sid = queue.popleft()
            seen += 1
            for nxt in dependents[sid]:
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    queue.append(nxt)
        if seen != len(steps):
            raise AeroMeshDomainError(
                "Workflow contains a cycle in depends_on.",
                ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                ExitCode.SCHEMA_VIOLATION,
            )

        if output is not None and output not in ids:
            raise AeroMeshDomainError(
                f"Workflow output references unknown step '{output}'.",
                ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                ExitCode.SCHEMA_VIOLATION,
            )
