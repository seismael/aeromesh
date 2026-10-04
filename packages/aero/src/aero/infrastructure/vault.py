"""Zero-Trust Secure Vault Resolver Infrastructure Adapter."""

import os
import json
from pathlib import Path
from typing import Dict, List, Union, Callable, Tuple
from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.domain.models import CapabilityProviderRequirement
from aero.domain.paths import (
    get_aeromesh_home,
)
from aero.infrastructure.credential_store import SecureCredentialStore


class ZeroTrustVaultResolver:
    """Resolves secret credentials for manifest requirements across Vault layers with Explicit User Approval."""

    def __init__(
        self,
        override_env: Dict[str, str] = None,
        config_dir: Union[str, Path] = None,
        prompt_fn: Callable[[str, str], str] = None,
        approval_fn: Callable[[str, str, str], Tuple[str, bool]] = None,
        store: SecureCredentialStore = None,
        allow_legacy_plaintext: bool = False,
    ):
        self.override_env = override_env or {}
        self.config_dir = Path(config_dir) if config_dir else get_aeromesh_home()
        self.config_file = self.config_dir / "config.json"
        self.credentials_file = self.config_dir / "credentials.json"
        self.prompt_fn = prompt_fn
        self.approval_fn = approval_fn
        self.store = store or SecureCredentialStore()
        self.allow_legacy_plaintext = allow_legacy_plaintext

    def _load_json_file(self, fpath: Path) -> Dict[str, str]:
        if fpath.exists():
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return {
                            key: value
                            for key, value in data.items()
                            if isinstance(value, str)
                        }
            except Exception:
                pass
        return {}

    def _save_credential(self, key_id: str, value: str) -> None:
        """Persist only in the OS keyring; never downgrade storage silently."""
        try:
            self.store.set(key_id, value)
        except Exception as exc:
            raise AeroMeshDomainError(
                "OS keyring unavailable; credential was not persisted. Configure a secure keyring or supply it through the environment.",
                ErrorCode.AMX_ERR_VAULT_KEY_MISSING,
                ExitCode.VAULT_KEY_MISSING,
            ) from exc

    def resolve_requirements(
        self,
        providers: List[CapabilityProviderRequirement],
        non_interactive: bool = False,
    ) -> Dict[str, str]:
        resolved_secrets = {}
        requested = [
            provider for provider in providers if provider.type == "credential"
        ]
        if not requested:
            return resolved_secrets
        # Legacy reads require explicit caller opt-in; desktop harvesting is removed.
        config_secrets = (
            self._load_json_file(self.config_file)
            if self.allow_legacy_plaintext
            else {}
        )
        vault_secrets = (
            self._load_json_file(self.credentials_file)
            if self.allow_legacy_plaintext
            else {}
        )

        for provider in requested:
            if provider.type == "credential":
                key_id = provider.id
                kind = getattr(provider, "kind", "credential")

                # Check for existing discovered value (keyring first, then legacy files)
                existing_val = (
                    self.override_env.get(key_id)
                    or os.environ.get(key_id)
                    or self.store.get(key_id)
                    or vault_secrets.get(key_id)
                    or config_secrets.get(key_id)
                )

                if existing_val:
                    if non_interactive:
                        # Automated non-interactive session (CI/CD)
                        resolved_secrets[key_id] = existing_val
                    else:
                        # Interactive human session: REQUIRE EXPLICIT USER APPROVAL
                        if self.approval_fn:
                            approved_val, is_approved = self.approval_fn(
                                key_id, existing_val, kind
                            )
                        else:
                            from aero.presentation.ui import AeroTerminalUI

                            approved_val, is_approved = (
                                AeroTerminalUI.prompt_credential_approval(
                                    key_id, existing_val, kind
                                )
                            )

                        if not is_approved or not approved_val:
                            raise AeroMeshDomainError(
                                f"Required credential '{key_id}' was rejected by user.",
                                ErrorCode.AMX_ERR_VAULT_KEY_MISSING,
                                ExitCode.VAULT_KEY_MISSING,
                            )
                        resolved_secrets[key_id] = approved_val
                        if approved_val != existing_val:
                            self._save_credential(key_id, approved_val)
                else:
                    if non_interactive:
                        raise AeroMeshDomainError(
                            f"Required vault credential '{key_id}' missing in non-interactive session.",
                            ErrorCode.AMX_ERR_VAULT_KEY_MISSING,
                            ExitCode.VAULT_KEY_MISSING,
                        )
                    else:
                        # Interactive human prompting for missing key
                        if self.prompt_fn:
                            secret_val = self.prompt_fn(key_id, kind)
                        else:
                            from aero.presentation.ui import AeroTerminalUI

                            secret_val = AeroTerminalUI.prompt_missing_credential(
                                key_id, kind
                            )

                        if not secret_val:
                            raise AeroMeshDomainError(
                                f"Required vault credential '{key_id}' was not provided.",
                                ErrorCode.AMX_ERR_VAULT_KEY_MISSING,
                                ExitCode.VAULT_KEY_MISSING,
                            )
                        # Persist only after secure storage succeeds.
                        self._save_credential(key_id, secret_val)
                        resolved_secrets[key_id] = secret_val

        return resolved_secrets
