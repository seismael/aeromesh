"""Integration tests for Interactive Credential Prompting & Vault Persistence."""

import os
import json
import pytest
from aero.infrastructure.vault import ZeroTrustVaultResolver
from aero.domain.models import CapabilityProviderRequirement

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
        kind="bearer_token"
    )

    # Mock interactive prompt callback
    def mock_prompt(key_id: str, kind: str) -> str:
        assert key_id == "MISSING_KEY_XYZ"
        return "secret_user_input_token_999"

    resolver = ZeroTrustVaultResolver(config_dir=workspace_scratch_dir, prompt_fn=mock_prompt)
    resolved = resolver.resolve_requirements([provider], non_interactive=False)

    assert resolved["MISSING_KEY_XYZ"] == "secret_user_input_token_999"

    # Verify auto-save to ~/.aeromesh/credentials.json
    cred_file = os.path.join(workspace_scratch_dir, "credentials.json")
    assert os.path.exists(cred_file)
    with open(cred_file, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
    assert saved_data["MISSING_KEY_XYZ"] == "secret_user_input_token_999"
