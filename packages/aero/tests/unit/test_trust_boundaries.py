"""Negative tests for local authorization, exact-content verification and secrets."""

import json
from pathlib import Path

import pytest

from aero.domain import paths
from aero.domain.errors import AeroMeshDomainError, ExitCode
from aero.domain.models import CapabilityProviderRequirement
from aero.infrastructure import attestation, keystore
from aero.infrastructure.vault import ZeroTrustVaultResolver
from aero.services import trust


def signed_artifact(tmp_path, artifact_id="approved-agent"):
    private, public = attestation.generate_keypair()
    data = {"identity": {"id": artifact_id, "name": "Approved", "version": "1.0.0"}}
    manifest = tmp_path / "agent.json"
    manifest.write_text(json.dumps(data))
    Path(str(manifest) + ".sig").write_text(
        json.dumps(attestation.sign_manifest_dict(data, private))
    )
    public_path = tmp_path / "author.pub"
    public_path.write_bytes(public)
    return manifest, public_path, data


def test_repository_keys_do_not_grant_local_trust(tmp_path, monkeypatch):
    manifest, public, _ = signed_artifact(tmp_path)
    registry = tmp_path / "registry" / "trusted"
    registry.mkdir(parents=True)
    (registry / "approved-agent.pub").write_bytes(public.read_bytes())
    monkeypatch.setattr(paths, "get_aeromesh_workspace_registry_dir", lambda: registry.parent / "agents")
    with pytest.raises(AeroMeshDomainError, match="trusted public key") as missing:
        trust.require_trusted_manifest(str(manifest))
    assert missing.value.exit_code == ExitCode.TRUST_VIOLATION


def test_explicit_trust_exact_content_and_revocation(tmp_path):
    manifest, public, data = signed_artifact(tmp_path)
    approved = trust.trust_key("approved-agent", public)
    assert approved == paths.get_aeromesh_home() / "trusted" / "approved-agent.pub"
    assert trust.require_trusted_manifest(manifest, "approved-agent") == data
    with pytest.raises(AeroMeshDomainError, match="identity") as identity:
        trust.require_trusted_manifest(manifest, "another-agent")
    assert identity.value.exit_code == ExitCode.SCHEMA_VIOLATION
    assert trust.revoke_key("approved-agent")
    with pytest.raises(AeroMeshDomainError, match="REVOKED") as revoked:
        trust.require_trusted_manifest(manifest)
    assert revoked.value.exit_code == ExitCode.TRUST_VIOLATION


@pytest.mark.parametrize(
    "unsafe", ["../escape", "/tmp/escape", r"..\escape", "a/b", "", ".", "A:B"]
)
def test_trust_rejects_paths_as_artifact_ids(tmp_path, unsafe):
    _, public, _ = signed_artifact(tmp_path)
    with pytest.raises(AeroMeshDomainError):
        trust.trust_key(unsafe, public)
    with pytest.raises(AeroMeshDomainError):
        trust.trusted_public_key(unsafe)


def test_key_import_does_not_silently_replace_approved_signer(tmp_path):
    _, public, _ = signed_artifact(tmp_path)
    trust.trust_key("approved-agent", public)
    _, other = attestation.generate_keypair()
    public.write_bytes(other)
    with pytest.raises(AeroMeshDomainError, match="already"):
        trust.trust_key("approved-agent", public)


def test_verified_data_is_read_once(tmp_path, monkeypatch):
    manifest, public, data = signed_artifact(tmp_path)
    trust.trust_key("approved-agent", public)
    original = trust._load_manifest
    calls = []

    def load_once(path):
        loaded = original(path)
        if Path(path) == manifest:
            calls.append(path)
            manifest.write_text('{"identity":{"id":"changed"}}')
        return loaded

    monkeypatch.setattr(trust, "_load_manifest", load_once)
    assert trust.require_trusted_manifest(manifest) == data
    assert len(calls) == 1


@pytest.mark.parametrize(
    "mutation",
    [
        {"algorithm": "rsa"},
        {"public_key": "garbage"},
        {"signature": "!bad!"},
        {"signature": None},
    ],
)
def test_malformed_attestation_fails_closed(mutation):
    private, _ = attestation.generate_keypair()
    data = {"identity": {"id": "agent"}}
    signature = attestation.sign_manifest_dict(data, private)
    signature.update(mutation)
    assert attestation.verify_manifest_dict(data, signature) is False


def test_duplicate_json_keys_are_rejected(tmp_path):
    manifest, public, _ = signed_artifact(tmp_path)
    trust.trust_key("approved-agent", public)
    manifest.write_text('{"identity":{"id":"approved-agent","id":"approved-agent"}}')
    with pytest.raises(AeroMeshDomainError, match="duplicate") as malformed:
        trust.require_trusted_manifest(manifest)
    assert malformed.value.exit_code == ExitCode.SCHEMA_VIOLATION


def test_tampered_signature_has_trust_exit_code(tmp_path):
    manifest, public, data = signed_artifact(tmp_path)
    trust.trust_key("approved-agent", public)
    data["identity"]["name"] = "Tampered"
    manifest.write_text(json.dumps(data))
    with pytest.raises(AeroMeshDomainError, match="tampered") as tampered:
        trust.require_trusted_manifest(manifest)
    assert tampered.value.exit_code == ExitCode.TRUST_VIOLATION


def test_unsigned_install_removes_stale_sidecar(tmp_path):
    source = tmp_path / "new.json"
    source.write_text("{}")
    target = tmp_path / "installed.json"
    stale = Path(str(target) + ".sig")
    stale.write_text("obsolete-signature")
    trust.install_attestation(source, target)
    assert not stale.exists()


def test_keygen_refuses_overwrite_and_path_escape(tmp_path):
    private, public = keystore.generate_and_store_keypair("unique")
    original = (private.read_bytes(), public.read_bytes())
    with pytest.raises((AeroMeshDomainError, FileExistsError)):
        keystore.generate_and_store_keypair("unique")
    assert (private.read_bytes(), public.read_bytes()) == original
    with pytest.raises(AeroMeshDomainError):
        keystore.generate_and_store_keypair("../escape")


class UnavailableStore:
    def get(self, key):
        return None

    def set(self, key, value):
        raise RuntimeError("keyring unavailable")


def test_vault_does_not_read_filesystem_secrets(tmp_path, monkeypatch):
    (tmp_path / "credentials.json").write_text('{"UNIQUE_AUDIT_SECRET":"unapproved-file-value"}')
    (tmp_path / "Desktop").mkdir()
    (tmp_path / "Desktop" / "tokens.txt").write_text("UNIQUE_AUDIT_SECRET=desktop")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    resolver = ZeroTrustVaultResolver(store=UnavailableStore())
    provider = CapabilityProviderRequirement(
        type="credential", id="UNIQUE_AUDIT_SECRET"
    )
    with pytest.raises(AeroMeshDomainError, match="missing"):
        resolver.resolve_requirements([provider], non_interactive=True)


def test_keyring_failure_does_not_write_plaintext(tmp_path):
    resolver = ZeroTrustVaultResolver(store=UnavailableStore())
    with pytest.raises(AeroMeshDomainError, match="keyring") as unavailable:
        resolver._save_credential("SECRET", "synthetic-value")
    assert unavailable.value.exit_code == ExitCode.VAULT_KEY_MISSING
    assert not (tmp_path / "credentials.json").exists()


def test_vault_only_resolves_requested_credentials(monkeypatch):
    monkeypatch.setenv("REQUESTED", "requested-value")
    monkeypatch.setenv("UNREQUESTED", "other-value")
    resolver = ZeroTrustVaultResolver(store=UnavailableStore())
    provider = CapabilityProviderRequirement(type="credential", id="REQUESTED")
    assert resolver.resolve_requirements([provider], non_interactive=True) == {
        "REQUESTED": "requested-value"
    }


def test_vault_locked_keyring_fails_without_prompting_or_overwriting(monkeypatch):
    monkeypatch.delenv("LOCKED_KEY", raising=False)

    class LockedStore:
        def get(self, key):
            raise RuntimeError("locked")

        def set(self, key, value):
            pytest.fail("Unavailable storage must not be overwritten")

    resolver = ZeroTrustVaultResolver(
        store=LockedStore(),
        prompt_fn=lambda *args: pytest.fail("Keyring failure is not a missing credential"),
    )
    provider = CapabilityProviderRequirement(type="credential", id="LOCKED_KEY")
    with pytest.raises(AeroMeshDomainError, match="OS keyring unavailable"):
        resolver.resolve_requirements([provider])


def test_explicit_credentials_work_without_keyring_access(monkeypatch):
    monkeypatch.setenv("ENV_KEY", "env-value")

    class LockedStore:
        def get(self, key):
            pytest.fail("Explicit credentials must not access the keyring")

    resolver = ZeroTrustVaultResolver(
        override_env={"EXPLICIT_KEY": "explicit-value"}, store=LockedStore()
    )
    providers = [
        CapabilityProviderRequirement(type="credential", id=key)
        for key in ("ENV_KEY", "EXPLICIT_KEY")
    ]
    assert resolver.resolve_requirements(providers, non_interactive=True) == {
        "ENV_KEY": "env-value", "EXPLICIT_KEY": "explicit-value"
    }


def test_atomic_sidecar_failure_preserves_previous_signature(tmp_path, monkeypatch):
    manifest, _, _ = signed_artifact(tmp_path)
    signature = Path(str(manifest) + ".sig")
    original = signature.read_bytes()

    def fail_replace(*args):
        raise OSError("synthetic publish failure")

    monkeypatch.setattr(trust.os, "replace", fail_replace)
    with pytest.raises(OSError):
        trust.atomic_write(signature, b"replacement")
    assert signature.read_bytes() == original
    assert list(tmp_path.glob(".agent.json.sig.*")) == []


def test_trust_store_symlink_cannot_import_external_key(tmp_path):
    _, public, _ = signed_artifact(tmp_path)
    directory = paths.get_aeromesh_trusted_dir()
    directory.mkdir(parents=True)
    (directory / "approved-agent.pub").symlink_to(public)
    with pytest.raises(AeroMeshDomainError, match="escapes"):
        trust.trusted_public_key("approved-agent")


def test_workflow_reference_cannot_supply_its_own_key_path(tmp_path):
    from types import SimpleNamespace

    manifest, public, _ = signed_artifact(tmp_path)
    Path(str(manifest) + ".pub").write_bytes(public.read_bytes())
    workflow = SimpleNamespace(steps=[SimpleNamespace(agent_id=str(manifest))])
    ok, _ = trust.verify_workflow_references(workflow)
    assert not ok


def test_revocation_applies_to_same_key_under_other_identity(tmp_path):
    _, public, _ = signed_artifact(tmp_path)
    trust.trust_key("approved-agent", public)
    trust.trust_key("second-agent", public)
    assert trust.revoke_key("approved-agent")
    assert trust.is_revoked("second-agent")
    with pytest.raises(AeroMeshDomainError, match="REVOKED"):
        trust.trust_key("third-agent", public)
