"""Integration tests for Explicit User Key Approval & Interactive Selection."""

import os
import pytest
from aero.infrastructure.vault import ZeroTrustVaultResolver
from aero.domain.models import CapabilityProviderRequirement
from aero.domain.errors import AeroMeshDomainError

@pytest.fixture
def workspace_scratch_dir():
    scratch_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "scratch")
    )
    os.makedirs(scratch_dir, exist_ok=True)
    yield scratch_dir

def test_explicit_user_approval_granted(workspace_scratch_dir, monkeypatch):
    monkeypatch.setenv("TEST_API_KEY", "env_secret_12345")
    provider = CapabilityProviderRequirement(type="credential", id="TEST_API_KEY", kind="api_key")

    def mock_approval(key_id: str, existing_val: str, kind: str):
        assert key_id == "TEST_API_KEY"
        assert existing_val == "env_secret_12345"
        return (existing_val, True)

    resolver = ZeroTrustVaultResolver(config_dir=workspace_scratch_dir, approval_fn=mock_approval)
    resolved = resolver.resolve_requirements([provider], non_interactive=False)
    assert resolved["TEST_API_KEY"] == "env_secret_12345"

def test_explicit_user_approval_rejected(workspace_scratch_dir, monkeypatch):
    monkeypatch.setenv("TEST_API_KEY", "env_secret_12345")
    provider = CapabilityProviderRequirement(type="credential", id="TEST_API_KEY", kind="api_key")

    def mock_rejection(key_id: str, existing_val: str, kind: str):
        return ("", False)

    resolver = ZeroTrustVaultResolver(config_dir=workspace_scratch_dir, approval_fn=mock_rejection)
    with pytest.raises(AeroMeshDomainError) as exc_info:
        resolver.resolve_requirements([provider], non_interactive=False)
    assert "rejected by user" in str(exc_info.value)
