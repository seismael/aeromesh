"""Small CLI user flows with isolated state and deterministic credential checks."""

import json

from aero.presentation.cli import main


def test_pm_init_command(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["init", "my-test-agent"]) == 0
    assert (tmp_path / "my-test-agent.agent.json").exists()


def test_pm_history_command():
    assert main(["history"]) == 0


def test_pm_vault_check_command(tmp_path, monkeypatch, capsys):
    source = tmp_path / "credentials.agent.json"
    assert main(["init", "credentials-agent", "--output", str(source)]) == 0
    data = json.loads(source.read_text())
    data["requirements"]["providers"] = [
        {"type": "credential", "id": "EXPLICIT_REPORT_KEY"}
    ]
    source.write_text(json.dumps(data))
    monkeypatch.delenv("EXPLICIT_REPORT_KEY", raising=False)
    assert main(["vault", "check", str(source)]) == 20
    monkeypatch.setenv("EXPLICIT_REPORT_KEY", "synthetic-report-key")
    assert main(["vault", "check", str(source)]) == 0
    captured = capsys.readouterr()
    assert "synthetic-report-key" not in captured.out + captured.err
