"""Integration Test Suite: Production Readiness, Edge Cases, and Systemic Error Resilience."""

import pytest
import os
import json
import shutil
from pathlib import Path
from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.infrastructure.parser import ManifestParser
from aero.services.workflow import AeroWorkflowEngine
from aero.services.runner import AeroAgentRunnerService
from aero.infrastructure.vault import ZeroTrustVaultResolver
from aero.infrastructure.sandbox import NetworkSandboxFirewall

INVALID_JSON_MANIFEST = """{
  "manifest_version": "3.0.0",
  "identity": { "id": "broken-manifest", "name": "Broken"
}"""

INVALID_SCHEMA_MANIFEST = """{
  "manifest_version": "3.0.0",
  "identity": { "id": "invalid-schema-agent", "name": 12345 },
  "capabilities": { "domain": "Database Engineering" }
}"""

CYCLIC_WORKFLOW_JSON = """{
  "workflow_version": "1.0.0",
  "identity": { "id": "cyclic-wf", "name": "Cyclic Test Workflow" },
  "steps": [
    { "id": "step-a", "agent_id": "postgres-performance-tuner", "intent": "Step A", "depends_on": ["step-b"] },
    { "id": "step-b", "agent_id": "enterprise-security-auditor", "intent": "Step B", "depends_on": ["step-a"] }
  ]
}"""

def test_edge_case_1_malformed_json():
    parser = ManifestParser()
    with pytest.raises(AeroMeshDomainError) as exc_info:
        parser.parse_raw(INVALID_JSON_MANIFEST)
    assert exc_info.value.error_code == ErrorCode.AMX_ERR_SCHEMA_VIOLATION
    assert exc_info.value.exit_code == ExitCode.SCHEMA_VIOLATION

def test_edge_case_2_invalid_schema():
    parser = ManifestParser()
    with pytest.raises(AeroMeshDomainError) as exc_info:
        parser.parse_raw(INVALID_SCHEMA_MANIFEST)
    assert exc_info.value.error_code == ErrorCode.AMX_ERR_SCHEMA_VIOLATION

def test_edge_case_3_cyclic_workflow_dag_detection():
    tmp_dir = Path.cwd() / ".test_tmp_cyclic"
    tmp_dir.mkdir(exist_ok=True)
    try:
        wf_file = tmp_dir / "cyclic.workflow.json"
        wf_file.write_text(CYCLIC_WORKFLOW_JSON, encoding="utf-8")

        engine = AeroWorkflowEngine()
        with pytest.raises(AeroMeshDomainError) as exc_info:
            engine.validate_workflow_file(str(wf_file))
        assert "cyclic dependency" in str(exc_info.value).lower()
        assert exc_info.value.error_code == ErrorCode.AMX_ERR_SCHEMA_VIOLATION
    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)

def test_edge_case_4_missing_vault_credentials_non_interactive():
    runner = AeroAgentRunnerService()
    runner.vault.override_env.clear()
    
    with pytest.raises(AeroMeshDomainError) as exc_info:
        runner.run_manifest_file("registry/agents/postgres-performance-tuner.json", "Test query", non_interactive=True)
    assert exc_info.value.error_code == ErrorCode.AMX_ERR_VAULT_KEY_MISSING
    assert exc_info.value.exit_code == ExitCode.VAULT_KEY_MISSING

def test_edge_case_5_sandbox_domain_firewall_blocking():
    firewall = NetworkSandboxFirewall(allowed_domains=["api.github.com", "api.stripe.com"])
    
    assert firewall.is_domain_allowed("api.github.com") is True
    assert firewall.is_domain_allowed("api.stripe.com") is True
    assert firewall.is_domain_allowed("malicious-hacker-site.com") is False

def test_edge_case_6_non_existent_agent_manifest_resolution():
    runner = AeroAgentRunnerService()
    with pytest.raises(AeroMeshDomainError) as exc_info:
        runner.run_manifest_file("non-existent-agent-id-999.json", "Test", non_interactive=True)
    assert exc_info.value.error_code in (ErrorCode.AMX_ERR_DISCOVERY_NO_MATCH, ErrorCode.AMX_ERR_SCHEMA_VIOLATION)
