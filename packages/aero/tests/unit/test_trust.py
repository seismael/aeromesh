"""Tests for the trust service (sign files, verify, install gating)."""

import json
import pytest

from aero.services import trust
from aero.domain.errors import AeroMeshDomainError


def _write_manifest(path, agent_id="demo-agent"):
    data = {
        "manifest_version": "1.0.0",
        "identity": {"id": agent_id, "name": "Demo", "version": "1.0.0"},
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def test_sign_and_verify_manifest_file_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("AEROMESH_HOME", str(tmp_path))
    manifest_path = tmp_path / "demo.json"
    _write_manifest(manifest_path)

    trust.generate_and_store_keypair("default")
    attestation = trust.sign_manifest_file(str(manifest_path))
    assert manifest_path.with_suffix(".json.sig").exists()

    ok, reason = trust.verify_manifest_file(str(manifest_path))
    assert ok is True
    assert "valid" in reason


def test_verify_manifest_file_detects_tamper(monkeypatch, tmp_path):
    monkeypatch.setenv("AEROMESH_HOME", str(tmp_path))
    manifest_path = tmp_path / "demo.json"
    _write_manifest(manifest_path)

    trust.generate_and_store_keypair("default")
    trust.sign_manifest_file(str(manifest_path))

    # Tamper after signing
    data = json.loads(manifest_path.read_text())
    data["identity"]["name"] = "EVIL"
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    ok, reason = trust.verify_manifest_file(str(manifest_path))
    assert ok is False


def test_verify_manifest_trusted_requires_trusted_key(monkeypatch, tmp_path):
    monkeypatch.setenv("AEROMESH_HOME", str(tmp_path))
    manifest_path = tmp_path / "demo.json"
    _write_manifest(manifest_path, agent_id="demo-agent")

    trust.generate_and_store_keypair("default")
    trust.sign_manifest_file(str(manifest_path))

    # No trusted key registered yet -> untrusted
    with pytest.raises(AeroMeshDomainError, match="trusted public key"):
        trust.require_trusted_manifest(manifest_path, "demo-agent")


def test_verify_manifest_trusted_succeeds_with_matching_key(monkeypatch, tmp_path):
    monkeypatch.setenv("AEROMESH_HOME", str(tmp_path))
    manifest_path = tmp_path / "demo.json"
    _write_manifest(manifest_path, agent_id="demo-agent")

    priv_path, pub_path = trust.generate_and_store_keypair("default")
    trust.sign_manifest_file(str(manifest_path))

    # Importing a repository or author key never grants implicit approval.
    trust.trust_key("demo-agent", pub_path)
    verified = trust.require_trusted_manifest(manifest_path, "demo-agent")
    assert verified == json.loads(manifest_path.read_text())


def test_revoke_key_blocks_verification(monkeypatch, tmp_path):
    monkeypatch.setenv("AEROMESH_HOME", str(tmp_path))
    manifest_path = tmp_path / "demo.json"
    _write_manifest(manifest_path, agent_id="demo-agent")

    trust.generate_and_store_keypair("default")
    trust.sign_manifest_file(str(manifest_path))
    pub_key = trust.load_attestation(str(manifest_path))["public_key"]

    public_path = tmp_path / "author.pub"
    public_path.write_text(pub_key, encoding="utf-8")
    trust.trust_key("demo-agent", public_path)

    assert trust.require_trusted_manifest(manifest_path, "demo-agent")
    assert trust.revoke_key("demo-agent") is True
    with pytest.raises(AeroMeshDomainError, match="REVOKED"):
        trust.require_trusted_manifest(manifest_path, "demo-agent")
