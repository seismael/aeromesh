"""Cross-Platform OS-Agnostic Path Resolution Module for AeroMesh."""

import os
import re
import sys
from pathlib import Path
from typing import Optional

from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode


def validate_artifact_id(value: str) -> str:
    """Registry identities and key names are identifiers, never filesystem paths."""
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,127}", value) is None
    ):
        raise AeroMeshDomainError(
            "Invalid artifact identifier; use 1–128 lowercase letters, digits, underscores or hyphens.",
            ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
            ExitCode.SCHEMA_VIOLATION,
        )
    return value


def confined_artifact_path(directory: Path, artifact_id: str, suffix: str) -> Path:
    """Reject path components and existing symlinks escaping the chosen store."""
    validate_artifact_id(artifact_id)
    target = directory / f"{artifact_id}{suffix}"
    if target.is_symlink() or not target.resolve().is_relative_to(directory.resolve()):
        raise AeroMeshDomainError(
            "Artifact path escapes its configured store.",
            ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
            ExitCode.SCHEMA_VIOLATION,
        )
    return target


def get_aeromesh_home() -> Path:
    """Returns cross-platform OS-agnostic AppData path for AeroMesh.

    Resolution Priority:
    1. AEROMESH_HOME environment variable (if set)
    2. Windows: %LOCALAPPDATA%\\AeroMesh (or %APPDATA%\\AeroMesh)
    3. macOS: ~/Library/Application Support/AeroMesh
    4. Linux / POSIX: $XDG_DATA_HOME/aeromesh (or ~/.local/share/aeromesh)
    5. Fallback: ~/.aeromesh
    """
    if "AEROMESH_HOME" in os.environ and os.environ["AEROMESH_HOME"].strip():
        return Path(os.environ["AEROMESH_HOME"])

    home = Path.home()

    if sys.platform == "win32":
        appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "AeroMesh"
        return home / ".aeromesh"
    elif sys.platform == "darwin":
        return home / "Library" / "Application Support" / "AeroMesh"
    else:
        # Linux / POSIX XDG standard
        xdg_data = os.environ.get("XDG_DATA_HOME")
        if xdg_data:
            return Path(xdg_data) / "aeromesh"
        return home / ".local" / "share" / "aeromesh"


def get_aeromesh_agents_dir() -> Path:
    return get_aeromesh_home() / "agents"


def get_aeromesh_workflows_dir() -> Path:
    return get_aeromesh_home() / "workflows"


def get_aeromesh_trusted_dir() -> Path:
    """Locally approved signer keys; registry contents never grant approval."""
    return get_aeromesh_home() / "trusted"


def get_aeromesh_revoked_dir() -> Path:
    return get_aeromesh_home() / "revoked"


def get_aeromesh_workspace_registry_dir() -> Path:
    """Returns absolute path to workspace registry/agents directory."""
    curr = Path(__file__).resolve()
    for parent in [curr] + list(curr.parents):
        reg_dir = parent / "registry" / "agents"
        if reg_dir.exists() and reg_dir.is_dir():
            return reg_dir
    return Path(__file__).resolve().parents[4] / "registry" / "agents"


def get_aeromesh_workspace_workflows_dir() -> Path:
    """Returns absolute path to workspace registry/workflows directory."""
    return get_aeromesh_workspace_registry_dir().parent / "workflows"


def resolve_agent_manifest_path(target_str: str) -> Optional[Path]:
    """Resolves target string to a manifest Path using OS-agnostic resolution priority:
    1. Direct absolute/relative file path
    2. User AppData store (~/.aeromesh/agents/<target>.json)
    3. Workspace repository registry (registry/agents/<target>.json)
    """
    if not target_str:
        return None

    path = Path(target_str)
    if path.exists() and path.is_file():
        return path

    artifact_id = target_str[:-5] if target_str.endswith(".json") else target_str
    try:
        local_store_path = confined_artifact_path(
            get_aeromesh_agents_dir(), artifact_id, ".json"
        )
        registry_path = confined_artifact_path(
            get_aeromesh_workspace_registry_dir(), artifact_id, ".json"
        )
    except AeroMeshDomainError:
        return None
    if local_store_path.exists():
        return local_store_path

    if registry_path.exists():
        return registry_path

    return None


def resolve_workflow_manifest_path(target_str: str) -> Optional[Path]:
    """Resolve a workflow target string to a manifest Path:
    1. Direct absolute/relative file path
    2. User AppData store (~/.aeromesh/workflows/<target>.json)
    3. Workspace registry (registry/workflows/<target>.json)
    """
    if not target_str:
        return None

    path = Path(target_str)
    if path.exists() and path.is_file():
        return path

    artifact_id = target_str[:-5] if target_str.endswith(".json") else target_str
    try:
        local_store_path = confined_artifact_path(
            get_aeromesh_workflows_dir(), artifact_id, ".json"
        )
        workspace_path = confined_artifact_path(
            get_aeromesh_workspace_workflows_dir(), artifact_id, ".json"
        )
    except AeroMeshDomainError:
        return None
    if local_store_path.exists():
        return local_store_path

    if workspace_path.exists():
        return workspace_path

    return None
