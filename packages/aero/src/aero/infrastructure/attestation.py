"""Ed25519 manifest attestation: canonical signing, verification, and trust."""

import base64
import hashlib
import json
from typing import Any, Dict, Tuple

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm

ALGORITHM = "ed25519"


def canonicalize(data: Dict[str, Any]) -> bytes:
    """Deterministic, order-independent JSON serialization used for signing."""
    if not isinstance(data, dict):
        raise ValueError("A signed manifest must be a JSON object")
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha256_hex(raw: bytes) -> str:
    """Hex SHA-256 digest of raw bytes."""
    return hashlib.sha256(raw).hexdigest()


def public_key_fingerprint(public_key_pem: bytes) -> str:
    """Stable SHA-256 fingerprint of a public key (for revocation lookup)."""
    public = serialization.load_pem_public_key(public_key_pem)
    if not isinstance(public, Ed25519PublicKey):
        raise ValueError("Only Ed25519 public keys are supported")
    return sha256_hex(
        public.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    )


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
    if not isinstance(priv, Ed25519PrivateKey):
        raise ValueError("Only Ed25519 signing keys are supported")
    return priv.sign(data)


def verify_bytes(public_key_pem: bytes, data: bytes, signature: bytes) -> bool:
    """Verify a raw Ed25519 signature. Returns False on mismatch instead of raising."""
    try:
        pub = serialization.load_pem_public_key(public_key_pem)
        if not isinstance(pub, Ed25519PublicKey):
            return False
        pub.verify(signature, data)
        return True
    except (InvalidSignature, UnsupportedAlgorithm, ValueError, TypeError):
        return False


def sign_manifest_dict(
    manifest: Dict[str, Any], private_key_pem: bytes
) -> Dict[str, Any]:
    """Sign a manifest dict, returning a self-describing attestation object."""
    raw = canonicalize(manifest)
    priv = serialization.load_pem_private_key(private_key_pem, password=None)
    if not isinstance(priv, Ed25519PrivateKey):
        raise ValueError("Only Ed25519 signing keys are supported")
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
        if (
            not isinstance(attestation, dict)
            or attestation.get("algorithm") != ALGORITHM
        ):
            return False
        signature = base64.b64decode(attestation["signature"], validate=True)
        if len(signature) != 64 or not isinstance(attestation["public_key"], str):
            return False
        raw = canonicalize(manifest)
        if sha256_hex(raw) != attestation.get("sha256"):
            return False
        return verify_bytes(attestation["public_key"].encode(), raw, signature)
    except (KeyError, ValueError, TypeError, AttributeError):
        return False


def verify_manifest_trusted(
    manifest: Dict[str, Any],
    attestation: Dict[str, Any],
    trusted_public_key_pem: bytes,
) -> bool:
    """Verify both the signature AND that it was produced by a specific trusted key."""
    try:
        if public_key_fingerprint(
            attestation["public_key"].encode()
        ) != public_key_fingerprint(trusted_public_key_pem):
            return False
    except (KeyError, ValueError, TypeError, AttributeError, UnsupportedAlgorithm):
        return False
    return verify_manifest_dict(manifest, attestation)
