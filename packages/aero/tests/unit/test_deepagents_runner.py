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


def test_manifest_to_deepagent_kwargs_includes_tools(monkeypatch):
    monkeypatch.setattr(deepagents_runner, "resolve_model", lambda creds=None: "fake-model")
    kwargs = deepagents_runner.manifest_to_deepagent_kwargs(_manifest(), tools=["tool-a"])
    assert kwargs["tools"] == ["tool-a"]


def test_mcp_connections_maps_stdio_provider():
    manifest = ManifestParser().validate_dict(
        {
            "manifest_version": "0.1.0",
            "identity": {"id": "mcp-demo", "name": "M", "version": "0.1.0"},
            "capabilities": {
                "domain": "M",
                "tags": ["m"],
                "short_description": "d",
                "evaluation_trigger": "e",
            },
            "cognitive_runtime": {"persona": "p", "success_criteria": "s"},
            "requirements": {
                "providers": [
                    {
                        "type": "mcp",
                        "id": "postgres-mcp",
                        "transport": "stdio",
                        "command": "npx",
                        "args": ["-y", "server"],
                        "required_tools": ["execute_query"],
                    }
                ]
            },
        }
    )
    conns = deepagents_runner.mcp_connections(
        manifest, credentials={"DB": "secret"}, proxy_env={"HTTP_PROXY": "http://p"}
    )
    assert conns["postgres-mcp"]["transport"] == "stdio"
    assert conns["postgres-mcp"]["command"] == "npx"
    assert conns["postgres-mcp"]["args"] == ["-y", "server"]
    assert conns["postgres-mcp"]["env"]["DB"] == "secret"
    assert conns["postgres-mcp"]["env"]["HTTP_PROXY"] == "http://p"


def test_required_tool_names():
    assert deepagents_runner._required_tool_names(_manifest()) == set()


def test_build_rubric_none_without_contract():
    assert deepagents_runner.build_rubric(_manifest()) is None


def test_build_rubric_with_contract():
    manifest = ManifestParser().validate_dict(
        {
            "manifest_version": "0.1.0",
            "identity": {"id": "contract", "name": "C", "version": "0.1.0"},
            "capabilities": {
                "domain": "C",
                "tags": ["c"],
                "short_description": "d",
                "evaluation_trigger": "e",
                "output_contract": {
                    "type": "object",
                    "required": ["result"],
                    "properties": {"result": {"type": "string"}},
                },
            },
            "cognitive_runtime": {"persona": "p", "success_criteria": "s"},
            "requirements": {"providers": []},
        }
    )
    rubric = deepagents_runner.build_rubric(manifest)
    assert "result" in rubric
    assert "JSON Schema" in rubric
