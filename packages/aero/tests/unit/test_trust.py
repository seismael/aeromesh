"""Tests for the trust service (sign files, verify, install gating)."""

import json
import pytest

from aero.services import trust


def _write_manifest(path, agent_id="demo-agent"):
    data = {
        "manifest_version": "0.1.0",
        "identity": {"id": agent_id, "name": "Demo", "version": "0.1.0"},
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
    ok, reason = trust.verify_manifest_trusted_file(str(manifest_path), "demo-agent")
    assert ok is False
    assert "trusted public key" in reason


def test_verify_manifest_trusted_succeeds_with_matching_key(monkeypatch, tmp_path):
    monkeypatch.setenv("AEROMESH_HOME", str(tmp_path))
    manifest_path = tmp_path / "demo.json"
    _write_manifest(manifest_path, agent_id="demo-agent")

    priv_path, pub_path = trust.generate_and_store_keypair("default")
    trust.sign_manifest_file(str(manifest_path))

    # Register the public key in the git-registry trust store
    trusted_dir = tmp_path / "registry" / "trusted"
    trusted_dir.mkdir(parents=True)
    (trusted_dir / "demo-agent.pub").write_bytes(pub_path.read_bytes())

    # Trust service must resolve the trust store relative to registry dir
    monkeypatch.setattr(
        trust.paths,
        "get_aeromesh_workspace_trusted_dir",
        lambda: trusted_dir,
    )
    ok, reason = trust.verify_manifest_trusted_file(str(manifest_path), "demo-agent")
    assert ok is True
