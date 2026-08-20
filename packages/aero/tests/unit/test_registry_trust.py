"""End-to-end trust test over the committed registry (real signed artifacts).

These tests assert that every manifest shipped in ``registry/`` is actually
signed and trusted — no fakes, no mocks — and that workflows reference only
verified agents. If the registry ever falls out of sync with its signatures,
these fail.
"""

from aero.domain.paths import (
    get_aeromesh_workspace_registry_dir,
    get_aeromesh_workspace_workflows_dir,
)
from aero.infrastructure.parser import ManifestParser, WorkflowParser
from aero.services import trust


def test_registry_agents_are_signed_and_trusted():
    parser = ManifestParser()
    files = sorted(get_aeromesh_workspace_registry_dir().glob("*.json"))
    assert files, "expected agent manifests in registry/agents"
    for f in files:
        agent_id = parser.parse_file(str(f)).identity.id
        ok, reason = trust.verify_manifest_trusted_file(str(f), agent_id)
        assert ok, f"agent '{agent_id}' not trusted: {reason}"


def test_registry_workflows_are_signed_and_references_verified():
    parser = WorkflowParser()
    files = sorted(get_aeromesh_workspace_workflows_dir().glob("*.json"))
    assert files, "expected workflow manifests in registry/workflows"
    for f in files:
        workflow = parser.parse_file(str(f))
        ok, reason = trust.verify_manifest_trusted_file(str(f), workflow.identity.id)
        assert ok, f"workflow '{workflow.identity.id}' not trusted: {reason}"
        ok, reason = trust.verify_workflow_references(workflow)
        assert ok, f"workflow '{workflow.identity.id}' has unverified refs: {reason}"


def test_install_attestation_preserves_sidecar(tmp_path):
    src = tmp_path / "agent.json"
    src.write_text("{}", encoding="utf-8")
    (tmp_path / "agent.json.sig").write_text('{"x": 1}', encoding="utf-8")
    target = tmp_path / "installed.json"
    target.write_text("{}", encoding="utf-8")

    trust.install_attestation(str(src), str(target))

    sidecar = tmp_path / "installed.json.sig"
    assert sidecar.exists()
    assert sidecar.read_text(encoding="utf-8") == '{"x": 1}'
