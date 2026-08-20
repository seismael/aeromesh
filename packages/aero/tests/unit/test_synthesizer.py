"""Tests for LLM-driven JIT agent manifest synthesis."""

import json
import pytest

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


class FakeAdapter:
    """Fake provider adapter returning canned responses."""

    def __init__(self, responses, api_key="sk-real-key-123"):
        self.responses = list(responses)
        self.api_key = api_key
        self.calls = []

    def complete_prompt(self, system_prompt, user_prompt):
        self.calls.append(user_prompt)
        if self.responses:
            return self.responses.pop(0)
        return "{}"


def test_extract_json_strips_code_fences():
    text = '```json\n{"a": 1}\n```'
    assert extract_json(text) == {"a": 1}


def test_extract_json_finds_object_embedded_in_text():
    text = 'Here is the manifest:\n{"manifest_version": "0.1.0"}\nDone.'
    assert extract_json(text) == {"manifest_version": "0.1.0"}


def test_synthesize_via_llm_returns_valid_manifest():
    adapter = FakeAdapter([json.dumps(VALID_MANIFEST)])
    synth = JitSynthesizer(adapter=adapter)
    manifest = synth.synthesize("Build an anomaly detector for IoT sensors")
    assert isinstance(manifest, AgentManifest)
    assert manifest.identity.id == "jit-anomaly-detector"


def test_synthesize_falls_back_to_template_when_mock_key():
    adapter = FakeAdapter([], api_key="sk-mock-fallback-key")
    synth = JitSynthesizer(adapter=adapter)
    manifest = synth.synthesize("Build an anomaly detector")
    assert isinstance(manifest, AgentManifest)
    assert manifest.identity.id.startswith("jit-")
    assert adapter.calls == []  # LLM was never called


def test_synthesize_raises_after_persistent_invalid_output():
    adapter = FakeAdapter(["not json at all", "also not json", "still bad"])
    synth = JitSynthesizer(adapter=adapter)
    with pytest.raises(AeroMeshDomainError) as exc:
        synth.synthesize("Build an anomaly detector")
    assert exc.value.error_code == ErrorCode.AMX_ERR_JIT_BUILD_FAILED
