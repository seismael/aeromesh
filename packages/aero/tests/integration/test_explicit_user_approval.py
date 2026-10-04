"""Integration tests for Explicit User Key Approval & Interactive Selection."""

import pytest
from aero.infrastructure.vault import ZeroTrustVaultResolver
from aero.domain.models import CapabilityProviderRequirement
from aero.domain.errors import AeroMeshDomainError

def test_explicit_user_approval_granted(monkeypatch):
    monkeypatch.setenv("TEST_API_KEY", "env_secret_12345")
    provider = CapabilityProviderRequirement(type="credential", id="TEST_API_KEY", kind="api_key")

    def mock_approval(key_id: str, existing_val: str, kind: str):
        assert key_id == "TEST_API_KEY"
        assert existing_val == "env_secret_12345"
        return (existing_val, True)

    resolver = ZeroTrustVaultResolver(approval_fn=mock_approval)
    resolved = resolver.resolve_requirements([provider], non_interactive=False)
    assert resolved["TEST_API_KEY"] == "env_secret_12345"

def test_explicit_user_approval_rejected(monkeypatch):
    monkeypatch.setenv("TEST_API_KEY", "env_secret_12345")
    provider = CapabilityProviderRequirement(type="credential", id="TEST_API_KEY", kind="api_key")

    def mock_rejection(key_id: str, existing_val: str, kind: str):
        return ("", False)

    resolver = ZeroTrustVaultResolver(approval_fn=mock_rejection)
    with pytest.raises(AeroMeshDomainError) as exc_info:
        resolver.resolve_requirements([provider], non_interactive=False)
    assert "rejected by user" in str(exc_info.value)
