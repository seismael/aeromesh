"""A consumer authors, approves, executes and reviews a bounded local release.

Only the model is deterministic. CLI, signatures, approval, graph execution,
contracts, immutable snapshots and permission diffs run through production code.
"""

import json

import pytest

from aero.domain.paths import get_aeromesh_home
from aero.presentation.cli import main


def write(path, data):
    path.write_text(json.dumps(data))
    return path


@pytest.fixture
def approved_summary(tmp_path, capsys):
    data = {
        "manifest_version": "1.0.0",
        "identity": {"id": "team-summary", "name": "Team summary", "version": "1.0.0"},
        "capabilities": {
            "domain": "Summarization",
            "tags": [],
            "short_description": "Summarize supplied text",
            "evaluation_trigger": "Manual",
            "input_contract": {
                "type": "object",
                "required": ["text"],
                "properties": {"text": {"type": "string"}},
                "additionalProperties": False,
            },
            "output_contract": {
                "type": "object",
                "required": ["summary"],
                "properties": {"summary": {"type": "string"}},
                "additionalProperties": False,
            },
        },
        "cognitive_runtime": {
            "persona": "Summarize only the supplied text.",
            "success_criteria": "Return a short grounded summary.",
        },
        "requirements": {"providers": []},
    }
    source = write(tmp_path / "draft.json", data)
    release = tmp_path / "release.json"
    policy = write(
        tmp_path / "policy.json",
        {"policy_version": "1", "allowed_credentials": [], "providers": {}},
    )
    assert main(["validate", str(source)]) == 0
    capsys.readouterr()
    assert main(["keygen"]) == 0
    public = json.loads(capsys.readouterr().out)["public_key"]
    assert main(["release", "build", str(source), "--output", str(release)]) == 0
    assert main(["sign", str(release)]) == 0
    assert main(["trust", "team-summary", public]) == 0
    capsys.readouterr()
    assert main(["release", "approve", str(release), "--policy", str(policy)]) == 0
    digest = json.loads(capsys.readouterr().out)["approved_release"]
    return {
        "source": source,
        "data": data,
        "release": release,
        "policy": policy,
        "digest": digest,
    }


def count_model_calls(model, monkeypatch):
    calls = []
    original = type(model)._generate

    def generate(self, messages, *args, **kwargs):
        calls.append(messages)
        return original(self, messages, *args, **kwargs)

    monkeypatch.setattr(type(model), "_generate", generate)
    return calls


def test_approved_summary_enforces_input_and_output_contracts(
    approved_summary, offline_runtime, monkeypatch, capsys
):
    offline_runtime.response = '{"summary":"Two action items remain."}'
    calls = count_model_calls(offline_runtime, monkeypatch)
    digest = approved_summary["digest"]
    assert (
        main(
            [
                "release",
                "run",
                digest,
                '{"text":"Two action items remain from the meeting."}',
                "--input-json",
                "--json",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["execution_result"]["output_valid"] is True
    assert result["execution_result"]["execution_success"] is True
    assert result["receipt"]["task_assessment"] == "unverified"
    assert result["receipt"]["release_digest"] == digest
    successful_calls = len(calls)
    assert successful_calls > 0
    assert (
        main(
            [
                "release",
                "run",
                digest,
                '{"unexpected":"data"}',
                "--input-json",
                "--json",
            ]
        )
        != 0
    )
    assert len(calls) == successful_calls, (
        "Rejected input must not consume a model invocation"
    )
    assert "input" in capsys.readouterr().err.lower()


def test_modified_installed_snapshot_is_denied_before_model_use(
    approved_summary, offline_runtime, monkeypatch, capsys
):
    calls = count_model_calls(offline_runtime, monkeypatch)
    digest = approved_summary["digest"]
    snapshot = (
        get_aeromesh_home() / "releases" / digest / "agents" / "team-summary.json"
    )
    changed = json.loads(snapshot.read_text())
    changed["cognitive_runtime"]["persona"] = "Changed after approval"
    write(snapshot, changed)
    assert (
        main(
            [
                "release",
                "run",
                digest,
                '{"text":"Meeting notes"}',
                "--input-json",
                "--json",
            ]
        )
        != 0
    )
    assert calls == []
    assert "snapshot" in capsys.readouterr().err.lower()


def test_permission_diff_requires_new_operator_grants(
    approved_summary, tmp_path, capsys
):
    data = approved_summary["data"]
    data["identity"]["version"] = "1.1.0"
    image = "example/local-reader@sha256:" + "c" * 64
    data["requirements"]["providers"] = [
        {"type": "credential", "id": "REPORT_KEY"},
        {
            "type": "mcp",
            "id": "local-reader",
            "transport": "stdio",
            "image": image,
            "required_tools": ["read_report"],
            "credential_bindings": {"REPORT_TOKEN": "REPORT_KEY"},
        },
    ]
    write(approved_summary["source"], data)
    update = tmp_path / "updated-release.json"
    assert (
        main(
            [
                "release",
                "build",
                str(approved_summary["source"]),
                "--output",
                str(update),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert main(["release", "diff", str(approved_summary["release"]), str(update)]) == 0
    diff = json.loads(capsys.readouterr().out)
    assert diff["added"]["images"] == [image]
    assert diff["added"]["credentials"] == ["REPORT_KEY"]
    assert diff["added"]["tools"] == {"local-reader": ["read_report"]}
    assert diff["added"]["credential_bindings"] == [
        "local-reader:REPORT_TOKEN=REPORT_KEY"
    ]
    assert main(["sign", str(update)]) == 0
    capsys.readouterr()
    # The same locally trusted author still cannot grant new credentials or tools.
    assert (
        main(
            [
                "release",
                "approve",
                str(update),
                "--policy",
                str(approved_summary["policy"]),
            ]
        )
        == 21
    )
    assert "policy" in capsys.readouterr().err.lower()
