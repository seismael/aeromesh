"""Trust service: sign manifests, verify them, and gate installs on trusted keys."""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from aero.domain import paths
from aero.infrastructure import keystore
from aero.infrastructure.attestation import (
    public_key_fingerprint,
    sign_manifest_dict,
    verify_manifest_dict,
    verify_manifest_trusted,
)

SIG_SUFFIX = ".sig"


def generate_and_store_keypair(name: str = keystore.DEFAULT_KEY_NAME) -> Tuple[Path, Path]:
    return keystore.generate_and_store_keypair(name)


def _sidecar_path(manifest_path: str) -> Path:
    p = Path(manifest_path)
    return p.with_suffix(p.suffix + SIG_SUFFIX)


def _load_manifest(manifest_path: str) -> Dict[str, Any]:
    return json.loads(Path(manifest_path).read_text(encoding="utf-8"))


def sign_manifest_file(manifest_path: str, key_name: str = keystore.DEFAULT_KEY_NAME) -> Dict[str, Any]:
    """Sign a manifest and write a `<manifest>.sig` sidecar attestation."""
    data = _load_manifest(manifest_path)
    priv = keystore.load_private_key(key_name)
    attestation = sign_manifest_dict(data, priv)
    _sidecar_path(manifest_path).write_text(
        json.dumps(attestation, indent=2), encoding="utf-8"
    )
    return attestation


def load_attestation(manifest_path: str) -> Optional[Dict[str, Any]]:
    sp = _sidecar_path(manifest_path)
    if not sp.exists():
        return None
    return json.loads(sp.read_text(encoding="utf-8"))


def verify_manifest_file(manifest_path: str) -> Tuple[bool, str]:
    """Verify a manifest against its sidecar attestation (signature + sha256)."""
    attestation = load_attestation(manifest_path)
    if attestation is None:
        return False, "no attestation sidecar found"
    data = _load_manifest(manifest_path)
    if verify_manifest_dict(data, attestation):
        return True, "signature valid"
    return False, "signature invalid or manifest tampered"


def trusted_public_key(agent_id: str) -> Optional[bytes]:
    p = paths.get_aeromesh_workspace_trusted_dir() / f"{agent_id}.pub"
    if p.exists():
        return p.read_bytes()
    return None


def is_revoked(agent_id: str) -> bool:
    """True if the agent's trusted key has been revoked."""
    pub = trusted_public_key(agent_id)
    if pub is None:
        return False
    fp = public_key_fingerprint(pub)
    marker = paths.get_aeromesh_workspace_revoked_dir() / fp
    return marker.exists()


def revoke_key(agent_id: str) -> bool:
    """Revoke the trusted signing key for an agent (records its fingerprint)."""
    pub = trusted_public_key(agent_id)
    if pub is None:
        return False
    fp = public_key_fingerprint(pub)
    rev_dir = paths.get_aeromesh_workspace_revoked_dir()
    rev_dir.mkdir(parents=True, exist_ok=True)
    (rev_dir / fp).touch()
    return True


def verify_manifest_trusted_file(manifest_path: str, agent_id: str) -> Tuple[bool, str]:
    """Verify a manifest's signature AND that it was signed by a trusted, non-revoked key."""
    if is_revoked(agent_id):
        return False, f"trusted key for '{agent_id}' has been REVOKED"
    pub = trusted_public_key(agent_id)
    if pub is None:
        return False, f"no trusted public key for '{agent_id}'"
    attestation = load_attestation(manifest_path)
    if attestation is None:
        return False, "no attestation sidecar found"
    data = _load_manifest(manifest_path)
    if verify_manifest_trusted(data, attestation, pub):
        return True, "verified against trusted key"
    return False, "signature not from trusted key or manifest tampered"


def verify_workflow_references(workflow: Any) -> Tuple[bool, str]:
    """Recursive trust: every agent a workflow references must be verified.

    A workflow is runnable only when (1) the workflow's own signature is trusted
    and (2) each referenced agent resolves to a signed, trusted, non-revoked
    manifest. This composes a verified workflow out of verified agents.
    """
    agent_ids: list = []
    seen = set()
    for step in workflow.steps:
        if step.agent_id not in seen:
            seen.add(step.agent_id)
            agent_ids.append(step.agent_id)

    for agent_id in agent_ids:
        resolved = paths.resolve_agent_manifest_path(agent_id)
        if resolved is None:
            return False, f"referenced agent '{agent_id}' not found"
        if is_revoked(agent_id):
            return False, f"referenced agent '{agent_id}' has a REVOKED key"
        if trusted_public_key(agent_id) is None:
            return False, f"referenced agent '{agent_id}' has no trusted key"
        ok, reason = verify_manifest_trusted_file(str(resolved), agent_id)
        if not ok:
            return False, f"referenced agent '{agent_id}' not verified: {reason}"
    return True, f"all {len(agent_ids)} referenced agents verified"
