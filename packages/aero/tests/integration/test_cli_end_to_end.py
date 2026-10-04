"""CLI contracts with real validation/state and an explicitly selected offline model."""

import json

import pytest

from aero import __version__
from aero.domain.errors import ExitCode
from aero.presentation.cli import main


@pytest.fixture
def manifest_file(tmp_path):
    data = {
        "manifest_version": "1.0.0",
        "identity": {
            "id": "integration-agent",
            "name": "CLI integration",
            "version": "1.0.0",
        },
        "capabilities": {
            "domain": "Test",
            "tags": [],
            "short_description": "CLI integration fixture",
            "evaluation_trigger": "manual",
        },
        "cognitive_runtime": {
            "persona": "Answer the supplied task.",
            "success_criteria": "Checked by external assertions.",
            "checkpoint_policy": "DISABLED",
        },
        "requirements": {"providers": []},
    }
    path = tmp_path / "agent.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_amx_version_command(capsys):
    assert main(["version"]) == 0
    assert f"aero / amx {__version__}" in capsys.readouterr().out


def test_amx_validate_command_success(manifest_file):
    assert main(["validate", str(manifest_file)]) == 0


def test_amx_validate_command_schema_error(manifest_file):
    data = json.loads(manifest_file.read_text())
    del data["manifest_version"]
    manifest_file.write_text(json.dumps(data))
    assert main(["validate", str(manifest_file)]) == ExitCode.SCHEMA_VIOLATION


def test_amx_explicit_development_execution(manifest_file, offline_runtime, capsys):
    assert (
        main(
            [
                "run",
                str(manifest_file),
                "Describe the result",
                "--development",
                "--non-interactive",
                "--json",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    execution = result["execution_result"]
    assert execution["execution_success"] is True
    assert execution["output"] == offline_runtime.response
    assert execution["success_criteria_met"] is None
    assert result["receipt"]["development"] is True


def test_amx_unsigned_execution_fails_closed(manifest_file):
    assert (
        main(["run", str(manifest_file), "Describe the result", "--non-interactive"])
        == ExitCode.TRUST_VIOLATION
    )


def test_amx_run_command_missing_vault_key_failure(manifest_file, monkeypatch):
    data = json.loads(manifest_file.read_text())
    data["requirements"]["providers"] = [
        {"type": "credential", "id": "TEST_INTEGRATION_CREDENTIAL"}
    ]
    manifest_file.write_text(json.dumps(data))
    monkeypatch.delenv("TEST_INTEGRATION_CREDENTIAL", raising=False)
    assert (
        main(
            [
                "run",
                str(manifest_file),
                "Describe the result",
                "--development",
                "--non-interactive",
            ]
        )
        == ExitCode.VAULT_KEY_MISSING
    )


@pytest.mark.parametrize('raw', ['{"amount":1,"amount":2}', '1e309'])
def test_structured_input_rejects_ambiguous_json_before_execution(raw, manifest_file, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Invalid structured input reached model resolution')
    monkeypatch.setattr('aero.services.deepagents_runner.resolve_model', forbidden)
    assert main([
        'run', str(manifest_file), raw, '--input-json', '--development', '--non-interactive'
    ]) == ExitCode.SCHEMA_VIOLATION
