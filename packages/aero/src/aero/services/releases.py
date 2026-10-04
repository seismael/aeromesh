"""Signed, closed agent releases with independently approved operator policy.

A release embeds every referenced manifest, pins references bottom-up, and pins
all executable MCP images. It installs no code and executes no provider during
build or approval. Runtime consumers use the verified in-memory snapshot.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from types import SimpleNamespace

import jsonschema

from aero.domain import paths
from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.infrastructure.attestation import canonicalize, sha256_hex
from aero.infrastructure.parser import (
    ManifestParser,
    WorkflowParser,
    strict_json,
    _read_manifest,
    MAX_MANIFEST_BYTES,
)
from aero.infrastructure.tool_execution import validate_stdio_provider
from aero.services import trust
from aero.services.policy import check_policy, load_policy, requested_capabilities

_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_MAX_AGENTS = 256
_MAX_DEPTH = 64
_RECORD_SCHEMA = {
    "type": "object",
    "required": ["sha256", "manifest"],
    "additionalProperties": False,
    "properties": {
        "sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
        "manifest": {"type": "object"},
    },
}
_RELEASE_SCHEMA = {
    "type": "object",
    "required": ["release_version", "identity", "entry", "agents"],
    "additionalProperties": False,
    "properties": {
        "release_version": {"const": "1"},
        "identity": {"type": "object"},
        "entry": {
            "type": "object",
            "required": ["kind", "id", "sha256"],
            "additionalProperties": False,
            "properties": {
                "kind": {"enum": ["agent", "workflow"]},
                "id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9_-]*$"},
                "sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
            },
        },
        "agents": {
            "type": "object",
            "minProperties": 1,
            "maxProperties": _MAX_AGENTS,
            "additionalProperties": _RECORD_SCHEMA,
        },
        "workflow": _RECORD_SCHEMA,
    },
}


def _fail(message: str) -> None:
    raise AeroMeshDomainError(
        message, ErrorCode.AMX_ERR_SCHEMA_VIOLATION, ExitCode.SCHEMA_VIOLATION
    )


def _hash(data: dict[str, Any]) -> str:
    return sha256_hex(canonicalize(data))


def _read(path: str | Path) -> dict[str, Any]:
    try:
        data = strict_json(_read_manifest(str(path)))
    except (OSError, ValueError) as exc:
        _fail(f"Cannot read release input {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"Release input {path} must be a JSON object.")
    return data


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        _fail(
            f"Invalid release agent identifier: {value!r}; paths are not permitted in references."
        )
    return value


def _references(data: dict[str, Any], kind: str):
    if kind == "workflow":
        return data["steps"]
    return [p for p in data["requirements"]["providers"] if p["type"] == "sub_agent"]


def _production_capabilities(manifest: dict[str, Any]) -> None:
    providers = manifest["requirements"]["providers"]
    credentials = {p["id"] for p in providers if p["type"] == "credential"}
    for provider in providers:
        kind = provider["type"]
        if kind not in {"mcp", "credential", "sub_agent"}:
            _fail(f"Release v1 does not implement provider type {kind!r}.")
        if kind != "mcp":
            continue
        if provider.get("transport", "stdio") != "stdio" or provider.get("uri"):
            _fail("Production releases do not support remote MCP endpoints.")
        validate_stdio_provider(SimpleNamespace(**provider))
        if not provider.get("required_tools"):
            _fail(
                f"MCP provider {provider['id']!r} must explicitly enumerate required_tools."
            )
        if "*" in provider["required_tools"]:
            _fail(
                "Release required_tools must enumerate names; wildcard tools are not allowed."
            )
        for credential in provider.get("credential_bindings", {}).values():
            if credential not in credentials:
                _fail(
                    f"Credential binding {credential!r} must be declared in the same agent."
                )


def build_release(target_path: str | Path) -> dict[str, Any]:
    """Build a deterministic release from a draft agent or workflow.

    Sources need not be signed: the final release signature approves the exact
    complete closure. Existing dependency pins must match the source being read.
    References in the release copies are then pinned to the locked child copies.
    """
    target = Path(target_path).resolve()
    root = _read(target)
    root_kind = "workflow" if "workflow_version" in root else "agent"
    agents: dict[str, Any] = {}
    active: set[str] = set()
    sources: dict[str, str] = {}

    def visit(
        source: Path, expected_id: str | None = None, depth: int = 0
    ) -> dict[str, Any]:
        if depth > _MAX_DEPTH:
            _fail("Release dependency graph exceeds maximum depth.")
        raw = _read(source)
        ManifestParser().validate_dict(raw)
        _production_capabilities(raw)
        agent_id = _identifier(raw["identity"]["id"])
        if expected_id and expected_id != agent_id:
            _fail(
                f"Referenced agent {expected_id!r} resolved to identity {agent_id!r}."
            )
        if agent_id in active:
            _fail(f"Release dependency cycle at {agent_id!r}.")
        source_digest = _hash(raw)
        if agent_id in sources and sources[agent_id] != source_digest:
            _fail(f"Conflicting source manifests for agent {agent_id!r}.")
        sources[agent_id] = source_digest
        if agent_id in agents:
            return agents[agent_id]
        if len(sources) > _MAX_AGENTS:
            _fail("Release exceeds maximum agent count.")
        active.add(agent_id)
        locked = copy.deepcopy(raw)
        pin_references(locked, "agent", source.parent, depth)
        active.remove(agent_id)
        record = {"sha256": _hash(locked), "manifest": locked}
        agents[agent_id] = record
        return record

    def pin_references(
        data: dict[str, Any], kind: str, directory: Path, depth: int
    ) -> None:
        for reference in _references(data, kind):
            agent_id = _identifier(reference.get("agent_id"))
            sibling = directory / f"{agent_id}.json"
            resolved = (
                sibling
                if sibling.is_file()
                else paths.resolve_agent_manifest_path(agent_id)
            )
            if resolved is None:
                _fail(f"Referenced agent {agent_id!r} not found.")
            record = visit(Path(resolved), agent_id, depth + 1)
            expected = reference.get("agent_sha256")
            if expected and expected != sources[agent_id]:
                _fail(f"Source digest mismatch for referenced agent {agent_id!r}.")
            reference["agent_sha256"] = record["sha256"]

    if root_kind == "workflow":
        WorkflowParser().validate_dict(root)
        locked = copy.deepcopy(root)
        pin_references(locked, "workflow", target.parent, 0)
        entry_record = {"sha256": _hash(locked), "manifest": locked}
    else:
        entry_record = visit(target)
    release = {
        "release_version": "1",
        "identity": copy.deepcopy(root["identity"]),
        "entry": {
            "kind": root_kind,
            "id": root["identity"]["id"],
            "sha256": entry_record["sha256"],
        },
        "agents": {key: agents[key] for key in sorted(agents)},
    }
    if root_kind == "workflow":
        release["workflow"] = entry_record
    validate_release(release)
    return release


def validate_release(data: dict[str, Any]) -> dict[str, Any]:
    """Validate schemas, all hashes, dependency closure, pins and capabilities."""
    try:
        if len(canonicalize(data)) > MAX_MANIFEST_BYTES:
            _fail("Release exceeds the 2 MiB total content limit.")
        jsonschema.validate(data, _RELEASE_SCHEMA)
    except jsonschema.ValidationError as exc:
        _fail(f"Invalid release: {exc.message}")
    agents = data["agents"]
    for agent_id, record in agents.items():
        _identifier(agent_id)
        raw = record["manifest"]
        if _hash(raw) != record["sha256"]:
            _fail(f"Release agent {agent_id!r} digest mismatch.")
        ManifestParser().validate_dict(raw)
        if raw["identity"]["id"] != agent_id:
            _fail(f"Release agent {agent_id!r} identity mismatch.")
        _production_capabilities(raw)
    entry = data["entry"]
    if entry["kind"] == "workflow":
        record = data.get("workflow")
        if not record:
            _fail("Workflow release has no workflow manifest.")
        raw = record["manifest"]
        if _hash(raw) != record["sha256"]:
            _fail("Release workflow digest mismatch.")
        WorkflowParser().validate_dict(raw)
    else:
        if "workflow" in data:
            _fail("Agent release cannot contain a workflow.")
        record = agents.get(entry["id"])
        if not record:
            _fail("Release entry agent is missing.")
        raw = record["manifest"]
    if record["sha256"] != entry["sha256"]:
        _fail("Release entry digest mismatch.")
    if raw["identity"] != data["identity"] or raw["identity"]["id"] != entry["id"]:
        _fail("Release entry identity mismatch.")
    visited, active = set(), set()

    def walk(agent_id: str, depth: int) -> None:
        if depth > _MAX_DEPTH:
            _fail("Release dependency graph exceeds maximum depth.")
        if agent_id in active:
            _fail(f"Release dependency cycle at {agent_id!r}.")
        if agent_id in visited:
            return
        active.add(agent_id)
        check_refs(agents[agent_id]["manifest"], "agent", depth)
        active.remove(agent_id)
        visited.add(agent_id)

    def check_refs(manifest: dict[str, Any], kind: str, depth: int) -> None:
        for reference in _references(manifest, kind):
            agent_id = _identifier(reference.get("agent_id"))
            if agent_id not in agents:
                _fail(f"Release missing referenced agent {agent_id!r}.")
            if reference.get("agent_sha256") != agents[agent_id]["sha256"]:
                _fail(f"Release reference digest mismatch for {agent_id!r}.")
            walk(agent_id, depth + 1)

    if entry["kind"] == "agent":
        walk(entry["id"], 0)
    else:
        check_refs(raw, "workflow", 0)
    if visited != set(agents):
        _fail(
            f"Release contains unreachable agents: {', '.join(sorted(set(agents) - visited))}"
        )
    return data


def diff_releases(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Compare permissions and all manifest identities; never grant changes."""
    validate_release(old)
    validate_release(new)
    before, after = requested_capabilities(old), requested_capabilities(new)

    def difference(left, right):
        result = {
            key: sorted(set(left[key]) - set(right[key]))
            for key in left
            if key != "tools"
        }
        result["tools"] = {
            key: sorted(set(values) - set(right["tools"].get(key, [])))
            for key, values in left["tools"].items()
            if set(values) - set(right["tools"].get(key, []))
        }
        return result

    old_agents, new_agents = old["agents"], new["agents"]
    return {
        "old_sha256": _hash(old),
        "new_sha256": _hash(new),
        "entry_changed": old["entry"] != new["entry"],
        "added": difference(after, before),
        "removed": difference(before, after),
        "added_agents": sorted(set(new_agents) - set(old_agents)),
        "removed_agents": sorted(set(old_agents) - set(new_agents)),
        "changed_agents": sorted(
            key
            for key in set(old_agents) & set(new_agents)
            if old_agents[key]["sha256"] != new_agents[key]["sha256"]
        ),
    }


@dataclass(frozen=True)
class ApprovedRelease:
    digest: str
    entry_path: Path
    agent_paths: dict[str, Path]
    data: dict[str, Any]
    policy: dict[str, Any]

    @property
    def agent_data(self) -> dict[str, dict[str, Any]]:
        return {key: record["manifest"] for key, record in self.data["agents"].items()}

    @property
    def entry_data(self) -> dict[str, Any]:
        if self.data["entry"]["kind"] == "workflow":
            return self.data["workflow"]["manifest"]
        return self.data["agents"][self.data["entry"]["id"]]["manifest"]


def _release_dir(digest: str) -> Path:
    if not _DIGEST.fullmatch(digest):
        _fail("Invalid release digest.")
    directory = paths.get_aeromesh_home() / "releases" / digest
    # Local storage is an operator trust boundary; still reject obvious link
    # substitution so approval cannot write outside its designated store.
    if directory.is_symlink() or directory.parent.is_symlink():
        _fail("Release store may not be a symbolic link.")
    return directory


def approve_release(release_path: str | Path, policy_path: str | Path) -> str:
    """Explicitly approve a signed complete release against an operator policy."""
    data = trust.require_trusted_manifest(str(release_path))
    validate_release(data)
    policy_path = Path(policy_path).resolve()
    policy = load_policy(policy_path)
    check_policy(data, policy)
    digest = _hash(data)
    directory = _release_dir(digest)
    directory.mkdir(parents=True, exist_ok=True)
    agent_directory = directory / "agents"
    if agent_directory.is_symlink():
        _fail("Release agent snapshot directory may not be a symbolic link.")
    agent_directory.mkdir(exist_ok=True)
    # Approval is the commit marker and is written last. A failed partial write
    # remains unusable; every load checks all contents and the signature again.
    for agent_id, record in data["agents"].items():
        trust.atomic_write(
            agent_directory / f"{agent_id}.json", canonicalize(record["manifest"])
        )
    if data["entry"]["kind"] == "workflow":
        trust.atomic_write(
            directory / "workflow.json", canonicalize(data["workflow"]["manifest"])
        )
    trust.atomic_write(directory / "release.json", canonicalize(data))
    attestation = trust.load_attestation(str(release_path))
    trust.atomic_write(directory / "release.json.sig", canonicalize(attestation))
    trust.atomic_write(
        directory / "approval.json",
        canonicalize(
            {
                "approval_version": "1",
                "release_sha256": digest,
                "policy_path": str(policy_path),
                "policy_sha256": _hash(policy),
            }
        ),
    )
    # Detect source attestation changes during approval; no unverified snapshot
    # can be returned as successfully approved.
    load_approved_release(digest)
    return digest


def load_approved_release(path_or_digest: str | Path) -> ApprovedRelease:
    """Recheck release trust, revocation, operator policy and snapshot integrity."""
    value = str(path_or_digest)
    digest = value if _DIGEST.fullmatch(value) else _hash(_read(value))
    directory = _release_dir(digest)
    data = trust.require_trusted_manifest(str(directory / "release.json"))
    validate_release(data)
    if _hash(data) != digest:
        _fail("Approved release digest mismatch.")
    approval = _read(directory / "approval.json")
    if (
        set(approval)
        != {"approval_version", "release_sha256", "policy_path", "policy_sha256"}
        or approval.get("approval_version") != "1"
        or approval.get("release_sha256") != digest
    ):
        _fail("Invalid release approval record.")
    if (
        not isinstance(approval["policy_path"], str)
        or not Path(approval["policy_path"]).is_absolute()
    ):
        _fail("Invalid operator policy path in release approval.")
    policy = load_policy(approval["policy_path"])
    if _hash(policy) != approval["policy_sha256"]:
        _fail("Operator policy has changed; explicitly approve the release again.")
    check_policy(data, policy)
    agent_paths = {}
    for agent_id, record in data["agents"].items():
        snapshot = directory / "agents" / f"{agent_id}.json"
        if (
            snapshot.is_symlink()
            or snapshot.parent.is_symlink()
            or _hash(_read(snapshot)) != record["sha256"]
        ):
            _fail(f"Approved agent snapshot changed: {agent_id!r}.")
        agent_paths[agent_id] = snapshot
    if data["entry"]["kind"] == "workflow":
        entry_path = directory / "workflow.json"
        if (
            entry_path.is_symlink()
            or _hash(_read(entry_path)) != data["workflow"]["sha256"]
        ):
            _fail("Approved workflow snapshot changed.")
    else:
        entry_path = agent_paths[data["entry"]["id"]]
    return ApprovedRelease(digest, entry_path, agent_paths, data, policy)
