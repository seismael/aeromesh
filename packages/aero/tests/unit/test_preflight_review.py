"""Cross-component preflight must verify the entire graph before side effects."""

import json

import pytest

from aero.domain import paths
from aero.domain.errors import AeroMeshDomainError
from aero.infrastructure.attestation import (
    canonicalize,
    generate_keypair,
    sha256_hex,
    sign_manifest_dict,
)
from aero.services.preflight import preflight
from aero.services.trust import revoke_key


def _agent(identity, providers=None):
    return {
        "manifest_version": "1.0.0",
        "identity": {"id": identity, "name": identity, "version": "1.0.0"},
        "capabilities": {
            "domain": "test",
            "tags": [],
            "short_description": "Test",
            "evaluation_trigger": "Manual",
        },
        "cognitive_runtime": {
            "persona": "Answer from provided evidence",
            "success_criteria": "Answer",
        },
        "requirements": {"providers": providers or []},
    }


def _install(raw, *, signed=True):
    directory = paths.get_aeromesh_agents_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (raw["identity"]["id"] + ".json")
    path.write_text(json.dumps(raw))
    if signed:
        private, public = generate_keypair()
        path.with_suffix(".json.sig").write_text(
            json.dumps(sign_manifest_dict(raw, private))
        )
        trusted = paths.get_aeromesh_trusted_dir()
        trusted.mkdir(parents=True, exist_ok=True)
        (trusted / (raw["identity"]["id"] + ".pub")).write_bytes(public)
    return path


def _ref(raw):
    return {
        "type": "sub_agent",
        "id": "delegate-" + raw["identity"]["id"],
        "agent_id": raw["identity"]["id"],
        "agent_sha256": sha256_hex(canonicalize(raw)),
    }


def _no_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid graph reached model, credential, or tool initialization")

    monkeypatch.setattr(
        "aero.infrastructure.vault.ZeroTrustVaultResolver.resolve_requirements",
        forbidden,
    )
    monkeypatch.setattr("aero.services.deepagents_runner.resolve_model", forbidden)
    monkeypatch.setattr("aero.services.deepagents_runner.build_mcp_tools", forbidden)
    monkeypatch.setenv("AEROMESH_MODEL", "openai:unused")


@pytest.mark.parametrize(
    "defect", ["missing", "unsigned", "revoked", "changed", "unpinned"]
)
def test_preflight_rejects_invalid_transitive_agent_before_effects(monkeypatch, defect):
    leaf = _agent("leaf")
    if defect != "missing":
        _install(leaf, signed=defect != "unsigned")
    reference = _ref(leaf)
    if defect == "revoked":
        assert revoke_key("leaf")
    if defect == "changed":
        reference["agent_sha256"] = "f" * 64
    if defect == "unpinned":
        del reference["agent_sha256"]
    middle = _agent("middle", [reference])
    _install(middle)
    root_path = _install(_agent("root", [_ref(middle)]))
    _no_effects(monkeypatch)
    with pytest.raises(AeroMeshDomainError):
        preflight(str(root_path), probe_tools=True)


def test_preflight_inspects_transitive_workflow_agent(monkeypatch):
    missing = _agent("missing")
    root = _agent("root", [_ref(missing)])
    _install(root)
    workflow = {
        "workflow_version": "1.0.0",
        "identity": {"id": "workflow", "name": "Workflow", "version": "1.0.0"},
        "steps": [
            {
                "id": "step",
                "agent_id": "root",
                "agent_sha256": sha256_hex(canonicalize(root)),
                "intent": "Do work",
            }
        ],
    }
    path = _install(workflow)
    _no_effects(monkeypatch)
    with pytest.raises(AeroMeshDomainError, match="Missing referenced agent"):
        preflight(str(path))


def test_preflight_reports_complete_valid_closure_without_model_calls(monkeypatch):
    leaf = _agent("leaf")
    _install(leaf)
    middle = _agent("middle", [_ref(leaf)])
    _install(middle)
    root = _install(_agent("root", [_ref(middle)]))
    monkeypatch.setenv("AEROMESH_MODEL", "openai:unused")
    monkeypatch.setattr(
        "aero.services.deepagents_runner.resolve_model",
        lambda *args, **kwargs: pytest.fail("Preflight invoked model"),
    )
    report = preflight(str(root))
    assert report["ready"] is True
    assert {item["agent_id"] for item in report["agents"]} == {"root", "middle", "leaf"}
    assert report["model_service_verified"] is False


def test_development_preflight_rejects_cycles(monkeypatch):
    first = _agent(
        "first", [{"type": "sub_agent", "id": "second", "agent_id": "second"}]
    )
    second = _agent(
        "second", [{"type": "sub_agent", "id": "first", "agent_id": "first"}]
    )
    path = _install(first, signed=False)
    _install(second, signed=False)
    _no_effects(monkeypatch)
    with pytest.raises(AeroMeshDomainError, match="cycle"):
        preflight(str(path), development=True)


@pytest.mark.parametrize(
    "model", ["model-without-provider", ":model", "openai:", " :model", "openai: "]
)
def test_preflight_rejects_malformed_model_before_credentials_or_tools(
    monkeypatch, model
):
    target = _install(_agent("root"))
    _no_effects(monkeypatch)
    monkeypatch.setenv("AEROMESH_MODEL", model)
    with pytest.raises(AeroMeshDomainError, match="provider:model"):
        preflight(str(target), probe_tools=True)


@pytest.mark.parametrize("development", [False, True])
def test_preflight_rejects_catalog_identity_mismatch_before_effects(monkeypatch, development):
    wrong = _install(_agent("different-agent"))
    monkeypatch.setattr(paths, "resolve_agent_manifest_path", lambda target: wrong)
    _no_effects(monkeypatch)
    with pytest.raises(AeroMeshDomainError, match="different artifact identity"):
        preflight("requested-agent", development=development, probe_tools=True)
