"""DAM v1 JSON Schema Validator Infrastructure Adapter."""

import os
import json
import math
import re
import jsonschema
from collections import deque
from typing import Dict, Any
from urllib.parse import unquote
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

MAX_MANIFEST_BYTES = 2 * 1024 * 1024


def _schema_path(name: str) -> str:
    from importlib.resources import files
    from pathlib import Path

    packaged = files("aero").joinpath("schemas", name)
    if packaged.is_file():
        return str(packaged)
    # Editable source checkout only. Wheels carry the resources above.
    return str(Path(__file__).resolve().parents[5] / "schemas" / name)


SCHEMA_PATH = _schema_path("declarative-agent.schema.json")
WORKFLOW_SCHEMA_PATH = _schema_path("declarative-workflow.schema.json")


def _violation(message: str) -> AeroMeshDomainError:
    return AeroMeshDomainError(
        message, ErrorCode.AMX_ERR_SCHEMA_VIOLATION, ExitCode.SCHEMA_VIOLATION
    )


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Non-finite JSON number")
    return number


def strict_json_value(raw: str) -> Any:
    """Decode bounded JSON without duplicate keys or non-finite numbers."""
    if len(raw.encode("utf-8")) > MAX_MANIFEST_BYTES:
        raise _violation("JSON exceeds the 2 MiB limit")
    try:
        return json.loads(
            raw,
            object_pairs_hook=_unique_object,
            parse_float=_finite_float,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError("Non-finite JSON number")
            ),
        )
    except (ValueError, RecursionError) as exc:
        raise _violation(f"Invalid JSON: {exc}") from exc


def strict_json(raw: str) -> Dict[str, Any]:
    data = strict_json_value(raw)
    if not isinstance(data, dict):
        raise _violation("Manifest must be a JSON object")
    return data


def _read_manifest(path: str) -> str:
    from pathlib import Path

    p = Path(path)
    try:
        with p.open("rb") as stream:
            raw = stream.read(MAX_MANIFEST_BYTES + 1)
        if len(raw) > MAX_MANIFEST_BYTES:
            raise _violation("Manifest exceeds the 2 MiB limit")
        return raw.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise _violation(f"Cannot read manifest '{path}': {exc}") from exc


def _resolve_contract_pointer(contract: Dict[str, Any], reference: str):
    """Resolve a local URI-fragment JSON Pointer without a network resolver."""
    if not isinstance(reference, str) or (
        reference != "#" and not reference.startswith("#/")
    ):
        raise ValueError(
            "Only local JSON Pointer references (# or #/...) are supported"
        )
    if re.search(r"%(?![0-9A-Fa-f]{2})", reference):
        raise ValueError(
            f"Malformed percent escape in contract reference: {reference!r}"
        )
    pointer = unquote(reference[1:], encoding="utf-8", errors="strict")
    target = contract
    if pointer:
        for component in pointer[1:].split("/"):
            if re.search(r"~(?:[^01]|$)", component):
                raise ValueError(
                    f"Malformed JSON Pointer escape in contract reference: {reference!r}"
                )
            component = component.replace("~1", "/").replace("~0", "~")
            if isinstance(target, dict) and component in target:
                target = target[component]
            elif isinstance(target, list) and re.fullmatch(r"0|[1-9][0-9]*", component):
                index = int(component)
                if index >= len(target):
                    raise ValueError(
                        f"Unresolved local contract reference: {reference!r}"
                    )
                target = target[index]
            else:
                raise ValueError(f"Unresolved local contract reference: {reference!r}")
    if not isinstance(target, (dict, bool)):
        raise ValueError(
            f"Contract reference must target an object or boolean schema: {reference!r}"
        )
    jsonschema.Draft7Validator.check_schema(target)
    return target


def validate_contract_definition(contract: Dict[str, Any]) -> None:
    """Contracts use local Draft 7 schemas; validation must never fetch a URL."""
    try:
        jsonschema.Draft7Validator.check_schema(contract)
        pending = [contract]
        visited = set()
        resolved = {}
        reference_edges = {}
        while pending:
            current = pending.pop()
            if id(current) in visited:
                continue
            visited.add(id(current))
            if len(visited) > 10000:
                raise ValueError("Contract is too complex")
            if isinstance(current, dict):
                for key, value in current.items():
                    if key == "$ref":
                        if not isinstance(value, str):
                            raise ValueError("Contract reference must be a string")
                        if value not in resolved:
                            resolved[value] = _resolve_contract_pointer(contract, value)
                        reference_edges[id(current)] = id(resolved[value])
                        pending.append(resolved[value])
                    if key in {
                        "$id",
                        "$dynamicRef",
                        "$recursiveRef",
                        "$anchor",
                        "$dynamicAnchor",
                        "$recursiveAnchor",
                    }:
                        raise ValueError(f"Unsupported contract keyword: {key}")
                    if key == "$schema" and value not in {
                        "http://json-schema.org/draft-07/schema#",
                        "https://json-schema.org/draft-07/schema",
                    }:
                        raise ValueError("Only Draft 7 contracts are supported")
                # Traverse schema-bearing locations only. Property names and
                # values under enum/const/default/examples are ordinary data,
                # even when their keys happen to be "$ref" or "$id".
                for key in ("definitions", "properties", "patternProperties"):
                    pending.extend(current.get(key, {}).values())
                for key in (
                    "additionalProperties", "additionalItems", "contains",
                    "propertyNames", "not", "if", "then", "else",
                ):
                    if key in current:
                        pending.append(current[key])
                for key in ("allOf", "anyOf", "oneOf"):
                    pending.extend(current.get(key, []))
                items = current.get("items", [])
                pending.extend(items if isinstance(items, list) else [items])
                pending.extend(
                    dependency
                    for dependency in current.get("dependencies", {}).values()
                    if isinstance(dependency, (dict, bool))
                )
        # Draft 7 ignores $ref siblings. A direct reference-only loop cannot
        # consume an instance. Structural recursion through properties/items is
        # intentionally allowed, and jsonschema handles its instance traversal.
        completed = set()
        for start in reference_edges:
            chain = set()
            node = start
            while node in reference_edges and node not in completed:
                if node in chain:
                    raise ValueError(
                        "Contract has a direct reference cycle without instance descent"
                    )
                chain.add(node)
                node = reference_edges[node]
            completed.update(chain)
    except (ValueError, jsonschema.SchemaError, RecursionError) as exc:
        raise _violation(f"Invalid contract: {exc}") from exc


def _validate_schema(data, schema, label):
    try:
        encoded = json.dumps(data, allow_nan=False)
        if len(encoded.encode("utf-8")) > MAX_MANIFEST_BYTES:
            raise ValueError("Manifest exceeds the 2 MiB limit")
        jsonschema.Draft7Validator(schema).validate(data)
    except (jsonschema.ValidationError, ValueError, TypeError, RecursionError) as exc:
        reason = (
            exc.message if isinstance(exc, jsonschema.ValidationError) else str(exc)
        )
        raise _violation(f"{label} validation failed: {reason}") from exc


class ManifestParser:
    """Parses raw manifest text or dict and validates against DAM v1 JSON Schema."""

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
        return self.validate_dict(strict_json(raw_json))

    def parse_file(self, file_path: str) -> AgentManifest:
        return self.parse_raw(_read_manifest(file_path))

    def validate_dict(self, data: Dict[str, Any]) -> AgentManifest:
        schema = self._load_schema()
        _validate_schema(data, schema, "Agent")
        for key in ("input_contract", "output_contract"):
            contract = data["capabilities"].get(key)
            if contract is not None:
                validate_contract_definition(contract)
        declared = data["requirements"]["providers"]
        ids = [p["id"] for p in declared]
        if len(ids) != len(set(ids)):
            raise _violation("Provider IDs must be unique")
        credential_ids = {p["id"] for p in declared if p["type"] == "credential"}
        for provider in declared:
            unknown = (
                set(provider.get("credential_bindings", {}).values()) - credential_ids
            )
            if unknown:
                raise _violation(
                    f"MCP credential bindings reference undeclared credentials: {sorted(unknown)}"
                )

        identity_data = data["identity"]
        identity = AgentIdentity(
            id=identity_data["id"],
            name=identity_data["name"],
            version=identity_data["version"],
            author=identity_data.get("author"),
            license=identity_data.get("license"),
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
            memory_policy=runtime_data.get("memory_policy", "NATIVE"),
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
                    agent_id=prov_data.get("agent_id"),
                    delegation_purpose=prov_data.get("delegation_purpose"),
                    image=prov_data.get("image"),
                    credential_bindings=prov_data.get("credential_bindings", {}),
                    agent_sha256=prov_data.get("agent_sha256"),
                )
            )

        swarm_topology = None
        if "swarm_topology" in data:
            st = data["swarm_topology"]
            swarm_topology = SwarmTopology(
                pattern=st.get("pattern", "hierarchical"),
            )

        observability = None
        if "observability" in data:
            obs = data["observability"]
            observability = ObservabilityProfile(
                cost_limit_usd=obs.get("cost_limit_usd"),
                max_execution_steps=obs.get("max_execution_steps"),
                max_model_calls=obs.get("max_model_calls"),
                max_output_tokens=obs.get("max_output_tokens"),
                input_price_per_million=obs.get("input_price_per_million"),
                output_price_per_million=obs.get("output_price_per_million"),
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
    """Parses a DWM v1 workflow manifest and validates against its schema."""

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
        return self.validate_dict(strict_json(raw_json))

    def parse_file(self, file_path: str) -> WorkflowManifest:
        return self.parse_raw(_read_manifest(file_path))

    def validate_dict(self, data: Dict[str, Any]) -> WorkflowManifest:
        schema = self._load_schema()
        _validate_schema(data, schema, "Workflow")
        identity_data = data["identity"]
        identity = WorkflowIdentity(
            id=identity_data["id"],
            name=identity_data["name"],
            version=identity_data["version"],
            author=identity_data.get("author"),
            license=identity_data.get("license"),
            description=identity_data.get("description"),
        )

        steps = [
            WorkflowStep(
                id=s["id"],
                agent_id=s["agent_id"],
                intent=s["intent"],
                depends_on=s.get("depends_on", []),
                agent_sha256=s.get("agent_sha256"),
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
        if "input" in ids:
            raise _violation(
                "Workflow step id 'input' is reserved for the root input placeholder"
            )
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
