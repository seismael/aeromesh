"""Unit tests for OS-agnostic dual registry manifest path resolution."""

import os
import pytest
from aero.domain.paths import resolve_agent_manifest_path, get_aeromesh_workspace_registry_dir

def test_resolve_existing_direct_path():
    registry_dir = get_aeromesh_workspace_registry_dir()
    direct_file = registry_dir / "postgres-performance-tuner.json"
    resolved = resolve_agent_manifest_path(str(direct_file))
    assert resolved is not None
    assert resolved.exists()

def test_resolve_by_agent_id_from_workspace_registry():
    resolved = resolve_agent_manifest_path("postgres-performance-tuner")
    assert resolved is not None
    assert resolved.name == "postgres-performance-tuner.json"
    assert resolved.exists()

def test_resolve_security_auditor_by_id():
    resolved = resolve_agent_manifest_path("enterprise-security-auditor")
    assert resolved is not None
    assert resolved.name == "enterprise-security-auditor.json"
    assert resolved.exists()

def test_resolve_non_existent_returns_none():
    resolved = resolve_agent_manifest_path("completely-fake-agent-12345")
    assert resolved is None
