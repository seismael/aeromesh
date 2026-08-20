"""Tests for LLM-driven JIT agent manifest synthesis."""

import json

import pytest
from langchain_core.messages import AIMessage

from aero.services.synthesizer import JitSynthesizer, extract_json
from aero.domain.errors import AeroMeshDomainError, ErrorCode
from aero.domain.models import AgentManifest


VALID_MANIFEST = {
    "manifest_version": "0.1.0",
    "identity": {
        "id": "jit-anomaly-detector",
        "name": "Anomaly Detector",
        "version": "0.1.0",
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
    text = 'Here is the manifest:\n{"manifest_version": "0.1.0"}\nDone.'
    assert extract_json(text) == {"manifest_version": "0.1.0"}


def test_synthesize_via_llm_returns_valid_manifest():
    model = FakeModel([json.dumps(VALID_MANIFEST)])
    synth = JitSynthesizer(model=model)
    manifest = synth.synthesize("Build an anomaly detector for IoT sensors")
    assert isinstance(manifest, AgentManifest)
    assert manifest.identity.id == "jit-anomaly-detector"
    assert model.calls  # the model was actually invoked


def test_synthesize_falls_back_to_template_when_offline(monkeypatch):
    monkeypatch.setenv("AEROMESH_OFFLINE", "1")
    synth = JitSynthesizer()
    manifest = synth.synthesize("Build an anomaly detector")
    assert isinstance(manifest, AgentManifest)
    assert manifest.identity.id.startswith("jit-")


def test_synthesize_raises_after_persistent_invalid_output():
    model = FakeModel(["not json at all", "also not json", "still bad"])
    synth = JitSynthesizer(model=model)
    with pytest.raises(AeroMeshDomainError) as exc:
        synth.synthesize("Build an anomaly detector")
    assert exc.value.error_code == ErrorCode.AMX_ERR_JIT_BUILD_FAILED
