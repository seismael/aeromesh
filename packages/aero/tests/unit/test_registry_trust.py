"""Shipped examples are drafts, and signer approval belongs to the consumer."""

import json
from pathlib import Path

import pytest

from aero.domain.errors import AeroMeshDomainError

from aero.domain.paths import (
    get_aeromesh_agents_dir,
    get_aeromesh_workspace_registry_dir,
    get_aeromesh_workspace_workflows_dir,
)
from aero.infrastructure.attestation import generate_keypair, sign_manifest_dict
from aero.infrastructure.parser import ManifestParser, WorkflowParser
from aero.services import trust


def test_registry_examples_are_valid_unsigned_drafts():
    groups = [
        (get_aeromesh_workspace_registry_dir(), ManifestParser()),
        (get_aeromesh_workspace_workflows_dir(), WorkflowParser()),
    ]
    for directory, parser in groups:
        files = sorted(directory.glob("*.json"))
        assert files, f"expected draft examples in {directory}"
        for path in files:
            artifact = parser.parse_file(str(path))
            assert trust.load_attestation(path) is None
            assert trust.trusted_public_key(artifact.identity.id) is None
            with pytest.raises(AeroMeshDomainError, match="trusted public key"):
                trust.require_trusted_manifest(path, artifact.identity.id)
    assert not list(get_aeromesh_workspace_registry_dir().parent.rglob("*.pub"))


def test_user_approved_workflow_and_references_verify(tmp_path):
    private, public = generate_keypair()
    public_path = tmp_path / "author.pub"
    public_path.write_bytes(public)
    drafts = list(get_aeromesh_workspace_registry_dir().glob("*.json"))
    assert drafts
    agent = ManifestParser().parse_file(str(drafts[0]))
    data = json.loads(drafts[0].read_text())
    installed = get_aeromesh_agents_dir() / f"{agent.identity.id}.json"
    installed.parent.mkdir(parents=True, exist_ok=True)
    installed.write_text(json.dumps(data))
    Path(str(installed) + ".sig").write_text(
        json.dumps(sign_manifest_dict(data, private))
    )
    trust.trust_key(agent.identity.id, public_path)

    workflow_data = {
        "workflow_version": "1.0.0",
        "identity": {
            "id": "locally-approved-workflow",
            "name": "Approved",
            "version": "1.0.0",
        },
        "steps": [{"id": "one", "agent_id": agent.identity.id, "intent": "Summarize"}],
    }
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(json.dumps(workflow_data))
    Path(str(workflow_path) + ".sig").write_text(
        json.dumps(sign_manifest_dict(workflow_data, private))
    )
    trust.trust_key("locally-approved-workflow", public_path)
    verified = trust.require_trusted_manifest(
        workflow_path, "locally-approved-workflow"
    )
    workflow = WorkflowParser().validate_dict(verified)
    ok, reason = trust.verify_workflow_references(workflow)
    assert ok, reason


def test_install_attestation_preserves_sidecar(tmp_path):
    src = tmp_path / "agent.json"
    src.write_text("{}", encoding="utf-8")
    (tmp_path / "agent.json.sig").write_text('{"x": 1}', encoding="utf-8")
    target = tmp_path / "installed.json"
    target.write_text("{}", encoding="utf-8")
    trust.install_attestation(str(src), str(target))
    sidecar = tmp_path / "installed.json.sig"
    assert sidecar.read_text(encoding="utf-8") == '{"x": 1}'
