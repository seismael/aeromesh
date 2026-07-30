"""Unit tests for OS-Agnostic Cross-Platform Path Resolution."""

import os
import shutil
import pytest
from pathlib import Path
from aero.domain.paths import (
    get_aeromesh_home,
    get_aeromesh_config_file,
    get_aeromesh_credentials_file,
    get_aeromesh_vfs_dir,
    get_aeromesh_logs_dir,
)

@pytest.fixture
def workspace_tmp_dir():
    scratch_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "scratch")
    )
    os.makedirs(scratch_dir, exist_ok=True)
    yield scratch_dir
    shutil.rmtree(scratch_dir, ignore_errors=True)

def test_aeromesh_home_custom_override(monkeypatch, workspace_tmp_dir):
    custom_dir = os.path.join(workspace_tmp_dir, "custom_aeromesh_home")
    monkeypatch.setenv("AEROMESH_HOME", custom_dir)
    
    path = get_aeromesh_home()
    assert str(path) == custom_dir
    assert get_aeromesh_config_file() == Path(custom_dir) / "config.json"
    assert get_aeromesh_credentials_file() == Path(custom_dir) / "credentials.json"
    assert get_aeromesh_vfs_dir() == Path(custom_dir) / "vfs"
    assert get_aeromesh_logs_dir() == Path(custom_dir) / "logs"

def test_aeromesh_home_default_resolution(monkeypatch):
    monkeypatch.delenv("AEROMESH_HOME", raising=False)
    path = get_aeromesh_home()
    assert isinstance(path, Path)
    assert len(str(path)) > 0
