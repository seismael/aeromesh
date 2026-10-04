"""Target typos must never silently invoke synthesis or acquire capabilities."""

import json

import pytest

from aero.domain.errors import AeroMeshDomainError
from aero.infrastructure.parser import ManifestParser
from aero.services.orchestrator import AeroMasterOrchestrator

RAW = {
    "manifest_version": "1.0.0",
    "identity": {"id": "jit-test", "name": "JIT Test", "version": "1.0.0"},
    "capabilities": {
        "domain": "test",
        "tags": [],
        "short_description": "d",
        "evaluation_trigger": "e",
    },
    "cognitive_runtime": {"persona": "p", "success_criteria": "s"},
    "requirements": {"providers": []},
}


def test_dispatch_single_agent(tmp_path, monkeypatch):
    path = tmp_path / "agent.json"
    path.write_text(json.dumps(RAW))
    orchestrator = AeroMasterOrchestrator()
    calls = []
    monkeypatch.setattr(
        orchestrator.runner,
        "run_manifest_file",
        lambda *args, **kwargs: calls.append((args, kwargs)) or {},
    )
    assert (
        orchestrator.dispatch(str(path), intent="Analyze", development=True)["mode"]
        == "AGENT"
    )
    assert calls[0][1]["development"] is True


def test_dispatch_natural_language_jit(monkeypatch):
    manifest = ManifestParser().validate_dict(RAW)

    class Synthesizer:
        def synthesize(self, goal):
            return manifest

    orchestrator = AeroMasterOrchestrator(synthesizer=Synthesizer())
    monkeypatch.setattr(
        orchestrator.runner,
        "run_manifest_file",
        lambda *args, **kwargs: {"manifest": kwargs["manifest_object"]},
    )
    result = orchestrator.dispatch(
        "Answer a question", development=True, synthesize=True
    )
    assert result["mode"] == "JIT_AGENT"
    assert result["result"]["manifest"].identity.id == "jit-test"


def test_missing_target_never_synthesizes():
    class NeverSynthesize:
        def synthesize(self, goal):
            pytest.fail("A typo must not invoke the model")

    with pytest.raises(AeroMeshDomainError, match="not found"):
        AeroMasterOrchestrator(NeverSynthesize()).dispatch(
            "missing-agent.json", intent="run"
        )


def test_jit_requires_explicit_development_before_model_call():
    class NeverSynthesize:
        def synthesize(self, goal):
            pytest.fail("Unapproved synthesis must fail before a model call")

    with pytest.raises(AeroMeshDomainError, match="development"):
        AeroMasterOrchestrator(NeverSynthesize()).dispatch("Answer", synthesize=True)


def test_catalog_id_cannot_execute_a_different_signed_identity(tmp_path, monkeypatch):
    from aero.domain.paths import get_aeromesh_agents_dir
    from aero.infrastructure.attestation import generate_keypair, sign_manifest_dict
    from aero.services import trust

    raw = dict(RAW)
    raw["identity"] = {"id": "different-agent", "name": "Different", "version": "1.0.0"}
    directory = get_aeromesh_agents_dir()
    directory.mkdir(parents=True)
    path = directory / "requested-agent.json"
    path.write_text(json.dumps(raw))
    private, public = generate_keypair()
    key = tmp_path / "author.pub"
    key.write_bytes(public)
    path.with_suffix(".json.sig").write_text(
        json.dumps(sign_manifest_dict(raw, private))
    )
    trust.trust_key("different-agent", key)
    orchestrator = AeroMasterOrchestrator()
    monkeypatch.setattr(
        orchestrator.runner,
        "_execute",
        lambda *args, **kwargs: pytest.fail("Executed mismatched catalog identity"),
    )
    with pytest.raises(AeroMeshDomainError, match="identity"):
        orchestrator.dispatch("requested-agent", intent="Run")
