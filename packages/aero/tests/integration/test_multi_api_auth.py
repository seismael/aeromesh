"""Integration tests for Multi-API Authentication & Sandbox Firewalls (packages/aero)."""

import os
import pytest
from aero.presentation.cli import main

REGISTRY_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "registry", "agents")
)

def test_multicloud_devops_manifest_validation():
    manifest_path = os.path.join(REGISTRY_DIR, "multicloud-devops-orchestrator.json")
    assert main(["validate", manifest_path]) == 0

def test_fintech_payment_auditor_manifest_validation():
    manifest_path = os.path.join(REGISTRY_DIR, "fintech-payment-auditor.json")
    assert main(["validate", manifest_path]) == 0

def test_ai_rag_pipeline_architect_manifest_validation():
    manifest_path = os.path.join(REGISTRY_DIR, "ai-rag-pipeline-architect.json")
    assert main(["validate", manifest_path]) == 0

def test_multicloud_devops_execution_with_multi_credentials(monkeypatch, capsys):
    manifest_path = os.path.join(REGISTRY_DIR, "multicloud-devops-orchestrator.json")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    monkeypatch.setenv("KUBECONFIG_DATA", "apiVersion: v1...")

    exit_code = main(["run", manifest_path, "Deploy helm chart to AWS EKS", "--diagnostics", "--non-interactive"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "multicloud-devops-orchestrator" in captured.out
    assert "Total Spans: 5" in captured.out

def test_fintech_payment_auditor_execution_with_multi_credentials(monkeypatch, capsys):
    manifest_path = os.path.join(REGISTRY_DIR, "fintech-payment-auditor.json")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_51M0...")
    monkeypatch.setenv("PLAID_CLIENT_SECRET", "secret_plaid_key_123")

    exit_code = main(["run", manifest_path, "Audit Stripe payout and Plaid balances", "--diagnostics", "--non-interactive"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "fintech-payment-auditor" in captured.out

def test_ai_rag_pipeline_architect_execution_with_multi_credentials(monkeypatch, capsys):
    manifest_path = os.path.join(REGISTRY_DIR, "ai-rag-pipeline-architect.json")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-openai-key-123")
    monkeypatch.setenv("PINECONE_API_KEY", "pcsk_pinecone_key_456")

    exit_code = main(["run", manifest_path, "Index text into Pinecone DB", "--diagnostics", "--non-interactive"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "ai-rag-pipeline-architect" in captured.out
