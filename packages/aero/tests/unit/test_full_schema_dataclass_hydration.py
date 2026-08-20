"""Unit tests verifying DAM v0.1 schema property hydration into domain models."""

import pytest
from aero.infrastructure.parser import ManifestParser

FULL_MANIFEST_JSON = """{
  "manifest_version": "0.1.0",
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
    "short_description": "Validates full DAM v0.1 schema field hydration.",
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
    "memory_policy": "CVM_LRU_PAGING",
    "checkpoint_policy": "ON_STEP"
  },
  "requirements": {
    "providers": [
      {
        "type": "mcp",
        "id": "full-mcp-server",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-git"],
        "required_tools": ["git_status", "git_log"],
        "fallback_action": "prompt_user",
        "isolation": "sandbox",
        "allowed_domains": ["github.com"]
      },
      {
        "type": "sub_agent",
        "id": "sub-agent-provider",
        "agent_id": "enterprise-security-auditor",
        "delegation_purpose": "Delegates security audit steps."
      }
    ]
  },
  "swarm_topology": {
    "pattern": "hierarchical",
    "consensus_threshold": 0.85,
    "routing_key": "audit.security"
  },
  "observability": {
    "trace_level": "info",
    "cost_limit_usd": 5.0,
    "max_execution_steps": 20
  }
}"""

def test_full_dam_v3_manifest_hydration():
    parser = ManifestParser()
    manifest = parser.parse_raw(FULL_MANIFEST_JSON)

    assert manifest.identity.funding == {"url": "https://github.com/sponsors/aeromesh", "type": "github"}
    assert manifest.capabilities.sub_domain == "TDD & Governance"
    assert manifest.capabilities.input_contract == {"type": "object", "properties": {"query": {"type": "string"}}}
    assert manifest.capabilities.output_contract == {"type": "object", "properties": {"status": {"type": "string"}}}

    assert manifest.cognitive_runtime.checkpoint_policy == "ON_STEP"

    assert len(manifest.providers) == 2
    prov1 = manifest.providers[0]
    assert prov1.required_tools == ["git_status", "git_log"]
    assert prov1.fallback_action == "prompt_user"
    assert prov1.isolation == "sandbox"

    prov2 = manifest.providers[1]
    assert prov2.agent_id == "enterprise-security-auditor"
    assert prov2.delegation_purpose == "Delegates security audit steps."

    assert manifest.swarm_topology is not None
    assert manifest.swarm_topology.pattern == "hierarchical"
    assert manifest.swarm_topology.consensus_threshold == 0.85
    assert manifest.swarm_topology.routing_key == "audit.security"

    assert manifest.observability is not None
    assert manifest.observability.trace_level == "info"
    assert manifest.observability.cost_limit_usd == 5.0
    assert manifest.observability.max_execution_steps == 20
