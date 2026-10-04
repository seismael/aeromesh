"""Resolve declared credentials from explicit inputs, environment, or OS keyring."""

import os
from typing import Callable, Dict, List, Optional, Tuple

from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.domain.models import CapabilityProviderRequirement
from aero.infrastructure.credential_store import SecureCredentialStore


class ZeroTrustVaultResolver:
    """Resolve only requested credentials, requiring approval in interactive use."""

    def __init__(
        self,
        override_env: Optional[Dict[str, str]] = None,
        prompt_fn: Optional[Callable[[str, str], str]] = None,
        approval_fn: Optional[Callable[[str, str, str], Tuple[str, bool]]] = None,
        store: Optional[SecureCredentialStore] = None,
    ):
        self.override_env = dict(override_env or {})
        self.prompt_fn = prompt_fn
        self.approval_fn = approval_fn
        self.store = store if store is not None else SecureCredentialStore()

    @staticmethod
    def _error(message: str) -> AeroMeshDomainError:
        return AeroMeshDomainError(
            message,
            ErrorCode.AMX_ERR_VAULT_KEY_MISSING,
            ExitCode.VAULT_KEY_MISSING,
        )

    def _save_credential(self, key_id: str, value: str) -> None:
        """Persist only in the OS keyring; never downgrade storage silently."""
        try:
            self.store.set(key_id, value)
        except Exception as exc:
            raise self._error(
                "OS keyring unavailable; credential was not persisted. Configure a secure keyring or supply it through the environment."
            ) from exc

    def _existing_credential(self, key_id: str) -> Optional[str]:
        explicit = self.override_env.get(key_id) or os.environ.get(key_id)
        if explicit:
            return explicit
        try:
            return self.store.get(key_id)
        except Exception as exc:
            raise self._error(
                "OS keyring unavailable; unlock or configure it, or supply the required credential through the environment."
            ) from exc

    def resolve_requirements(
        self,
        providers: List[CapabilityProviderRequirement],
        non_interactive: bool = False,
    ) -> Dict[str, str]:
        resolved_secrets = {}
        for provider in providers:
            if provider.type != "credential" or provider.id in resolved_secrets:
                continue
            key_id = provider.id
            kind = provider.kind or "credential"
            existing_val = self._existing_credential(key_id)

            if existing_val:
                if non_interactive:
                    resolved_secrets[key_id] = existing_val
                    continue
                if self.approval_fn:
                    approved_val, is_approved = self.approval_fn(
                        key_id, existing_val, kind
                    )
                else:
                    from aero.presentation.ui import AeroTerminalUI

                    approved_val, is_approved = AeroTerminalUI.prompt_credential_approval(
                        key_id, existing_val, kind
                    )
                if not is_approved or not approved_val:
                    raise self._error(
                        f"Required credential '{key_id}' was rejected by user."
                    )
                if approved_val != existing_val:
                    self._save_credential(key_id, approved_val)
                resolved_secrets[key_id] = approved_val
                continue

            if non_interactive:
                raise self._error(
                    f"Required vault credential '{key_id}' missing in non-interactive session."
                )
            if self.prompt_fn:
                secret_val = self.prompt_fn(key_id, kind)
            else:
                from aero.presentation.ui import AeroTerminalUI

                secret_val = AeroTerminalUI.prompt_missing_credential(key_id, kind)
            if not secret_val:
                raise self._error(
                    f"Required vault credential '{key_id}' was not provided."
                )
            self._save_credential(key_id, secret_val)
            resolved_secrets[key_id] = secret_val

        return resolved_secrets
