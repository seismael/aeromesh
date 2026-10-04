"""Manifest lookup tests use temporary registries and never depend on examples."""

import pytest

from aero.domain import paths


@pytest.fixture
def registry(tmp_path, monkeypatch):
    directory = tmp_path / "registry"
    directory.mkdir()
    for agent_id in ("first-agent", "second-agent"):
        (directory / f"{agent_id}.json").write_text("{}")
    monkeypatch.setattr(paths, "get_aeromesh_workspace_registry_dir", lambda: directory)
    return directory


def test_resolve_existing_direct_path(registry):
    direct = registry / "first-agent.json"
    assert paths.resolve_agent_manifest_path(str(direct)) == direct


def test_resolve_by_agent_id_from_workspace_registry(registry):
    assert (
        paths.resolve_agent_manifest_path("first-agent")
        == registry / "first-agent.json"
    )


def test_local_installed_agent_takes_priority(registry):
    directory = paths.get_aeromesh_agents_dir()
    directory.mkdir(parents=True)
    local = directory / "first-agent.json"
    local.write_text("{}")
    assert paths.resolve_agent_manifest_path("first-agent") == local


def test_resolve_nonexistent_returns_none(registry):
    assert paths.resolve_agent_manifest_path("completely-fake-agent-12345") is None


def test_registry_id_cannot_escape_store(registry):
    assert paths.resolve_agent_manifest_path("../not-a-registry-id") is None
