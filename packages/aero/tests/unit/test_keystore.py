"""Tests for encrypted Ed25519 key storage."""

import pytest

from aero.infrastructure import keystore


def test_generate_and_store_keypair_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("AEROMESH_HOME", str(tmp_path))
    priv_path, pub_path = keystore.generate_and_store_keypair("testkey")
    assert priv_path.name == "testkey.key"
    assert pub_path.name == "testkey.pub"
    assert priv_path.exists() and pub_path.exists()

    loaded_priv = keystore.load_private_key("testkey")
    loaded_pub = keystore.load_public_key("testkey")
    # Private key decrypts to a valid PEM (roundtrip).
    assert b"PRIVATE KEY" in loaded_priv
    assert loaded_pub == pub_path.read_bytes()

    # Private key is encrypted at rest, not plaintext.
    assert b"PRIVATE KEY" not in priv_path.read_bytes()


def test_private_key_is_encrypted_at_rest(monkeypatch, tmp_path):
    monkeypatch.setenv("AEROMESH_HOME", str(tmp_path))
    priv_path, _ = keystore.generate_and_store_keypair("encrypted")
    on_disk = priv_path.read_bytes()
    assert b"-----BEGIN PRIVATE KEY-----" not in on_disk
    assert b"-----BEGIN ENCRYPTED PRIVATE KEY-----" not in on_disk



def test_concurrent_key_generation_keeps_every_private_key_decryptable(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import keyring

    writes = []
    save = keyring.set_password

    def observe_set(service, key, value):
        writes.append(key)
        save(service, key, value)

    monkeypatch.setattr(keyring, "set_password", observe_set)
    names = [f"concurrent-{index}" for index in range(16)]
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(keystore.generate_and_store_keypair, names))
    assert len(writes) == 1, "Concurrent initialization must create exactly one master key"
    for name in names:
        assert b"PRIVATE KEY" in keystore.load_private_key(name)


def test_independent_state_directories_have_independent_encryption_keys(monkeypatch, tmp_path):
    monkeypatch.setenv("AEROMESH_HOME", str(tmp_path / "one"))
    keystore.generate_and_store_keypair("signer")
    first_slot = keystore._encryption_key_id()
    first_private = keystore.load_private_key("signer")
    monkeypatch.setenv("AEROMESH_HOME", str(tmp_path / "two"))
    keystore.generate_and_store_keypair("signer")
    assert keystore._encryption_key_id() != first_slot
    assert keystore.load_private_key("signer") != first_private
    monkeypatch.setenv("AEROMESH_HOME", str(tmp_path / "one"))
    assert keystore.load_private_key("signer") == first_private


def test_locked_keyring_cannot_replace_signing_encryption_key(monkeypatch):
    import keyring
    from aero.domain.errors import AeroMeshDomainError

    keystore.generate_and_store_keypair("existing")

    def unavailable(*args):
        raise RuntimeError("locked keyring")

    def forbid_overwrite(*args):
        pytest.fail("A locked encryption-key slot must never be replaced")

    monkeypatch.setattr(keyring, "get_password", unavailable)
    monkeypatch.setattr(keyring, "set_password", forbid_overwrite)
    with pytest.raises(AeroMeshDomainError, match="cannot be read"):
        keystore.generate_and_store_keypair("new")
    assert not (keystore.keys_dir() / "new.key").exists()


def test_moving_state_directory_preserves_signing_key_access(monkeypatch, tmp_path):
    original = tmp_path / "original"
    relocated = tmp_path / "relocated"
    monkeypatch.setenv("AEROMESH_HOME", str(original))
    keystore.generate_and_store_keypair("signer")
    original_private = keystore.load_private_key("signer")
    original_identity = (keystore.keys_dir() / "store-id").read_bytes()
    original.rename(relocated)
    monkeypatch.setenv("AEROMESH_HOME", str(relocated))
    assert (keystore.keys_dir() / "store-id").read_bytes() == original_identity
    assert keystore.load_private_key("signer") == original_private


def test_missing_store_identity_does_not_create_new_master_key(monkeypatch):
    import keyring
    from aero.domain.errors import AeroMeshDomainError

    keystore.generate_and_store_keypair("existing")
    identity_path = keystore.keys_dir() / "store-id"
    identity_path.unlink()
    monkeypatch.setattr(
        keyring, "set_password", lambda *args: pytest.fail("No replacement master key")
    )
    with pytest.raises(AeroMeshDomainError, match="store identity is missing"):
        keystore.load_private_key("existing")
    assert not identity_path.exists()
