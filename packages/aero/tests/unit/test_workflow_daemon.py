"""Unit tests for amx workflow daemon and AeroWorkflowEngine.run_daemon_step."""

import pytest
from pathlib import Path
from aero.services.workflow import AeroWorkflowEngine
from aero.presentation.cli import main

def test_workflow_daemon_empty_schedules(monkeypatch, tmp_path):
    monkeypatch.setenv("AEROMESH_HOME", str(tmp_path))
    engine = AeroWorkflowEngine()
    res = engine.run_daemon_step()
    assert res["daemon_status"] == "IDLE"
    assert res["executed_count"] == 0

def test_cli_workflow_daemon(monkeypatch, tmp_path):
    monkeypatch.setenv("AEROMESH_HOME", str(tmp_path))
    exit_code = main(["workflow", "daemon"])
    assert exit_code == 0
