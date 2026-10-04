"""Integrate manifest, approval, vault and per-tool least-privilege boundaries.

These tests compile container connections without starting containers. A missing
credential must stop the real execution path before model/tool initialization.
"""

import copy
import json

import pytest

from aero.domain.errors import AeroMeshDomainError
from aero.infrastructure.credential_store import SecureCredentialStore
from aero.infrastructure.parser import ManifestParser
from aero.infrastructure.vault import ZeroTrustVaultResolver
from aero.presentation.cli import main
from aero.services.deepagents_runner import mcp_connections
from aero.services.policy import check_policy
from aero.services.releases import build_release


@pytest.fixture
def multi_tool_draft(tmp_path):
    data = {
        "manifest_version": "1.0.0",
        "identity": {"id": "local-report", "name": "Local report", "version": "1.0.0"},
        "capabilities": {
            "domain": "Testing",
            "tags": [],
            "short_description": "Read two local datasets",
            "evaluation_trigger": "Manual",
        },
        "cognitive_runtime": {
            "persona": "Summarize supplied local datasets.",
            "success_criteria": "Return evidence from both sources.",
        },
        "requirements": {
            "providers": [
                {"type": "credential", "id": "FIRST_DATA_KEY"},
                {"type": "credential", "id": "SECOND_DATA_KEY"},
                {
                    "type": "mcp",
                    "id": "first-reader",
                    "transport": "stdio",
                    "image": "example/first@sha256:" + "a" * 64,
                    "required_tools": ["read_first"],
                    "credential_bindings": {"DATA_TOKEN": "FIRST_DATA_KEY"},
                },
                {
                    "type": "mcp",
                    "id": "second-reader",
                    "transport": "stdio",
                    "image": "example/second@sha256:" + "b" * 64,
                    "required_tools": ["read_second"],
                    "credential_bindings": {"DATA_TOKEN": "SECOND_DATA_KEY"},
                },
            ]
        },
    }
    policy = {
        "policy_version": "1",
        "allowed_credentials": ["FIRST_DATA_KEY", "SECOND_DATA_KEY"],
        "providers": {
            p["id"]: {
                "image": p["image"],
                "tools": p["required_tools"],
                "credential_bindings": p["credential_bindings"],
            }
            for p in data["requirements"]["providers"]
            if p["type"] == "mcp"
        },
    }
    source = tmp_path / "agent.json"
    source.write_text(json.dumps(data))
    return source, data, policy


def test_multi_tool_manifest_and_operator_grants_agree(multi_tool_draft):
    source, _, policy = multi_tool_draft
    assert main(["validate", str(source)]) == 0
    capabilities = check_policy(build_release(source), policy)
    assert capabilities["credentials"] == ["FIRST_DATA_KEY", "SECOND_DATA_KEY"]
    assert capabilities["tools"] == {
        "first-reader": ["read_first"],
        "second-reader": ["read_second"],
    }


def test_vault_and_connections_keep_credentials_scoped(multi_tool_draft, monkeypatch):
    source, _, policy = multi_tool_draft
    release = build_release(source)
    check_policy(release, policy)
    manifest = ManifestParser().validate_dict(
        release["agents"]["local-report"]["manifest"]
    )
    store = SecureCredentialStore()
    store.set("FIRST_DATA_KEY", "first-synthetic-secret")
    store.set("SECOND_DATA_KEY", "second-synthetic-secret")
    store.set("UNREQUESTED_KEY", "never-resolved")
    monkeypatch.setenv("UNRELATED_PROCESS_SECRET", "never-inherited")
    monkeypatch.delenv("FIRST_DATA_KEY", raising=False)
    monkeypatch.delenv("SECOND_DATA_KEY", raising=False)
    credentials = ZeroTrustVaultResolver(store=store).resolve_requirements(
        manifest.providers, non_interactive=True
    )
    assert credentials == {
        "FIRST_DATA_KEY": "first-synthetic-secret",
        "SECOND_DATA_KEY": "second-synthetic-secret",
    }
    # Isolate image metadata discovery here; real Docker behavior has its own gate.
    import subprocess

    monkeypatch.setattr(
        "aero.infrastructure.tool_execution.shutil.which",
        lambda executable: "/audit/docker",
    )
    monkeypatch.setattr(
        "aero.infrastructure.tool_execution.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, stdout=b"null" if "inspect" in command else b""
        ),
    )
    cleanup = []
    try:
        connections = mcp_connections(
            manifest, credentials, cleanup_callbacks=cleanup
        )
    finally:
        for callback in reversed(cleanup):
            callback()
    first, second = (
        connections["first-reader"]["env"],
        connections["second-reader"]["env"],
    )
    assert first["DATA_TOKEN"] == "first-synthetic-secret"
    assert second["DATA_TOKEN"] == "second-synthetic-secret"
    assert "second-synthetic-secret" not in first.values()
    assert "first-synthetic-secret" not in second.values()
    assert all(
        "UNREQUESTED_KEY" not in env and "UNRELATED_PROCESS_SECRET" not in env
        for env in (first, second)
    )
    assert all(
        "FIRST_DATA_KEY" not in env and "SECOND_DATA_KEY" not in env
        for env in (first, second)
    )


def test_same_declared_credentials_do_not_allow_swapped_tool_bindings(multi_tool_draft):
    source, data, policy = multi_tool_draft
    changed = copy.deepcopy(data)
    changed["requirements"]["providers"][2]["credential_bindings"]["DATA_TOKEN"] = (
        "SECOND_DATA_KEY"
    )
    source.write_text(json.dumps(changed))
    # Both keys are granted globally; their exact tool binding is still mandatory.
    with pytest.raises(AeroMeshDomainError, match="binding"):
        check_policy(build_release(source), policy)


def test_missing_bound_credential_blocks_approved_execution_before_launch(
    multi_tool_draft, tmp_path, monkeypatch, capsys
):
    source, _, policy = multi_tool_draft
    release = tmp_path / "release.json"
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy))
    assert main(["keygen"]) == 0
    public = json.loads(capsys.readouterr().out)["public_key"]
    assert main(["release", "build", str(source), "--output", str(release)]) == 0
    assert main(["sign", str(release)]) == 0
    assert main(["trust", "local-report", public]) == 0
    capsys.readouterr()
    assert main(["release", "approve", str(release), "--policy", str(policy_path)]) == 0
    digest = json.loads(capsys.readouterr().out)["approved_release"]
    monkeypatch.setenv("FIRST_DATA_KEY", "first-synthetic-secret")
    monkeypatch.delenv("SECOND_DATA_KEY", raising=False)

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "Model/tool initialization happened before required credentials were resolved"
        )

    monkeypatch.setattr("aero.services.deepagents_runner.resolve_model", forbidden)
    monkeypatch.setattr("aero.services.deepagents_runner.build_mcp_tools", forbidden)
    assert main(["release", "run", digest, "Summarize", "--json"]) == 20
    output = capsys.readouterr()
    assert "SECOND_DATA_KEY" in output.err
    assert "first-synthetic-secret" not in output.out + output.err
