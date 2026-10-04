"""Approved releases freeze executable inputs and fail closed after changes."""

import copy
import json

import pytest

from aero.domain import paths
from aero.domain.errors import AeroMeshDomainError
from aero.infrastructure.attestation import (
    canonicalize,
    generate_keypair,
    sha256_hex,
    sign_manifest_dict,
)
from aero.services.policy import check_policy, requested_capabilities
from aero.services.releases import (
    approve_release,
    build_release,
    diff_releases,
    load_approved_release,
    validate_release,
)


IMAGE = "example/scanner@sha256:" + "a" * 64


def agent(agent_id="root", providers=None):
    return {
        "manifest_version": "1.0.0",
        "identity": {"id": agent_id, "name": agent_id, "version": "1.0.0"},
        "capabilities": {
            "domain": "testing",
            "tags": [],
            "short_description": "Test",
            "evaluation_trigger": "Test",
        },
        "cognitive_runtime": {"persona": "Test", "success_criteria": "Return a result"},
        "requirements": {"providers": providers or []},
    }


def write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def policy(**kwargs):
    return {"policy_version": "1", "allowed_credentials": [], "providers": {}, **kwargs}


def signed_release(tmp_path, data):
    private, public = generate_keypair()
    release_path = write(tmp_path / "release.json", data)
    write(tmp_path / "release.json.sig", sign_manifest_dict(data, private))
    trusted = paths.get_aeromesh_home() / "trusted"
    trusted.mkdir(parents=True, exist_ok=True)
    (trusted / (data["identity"]["id"] + ".pub")).write_bytes(public)
    return release_path


def test_release_is_deterministic_and_has_closed_pinned_graph(tmp_path):
    write(tmp_path / "child.json", agent("child"))
    target = write(
        tmp_path / "root.json",
        agent(providers=[{"id": "delegate", "type": "sub_agent", "agent_id": "child"}]),
    )
    release = build_release(target)
    assert release == build_release(target)
    assert set(release["agents"]) == {"root", "child"}
    parent = release["agents"]["root"]["manifest"]
    assert (
        parent["requirements"]["providers"][0]["agent_sha256"]
        == release["agents"]["child"]["sha256"]
    )
    assert (
        "agent_sha256"
        not in json.loads(target.read_text())["requirements"]["providers"][0]
    )
    validate_release(release)


def test_release_rejects_cycles_and_path_references(tmp_path):
    a = agent("a", [{"type": "sub_agent", "id": "b", "agent_id": "b"}])
    b = agent("b", [{"type": "sub_agent", "id": "a", "agent_id": "a"}])
    write(tmp_path / "b.json", b)
    target = write(tmp_path / "a.json", a)
    with pytest.raises(AeroMeshDomainError, match="cycle"):
        build_release(target)
    a["requirements"]["providers"][0]["agent_id"] = "../b"
    write(target, a)
    with pytest.raises(AeroMeshDomainError):
        build_release(target)


def test_release_rejects_source_hash_mismatch(tmp_path):
    write(tmp_path / "child.json", agent("child"))
    target = write(
        tmp_path / "root.json",
        agent(
            providers=[
                {
                    "type": "sub_agent",
                    "id": "child",
                    "agent_id": "child",
                    "agent_sha256": "f" * 64,
                }
            ]
        ),
    )
    with pytest.raises(AeroMeshDomainError, match="digest"):
        build_release(target)


def test_release_detects_tampering_and_unreachable_agents(tmp_path):
    target = write(tmp_path / "root.json", agent())
    release = build_release(target)
    modified = copy.deepcopy(release)
    modified["agents"]["root"]["manifest"]["cognitive_runtime"]["persona"] = "Changed"
    with pytest.raises(AeroMeshDomainError, match="digest"):
        validate_release(modified)
    child = agent("extra")
    release["agents"]["extra"] = {
        "manifest": child,
        "sha256": sha256_hex(canonicalize(child)),
    }
    with pytest.raises(AeroMeshDomainError, match="unreachable"):
        validate_release(release)


@pytest.mark.parametrize(
    "provider",
    [
        {
            "type": "mcp",
            "id": "scan",
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "mutable"],
        },
        {
            "type": "mcp",
            "id": "scan",
            "transport": "stdio",
            "image": "example/scanner:latest",
            "required_tools": ["scan"],
        },
        {"type": "mcp", "id": "scan", "transport": "stdio", "image": IMAGE},
        {
            "type": "mcp",
            "id": "scan",
            "transport": "stdio",
            "image": IMAGE,
            "required_tools": ["scan"],
            "allowed_domains": ["example.com"],
        },
        {
            "type": "mcp",
            "id": "scan",
            "transport": "sse",
            "uri": "https://example.com/mcp",
            "required_tools": ["scan"],
        },
    ],
)
def test_release_rejects_unbounded_tool_capabilities(tmp_path, provider):
    target = write(tmp_path / "root.json", agent(providers=[provider]))
    with pytest.raises(AeroMeshDomainError):
        build_release(target)


def test_policy_denies_by_default_and_diff_shows_permission_changes(tmp_path):
    target = write(tmp_path / "root.json", agent())
    previous = build_release(target)
    providers = [
        {"type": "credential", "id": "SCAN_KEY"},
        {
            "type": "mcp",
            "id": "scan",
            "transport": "stdio",
            "image": IMAGE,
            "required_tools": ["scan"],
            "credential_bindings": {"SCAN_TOKEN": "SCAN_KEY"},
        },
    ]
    write(target, agent(providers=providers))
    release = build_release(target)
    requested = requested_capabilities(release)
    assert requested["images"] == [IMAGE]
    assert requested["credentials"] == ["SCAN_KEY"]
    assert requested["tools"] == {"scan": ["scan"]}
    with pytest.raises(AeroMeshDomainError, match="policy"):
        check_policy(release, policy())
    check_policy(
        release,
        policy(
            allowed_credentials=["SCAN_KEY"],
            providers={
                "scan": {
                    "image": IMAGE,
                    "tools": ["scan"],
                    "credential_bindings": {"SCAN_TOKEN": "SCAN_KEY"},
                }
            },
        ),
    )
    changes = diff_releases(previous, release)
    assert changes["added"]["images"] == [IMAGE]
    assert changes["added"]["credentials"] == ["SCAN_KEY"]
    assert changes["added"]["tools"] == {"scan": ["scan"]}
    assert changes["changed_agents"] == ["root"]


def test_approval_revalidates_snapshot_policy_and_signature(tmp_path):
    target = write(tmp_path / "root.json", agent())
    release = build_release(target)
    source = signed_release(tmp_path, release)
    policy_path = write(tmp_path / "policy.json", policy())
    digest = approve_release(source, policy_path)
    approved = load_approved_release(digest)
    assert approved.digest == sha256_hex(canonicalize(release))
    assert approved.entry_data == approved.agent_data["root"]
    assert approved.agent_paths["root"].exists()
    assert load_approved_release(source).digest == digest
    # Editing draft/source files never changes an installed release.
    write(target, agent("different"))
    assert load_approved_release(digest).entry_data["identity"]["id"] == "root"
    snapshot = approved.agent_paths["root"]
    snapshot.write_text("{}")
    with pytest.raises(AeroMeshDomainError, match="snapshot"):
        load_approved_release(digest)


def test_policy_edit_requires_explicit_reapproval(tmp_path):
    source = signed_release(
        tmp_path, build_release(write(tmp_path / "root.json", agent()))
    )
    policy_path = write(tmp_path / "policy.json", policy())
    digest = approve_release(source, policy_path)
    write(policy_path, policy(allowed_credentials=["NEW_KEY"]))
    with pytest.raises(AeroMeshDomainError, match="policy.*changed"):
        load_approved_release(digest)
    assert approve_release(source, policy_path) == digest
    assert load_approved_release(digest).policy["allowed_credentials"] == ["NEW_KEY"]


def test_approval_rejects_unsigned_and_signature_tampering(tmp_path):
    release = build_release(write(tmp_path / "root.json", agent()))
    source = write(tmp_path / "release.json", release)
    policy_path = write(tmp_path / "policy.json", policy())
    with pytest.raises(AeroMeshDomainError):
        approve_release(source, policy_path)
    signed_release(tmp_path, release)
    digest = approve_release(source, policy_path)
    installed = paths.get_aeromesh_home() / "releases" / digest / "release.json"
    modified = copy.deepcopy(release)
    modified["identity"]["version"] = "2.0.0"
    write(installed, modified)
    with pytest.raises(AeroMeshDomainError):
        load_approved_release(digest)


def test_release_verifies_revocation_at_each_load(tmp_path):
    from aero.services.trust import revoke_key

    source = signed_release(
        tmp_path, build_release(write(tmp_path / "root.json", agent()))
    )
    policy_path = write(tmp_path / "policy.json", policy())
    digest = approve_release(source, policy_path)
    assert revoke_key("root")
    with pytest.raises(AeroMeshDomainError, match="[Rr][Ee][Vv][Oo][Kk]"):
        load_approved_release(digest)


def test_credential_grants_are_bound_to_exact_tool_image(tmp_path):
    providers = [
        {"type": "credential", "id": "SCAN_KEY"},
        {
            "type": "mcp",
            "id": "scan",
            "transport": "stdio",
            "image": IMAGE,
            "required_tools": ["scan"],
            "credential_bindings": {"SCAN_TOKEN": "SCAN_KEY"},
        },
    ]
    target = write(tmp_path / "root.json", agent(providers=providers))
    approved_policy = {
        "policy_version": "1",
        "allowed_credentials": ["SCAN_KEY"],
        "providers": {
            "scan": {
                "image": IMAGE,
                "tools": ["scan"],
                "credential_bindings": {"SCAN_TOKEN": "SCAN_KEY"},
            }
        },
    }
    check_policy(build_release(target), approved_policy)
    providers[1]["image"] = "example/other@sha256:" + "b" * 64
    write(target, agent(providers=providers))
    with pytest.raises(AeroMeshDomainError, match="image"):
        check_policy(build_release(target), approved_policy)


def test_workflow_release_resolves_nested_agents_and_pins_steps(tmp_path):
    write(tmp_path / "child.json", agent("child"))
    write(
        tmp_path / "root.json",
        agent(providers=[{"type": "sub_agent", "id": "delegate", "agent_id": "child"}]),
    )
    workflow = {
        "workflow_version": "1.0.0",
        "identity": {"id": "workflow", "name": "Workflow", "version": "1.0.0"},
        "steps": [{"id": "first", "agent_id": "root", "intent": "Do it"}],
    }
    release = build_release(write(tmp_path / "workflow.json", workflow))
    assert (
        release["workflow"]["manifest"]["steps"][0]["agent_sha256"]
        == release["agents"]["root"]["sha256"]
    )
    assert set(release["agents"]) == {"root", "child"}
    source = signed_release(tmp_path, release)
    digest = approve_release(source, write(tmp_path / "policy.json", policy()))
    context = load_approved_release(digest)
    assert context.entry_path.name == "workflow.json"
    assert context.entry_data == release["workflow"]["manifest"]
    source.unlink()
    assert load_approved_release(digest).agent_data["child"] == agent("child")


def test_workflow_cannot_omit_reference_pin_in_signed_release(tmp_path):
    write(tmp_path / "root.json", agent())
    workflow = {
        "workflow_version": "1.0.0",
        "identity": {"id": "workflow", "name": "Workflow", "version": "1.0.0"},
        "steps": [{"id": "first", "agent_id": "root", "intent": "Do it"}],
    }
    release = build_release(write(tmp_path / "workflow.json", workflow))
    del release["workflow"]["manifest"]["steps"][0]["agent_sha256"]
    release["workflow"]["sha256"] = sha256_hex(
        canonicalize(release["workflow"]["manifest"])
    )
    release["entry"]["sha256"] = release["workflow"]["sha256"]
    with pytest.raises(AeroMeshDomainError, match="reference digest"):
        validate_release(release)


def test_cli_release_build_trust_approve_execute_receipt(
    tmp_path, capsys, offline_runtime
):
    """Real CLI, signature, storage and runner; only the suite's model is offline."""
    from aero.presentation.cli import main
    from aero.services.session import SessionRegistry

    source = write(tmp_path / "root.json", agent())
    release_path = tmp_path / "locked.json"
    assert main(["release", "build", str(source), "--output", str(release_path)]) == 0
    capsys.readouterr()
    release = json.loads(release_path.read_text())
    private, public = generate_keypair()
    key_path = tmp_path / "author.pub"
    key_path.write_bytes(public)
    write(tmp_path / "locked.json.sig", sign_manifest_dict(release, private))
    policy_path = write(tmp_path / "policy.json", policy())
    assert (
        main(["release", "approve", str(release_path), "--policy", str(policy_path)])
        != 0
    )
    capsys.readouterr()
    assert main(["trust", "root", str(key_path)]) == 0
    capsys.readouterr()
    assert (
        main(["release", "approve", str(release_path), "--policy", str(policy_path)])
        == 0
    )
    digest = json.loads(capsys.readouterr().out)["approved_release"]
    assert main(["release", "run", digest, "Describe your result", "--json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["receipt"]["release_digest"] == digest
    sessions = SessionRegistry().list()
    assert any(
        s["release_digest"] == digest and s["status"] == "completed" for s in sessions
    )
    assert main(["revoke", "root"]) == 0
    capsys.readouterr()
    assert main(["release", "run", digest, "Try again", "--json"]) != 0


def test_cli_workflow_release_runs_verified_closure(tmp_path, capsys, offline_runtime):
    from aero.presentation.cli import main
    from aero.services.session import SessionRegistry

    write(tmp_path / "first.json", agent("first"))
    write(tmp_path / "second.json", agent("second"))
    workflow = {
        "workflow_version": "1.0.0",
        "identity": {"id": "workflow", "name": "Workflow", "version": "1.0.0"},
        "steps": [
            {"id": "a", "agent_id": "first", "intent": "Inspect {input}"},
            {
                "id": "b",
                "agent_id": "second",
                "intent": "Summarize {a}",
                "depends_on": ["a"],
            },
        ],
        "output": "b",
    }
    source = signed_release(
        tmp_path, build_release(write(tmp_path / "workflow.json", workflow))
    )
    policy_path = write(tmp_path / "policy.json", policy())
    digest = approve_release(source, policy_path)
    assert main(["release", "run", digest, "Supplied task", "--json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert set(output["outputs"]) == {"a", "b"}
    assert output["execution_success"] is True
    receipts = SessionRegistry().receipts(output["execution_id"])
    assert len(receipts) == 3  # workflow plus both independently evidenced steps
    assert all(
        item["release_digest"] == digest and item["status"] == "completed"
        for item in receipts
    )
    assert all(
        item["policy_sha256"] == sha256_hex(canonicalize(policy())) for item in receipts
    )


def test_forged_context_fields_cannot_replace_approved_entry(tmp_path, offline_runtime):
    from types import SimpleNamespace
    from aero.services.runner import AeroAgentRunnerService

    source = signed_release(
        tmp_path, build_release(write(tmp_path / "root.json", agent()))
    )
    digest = approve_release(source, write(tmp_path / "policy.json", policy()))
    malicious = agent()
    malicious["cognitive_runtime"]["persona"] = "Unapproved replacement"
    forged = SimpleNamespace(
        digest=digest,
        entry_data=malicious,
        entry_path=tmp_path / "unapproved.json",
        agent_data={"root": malicious},
    )
    result = AeroAgentRunnerService().run_manifest_file(
        None, "Inspect", approved_release=forged, non_interactive=True
    )
    assert result["manifest"].cognitive_runtime.persona == "Test"
    assert result["receipt"]["release_digest"] == digest


def test_runtime_rejects_changed_manifest_before_model_or_tools(tmp_path, monkeypatch):
    from aero.infrastructure.parser import ManifestParser
    from aero.services.deepagents_runner import DeepAgentsExecutionDriver

    source = signed_release(
        tmp_path, build_release(write(tmp_path / "root.json", agent()))
    )
    context = load_approved_release(
        approve_release(source, write(tmp_path / "policy.json", policy()))
    )
    malicious = agent()
    malicious["cognitive_runtime"]["persona"] = "Unapproved replacement"

    def forbidden(*args, **kwargs):
        pytest.fail("Changed manifest reached model or tools")

    monkeypatch.setattr("aero.services.deepagents_runner.resolve_model", forbidden)
    monkeypatch.setattr("aero.services.deepagents_runner.build_mcp_tools", forbidden)
    with pytest.raises(AeroMeshDomainError, match="changed"):
        DeepAgentsExecutionDriver(
            ManifestParser().validate_dict(malicious), approved_release=context
        )
