"""Tests for Ed25519 key storage and git-registry trust store."""

import pytest

from aero.infrastructure import keystore
from aero.domain import paths


def test_generate_and_store_keypair_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("AEROMESH_HOME", str(tmp_path))
    priv_path, pub_path = keystore.generate_and_store_keypair("testkey")
    assert priv_path.name == "testkey.key"
    assert pub_path.name == "testkey.pub"
    assert priv_path.exists() and pub_path.exists()

    loaded_priv = keystore.load_private_key("testkey")
    loaded_pub = keystore.load_public_key("testkey")
    assert loaded_priv == priv_path.read_bytes()
    assert loaded_pub == pub_path.read_bytes()


def test_workspace_trusted_dir_is_sibling_of_registry_agents():
    trusted = paths.get_aeromesh_workspace_trusted_dir()
    agents = paths.get_aeromesh_workspace_registry_dir()
    assert trusted == agents.parent / "trusted"
