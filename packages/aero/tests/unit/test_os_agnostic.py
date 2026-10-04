"""Unit tests for platform-aware application state paths."""

from pathlib import Path

import pytest

from aero.domain import paths


def test_aeromesh_home_custom_override(monkeypatch, tmp_path):
    custom_dir = tmp_path / "custom_aeromesh_home"
    monkeypatch.setenv("AEROMESH_HOME", str(custom_dir))

    assert paths.get_aeromesh_home() == custom_dir
    assert paths.get_aeromesh_agents_dir() == custom_dir / "agents"
    assert paths.get_aeromesh_workflows_dir() == custom_dir / "workflows"
    assert paths.get_aeromesh_trusted_dir() == custom_dir / "trusted"
    assert paths.get_aeromesh_revoked_dir() == custom_dir / "revoked"


@pytest.mark.parametrize(
    "platform, environment, relative_path",
    [
        ("win32", {"LOCALAPPDATA": "local-app-data"}, "local-app-data/AeroMesh"),
        ("win32", {"APPDATA": "app-data"}, "app-data/AeroMesh"),
        ("win32", {}, "home/.aeromesh"),
        ("darwin", {}, "home/Library/Application Support/AeroMesh"),
        ("linux", {"XDG_DATA_HOME": "xdg-data"}, "xdg-data/aeromesh"),
        ("linux", {}, "home/.local/share/aeromesh"),
    ],
)
def test_aeromesh_home_platform_resolution(monkeypatch, tmp_path, platform, environment, relative_path):
    monkeypatch.delenv("AEROMESH_HOME", raising=False)
    for variable in ("LOCALAPPDATA", "APPDATA", "XDG_DATA_HOME"):
        monkeypatch.delenv(variable, raising=False)
    for variable, value in environment.items():
        monkeypatch.setenv(variable, str(tmp_path / value))
    monkeypatch.setattr(paths.sys, "platform", platform)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    assert paths.get_aeromesh_home() == tmp_path / relative_path
