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
