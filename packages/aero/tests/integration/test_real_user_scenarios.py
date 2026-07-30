"""Progressive Real User Simulation Test Suite (packages/aero)."""

import os
import pytest
from aero.presentation.cli import main

REGISTRY_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "registry", "agents")
)

# Stage 1: Manifest Schema Validation Scenarios
def test_stage_1_validate_postgres_tuner_manifest():
    manifest_path = os.path.join(REGISTRY_DIR, "postgres-performance-tuner.json")
    exit_code = main(["validate", manifest_path])
    assert exit_code == 0

def test_stage_1_validate_security_auditor_manifest():
    manifest_path = os.path.join(REGISTRY_DIR, "enterprise-security-auditor.json")
    exit_code = main(["validate", manifest_path])
    assert exit_code == 0

# Stage 2: Single-Purpose PostgreSQL Performance Tuner End-to-End Execution
def test_stage_2_run_postgres_performance_tuner_scenario(monkeypatch, capsys):
    manifest_path = os.path.join(REGISTRY_DIR, "postgres-performance-tuner.json")
    monkeypatch.setenv("DB_CONNECT_STRING", "postgresql://admin:secret@localhost:5432/orders_db")

    user_intent = "Analyze slow query SELECT * FROM orders WHERE status = 'pending' AND created_at > NOW() - INTERVAL '7 days'"
    exit_code = main(["run", manifest_path, user_intent, "--non-interactive"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "postgres-performance-tuner" in captured.out
    assert "Verified Execution Result" in captured.out

# Stage 3: Complex Multi-Agent Swarm Enterprise Security Auditor Execution
def test_stage_3_run_enterprise_security_auditor_scenario(monkeypatch, capsys):
    manifest_path = os.path.join(REGISTRY_DIR, "enterprise-security-auditor.json")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_mock_token_1234567890")

    user_intent = "Audit GitHub repository aeromesh/aero for exposed secrets and perform dependency CVE vulnerability scan"
    exit_code = main(["run", manifest_path, user_intent, "--non-interactive"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "enterprise-security-auditor" in captured.out
    assert "Verified Execution Result" in captured.out
