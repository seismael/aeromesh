"""Ed25519 key storage (encrypted at rest) and git-registry trust store helpers."""

from pathlib import Path
from typing import Tuple

from cryptography.fernet import Fernet

from aero.domain.paths import get_aeromesh_home
from aero.infrastructure.attestation import generate_keypair
from aero.infrastructure.credential_store import SecureCredentialStore

DEFAULT_KEY_NAME = "default"
_ENCRYPTION_KEY_ID = "aeromesh/signing-key-encryption"


def keys_dir() -> Path:
    """Directory holding local Ed25519 keypairs under ~/.aeromesh/keys."""
    d = get_aeromesh_home() / "keys"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _fernet(store: SecureCredentialStore = None) -> Fernet:
    """Fernet using a key held in the OS keyring (encrypted at rest)."""
    store = store or SecureCredentialStore()
    key = store.get(_ENCRYPTION_KEY_ID)
    if not key:
        key = Fernet.generate_key().decode()
        store.set(_ENCRYPTION_KEY_ID, key)
    return Fernet(key.encode())


def generate_and_store_keypair(name: str = DEFAULT_KEY_NAME) -> Tuple[Path, Path]:
    """Generate an Ed25519 keypair, encrypt the private key at rest, persist it."""
    priv_pem, pub_pem = generate_keypair()
    kd = keys_dir()
    priv_path = kd / f"{name}.key"
    pub_path = kd / f"{name}.pub"
    priv_path.write_bytes(_fernet().encrypt(priv_pem))
    pub_path.write_bytes(pub_pem)
    return priv_path, pub_path


def load_private_key(name: str = DEFAULT_KEY_NAME) -> bytes:
    encrypted = (keys_dir() / f"{name}.key").read_bytes()
    return _fernet().decrypt(encrypted)


def load_public_key(name: str = DEFAULT_KEY_NAME) -> bytes:
    return (keys_dir() / f"{name}.pub").read_bytes()
