import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from aero.domain.errors import AeroMeshDomainError
from aero.services import workflow_synthesizer as module
from aero.infrastructure.attestation import canonicalize, sha256_hex

RAW = {
    "manifest_version": "1.0.0",
    "identity": {"id": "worker", "name": "Worker", "version": "1.0.0"},
    "capabilities": {
        "domain": "test",
        "tags": [],
        "short_description": "d",
        "evaluation_trigger": "e",
    },
    "cognitive_runtime": {"persona": "p", "success_criteria": "s"},
    "requirements": {"providers": []},
}


def setup(monkeypatch, agent_id="worker"):
    class Model:
        def invoke(self, messages):
            return AIMessage(
                content=json.dumps(
                    {
                        "workflow_version": "1.0.0",
                        "identity": {
                            "id": "pipeline",
                            "name": "Pipeline",
                            "version": "1.0.0",
                        },
                        "steps": [
                            {
                                "id": "first",
                                "agent_id": agent_id,
                                "intent": "answer {input}",
                            }
                        ],
                        "output": "first",
                    }
                )
            )

    discovery = SimpleNamespace(
        build_registry_index=lambda: [
            SimpleNamespace(
                id="worker",
                path="worker.json",
                name="Worker",
                domain="test",
                short_description="d",
                evaluation_trigger="e",
            )
        ]
    )
    monkeypatch.setattr(module.trust, "require_trusted_manifest", lambda *a, **k: RAW)
    return module.WorkflowSynthesizer(model=Model(), discovery=discovery)


def test_generated_workflow_references_are_pinned_to_verified_catalog(monkeypatch):
    synth = setup(monkeypatch)
    workflow = synth.synthesize("answer")
    assert workflow.steps[0].agent_sha256 == sha256_hex(canonicalize(RAW))
    assert synth.last_manifest_path.exists()


def test_model_cannot_invent_an_agent_outside_verified_catalog(monkeypatch):
    synth = setup(monkeypatch, "unknown")
    with pytest.raises(AeroMeshDomainError):
        synth.synthesize("answer", max_retries=1)
