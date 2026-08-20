"""Live Model Provider API Binding for DeepSeek, Anthropic, OpenAI, and Gemini."""

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.infrastructure.sandbox import NetworkSandboxFirewall


@dataclass
class ProviderConfig:
    """Configuration specification for a model provider."""

    provider_id: str
    name: str
    api_key_env_var: str
    default_model: str
    base_url: Optional[str] = None


SUPPORTED_PROVIDERS: Dict[str, ProviderConfig] = {
    "deepseek": ProviderConfig(
        provider_id="deepseek",
        name="DeepSeek AI",
        api_key_env_var="DEEPSEEK_API_KEY",
        default_model="deepseek-chat",
        base_url="https://api.deepseek.com/v1/chat/completions",
    ),
    "anthropic": ProviderConfig(
        provider_id="anthropic",
        name="Anthropic Claude",
        api_key_env_var="ANTHROPIC_API_KEY",
        default_model="claude-3-5-sonnet-20241022",
        base_url="https://api.anthropic.com/v1/messages",
    ),
    "openai": ProviderConfig(
        provider_id="openai",
        name="OpenAI GPT",
        api_key_env_var="OPENAI_API_KEY",
        default_model="gpt-4o",
        base_url="https://api.openai.com/v1/chat/completions",
    ),
    "gemini": ProviderConfig(
        provider_id="gemini",
        name="Google Gemini",
        api_key_env_var="GEMINI_API_KEY",
        default_model="gemini-2.5-flash",
        base_url="https://generativelanguage.googleapis.com/v1beta/models",
    ),
}

OFFLINE_MARKER = "[offline] deterministic model response (AEROMESH_OFFLINE=1)"


class CognitiveProviderAdapter:
    """Binds a resolved model API key to a real LLM provider endpoint.

    There is no mock fallback: a real key makes a real call, and failures raise.
    ``offline=True`` (or ``AEROMESH_OFFLINE=1``) returns a clearly-marked
    deterministic placeholder for tests and CI only.
    """

    def __init__(
        self,
        credentials: Dict[str, str] = None,
        preferred_provider: str = None,
        offline: Optional[bool] = None,
    ):
        self.credentials = credentials or {}
        if offline is None:
            offline = os.environ.get("AEROMESH_OFFLINE") == "1"
        self.offline = offline

        self.active_provider_id, self.api_key = self._resolve_active_provider(
            preferred_provider
        )
        if self.active_provider_id is None:
            self.provider_config: Optional[ProviderConfig] = None
            self.active_model: Optional[str] = None
            self.sandbox = NetworkSandboxFirewall(allowed_domains=[])
        else:
            self.provider_config = SUPPORTED_PROVIDERS[self.active_provider_id]
            self.active_model = self.provider_config.default_model
            # Kernel egress is bounded to the provider's own endpoint.
            host = urlparse(self.provider_config.base_url).hostname or ""
            self.sandbox = NetworkSandboxFirewall(allowed_domains=[host] if host else [])

    def _resolve_active_provider(self, preferred: Optional[str]):
        if preferred and preferred in SUPPORTED_PROVIDERS:
            cfg = SUPPORTED_PROVIDERS[preferred]
            key = self.credentials.get(cfg.api_key_env_var) or os.environ.get(
                cfg.api_key_env_var, ""
            )
            if key:
                return preferred, key

        # Priority 1: explicit credentials dictionary
        for prov_id, cfg in SUPPORTED_PROVIDERS.items():
            if (
                cfg.api_key_env_var in self.credentials
                and self.credentials[cfg.api_key_env_var]
            ):
                return prov_id, self.credentials[cfg.api_key_env_var]

        # Priority 2: OS environment variables
        for prov_id, cfg in SUPPORTED_PROVIDERS.items():
            key = os.environ.get(cfg.api_key_env_var, "")
            if key:
                return prov_id, key

        return None, None

    def complete_prompt(
        self, system_prompt: str, user_prompt: str, tools: List[Any] = None
    ) -> str:
        """Send a prompt to the live provider and return its response (or raise)."""
        if self.offline:
            return OFFLINE_MARKER

        if not self.api_key:
            raise AeroMeshDomainError(
                "No LLM provider API key configured. Set DEEPSEEK_API_KEY, "
                "ANTHROPIC_API_KEY, OPENAI_API_KEY, or GEMINI_API_KEY.",
                ErrorCode.AMX_ERR_VAULT_KEY_MISSING,
                ExitCode.VAULT_KEY_MISSING,
            )

        try:
            if self.active_provider_id in ("deepseek", "openai"):
                return self._call_openai_compatible_api(system_prompt, user_prompt)
            elif self.active_provider_id == "anthropic":
                return self._call_anthropic_api(system_prompt, user_prompt)
            elif self.active_provider_id == "gemini":
                return self._call_gemini_api(system_prompt, user_prompt)
            raise AeroMeshDomainError(
                f"Unsupported provider '{self.active_provider_id}'.",
                ErrorCode.AMX_ERR_PROVIDER_FAILED,
                ExitCode.PROVIDER_FAILED,
            )
        except AeroMeshDomainError:
            raise
        except Exception as e:  # noqa: BLE001 — wrap network/API errors clearly
            raise AeroMeshDomainError(
                f"LLM provider call failed: {e}",
                ErrorCode.AMX_ERR_PROVIDER_FAILED,
                ExitCode.PROVIDER_FAILED,
            ) from e

    def _call_openai_compatible_api(self, system_prompt: str, user_prompt: str) -> str:
        url = self.provider_config.base_url
        self.sandbox.validate_network_request(url)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.active_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]

    def _call_anthropic_api(self, system_prompt: str, user_prompt: str) -> str:
        url = self.provider_config.base_url
        self.sandbox.validate_network_request(url)
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": self.active_model,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "max_tokens": 1024,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["content"][0]["text"]

    def _call_gemini_api(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self.provider_config.base_url}/{self.active_model}:generateContent"
        self.sandbox.validate_network_request(url)
        headers = {"Content-Type": "application/json"}
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        }
        # Gemini passes the API key as a query parameter, not a header.
        req = urllib.request.Request(
            f"{url}?key={self.api_key}",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["candidates"][0]["content"]["parts"][0]["text"]
