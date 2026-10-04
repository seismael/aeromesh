"""CLI tests for Ed25519 keygen/sign/verify and trusted install gating."""

import json
import pytest

from aero.presentation.cli import main
from aero.services import trust


def _write_manifest(path, agent_id="demo-agent"):
    data = {
        "manifest_version": "1.0.0",
        "identity": {"id": agent_id, "name": "Demo", "version": "1.0.0"},
        "capabilities": {
            "domain": "Demo",
            "tags": ["demo"],
            "short_description": "Demo agent",
            "evaluation_trigger": "Manual",
        },
        "cognitive_runtime": {"persona": "Assistant", "success_criteria": "Done"},
        "requirements": {"providers": []},
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_keygen_sign_verify_roundtrip_cli(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("AEROMESH_HOME", str(tmp_path))
    manifest = _write_manifest(tmp_path / "demo.json")

    assert main(["keygen"]) == 0
    assert main(["sign", str(manifest)]) == 0
    assert (tmp_path / "demo.json.sig").exists()
    # Signing is authorship, not authorization. Signature-only inspection is explicit.
    assert main(["verify", str(manifest)]) != 0
    assert main(["verify", str(manifest), "--signature-only"]) == 0
    assert main(["trust", "demo-agent", str(tmp_path / "keys" / "default.pub")]) == 0
    assert main(["verify", str(manifest)]) == 0
    assert "signature valid" in capsys.readouterr().out


def test_install_refuses_untrusted_agent(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("AEROMESH_HOME", str(tmp_path))
    manifest = _write_manifest(tmp_path / "demo.json", agent_id="demo-agent")

    _, pub_path = trust.generate_and_store_keypair("default")
    trust.trust_key("demo-agent", pub_path)

    exit_code = main(["install", str(manifest)])
    assert exit_code != 0
    assert "no attestation" in capsys.readouterr().err


def test_install_allows_verified_agent(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("AEROMESH_HOME", str(tmp_path))
    manifest = _write_manifest(tmp_path / "demo.json", agent_id="demo-agent")

    _, public_path = trust.generate_and_store_keypair("default")
    trust.sign_manifest_file(str(manifest))
    trust.trust_key("demo-agent", public_path)

    exit_code = main(["install", str(manifest)])
    assert exit_code == 0
    assert "Installed agent 'demo-agent'" in capsys.readouterr().out
