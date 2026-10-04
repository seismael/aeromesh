"""Sign artifacts and authorize their exact content against user-approved keys."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from cryptography.exceptions import UnsupportedAlgorithm

from aero.domain import paths
from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.infrastructure import keystore
from aero.infrastructure.attestation import (
    public_key_fingerprint,
    sign_manifest_dict,
    verify_manifest_dict,
    verify_manifest_trusted,
)

SIG_SUFFIX = ".sig"


def _error(message: str) -> AeroMeshDomainError:
    return AeroMeshDomainError(
        message, ErrorCode.AMX_ERR_SCHEMA_VIOLATION, ExitCode.SCHEMA_VIOLATION
    )


def _trust_error(message: str) -> AeroMeshDomainError:
    return AeroMeshDomainError(
        message, ErrorCode.AMX_ERR_TRUST_VIOLATION, ExitCode.TRUST_VIOLATION
    )


def atomic_write(path: Path, content: bytes) -> None:
    """Publish a complete file with restrictive permissions using atomic replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def generate_and_store_keypair(
    name: str = keystore.DEFAULT_KEY_NAME,
) -> Tuple[Path, Path]:
    return keystore.generate_and_store_keypair(name)


def _sidecar_path(manifest_path: str) -> Path:
    p = Path(manifest_path)
    return p.with_suffix(p.suffix + SIG_SUFFIX)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key '{key}'")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f"Non-finite JSON value '{value}' is not supported")


def _load_manifest(manifest_path: str) -> Dict[str, Any]:
    data = json.loads(
        Path(manifest_path).read_text(encoding="utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=_invalid_constant,
    )
    if not isinstance(data, dict):
        raise ValueError("Artifact must contain a JSON object")
    return data


def sign_manifest_file(
    manifest_path: str, key_name: str = keystore.DEFAULT_KEY_NAME
) -> Dict[str, Any]:
    """Sign content; authoring a signature never approves its signer locally."""
    data = _load_manifest(manifest_path)
    attestation = sign_manifest_dict(data, keystore.load_private_key(key_name))
    atomic_write(
        _sidecar_path(manifest_path), json.dumps(attestation, indent=2).encode()
    )
    return attestation


def load_attestation(manifest_path: str) -> Optional[Dict[str, Any]]:
    sp = _sidecar_path(manifest_path)
    if not sp.exists():
        return None
    return _load_manifest(sp)


def install_attestation(source_path: str, target_path: str) -> None:
    """Atomically copy a sidecar; unsigned replacement removes stale evidence."""
    src, target = _sidecar_path(source_path), _sidecar_path(target_path)
    if src.exists():
        atomic_write(target, src.read_bytes())
    elif target.exists():
        target.unlink()


def verify_manifest_file(manifest_path: str) -> Tuple[bool, str]:
    """Check signature integrity only, without granting signer authorization."""
    try:
        attestation = load_attestation(manifest_path)
        if attestation is None:
            return False, "no attestation sidecar found"
        if verify_manifest_dict(_load_manifest(manifest_path), attestation):
            return True, "signature valid"
        return False, "signature invalid or manifest tampered"
    except (OSError, ValueError, TypeError, UnsupportedAlgorithm) as exc:
        return False, f"invalid artifact or attestation: {exc}"


def trusted_public_key(agent_id: str) -> Optional[bytes]:
    key_path = paths.confined_artifact_path(
        paths.get_aeromesh_trusted_dir(), agent_id, ".pub"
    )
    return key_path.read_bytes() if key_path.exists() else None


def trust_key(artifact_id: str, public_key_path: str) -> Path:
    """Explicitly approve an Ed25519 signer for one artifact identifier.

    Idempotent for the same key. A different key requires deliberate removal of
    the old approval; key import never silently replaces trust or unrevokes it.
    """
    target = paths.confined_artifact_path(
        paths.get_aeromesh_trusted_dir(), artifact_id, ".pub"
    )
    try:
        public = Path(public_key_path).read_bytes()
        fingerprint = public_key_fingerprint(public)
        if (paths.get_aeromesh_revoked_dir() / fingerprint).exists():
            raise _trust_error("This signing key has been REVOKED; approval refused.")
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if target.exists():
            if public_key_fingerprint(target.read_bytes()) != fingerprint:
                raise _trust_error(
                    f"A different signing key is already approved for '{artifact_id}'."
                )
            return target
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(public)
            stream.flush()
            os.fsync(stream.fileno())
        return target
    except (OSError, ValueError, TypeError, UnsupportedAlgorithm) as exc:
        raise _trust_error(f"Cannot approve signing key: {exc}") from exc


def is_revoked(agent_id: str) -> bool:
    public = trusted_public_key(agent_id)
    return (
        public is not None
        and (paths.get_aeromesh_revoked_dir() / public_key_fingerprint(public)).exists()
    )


def revoke_key(agent_id: str) -> bool:
    public = trusted_public_key(agent_id)
    if public is None:
        return False
    atomic_write(
        paths.get_aeromesh_revoked_dir() / public_key_fingerprint(public), b"revoked\n"
    )
    return True


def require_trusted_manifest(
    manifest_path: str, expected_id: Optional[str] = None
) -> Dict[str, Any]:
    """Return the exact verified JSON object or raise; callers must use this object.

    This does not re-read content after verification, validate an agent-specific
    schema, or infer approval from a key shipped beside an artifact.
    """
    try:
        data = _load_manifest(manifest_path)
        identity = data.get("identity")
        if not isinstance(identity, dict):
            raise _error("Artifact identity is missing or invalid.")
        artifact_id = paths.validate_artifact_id(identity.get("id"))
        if expected_id is not None:
            paths.validate_artifact_id(expected_id)
            if artifact_id != expected_id:
                raise _error(
                    f"Artifact identity '{artifact_id}' does not match expected identity '{expected_id}'."
                )
        try:
            public = trusted_public_key(artifact_id)
            fingerprint = public_key_fingerprint(public) if public is not None else None
        except (OSError, ValueError, TypeError, UnsupportedAlgorithm) as exc:
            raise _trust_error(
                f"Invalid or unavailable trusted signing key: {exc}"
            ) from exc
        if public is None:
            raise _trust_error(
                f"no trusted public key for '{artifact_id}'; explicitly approve its signer first"
            )
        if (paths.get_aeromesh_revoked_dir() / fingerprint).exists():
            raise _trust_error(f"trusted key for '{artifact_id}' has been REVOKED")
        try:
            signature = load_attestation(manifest_path)
        except (OSError, ValueError, TypeError) as exc:
            raise _trust_error(f"Invalid or unavailable attestation: {exc}") from exc
        if signature is None:
            raise _trust_error("no attestation sidecar found")
        if not verify_manifest_trusted(data, signature, public):
            raise _trust_error("signature not from trusted key or manifest tampered")
        return data
    except (OSError, ValueError, TypeError, UnsupportedAlgorithm) as exc:
        raise _error(f"Invalid artifact or signing key: {exc}") from exc


def verify_manifest_trusted_file(manifest_path: str, agent_id: str) -> Tuple[bool, str]:
    """Compatibility query; execution must use require_trusted_manifest's data."""
    try:
        require_trusted_manifest(manifest_path, agent_id)
        return True, "verified against trusted key"
    except AeroMeshDomainError as exc:
        return False, exc.message


def verify_workflow_references(workflow: Any) -> Tuple[bool, str]:
    """Verify every directly referenced agent by its confined registry identity."""
    agent_ids = dict.fromkeys(step.agent_id for step in workflow.steps)
    for agent_id in agent_ids:
        try:
            paths.validate_artifact_id(agent_id)
            resolved = paths.resolve_agent_manifest_path(agent_id)
            if resolved is None:
                return False, f"referenced agent '{agent_id}' not found"
            require_trusted_manifest(resolved, agent_id)
        except AeroMeshDomainError as exc:
            return False, f"referenced agent '{agent_id}' not verified: {exc.message}"
    return True, f"all {len(agent_ids)} referenced agents verified"
