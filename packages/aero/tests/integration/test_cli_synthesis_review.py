"""Explicit CLI synthesis authoring reaches the real draft execution path."""

import json

from aero.domain import paths
from aero.infrastructure.parser import ManifestParser
from aero.presentation.cli import main


def _draft():
    return {
        "manifest_version": "0.2.0",
        "identity": {"id": "reviewed-draft", "name": "Draft", "version": "1.0.0"},
        "capabilities": {
            "domain": "test",
            "tags": [],
            "short_description": "Test",
            "evaluation_trigger": "Manual",
        },
        "cognitive_runtime": {
            "persona": "Answer from provided information.",
            "success_criteria": "Summarize",
        },
        "requirements": {"providers": []},
    }


def test_cli_explicit_synthesis_uses_goal_without_fabricated_intent(
    monkeypatch, capsys, offline_runtime
):
    calls = []

    def synthesize(self, goal):
        calls.append(goal)
        return ManifestParser().validate_dict(_draft())

    monkeypatch.setattr(
        "aero.services.synthesizer.JitSynthesizer.synthesize", synthesize
    )
    assert (
        main(
            [
                "run",
                "Summarize supplied facts",
                "--synthesize",
                "--development",
                "--json",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert calls == ["Summarize supplied facts"]
    assert result["execution_result"]["execution_success"] is True
    assert result["receipt"]["development"] is True
    drafts = list((paths.get_aeromesh_home() / "drafts").glob("*.json"))
    assert len(drafts) == 1
    assert json.loads(drafts[0].read_text())["identity"]["id"] == "reviewed-draft"
    assert not paths.get_aeromesh_trusted_dir().exists()


def test_cli_synthesis_rejects_extra_intent_before_authoring(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(
        "aero.services.synthesizer.JitSynthesizer.synthesize",
        lambda self, goal: calls.append(goal),
    )
    assert (
        main(["run", "Goal", "Ambiguous extra intent", "--synthesize", "--development"])
        != 0
    )
    assert calls == []
    assert "without a separate intent" in capsys.readouterr().err


def test_cli_synthesis_requires_explicit_development_before_authoring(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "aero.services.synthesizer.JitSynthesizer.synthesize",
        lambda self, goal: calls.append(goal),
    )
    assert main(["run", "Goal", "--synthesize"]) != 0
    assert calls == []
