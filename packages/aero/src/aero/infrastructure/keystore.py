"""Ed25519 key storage (encrypted at rest) and git-registry trust store helpers."""

import os
from pathlib import Path
from typing import Tuple

from cryptography.fernet import Fernet

from aero.domain.paths import get_aeromesh_home, confined_artifact_path
from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.infrastructure.attestation import generate_keypair
from aero.infrastructure.credential_store import SecureCredentialStore

DEFAULT_KEY_NAME = "default"
_ENCRYPTION_KEY_ID = "aeromesh/signing-key-encryption"


def keys_dir() -> Path:
    """Directory holding local Ed25519 keypairs under ~/.aeromesh/keys."""
    d = get_aeromesh_home() / "keys"
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    return d


def _fernet(store: SecureCredentialStore = None) -> Fernet:
    """Fernet using a key held in the OS keyring (encrypted at rest)."""
    store = store or SecureCredentialStore()
    try:
        key = store.get_strict(_ENCRYPTION_KEY_ID)
    except Exception as exc:
        raise AeroMeshDomainError(
            "Signing-key encryption key cannot be read from the OS keyring.",
            ErrorCode.AMX_ERR_VAULT_KEY_MISSING,
            ExitCode.VAULT_KEY_MISSING,
        ) from exc
    if not key:
        if any(keys_dir().glob("*.key")):
            raise AeroMeshDomainError(
                "Signing-key encryption key is unavailable in the OS keyring; refusing to replace it.",
                ErrorCode.AMX_ERR_VAULT_KEY_MISSING,
                ExitCode.VAULT_KEY_MISSING,
            )
        key = Fernet.generate_key().decode()
        try:
            store.set(_ENCRYPTION_KEY_ID, key)
        except Exception as exc:
            raise AeroMeshDomainError(
                "A secure OS keyring is required to store signing keys.",
                ErrorCode.AMX_ERR_VAULT_KEY_MISSING,
                ExitCode.VAULT_KEY_MISSING,
            ) from exc
    return Fernet(key.encode())


def generate_and_store_keypair(name: str = DEFAULT_KEY_NAME) -> Tuple[Path, Path]:
    """Generate an Ed25519 keypair, encrypt the private key at rest, persist it."""
    kd = keys_dir()
    priv_path = confined_artifact_path(kd, name, ".key")
    pub_path = confined_artifact_path(kd, name, ".pub")
    if priv_path.exists() or pub_path.exists():
        raise AeroMeshDomainError(
            f"Signing key '{name}' already exists; choose a new key name.",
            ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
            ExitCode.SCHEMA_VIOLATION,
        )
    priv_pem, pub_pem = generate_keypair()
    encrypted = _fernet().encrypt(priv_pem)
    created = []
    try:
        for path, content in ((priv_path, encrypted), (pub_path, pub_pem)):
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created.append(path)
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return priv_path, pub_path


def load_private_key(name: str = DEFAULT_KEY_NAME) -> bytes:
    encrypted = confined_artifact_path(keys_dir(), name, ".key").read_bytes()
    return _fernet().decrypt(encrypted)


def load_public_key(name: str = DEFAULT_KEY_NAME) -> bytes:
    return confined_artifact_path(keys_dir(), name, ".pub").read_bytes()
