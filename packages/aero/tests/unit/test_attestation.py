"""Tests for Ed25519 manifest attestation (sign/verify/trust)."""

import json
import base64
import pytest

from aero.infrastructure.attestation import (
    canonicalize,
    generate_keypair,
    sign_bytes,
    verify_bytes,
    sign_manifest_dict,
    verify_manifest_dict,
    verify_manifest_trusted,
)


def test_canonicalize_is_stable_and_order_independent():
    a = {"b": 1, "a": 2, "c": [3, 2, 1]}
    b = {"c": [3, 2, 1], "a": 2, "b": 1}
    assert canonicalize(a) == canonicalize(b)
    # Should be compact, sorted-key JSON
    assert canonicalize({"a": 1, "b": "x"}) == b'{"a":1,"b":"x"}'


def test_generate_keypair_sign_verify_roundtrip():
    priv_pem, pub_pem = generate_keypair()
    data = b"hello manifest"
    sig = sign_bytes(priv_pem, data)
    assert verify_bytes(pub_pem, data, sig) is True


def test_verify_bytes_rejects_tampered_data():
    priv_pem, pub_pem = generate_keypair()
    sig = sign_bytes(priv_pem, b"original")
    assert verify_bytes(pub_pem, b"tampered", sig) is False


def test_sign_and_verify_manifest_roundtrip():
    priv_pem, pub_pem = generate_keypair()
    manifest = {
        "manifest_version": "0.1.0",
        "identity": {"id": "demo", "name": "Demo", "version": "0.1.0"},
    }
    attestation = sign_manifest_dict(manifest, priv_pem)
    assert attestation["algorithm"] == "ed25519"
    assert attestation["public_key"] == pub_pem.decode()
    assert verify_manifest_dict(manifest, attestation) is True


def test_verify_manifest_rejects_tampered_manifest():
    priv_pem, _ = generate_keypair()
    manifest = {"identity": {"id": "demo"}}
    attestation = sign_manifest_dict(manifest, priv_pem)
    # Tamper with the manifest content
    tampered = {"identity": {"id": "evil"}}
    assert verify_manifest_dict(tampered, attestation) is False


def test_verify_manifest_trusted_rejects_wrong_signer():
    priv_pem, _ = generate_keypair()
    _, other_pub_pem = generate_keypair()
    manifest = {"identity": {"id": "demo"}}
    attestation = sign_manifest_dict(manifest, priv_pem)
    # Signature is valid but the signer is not the trusted key
    assert verify_manifest_trusted(manifest, attestation, other_pub_pem) is False
