"""Supported DAM 0.2 fields survive schema validation and model hydration."""

import pytest
from aero.infrastructure.parser import ManifestParser

FULL_MANIFEST_JSON = """{
  "manifest_version": "1.0.0",
  "identity": {
    "id": "full-test-agent",
    "name": "Full Test Agent Manifest",
    "version": "1.2.3",
    "author": "AeroMesh Core Team",
    "license": "Apache-2.0",
    "funding": {
      "url": "https://github.com/sponsors/aeromesh",
      "type": "github"
    }
  },
  "capabilities": {
    "domain": "Software Testing",
    "sub_domain": "TDD & Governance",
    "tags": ["testing", "tdd", "schema-validation"],
    "short_description": "Validates full DAM v1 schema field hydration.",
    "evaluation_trigger": "Use for verifying domain model completeness.",
    "input_contract": {
      "type": "object",
      "properties": {
        "query": { "type": "string" }
      }
    },
    "output_contract": {
      "type": "object",
      "properties": {
        "status": { "type": "string" }
      }
    }
  },
  "cognitive_runtime": {
    "driver": "Driver.LangGraph",
    "persona": "You are a Quality Assurance Specialist.",
    "success_criteria": "All schema properties must hydrate cleanly without loss.",
    "memory_policy": "NATIVE",
    "checkpoint_policy": "ON_STEP"
  },
  "requirements": {
    "providers": [
      {
        "type": "mcp",
        "id": "full-mcp-server",
        "transport": "stdio",
        "image": "example/git@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "args": ["--read-only"],
        "required_tools": ["git_status", "git_log"],
        "credential_bindings": {"GIT_TOKEN": "REPOSITORY_TOKEN"},
        "allowed_domains": []
      },
      {
        "type": "credential",
        "id": "REPOSITORY_TOKEN",
        "kind": "bearer_token"
      },
      {
        "type": "sub_agent",
        "id": "sub-agent-provider",
        "agent_id": "bounded-auditor",
        "agent_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "delegation_purpose": "Delegates security audit steps."
      }
    ]
  },
  "swarm_topology": {
    "pattern": "hierarchical"
  },
  "observability": {
    "cost_limit_usd": 5.0,
    "max_execution_steps": 20,
    "max_model_calls": 5,
    "max_output_tokens": 1024,
    "input_price_per_million": 1.5,
    "output_price_per_million": 6.0
  }
}"""


def test_supported_dam_manifest_hydration():
    parser = ManifestParser()
    manifest = parser.parse_raw(FULL_MANIFEST_JSON)

    assert manifest.identity.funding == {
        "url": "https://github.com/sponsors/aeromesh",
        "type": "github",
    }
    assert manifest.capabilities.sub_domain == "TDD & Governance"
    assert manifest.capabilities.input_contract == {
        "type": "object",
        "properties": {"query": {"type": "string"}},
    }
    assert manifest.capabilities.output_contract == {
        "type": "object",
        "properties": {"status": {"type": "string"}},
    }

    assert manifest.cognitive_runtime.checkpoint_policy == "ON_STEP"

    assert len(manifest.providers) == 3
    prov1 = manifest.providers[0]
    assert prov1.required_tools == ["git_status", "git_log"]
    assert prov1.image == "example/git@sha256:" + "a" * 64
    assert prov1.args == ["--read-only"]
    assert prov1.credential_bindings == {"GIT_TOKEN": "REPOSITORY_TOKEN"}
    assert prov1.allowed_domains == []

    credential = manifest.providers[1]
    assert credential.id == "REPOSITORY_TOKEN"
    assert credential.kind == "bearer_token"

    subagent = manifest.providers[2]
    assert subagent.agent_id == "bounded-auditor"
    assert subagent.agent_sha256 == "b" * 64
    assert subagent.delegation_purpose == "Delegates security audit steps."

    assert manifest.swarm_topology is not None
    assert manifest.swarm_topology.pattern == "hierarchical"

    assert manifest.observability is not None
    assert manifest.observability.cost_limit_usd == 5.0
    assert manifest.observability.max_execution_steps == 20
    assert manifest.observability.max_model_calls == 5
    assert manifest.observability.max_output_tokens == 1024
    assert manifest.observability.input_price_per_million == 1.5
    assert manifest.observability.output_price_per_million == 6.0
