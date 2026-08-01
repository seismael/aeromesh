"""Unit tests for PM Usecase User Flows (init, history, vault check, workflow list)."""

import pytest
import shutil
from pathlib import Path
from aero.presentation.cli import main

def test_pm_init_command(monkeypatch):
    tmp_dir = Path.cwd() / ".test_tmp_init"
    tmp_dir.mkdir(exist_ok=True)
    try:
        monkeypatch.chdir(tmp_dir)
        exit_code = main(["init", "my-test-agent"])
        assert exit_code == 0
        assert (tmp_dir / "my-test-agent.agent.json").exists()
    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)

def test_pm_history_command():
    exit_code = main(["history"])
    assert exit_code == 0

def test_pm_workflow_list_command():
    exit_code = main(["workflow", "list"])
    assert exit_code == 0

def test_pm_vault_check_command():
    exit_code = main(["vault", "check", "registry/agents/postgres-performance-tuner.json"])
    # May fail if DB_CONNECT_STRING not in env, but exit code handled cleanly
    assert exit_code in (0, 20)
