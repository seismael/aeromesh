"""Credential storage restricted to native OS keyring backends."""

from typing import Any, Optional

SERVICE = "aeromesh"
_OS_BACKENDS = {
    ("keyring.backends.Windows", "WinVaultKeyring"),
    ("keyring.backends.macOS", "Keyring"),
    ("keyring.backends.SecretService", "Keyring"),
    ("keyring.backends.libsecret", "Keyring"),
    ("keyring.backends.kwallet", "DBusKeyring"),
    ("keyring.backends.kwallet", "DBusKeyringKWallet4"),
}


def _select_os_backend(backend: Any) -> Any:
    identity = (type(backend).__module__, type(backend).__name__)
    if identity in _OS_BACKENDS:
        return backend
    if identity == ("keyring.backends.chainer", "ChainerBackend"):
        for candidate in backend.backends:
            candidate_identity = (type(candidate).__module__, type(candidate).__name__)
            if candidate_identity in _OS_BACKENDS:
                return candidate
    raise RuntimeError(
        "No supported OS keyring backend configured; use Windows Credential Locker, "
        "macOS Keychain, Secret Service/libsecret, or KWallet."
    )


def _load_os_backend() -> Any:
    import keyring

    return _select_os_backend(keyring.get_keyring())


class SecureCredentialStore:
    """Use one supported OS keyring; never fall back to file or plugin storage.

    Backend errors propagate so callers distinguish unavailable storage from an
    absent credential. Resolution is lazy: environment-only execution requires
    no keyring. An embedding application may explicitly inject a trusted backend;
    AeroMesh uses that seam for deterministic tests.
    """

    def __init__(self, service: str = SERVICE, backend: Any = None):
        self.service = service
        self._backend = backend

    def _storage(self) -> Any:
        if self._backend is None:
            self._backend = _load_os_backend()
        return self._backend

    def set(self, key_id: str, value: str) -> None:
        self._storage().set_password(self.service, key_id, value)

    def get(self, key_id: str) -> Optional[str]:
        """Read a credential; only a successful lookup can report it missing."""
        return self._storage().get_password(self.service, key_id)

    def delete(self, key_id: str) -> None:
        """Delete a credential and propagate failure to the caller."""
        self._storage().delete_password(self.service, key_id)
