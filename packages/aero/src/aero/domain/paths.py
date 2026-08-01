"""Cross-Platform OS-Agnostic Path Resolution Module for AeroMesh."""

import os
import sys
from pathlib import Path
from typing import Optional


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


def get_aeromesh_config_file() -> Path:
    return get_aeromesh_home() / "config.json"


def get_aeromesh_credentials_file() -> Path:
    return get_aeromesh_home() / "credentials.json"


def get_aeromesh_agents_dir() -> Path:
    return get_aeromesh_home() / "agents"


def get_aeromesh_vfs_dir() -> Path:
    return get_aeromesh_home() / "vfs"


def get_aeromesh_logs_dir() -> Path:
    return get_aeromesh_home() / "logs"


def get_aeromesh_workspace_registry_dir() -> Path:
    """Returns absolute path to workspace registry/agents directory."""
    curr = Path(__file__).resolve()
    for parent in [curr] + list(curr.parents):
        reg_dir = parent / "registry" / "agents"
        if reg_dir.exists() and reg_dir.is_dir():
            return reg_dir
    return Path(__file__).resolve().parents[4] / "registry" / "agents"


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

    target_name = target_str if target_str.endswith(".json") else f"{target_str}.json"

    local_store_path = get_aeromesh_agents_dir() / target_name
    if local_store_path.exists():
        return local_store_path

    registry_path = get_aeromesh_workspace_registry_dir() / target_name
    if registry_path.exists():
        return registry_path

    return None
