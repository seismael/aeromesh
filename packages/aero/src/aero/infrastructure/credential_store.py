"""Encrypted credential storage backed by the OS keyring."""

from typing import Any, Optional

SERVICE = "aeromesh"


class SecureCredentialStore:
    """Stores secrets in the OS keyring (encrypted at rest by the OS).

    A backend may be injected for deterministic tests; production uses the
    `keyring` library (Windows Credential Locker / macOS Keychain / Secret Service).
    """

    def __init__(self, service: str = SERVICE, backend: Any = None):
        self.service = service
        if backend is not None:
            self._backend = backend
        else:
            import keyring  # lazy import to keep module import cheap

            self._backend = keyring

    def set(self, key_id: str, value: str) -> None:
        self._backend.set_password(self.service, key_id, value)

    def get(self, key_id: str) -> Optional[str]:
        return self._backend.get_password(self.service, key_id)

    def delete(self, key_id: str) -> None:
        self._backend.delete_password(self.service, key_id)
