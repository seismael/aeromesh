"""Integration tests for Interactive Credential Prompting & Vault Persistence."""

import os
import json
import pytest
from aero.infrastructure.vault import ZeroTrustVaultResolver
from aero.infrastructure.credential_store import SecureCredentialStore
from aero.domain.models import CapabilityProviderRequirement


class FakeBackend:
    def __init__(self):
        self.data = {}

    def set_password(self, service, key, value):
        self.data[(service, key)] = value

    def get_password(self, service, key):
        return self.data.get((service, key))

    def delete_password(self, service, key):
        self.data.pop((service, key), None)


@pytest.fixture
def workspace_scratch_dir():
    scratch_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "scratch")
    )
    os.makedirs(scratch_dir, exist_ok=True)
    yield scratch_dir


def test_interactive_credential_prompting_and_auto_save(workspace_scratch_dir, monkeypatch):
    # Isolated test directory
    monkeypatch.setenv("AEROMESH_HOME", workspace_scratch_dir)
    monkeypatch.delenv("MISSING_KEY_XYZ", raising=False)

    provider = CapabilityProviderRequirement(
        type="credential",
        id="MISSING_KEY_XYZ",
        kind="bearer_token",
    )

    def mock_prompt(key_id: str, kind: str) -> str:
        assert key_id == "MISSING_KEY_XYZ"
        return "secret_user_input_token_999"

    store = SecureCredentialStore(backend=FakeBackend())
    resolver = ZeroTrustVaultResolver(
        config_dir=workspace_scratch_dir, prompt_fn=mock_prompt, store=store
    )
    resolved = resolver.resolve_requirements([provider], non_interactive=False)

    assert resolved["MISSING_KEY_XYZ"] == "secret_user_input_token_999"

    # Credential is persisted to the encrypted OS-keyring store, not plaintext.
    assert store.get("MISSING_KEY_XYZ") == "secret_user_input_token_999"
    assert not os.path.exists(os.path.join(workspace_scratch_dir, "credentials.json"))
