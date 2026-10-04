"""Ed25519 signing keys encrypted using an OS-keyring-held encryption key."""

import os
from contextlib import contextmanager
import re
import secrets
from pathlib import Path
from typing import Tuple

from cryptography.fernet import Fernet

from aero.domain.paths import get_aeromesh_home, confined_artifact_path
from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.infrastructure.attestation import generate_keypair
from aero.infrastructure.credential_store import SecureCredentialStore
from aero.infrastructure.file_lock import FileLockUnavailable, exclusive_file_lock

DEFAULT_KEY_NAME = "default"

def _encryption_key_id() -> str:
    """Non-secret identity moves with the key store; caller holds its lock."""
    directory = keys_dir()
    identity_path = directory / "store-id"
    if identity_path.exists():
        store_id = identity_path.read_text(encoding="ascii").strip()
        if re.fullmatch(r"[0-9a-f]{32}", store_id) is None:
            raise AeroMeshDomainError(
                "Signing-key store identity is invalid.",
                ErrorCode.AMX_ERR_VAULT_KEY_MISSING,
                ExitCode.VAULT_KEY_MISSING,
            )
    else:
        if any(directory.glob("*.key")):
            raise AeroMeshDomainError(
                "Signing-key store identity is missing; restore it with the encrypted signing keys.",
                ErrorCode.AMX_ERR_VAULT_KEY_MISSING,
                ExitCode.VAULT_KEY_MISSING,
            )
        store_id = secrets.token_hex(16)
        fd = os.open(identity_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as stream:
            stream.write(store_id + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    return f"aeromesh/signing-key-encryption/{store_id}"


@contextmanager
def _key_store_lock():
    try:
        with exclusive_file_lock(keys_dir() / ".lock", timeout=30):
            yield
    except FileLockUnavailable as exc:
        raise AeroMeshDomainError(
            "Signing key storage is busy; retry when the active operation completes.",
            ErrorCode.AMX_ERR_VAULT_KEY_MISSING,
            ExitCode.VAULT_KEY_MISSING,
        ) from exc


def keys_dir() -> Path:
    """Directory holding local Ed25519 keypairs under ~/.aeromesh/keys."""
    d = get_aeromesh_home() / "keys"
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    return d


def _fernet(store: SecureCredentialStore = None) -> Fernet:
    """Fernet using a key held in the OS keyring (encrypted at rest)."""
    store = store or SecureCredentialStore()
    key_id = _encryption_key_id()
    try:
        key = store.get(key_id)
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
            store.set(key_id, key)
        except Exception as exc:
            raise AeroMeshDomainError(
                "A secure OS keyring is required to store signing keys.",
                ErrorCode.AMX_ERR_VAULT_KEY_MISSING,
                ExitCode.VAULT_KEY_MISSING,
            ) from exc
    return Fernet(key.encode())


def generate_and_store_keypair(name: str = DEFAULT_KEY_NAME) -> Tuple[Path, Path]:
    """Generate an Ed25519 keypair, encrypt the private key at rest, persist it."""
    with _key_store_lock():
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
    with _key_store_lock():
        encrypted = confined_artifact_path(keys_dir(), name, ".key").read_bytes()
        return _fernet().decrypt(encrypted)


def load_public_key(name: str = DEFAULT_KEY_NAME) -> bytes:
    return confined_artifact_path(keys_dir(), name, ".pub").read_bytes()
