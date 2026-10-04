"""User-visible authorization, syntax and failure contracts."""

import json

from aero.presentation.cli import main
from aero.domain.paths import get_aeromesh_agents_dir
from aero.services import trust


def manifest(tmp_path, name="cli-demo"):
    data = {
        "manifest_version": "0.2.0",
        "identity": {"id": name, "name": "Demo", "version": "1.0.0"},
        "capabilities": {
            "domain": "test",
            "tags": [],
            "short_description": "test",
            "evaluation_trigger": "manual",
        },
        "cognitive_runtime": {"persona": "Help", "success_criteria": "Answer"},
        "requirements": {"providers": []},
    }
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(data))
    return path


def test_unknown_unsigned_install_fails_closed(tmp_path):
    assert main(["install", str(manifest(tmp_path))]) != 0
    assert not (get_aeromesh_agents_dir() / "cli-demo.json").exists()


def test_explicit_trust_install_by_id_roundtrip(tmp_path, monkeypatch):
    path = manifest(tmp_path)
    _, pub = trust.generate_and_store_keypair()
    trust.sign_manifest_file(str(path))
    assert main(["trust", "cli-demo", str(pub)]) == 0
    assert main(["install", str(path)]) == 0
    assert main(["verify", str(get_aeromesh_agents_dir() / "cli-demo.json")]) == 0
    assert main(["install", "cli-demo"]) == 0


def test_development_install_does_not_grant_trust(tmp_path):
    path = manifest(tmp_path)
    assert main(["install", str(path), "--development"]) == 0
    assert main(["run", "cli-demo", "Answer"]) != 0


def test_missing_path_never_triggers_synthesis(monkeypatch):
    from aero.services.synthesizer import JitSynthesizer

    def forbidden(*args, **kwargs):
        raise AssertionError("Accidental synthesis")

    monkeypatch.setattr(JitSynthesizer, "synthesize", forbidden)
    assert main(["run", "misspelled-file.json", "Answer"]) != 0


def test_keygen_and_init_never_overwrite(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["init", "cli-demo"]) == 0
    original = (tmp_path / "cli-demo.agent.json").read_bytes()
    assert main(["init", "cli-demo"]) != 0
    assert (tmp_path / "cli-demo.agent.json").read_bytes() == original


def test_doctor_is_machine_readable_and_no_model_call(capsys):
    assert main(["doctor"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["version"] == "0.2.0"
    assert "provider_credentials" not in result
