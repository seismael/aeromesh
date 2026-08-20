"""Tests for the DAM -> Deep Agents compiler (deepagents_runner)."""

import pytest

from aero.infrastructure.parser import ManifestParser
from aero.services import deepagents_runner


def _manifest():
    return ManifestParser().validate_dict(
        {
            "manifest_version": "0.1.0",
            "identity": {"id": "swarm-demo", "name": "Swarm Demo", "version": "0.1.0"},
            "capabilities": {
                "domain": "General",
                "tags": ["demo"],
                "short_description": "demo",
                "evaluation_trigger": "test",
            },
            "cognitive_runtime": {
                "persona": "You are a helpful orchestrator.",
                "success_criteria": "reply",
            },
            "requirements": {
                "providers": [
                    {
                        "type": "sub_agent",
                        "id": "dep-scanner",
                        "agent_id": "dependency-vulnerability-scanner",
                        "delegation_purpose": "Scan dependencies for CVEs",
                    },
                    {"type": "skill", "id": "python-testing"},
                ]
            },
        }
    )


def test_extract_subagents_maps_providers():
    subagents = deepagents_runner.extract_subagents(_manifest())
    assert subagents == [
        {
            "name": "dependency-vulnerability-scanner",
            "description": "Scan dependencies for CVEs",
            "system_prompt": "You are a specialized sub-agent. Purpose: Scan dependencies for CVEs.",
        }
    ]


def test_extract_skills_maps_providers():
    skills = deepagents_runner.extract_skills(_manifest())
    assert skills == ["python-testing"]


def test_manifest_to_deepagent_kwargs(monkeypatch):
    monkeypatch.setattr(deepagents_runner, "resolve_model", lambda creds=None: "fake-model")
    kwargs = deepagents_runner.manifest_to_deepagent_kwargs(_manifest())
    assert kwargs["name"] == "Swarm Demo"
    assert kwargs["system_prompt"] == "You are a helpful orchestrator."
    assert kwargs["model"] == "fake-model"
    assert kwargs["subagents"][0]["name"] == "dependency-vulnerability-scanner"
    assert kwargs["skills"] == ["python-testing"]


def test_resolve_model_offline_returns_offline_model(monkeypatch):
    monkeypatch.setenv("AEROMESH_OFFLINE", "1")
    model = deepagents_runner.resolve_model()
    assert type(model).__name__ == "OfflineChatModel"
