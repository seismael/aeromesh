"""Preflight reports bounded local evidence and never invokes an LLM."""

import json
import pytest
from aero.services.preflight import preflight
from aero.domain.errors import AeroMeshDomainError


def data():
    return {
        "manifest_version": "1.0.0",
        "identity": {"id": "preflight", "name": "Preflight", "version": "1.0.0"},
        "capabilities": {
            "domain": "test",
            "tags": [],
            "short_description": "test",
            "evaluation_trigger": "manual",
        },
        "cognitive_runtime": {"persona": "Help", "success_criteria": "Answer"},
        "requirements": {"providers": []},
    }


def test_static_preflight_no_paid_calls(tmp_path, monkeypatch):
    path = tmp_path / "preflight.json"
    path.write_text(json.dumps(data()))
    monkeypatch.setenv("AEROMESH_MODEL", "openai:test-model")

    def forbidden(*a, **kw):
        raise AssertionError("No model calls permitted")

    monkeypatch.setattr("aero.services.deepagents_runner.resolve_model", forbidden)
    result = preflight(str(path), development=True)
    assert result["ready"] is True
    assert result["model_service_verified"] is False


def test_unsigned_preflight_refused(tmp_path):
    path = tmp_path / "preflight.json"
    path.write_text(json.dumps(data()))
    with pytest.raises(AeroMeshDomainError):
        preflight(str(path))


def test_no_ambient_secrets_in_preflight(tmp_path, monkeypatch):
    path = tmp_path / "preflight.json"
    path.write_text(json.dumps(data()))
    monkeypatch.setenv("AEROMESH_MODEL", "openai:test-model")
    monkeypatch.setenv("UNRELATED_SECRET", "secret-sentinel-do-not-disclose")
    assert "secret-sentinel-do-not-disclose" not in json.dumps(
        preflight(str(path), development=True)
    )
