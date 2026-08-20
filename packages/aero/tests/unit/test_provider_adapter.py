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

def test_provider_adapter_complete_prompt_fallback(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-mock-key")
    adapter = CognitiveProviderAdapter(credentials={"DEEPSEEK_API_KEY": "sk-mock-key"})
    
    response = adapter.complete_prompt(
        system_prompt="You are a PostgreSQL tuning DBA.",
        user_prompt="Optimize query SELECT * FROM orders;"
    )
    
    assert response is not None
    assert len(response) > 0
    assert "postgres" in response.lower() or "query" in response.lower() or "index" in response.lower() or "create" in response.lower()


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
    # A key without mock/test/fake markers must hit the real API path.
    adapter = CognitiveProviderAdapter(credentials={"DEEPSEEK_API_KEY": "sk-abc123"})
    response = adapter.complete_prompt("system", "user")
    assert response == "REAL ANSWER"
