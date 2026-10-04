"""Exercise the real credential UI, including its vault call site."""

from aero.domain.models import CapabilityProviderRequirement
from aero.infrastructure.vault import ZeroTrustVaultResolver
from aero.presentation.ui import AeroTerminalUI


class MemoryStore:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value):
        self.values[key] = value


def test_missing_credential_uses_hidden_prompt_and_persists(monkeypatch, capsys):
    monkeypatch.delenv("V1_MISSING_SECRET", raising=False)
    monkeypatch.setattr("getpass.getpass", lambda prompt: "test-secret-never-display")
    store = MemoryStore()
    resolver = ZeroTrustVaultResolver(store=store)
    result = resolver.resolve_requirements([
        CapabilityProviderRequirement(type="credential", id="V1_MISSING_SECRET")
    ])
    assert result == {"V1_MISSING_SECRET": "test-secret-never-display"}
    assert store.values == result
    output = capsys.readouterr()
    assert "test-secret-never-display" not in output.out + output.err
    assert not output.out  # JSON stdout stays usable in interactive CLI calls.


def test_existing_credential_approval_never_displays_secret(capsys):
    secret = "secret-prefix-and-suffix"
    value, approved = AeroTerminalUI.prompt_credential_approval(
        "TOKEN", secret, input_fn=lambda prompt: "1"
    )
    assert approved and value == secret
    output = capsys.readouterr()
    assert "secret" not in output.out + output.err
    assert "suffix" not in output.out + output.err
    assert not output.out


def test_replacement_credential_uses_getpass(monkeypatch):
    monkeypatch.setattr("getpass.getpass", lambda prompt: "replacement-value")
    assert AeroTerminalUI.prompt_credential_approval(
        "TOKEN", "old-value", input_fn=lambda prompt: "2"
    ) == ("replacement-value", True)


def test_rejected_credential_is_not_returned():
    assert AeroTerminalUI.prompt_credential_approval(
        "TOKEN", "old-value", input_fn=lambda prompt: "3"
    ) == ("", False)
