"""Encrypted credential storage backed by the OS keyring."""

from typing import Any, Optional

SERVICE = "aeromesh"


class SecureCredentialStore:
    """Stores secrets in the OS keyring (encrypted at rest by the OS).

    A backend may be injected for deterministic tests; production uses the
    `keyring` library (Windows Credential Locker / macOS Keychain / Secret Service).

    When no keyring backend is available (e.g. a headless CI runner), reads return
    ``None`` (treated as "not found") and writes raise. Callers must not downgrade
    storage to a plaintext file.
    """

    def __init__(self, service: str = SERVICE, backend: Any = None):
        self.service = service
        if backend is not None:
            self._backend = backend
        else:
            try:
                import keyring  # lazy import to keep module import cheap

                self._backend = keyring
            except Exception:  # noqa: BLE001 — keyring not importable
                self._backend = None

    def set(self, key_id: str, value: str) -> None:
        if self._backend is None:
            raise RuntimeError("no OS keyring backend available")
        self._backend.set_password(self.service, key_id, value)

    def get(self, key_id: str) -> Optional[str]:
        if self._backend is None:
            return None
        try:
            return self._backend.get_password(self.service, key_id)
        except Exception:  # noqa: BLE001 — no backend → treat as "not found"
            return None

    def get_strict(self, key_id: str) -> Optional[str]:
        """For encryption keys, a locked backend must never mean 'create a key'."""
        if self._backend is None:
            raise RuntimeError("no OS keyring backend available")
        return self._backend.get_password(self.service, key_id)

    def delete(self, key_id: str) -> None:
        if self._backend is None:
            return
        try:
            self._backend.delete_password(self.service, key_id)
        except Exception:  # noqa: BLE001 — best-effort cleanup
            pass
