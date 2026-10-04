"""Installation and sharing require signed, explicitly approved artifacts."""

import json

import pytest

from aero.domain.paths import get_aeromesh_agents_dir
from aero.presentation.cli import main
from aero.services import trust

SAMPLE_MANIFEST = {
    "manifest_version": "0.2.0",
    "identity": {
        "id": "shared-test-agent",
        "name": "Shared Test Agent",
        "version": "1.0.0",
    },
    "capabilities": {
        "domain": "Sharing & Installing",
        "tags": ["share", "install"],
        "short_description": "Agent for testing install and share commands.",
        "evaluation_trigger": "Manual",
    },
    "cognitive_runtime": {
        "persona": "You are a test agent.",
        "success_criteria": "Explain the supplied information.",
    },
    "requirements": {"providers": []},
}


@pytest.fixture
def approved_manifest(tmp_path):
    path = tmp_path / "shared-agent.json"
    path.write_text(json.dumps(SAMPLE_MANIFEST))
    _, public = trust.generate_and_store_keypair()
    trust.sign_manifest_file(path)
    trust.trust_key("shared-test-agent", public)
    return path


def test_amx_install_and_run_from_local_store(
    approved_manifest, capsys, offline_runtime
):
    assert main(["install", str(approved_manifest)]) == 0
    installed = get_aeromesh_agents_dir() / "shared-test-agent.json"
    assert installed.exists()
    assert (
        trust.require_trusted_manifest(installed)["identity"]["id"]
        == "shared-test-agent"
    )
    assert (
        main(
            [
                "run",
                "shared-test-agent",
                "Test running from local store",
                "--non-interactive",
            ]
        )
        == 0
    )
    assert "deterministic response" in capsys.readouterr().out


def test_amx_share_command_requires_and_returns_verified_signature(
    approved_manifest, capsys
):
    assert main(["share", str(approved_manifest)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["identity"]["id"] == "shared-test-agent"
    assert payload["attestation"]["algorithm"] == "ed25519"
    assert payload["attestation"]["sha256"]


def test_amx_share_refuses_unsigned_artifact(tmp_path, capsys):
    path = tmp_path / "unsigned.json"
    path.write_text(json.dumps(SAMPLE_MANIFEST))
    assert main(["share", str(path)]) != 0
    assert "trusted public key" in capsys.readouterr().err
