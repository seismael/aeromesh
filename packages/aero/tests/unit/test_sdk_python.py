"""SDK executes the real shared trust/policy services with explicit offline models."""

import json
import sys
from pathlib import Path

import pytest

sdk_path = Path(__file__).resolve().parents[4] / "packages" / "sdk-python" / "src"
if str(sdk_path) not in sys.path:
    sys.path.insert(0, str(sdk_path))

from aeromesh import AeroKernel
from aero.domain.errors import AeroMeshDomainError, ExitCode
from aero.domain.paths import get_aeromesh_agents_dir
from aero.infrastructure.attestation import generate_keypair, sign_manifest_dict
from aero.services import trust
from aero.services.releases import approve_release, build_release


def write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def agent(agent_id="sdk-agent"):
    return {
        "manifest_version": "0.2.0",
        "identity": {"id": agent_id, "name": agent_id, "version": "1.0.0"},
        "capabilities": {
            "domain": "Test",
            "tags": [],
            "short_description": "SDK fixture",
            "evaluation_trigger": "manual",
        },
        "cognitive_runtime": {
            "persona": "Answer the task.",
            "success_criteria": "Checked by external assertions.",
            "checkpoint_policy": "DISABLED",
        },
        "requirements": {"providers": []},
    }


def workflow(tmp_path):
    agents = get_aeromesh_agents_dir()
    agents.mkdir(parents=True, exist_ok=True)
    for name in ("sdk-a", "sdk-b"):
        write(agents / f"{name}.json", agent(name))
    return write(
        tmp_path / "workflow.json",
        {
            "workflow_version": "0.2.0",
            "identity": {
                "id": "sdk-workflow",
                "name": "SDK workflow",
                "version": "1.0.0",
            },
            "steps": [
                {
                    "id": "a",
                    "agent_id": "sdk-a",
                    "intent": "Answer the supplied input.",
                },
                {
                    "id": "b",
                    "agent_id": "sdk-b",
                    "intent": "Use the prior output: {a}",
                    "depends_on": ["a"],
                },
            ],
            "output": "b",
        },
    )


def approved_release(tmp_path, entry):
    release = build_release(entry)
    release_path = write(tmp_path / "release.json", release)
    private, public = generate_keypair()
    write(tmp_path / "release.json.sig", sign_manifest_dict(release, private))
    public_path = tmp_path / "author.pub"
    public_path.write_bytes(public)
    trust.trust_key(release["identity"]["id"], str(public_path))
    policy_path = write(
        tmp_path / "policy.json",
        {"policy_version": "1", "allowed_credentials": [], "providers": {}},
    )
    return approve_release(release_path, policy_path), policy_path


def test_sdk_agent_explicit_development(tmp_path, offline_runtime):
    path = write(tmp_path / "agent.json", agent())
    result = AeroKernel().run_agent(str(path), "Answer", development=True)
    assert result["mode"] == "AGENT"
    assert (
        result["result"]["execution_result"]["verified_result"]
        == offline_runtime.response
    )
    assert result["result"]["receipt"]["development"] is True


def test_sdk_workflow_explicit_development(tmp_path, offline_runtime):
    result = AeroKernel().run_workflow(
        str(workflow(tmp_path)), "Input", development=True
    )
    assert result["workflow_id"] == "sdk-workflow"
    assert result["result"]["outputs"] == {
        "a": offline_runtime.response,
        "b": offline_runtime.response,
    }


@pytest.mark.parametrize("kind", ["agent", "workflow"])
def test_sdk_unsigned_artifacts_fail_closed(tmp_path, kind):
    path = (
        write(tmp_path / "agent.json", agent())
        if kind == "agent"
        else workflow(tmp_path)
    )
    operation = AeroKernel().run_agent if kind == "agent" else AeroKernel().run_workflow
    with pytest.raises(AeroMeshDomainError) as error:
        operation(str(path), "Answer")
    assert error.value.exit_code == ExitCode.TRUST_VIOLATION


@pytest.mark.parametrize("kind", ["agent", "workflow"])
def test_sdk_missing_target_never_triggers_synthesis(tmp_path, monkeypatch, kind):
    from aero.services.synthesizer import JitSynthesizer
    from aero.services.workflow_synthesizer import WorkflowSynthesizer

    def forbidden(*args, **kwargs):
        pytest.fail("A missing path must not authorize synthesis")

    monkeypatch.setattr(JitSynthesizer, "synthesize", forbidden)
    monkeypatch.setattr(WorkflowSynthesizer, "synthesize", forbidden)
    operation = AeroKernel().run_agent if kind == "agent" else AeroKernel().run_workflow
    with pytest.raises(AeroMeshDomainError) as error:
        operation(str(tmp_path / "typo.json"), "Answer", development=True)
    assert error.value.exit_code == ExitCode.DISCOVERY_NO_MATCH


@pytest.mark.parametrize("kind", ["agent", "workflow"])
def test_sdk_approved_release_rechecks_policy_and_revocation(
    tmp_path, offline_runtime, kind
):
    entry = (
        write(tmp_path / "agent.json", agent())
        if kind == "agent"
        else workflow(tmp_path)
    )
    digest, policy_path = approved_release(tmp_path, entry)
    kernel = AeroKernel()
    result = kernel.run_release(digest, "Answer")
    if kind == "agent":
        assert result["receipt"]["release_digest"] == digest
        assert result["execution_result"]["verified_result"] == offline_runtime.response
    else:
        assert result["outputs"] == {
            "a": offline_runtime.response,
            "b": offline_runtime.response,
        }

    original_policy = policy_path.read_bytes()
    write(
        policy_path,
        {"policy_version": "1", "allowed_credentials": ["NEW_SECRET"], "providers": {}},
    )
    with pytest.raises(AeroMeshDomainError, match="policy.*changed"):
        kernel.run_release(digest, "Answer")
    policy_path.write_bytes(original_policy)
    identity = "sdk-agent" if kind == "agent" else "sdk-workflow"
    assert trust.revoke_key(identity)
    with pytest.raises(AeroMeshDomainError, match="REVOKED"):
        kernel.run_release(digest, "Answer")


def test_sdk_unapproved_release_fails_closed():
    with pytest.raises(AeroMeshDomainError):
        AeroKernel().run_release("a" * 64, "Answer")


@pytest.mark.parametrize("kind", ["agent", "workflow"])
@pytest.mark.parametrize("development", [False, True])
def test_sdk_catalog_ids_cannot_select_another_identity(
    tmp_path, monkeypatch, kind, development
):
    from aero.domain.paths import get_aeromesh_workflows_dir
    from aero.services.runner import AeroAgentRunnerService
    from aero.services.workflow_runner import WorkflowExecutionDriver

    data = (
        agent("different-agent")
        if kind == "agent"
        else json.loads(workflow(tmp_path).read_text())
    )
    directory = (
        get_aeromesh_agents_dir() if kind == "agent" else get_aeromesh_workflows_dir()
    )
    directory.mkdir(parents=True, exist_ok=True)
    path = write(directory / "requested-identity.json", data)
    private, public = generate_keypair()
    write(path.with_suffix(".json.sig"), sign_manifest_dict(data, private))
    public_path = tmp_path / "author.pub"
    public_path.write_bytes(public)
    trust.trust_key(data["identity"]["id"], public_path)

    def must_not_execute(*args, **kwargs):
        pytest.fail("Executed a catalog artifact with a different identity")

    monkeypatch.setattr(AeroAgentRunnerService, "_execute", must_not_execute)
    monkeypatch.setattr(WorkflowExecutionDriver, "execute", must_not_execute)
    operation = AeroKernel().run_agent if kind == "agent" else AeroKernel().run_workflow
    with pytest.raises(AeroMeshDomainError, match="identity"):
        operation("requested-identity", "Answer", development=development)


def test_sdk_signed_explicit_path_keeps_its_declared_identity(
    tmp_path, offline_runtime
):
    path = write(tmp_path / "arbitrary-filename.json", agent())
    private, public = generate_keypair()
    write(path.with_suffix(".json.sig"), sign_manifest_dict(agent(), private))
    public_path = tmp_path / "author.pub"
    public_path.write_bytes(public)
    trust.trust_key("sdk-agent", public_path)
    result = AeroKernel().run_agent(str(path), "Answer")
    assert result["result"]["manifest"].identity.id == "sdk-agent"
