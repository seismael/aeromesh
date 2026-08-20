"""Ed25519 manifest attestation: canonical signing, verification, and trust."""

import base64
import hashlib
import json
from typing import Any, Dict, Tuple

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ALGORITHM = "ed25519"


def canonicalize(data: Dict[str, Any]) -> bytes:
    """Deterministic, order-independent JSON serialization used for signing."""
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_hex(raw: bytes) -> str:
    """Hex SHA-256 digest of raw bytes."""
    return hashlib.sha256(raw).hexdigest()


def generate_keypair() -> Tuple[bytes, bytes]:
    """Generate an Ed25519 keypair, returning (private_pem, public_pem)."""
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return priv_pem, pub_pem


def sign_bytes(private_key_pem: bytes, data: bytes) -> bytes:
    """Produce a raw Ed25519 signature over ``data`` using a PEM private key."""
    priv = serialization.load_pem_private_key(private_key_pem, password=None)
    return priv.sign(data)


def verify_bytes(public_key_pem: bytes, data: bytes, signature: bytes) -> bool:
    """Verify a raw Ed25519 signature. Returns False on mismatch instead of raising."""
    pub = serialization.load_pem_public_key(public_key_pem)
    try:
        pub.verify(signature, data)
        return True
    except Exception:
        return False


def sign_manifest_dict(manifest: Dict[str, Any], private_key_pem: bytes) -> Dict[str, Any]:
    """Sign a manifest dict, returning a self-describing attestation object."""
    raw = canonicalize(manifest)
    priv = serialization.load_pem_private_key(private_key_pem, password=None)
    pub_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    sig = priv.sign(raw)
    return {
        "algorithm": ALGORITHM,
        "sha256": sha256_hex(raw),
        "public_key": pub_pem.decode(),
        "signature": base64.b64encode(sig).decode(),
    }


def verify_manifest_dict(manifest: Dict[str, Any], attestation: Dict[str, Any]) -> bool:
    """Cryptographically verify an attestation against the manifest content."""
    try:
        signature = base64.b64decode(attestation["signature"])
    except (KeyError, ValueError):
        return False
    raw = canonicalize(manifest)
    if sha256_hex(raw) != attestation.get("sha256"):
        return False
    return verify_bytes(attestation["public_key"].encode(), raw, signature)


def _normalize_pem(text: str) -> str:
    """Normalize PEM text for comparison (tolerate LF vs CRLF line endings)."""
    return text.replace("\r\n", "\n").strip()


def verify_manifest_trusted(
    manifest: Dict[str, Any],
    attestation: Dict[str, Any],
    trusted_public_key_pem: bytes,
) -> bool:
    """Verify both the signature AND that it was produced by a specific trusted key."""
    if _normalize_pem(attestation.get("public_key", "")) != _normalize_pem(
        trusted_public_key_pem.decode()
    ):
        return False
    return verify_manifest_dict(manifest, attestation)
