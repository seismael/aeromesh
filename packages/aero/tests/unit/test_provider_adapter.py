"""Unit tests for CognitiveProviderAdapter multi-provider API resolution engine."""

import os
import pytest
from aero.infrastructure.providers import CognitiveProviderAdapter, ProviderConfig
from aero.domain.errors import AeroMeshDomainError

def test_provider_config_dataclass():
    cfg = ProviderConfig(provider_id="deepseek", name="DeepSeek AI", api_key_env_var="DEEPSEEK_API_KEY", default_model="deepseek-chat")
    assert cfg.provider_id == "deepseek"
    assert cfg.name == "DeepSeek AI"
    assert cfg.api_key_env_var == "DEEPSEEK_API_KEY"
    assert cfg.default_model == "deepseek-chat"

def test_provider_adapter_detect_active_provider_from_credentials():
    credentials = {"DEEPSEEK_API_KEY": "sk-deepseek-test-key-123"}
    adapter = CognitiveProviderAdapter(credentials=credentials)
    
    assert adapter.active_provider_id == "deepseek"
    assert adapter.active_model == "deepseek-chat"

def test_provider_adapter_detect_anthropic_from_credentials():
    credentials = {"ANTHROPIC_API_KEY": "sk-ant-test-key-456"}
    adapter = CognitiveProviderAdapter(credentials=credentials)
    
    assert adapter.active_provider_id == "anthropic"
    assert adapter.active_model == "claude-3-5-sonnet-20241022"

def test_provider_adapter_offline_mode_returns_marker():
    adapter = CognitiveProviderAdapter(offline=True)
    response = adapter.complete_prompt("sys", "user")
    assert "[offline]" in response


def test_provider_adapter_missing_key_raises(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    adapter = CognitiveProviderAdapter(offline=False)
    with pytest.raises(AeroMeshDomainError) as exc:
        adapter.complete_prompt("sys", "user")
    assert exc.value.error_code.value == "AMX_ERR_VAULT_KEY_MISSING"


def test_provider_adapter_real_key_calls_api_by_default(monkeypatch):
    import urllib.request

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"choices":[{"message":{"content":"REAL ANSWER"}}]}'

    monkeypatch.setattr(
        urllib.request, "urlopen", lambda req, timeout=None: FakeResp()
    )
    adapter = CognitiveProviderAdapter(
        credentials={"DEEPSEEK_API_KEY": "sk-abc123"}, offline=False
    )
    response = adapter.complete_prompt("system", "user")
    assert response == "REAL ANSWER"


def test_provider_adapter_egress_goes_through_sandbox(monkeypatch):
    from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode

    adapter = CognitiveProviderAdapter(
        credentials={"DEEPSEEK_API_KEY": "sk-abc123"}, offline=False
    )
    calls = []

    def fake_validate(url):
        calls.append(url)
        raise AeroMeshDomainError(
            "blocked", ErrorCode.AMX_ERR_DOMAIN_BLOCKED, ExitCode.DOMAIN_BLOCKED
        )

    monkeypatch.setattr(adapter.sandbox, "validate_network_request", fake_validate)
    with pytest.raises(AeroMeshDomainError):
        adapter.complete_prompt("system", "user")

    assert calls and "api.deepseek.com" in calls[0]
