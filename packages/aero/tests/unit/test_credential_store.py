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


def test_read_distinguishes_unavailable_from_missing():
    class UnavailableBackend:
        def get_password(self, service, key):
            raise RuntimeError("locked keyring")

    store = SecureCredentialStore(backend=UnavailableBackend())
    with pytest.raises(RuntimeError, match="locked"):
        store.get("key")
    assert SecureCredentialStore(backend=FakeBackend()).get("missing") is None


def test_delete_failure_is_visible():
    class UnavailableBackend:
        def delete_password(self, service, key):
            raise RuntimeError("locked keyring")

    with pytest.raises(RuntimeError, match="locked keyring"):
        SecureCredentialStore(backend=UnavailableBackend()).delete("key")


def test_plaintext_and_unknown_keyring_backends_are_rejected():
    from aero.infrastructure.credential_store import _select_os_backend

    plaintext = type("PlaintextKeyring", (), {"__module__": "keyrings.alt.file"})()
    with pytest.raises(RuntimeError, match="supported OS keyring"):
        _select_os_backend(plaintext)
    with pytest.raises(RuntimeError, match="supported OS keyring"):
        _select_os_backend(FakeBackend())


def test_chainer_selects_one_supported_os_backend_without_plaintext_fallback():
    from aero.infrastructure.credential_store import _select_os_backend

    plaintext = type("PlaintextKeyring", (), {"__module__": "keyrings.alt.file"})()
    native = type("Keyring", (), {"__module__": "keyring.backends.SecretService"})()
    chain = type(
        "ChainerBackend", (),
        {"__module__": "keyring.backends.chainer", "backends": [plaintext, native]},
    )()
    assert _select_os_backend(chain) is native
    chain.backends = [plaintext]
    with pytest.raises(RuntimeError, match="supported OS keyring"):
        _select_os_backend(chain)


def test_os_backend_is_resolved_only_on_storage_access(monkeypatch):
    from aero.infrastructure import credential_store

    def unavailable():
        raise RuntimeError("OS keyring unavailable")

    monkeypatch.setattr(credential_store, "_load_os_backend", unavailable)
    store = SecureCredentialStore()
    with pytest.raises(RuntimeError, match="OS keyring unavailable"):
        store.get("key")
