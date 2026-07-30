"""Integration tests for Declarative Mesh Workflow Engine (DWM v1.0) & Crontab Scheduling."""

import os
import json
import pytest
from aero.presentation.cli import main
from aero.domain.paths import get_aeromesh_home

REGISTRY_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "registry", "agents")
)

SAMPLE_WORKFLOW = {
    "workflow_version": "1.0.0",
    "identity": {
        "id": "daily-executive-email-summary",
        "name": "Daily Executive Email Summary & Security Audit",
        "description": "Fetch emails, analyze database queries, and audit security secrets.",
        "schedule": "0 8 * * 1-5"
    },
    "steps": [
        {
          "id": "step-1-tune-queries",
          "agent_id": "postgres-performance-tuner",
          "intent": "Analyze slow SQL query SELECT * FROM users"
        },
        {
          "id": "step-2-audit-secrets",
          "agent_id": "enterprise-security-auditor",
          "intent": "Audit repository secrets",
          "depends_on": ["step-1-tune-queries"]
        }
    ]
}

@pytest.fixture
def workspace_scratch_dir():
    scratch_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "scratch")
    )
    os.makedirs(scratch_dir, exist_ok=True)
    yield scratch_dir

def test_workflow_execution_and_crontab_scheduling(workspace_scratch_dir, monkeypatch, capsys):
    monkeypatch.setenv("AEROMESH_HOME", workspace_scratch_dir)
    monkeypatch.setenv("DB_CONNECT_STRING", "postgresql://admin:secret@localhost:5432/db")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_mock_token_123")

    workflow_file = os.path.join(workspace_scratch_dir, "daily_summary_workflow.json")
    with open(workflow_file, "w", encoding="utf-8") as f:
        json.dump(SAMPLE_WORKFLOW, f, indent=2)

    # 1. Test amx workflow run
    exit_code_run = main(["workflow", "run", workflow_file, "--non-interactive", "--diagnostics"])
    assert exit_code_run == 0
    captured_run = capsys.readouterr()
    assert "Executed Workflow 'Daily Executive Email Summary & Security Audit'" in captured_run.out
    assert "Step 'step-1-tune-queries'" in captured_run.out
    assert "Step 'step-2-audit-secrets'" in captured_run.out

    # 2. Test amx workflow schedule
    exit_code_sched = main(["workflow", "schedule", workflow_file])
    assert exit_code_sched == 0
    captured_sched = capsys.readouterr()
    assert "Scheduled Workflow 'daily-executive-email-summary'" in captured_sched.out

    schedules_file = get_aeromesh_home() / "schedules.json"
    assert schedules_file.exists()
    with open(schedules_file, "r", encoding="utf-8") as f_sched:
        sched_data = json.load(f_sched)
    assert "daily-executive-email-summary" in sched_data
    assert sched_data["daily-executive-email-summary"]["schedule"] == "0 8 * * 1-5"
