"""Ed25519 key storage and git-registry trust store helpers."""

from pathlib import Path
from typing import Tuple

from aero.domain.paths import get_aeromesh_home
from aero.infrastructure.attestation import generate_keypair

DEFAULT_KEY_NAME = "default"


def keys_dir() -> Path:
    """Directory holding local Ed25519 keypairs under ~/.aeromesh/keys."""
    d = get_aeromesh_home() / "keys"
    d.mkdir(parents=True, exist_ok=True)
    return d


def generate_and_store_keypair(name: str = DEFAULT_KEY_NAME) -> Tuple[Path, Path]:
    """Generate an Ed25519 keypair and persist it, returning (priv_path, pub_path)."""
    priv_pem, pub_pem = generate_keypair()
    kd = keys_dir()
    priv_path = kd / f"{name}.key"
    pub_path = kd / f"{name}.pub"
    priv_path.write_bytes(priv_pem)
    pub_path.write_bytes(pub_pem)
    return priv_path, pub_path


def load_private_key(name: str = DEFAULT_KEY_NAME) -> bytes:
    return (keys_dir() / f"{name}.key").read_bytes()


def load_public_key(name: str = DEFAULT_KEY_NAME) -> bytes:
    return (keys_dir() / f"{name}.pub").read_bytes()
