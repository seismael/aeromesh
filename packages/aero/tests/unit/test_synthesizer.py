"""Tests for LLM-driven JIT agent manifest synthesis."""

import json

import pytest
from langchain_core.messages import AIMessage

from aero.services.synthesizer import JitSynthesizer, extract_json
from aero.domain.errors import AeroMeshDomainError, ErrorCode
from aero.domain.models import AgentManifest


VALID_MANIFEST = {
    "manifest_version": "1.0.0",
    "identity": {
        "id": "jit-anomaly-detector",
        "name": "Anomaly Detector",
        "version": "1.0.0",
    },
    "capabilities": {
        "domain": "Time Series Monitoring",
        "tags": ["iot", "anomaly"],
        "short_description": "Detects anomalies in IoT sensor data",
        "evaluation_trigger": "Use when monitoring sensor data",
    },
    "cognitive_runtime": {
        "persona": "You are an IoT monitoring specialist.",
        "success_criteria": "Detect anomalies",
    },
    "requirements": {"providers": []},
}


class FakeModel:
    """Returns a fixed sequence of AIMessages (for the model.invoke interface)."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def invoke(self, messages, **kwargs):
        self.calls.append(messages)
        if self.responses:
            return AIMessage(content=self.responses.pop(0))
        return AIMessage(content="{}")


def test_extract_json_strips_code_fences():
    text = '```json\n{"a": 1}\n```'
    assert extract_json(text) == {"a": 1}


def test_extract_json_finds_object_embedded_in_text():
    text = 'Here is the manifest:\n{"manifest_version": "1.0.0"}\nDone.'
    assert extract_json(text) == {"manifest_version": "1.0.0"}


def test_synthesize_via_llm_returns_valid_manifest():
    model = FakeModel([json.dumps(VALID_MANIFEST)])
    synth = JitSynthesizer(model=model)
    manifest = synth.synthesize("Build an anomaly detector for IoT sensors")
    assert isinstance(manifest, AgentManifest)
    assert manifest.identity.id == "jit-anomaly-detector"
    assert model.calls  # the model was actually invoked


def test_synthesize_raises_without_key(monkeypatch):
    """No key -> JIT synthesis raises clearly (no synthetic/template fallback)."""
    import aero.services.deepagents_runner as dgr

    def raise_no_key(credentials=None):
        raise AeroMeshDomainError("no key", ErrorCode.AMX_ERR_VAULT_KEY_MISSING, 20)

    monkeypatch.setattr(dgr, "resolve_model", raise_no_key)
    synth = JitSynthesizer()
    with pytest.raises(AeroMeshDomainError) as exc:
        synth.synthesize("Build an anomaly detector")
    assert exc.value.error_code == ErrorCode.AMX_ERR_VAULT_KEY_MISSING


def test_synthesize_raises_after_persistent_invalid_output():
    model = FakeModel(["not json at all", "also not json", "still bad"])
    synth = JitSynthesizer(model=model)
    with pytest.raises(AeroMeshDomainError) as exc:
        synth.synthesize("Build an anomaly detector")
    assert exc.value.error_code == ErrorCode.AMX_ERR_JIT_BUILD_FAILED


def test_extract_json_handles_braces_and_escapes_in_strings():
    assert extract_json('prefix {"text": "a } and { and \\" quote"} suffix') == {
        "text": 'a } and { and " quote'
    }


def test_synthesis_cannot_add_executable_providers():
    import copy

    data = copy.deepcopy(VALID_MANIFEST)
    data["requirements"]["providers"] = [
        {"type": "mcp", "id": "shell", "transport": "stdio", "command": "sh"}
    ]
    with pytest.raises(AeroMeshDomainError):
        JitSynthesizer(model=FakeModel([json.dumps(data)])).synthesize(
            "do something", max_retries=1
        )


def test_successful_synthesis_is_persisted():
    from aero.domain.paths import get_aeromesh_home

    synth = JitSynthesizer(model=FakeModel([json.dumps(VALID_MANIFEST)]))
    synth.synthesize("answer a question")
    files = list((get_aeromesh_home() / "drafts").glob("*.json"))
    assert len(files) == 1
    assert json.loads(files[0].read_text())["identity"]["id"] == "jit-anomaly-detector"


def test_in_memory_serialization_rejects_unsupported_provider_behavior():
    from dataclasses import replace
    from aero.domain.models import CapabilityProviderRequirement
    from aero.infrastructure.parser import ManifestParser
    from aero.services.synthesizer import manifest_to_dict

    manifest = ManifestParser().validate_dict(VALID_MANIFEST)
    manifest = replace(
        manifest,
        providers=[
            CapabilityProviderRequirement(
                type="credential", id="token", command="unexpected"
            )
        ],
    )
    with pytest.raises(AeroMeshDomainError, match="Unsupported"):
        manifest_to_dict(manifest)
