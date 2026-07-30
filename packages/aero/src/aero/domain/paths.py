"""Cross-Platform OS-Agnostic Path Resolution Module for AeroMesh."""

import os
import sys
from pathlib import Path

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
