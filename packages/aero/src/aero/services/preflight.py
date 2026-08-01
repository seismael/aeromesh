"""Interactive Pre-Flight Engine: Model Provider Setup, Feasibility Audit, and Dynamic Requirement Fallback."""

import os
import json
from typing import Dict, Any, Optional, Callable, Tuple
from aero.domain.models import AgentManifest, CapabilityProviderRequirement
from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.domain.paths import get_aeromesh_config_file, get_aeromesh_credentials_file

SUPPORTED_PROVIDERS = [
    {
        "id": "deepseek",
        "name": "DeepSeek AI (DeepSeek-V3 / R1)",
        "env_var": "DEEPSEEK_API_KEY",
    },
    {
        "id": "anthropic",
        "name": "Anthropic Claude (Claude 3.7 Sonnet)",
        "env_var": "ANTHROPIC_API_KEY",
    },
    {"id": "openai", "name": "OpenAI (GPT-4o / o3-mini)", "env_var": "OPENAI_API_KEY"},
    {
        "id": "google",
        "name": "Google Gemini (Gemini 2.5 Pro)",
        "env_var": "GEMINI_API_KEY",
    },
]


class AeroInteractivePreflightEngine:
    """Manages pre-flight LLM provider selection, agent capability feasibility verification, and dynamic credential negotiation."""

    def __init__(
        self,
        config_file: Optional[str] = None,
        credentials_file: Optional[str] = None,
        provider_prompt_fn: Optional[Callable[[], Tuple[str, str]]] = None,
        requirement_prompt_fn: Optional[
            Callable[[str, str, str], Tuple[str, bool]]
        ] = None,
    ):
        self.config_file = str(config_file or get_aeromesh_config_file())
        self.credentials_file = str(credentials_file or get_aeromesh_credentials_file())
        self.provider_prompt_fn = provider_prompt_fn
        self.requirement_prompt_fn = requirement_prompt_fn

    def _load_json(self, path: str) -> Dict[str, Any]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_json(self, path: str, data: Dict[str, Any]):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_configured_providers(self) -> Dict[str, Any]:
        """Returns current config containing default provider and keys."""
        config = self._load_json(self.config_file)
        return {
            "default_provider": config.get("default_provider"),
            "providers": config.get("providers", {}),
        }

    def ensure_default_provider(self, non_interactive: bool = False) -> Tuple[str, str]:
        """Verifies that a default LLM provider and API key are configured. Prompts interactively if missing."""
        config = self._load_json(self.config_file)
        default_prov_id = config.get("default_provider")
        providers_dict = config.get("providers", {})

        if default_prov_id and default_prov_id in providers_dict:
            api_key = providers_dict[default_prov_id].get("api_key")
            if api_key:
                return default_prov_id, api_key

        # Check environment variables fallback
        for prov in SUPPORTED_PROVIDERS:
            env_val = os.environ.get(prov["env_var"])
            if env_val:
                config["default_provider"] = prov["id"]
                providers_dict[prov["id"]] = {"api_key": env_val}
                config["providers"] = providers_dict
                self._save_json(self.config_file, config)
                return prov["id"], env_val

        if non_interactive:
            raise AeroMeshDomainError(
                "No default LLM model provider or API key configured. Set DEEPSEEK_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY.",
                ErrorCode.AMX_ERR_VAULT_KEY_MISSING,
                ExitCode.VAULT_KEY_MISSING,
            )

        # Interactive Setup Call
        if self.provider_prompt_fn:
            selected_prov_id, api_key = self.provider_prompt_fn()
        else:
            from aero.presentation.ui import AeroTerminalUI

            selected_prov_id, api_key = AeroTerminalUI.prompt_provider_selection(
                SUPPORTED_PROVIDERS
            )

        if not selected_prov_id or not api_key:
            raise AeroMeshDomainError(
                "LLM provider setup aborted. An active model provider is required to run agents.",
                ErrorCode.AMX_ERR_VAULT_KEY_MISSING,
                ExitCode.VAULT_KEY_MISSING,
            )

        config["default_provider"] = selected_prov_id
        providers_dict[selected_prov_id] = {"api_key": api_key}
        config["providers"] = providers_dict
        self._save_json(self.config_file, config)

        return selected_prov_id, api_key

    def verify_agent_feasibility(
        self, manifest: AgentManifest, user_intent: str
    ) -> bool:
        """Verifies that the agent has valid tool declarations and schemas to fulfill intent BEFORE requesting keys."""
        if not manifest.identity or not manifest.identity.id:
            raise AeroMeshDomainError(
                "Agent feasibility check failed: missing identity.",
                ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                ExitCode.SCHEMA_VIOLATION,
            )

        # Check that agent has capability providers or tools defined
        if not manifest.providers and not manifest.capabilities:
            raise AeroMeshDomainError(
                f"Agent '{manifest.identity.id}' has no capability providers or tools to fulfill task.",
                ErrorCode.AMX_ERR_DISCOVERY_NO_MATCH,
                ExitCode.DISCOVERY_NO_MATCH,
            )

        return True

    def negotiate_requirement_with_fallback(
        self,
        provider_req: CapabilityProviderRequirement,
        existing_val: Optional[str],
        non_interactive: bool = False,
    ) -> Tuple[Optional[str], bool]:
        """Presents requirement upfront. If rejected, allows user to provide an alternative or attempt fallback."""
        key_id = provider_req.id
        kind = getattr(provider_req, "kind", "credential")

        if existing_val and non_interactive:
            return existing_val, True

        if not existing_val and non_interactive:
            raise AeroMeshDomainError(
                f"Required credential '{key_id}' missing in non-interactive session.",
                ErrorCode.AMX_ERR_VAULT_KEY_MISSING,
                ExitCode.VAULT_KEY_MISSING,
            )

        # Prompt user
        if self.requirement_prompt_fn:
            user_val, approved = self.requirement_prompt_fn(
                key_id, existing_val or "", kind
            )
        else:
            from aero.presentation.ui import AeroTerminalUI

            user_val, approved = AeroTerminalUI.prompt_credential_approval(
                key_id, existing_val, kind
            )

        if approved and user_val:
            return user_val, True

        # User rejected requirement: Return None to trigger fallback negotiation
        return None, False
