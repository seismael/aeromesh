"""Tests for AeroMasterOrchestrator (simplified two-mode dispatch)."""

import os

from aero.services.orchestrator import AeroMasterOrchestrator

REGISTRY_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "registry")
)


def test_dispatch_single_agent(monkeypatch):
    monkeypatch.setenv("DB_CONNECT_STRING", "postgresql://admin:secret@localhost:5432/db")
    agent_path = os.path.join(REGISTRY_DIR, "agents", "postgres-performance-tuner.json")

    res = AeroMasterOrchestrator().dispatch(
        agent_path, intent="Analyze query SELECT 1", non_interactive=True
    )
    assert res["mode"] == "AGENT"
    assert res["result"]["manifest"].identity.id == "postgres-performance-tuner"


def test_dispatch_natural_language_jit():
    from aero.domain.models import (
        AgentManifest,
        AgentIdentity,
        AgentCapabilities,
        CognitiveRuntimeProfile,
    )

    manifest = AgentManifest(
        manifest_version="0.1.0",
        identity=AgentIdentity(id="jit-test", name="JIT Test", version="0.1.0"),
        capabilities=AgentCapabilities(
            domain="test", tags=["test"], short_description="d", evaluation_trigger="e"
        ),
        cognitive_runtime=CognitiveRuntimeProfile(persona="p", success_criteria="s"),
        providers=[],
    )

    class FakeSynthesizer:
        def synthesize(self, goal, max_retries=3):
            return manifest

    res = AeroMasterOrchestrator(synthesizer=FakeSynthesizer()).dispatch(
        "Build a real-time anomaly detector for IoT sensors", non_interactive=True
    )
    assert res["mode"] == "JIT_AGENT"
    assert res["result"]["manifest"].identity.id == "jit-test"
