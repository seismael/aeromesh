"""Tests for SecureCredentialStore (encrypted OS-keyring storage)."""

import pytest

from aero.infrastructure.credential_store import SecureCredentialStore


class FakeBackend:
    def __init__(self):
        self.data = {}

    def set_password(self, service, key, value):
        self.data[(service, key)] = value

    def get_password(self, service, key):
        return self.data.get((service, key))

    def delete_password(self, service, key):
        self.data.pop((service, key), None)


def test_secure_credential_store_roundtrip():
    store = SecureCredentialStore(backend=FakeBackend())
    store.set("API_KEY", "secret-value")
    assert store.get("API_KEY") == "secret-value"

    store.delete("API_KEY")
    assert store.get("API_KEY") is None


def test_strict_read_distinguishes_unavailable_from_missing():
    class UnavailableBackend:
        def get_password(self, service, key):
            raise RuntimeError("locked keyring")

    store = SecureCredentialStore(backend=UnavailableBackend())
    assert store.get("key") is None
    with pytest.raises(RuntimeError, match="locked"):
        store.get_strict("key")
    assert SecureCredentialStore(backend=FakeBackend()).get_strict("missing") is None
