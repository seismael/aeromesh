"""Integration tests for Interactive Credential Prompting & Vault Persistence."""

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


def test_interactive_credential_prompting_and_auto_save(tmp_path, monkeypatch):
    # Isolated test directory
    monkeypatch.setenv("AEROMESH_HOME", str(tmp_path))
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
        prompt_fn=mock_prompt, store=store
    )
    resolved = resolver.resolve_requirements([provider], non_interactive=False)

    assert resolved["MISSING_KEY_XYZ"] == "secret_user_input_token_999"

    # Credential is persisted to the encrypted OS-keyring store, not plaintext.
    assert store.get("MISSING_KEY_XYZ") == "secret_user_input_token_999"
    assert not (tmp_path / "credentials.json").exists()
