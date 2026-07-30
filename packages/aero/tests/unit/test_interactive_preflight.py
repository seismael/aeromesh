"""Unit tests for AeroInteractivePreflightEngine."""

import os
import json
import shutil
import pytest
from aero.services.preflight import AeroInteractivePreflightEngine
from aero.domain.models import (
    AgentManifest, AgentIdentity, AgentCapabilities,
    CognitiveRuntimeProfile, CapabilityProviderRequirement,
)
from aero.domain.errors import AeroMeshDomainError, ErrorCode

# Use workspace-relative scratch directory instead of tmp_path to avoid
# Windows PermissionError on pytest temp directory creation.
SCRATCH_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".test_scratch")


@pytest.fixture(autouse=True)
def scratch_config_dir():
    """Creates and cleans up a workspace-local scratch directory for config files."""
    abs_dir = os.path.abspath(SCRATCH_DIR)
    os.makedirs(abs_dir, exist_ok=True)
    yield abs_dir
    shutil.rmtree(abs_dir, ignore_errors=True)


@pytest.fixture
def config_paths(scratch_config_dir):
    """Returns (config_file_path, credentials_file_path) inside the scratch dir."""
    cfg = os.path.join(scratch_config_dir, "config.json")
    cred = os.path.join(scratch_config_dir, "credentials.json")
    # Ensure clean slate
    for f in (cfg, cred):
        if os.path.exists(f):
            os.remove(f)
    return cfg, cred


def test_preflight_ensure_default_provider_from_env(monkeypatch, config_paths):
    """Verifies env-var-based auto-detection selects the first matching provider."""
    cfg_path, cred_path = config_paths
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test-12345")

    engine = AeroInteractivePreflightEngine(config_file=cfg_path, credentials_file=cred_path)
    prov_id, api_key = engine.ensure_default_provider(non_interactive=True)

    assert prov_id == "deepseek"
    assert api_key == "sk-deepseek-test-12345"

    # Verify config was persisted
    with open(cfg_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["default_provider"] == "deepseek"
    assert saved["providers"]["deepseek"]["api_key"] == "sk-deepseek-test-12345"


def test_preflight_ensure_default_provider_missing_non_interactive(monkeypatch, config_paths):
    """Verifies deterministic failure when no provider keys exist in non-interactive mode."""
    cfg_path, cred_path = config_paths
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    engine = AeroInteractivePreflightEngine(config_file=cfg_path, credentials_file=cred_path)
    with pytest.raises(AeroMeshDomainError) as exc:
        engine.ensure_default_provider(non_interactive=True)
    assert exc.value.error_code == ErrorCode.AMX_ERR_VAULT_KEY_MISSING


def test_preflight_interactive_provider_selection(monkeypatch, config_paths):
    """Verifies injectable prompt function is used for interactive provider setup."""
    cfg_path, cred_path = config_paths
    # Clear all provider env vars to force fallthrough to interactive prompt
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    def mock_prompt():
        return "anthropic", "sk-ant-test-key-999"

    engine = AeroInteractivePreflightEngine(
        config_file=cfg_path,
        credentials_file=cred_path,
        provider_prompt_fn=mock_prompt
    )
    prov_id, api_key = engine.ensure_default_provider(non_interactive=False)

    assert prov_id == "anthropic"
    assert api_key == "sk-ant-test-key-999"


def test_preflight_agent_feasibility_check():
    """Verifies feasibility check passes for a properly formed manifest."""
    engine = AeroInteractivePreflightEngine()
    req = CapabilityProviderRequirement(type="credential", id="DB_KEY", kind="credential")
    manifest = AgentManifest(
        manifest_version="3.0",
        identity=AgentIdentity(id="test-agent", name="Test", version="1.0"),
        cognitive_runtime=CognitiveRuntimeProfile(persona="test", success_criteria="done", driver="Driver.LangGraph"),
        capabilities=AgentCapabilities(domain="Database", tags=["db"], short_description="Test agent", evaluation_trigger="tune"),
        providers=[req],
    )

    assert engine.verify_agent_feasibility(manifest, "tune query") is True


def test_preflight_negotiate_requirement_non_interactive_with_value():
    """Verifies that an existing credential is returned in non-interactive mode."""
    engine = AeroInteractivePreflightEngine()
    req = CapabilityProviderRequirement(type="credential", id="MY_KEY")
    val, approved = engine.negotiate_requirement_with_fallback(req, "existing_val", non_interactive=True)
    assert val == "existing_val"
    assert approved is True


def test_preflight_negotiate_requirement_non_interactive_missing():
    """Verifies deterministic failure when credential is missing in non-interactive mode."""
    engine = AeroInteractivePreflightEngine()
    req = CapabilityProviderRequirement(type="credential", id="MISSING_KEY")
    with pytest.raises(AeroMeshDomainError) as exc:
        engine.negotiate_requirement_with_fallback(req, None, non_interactive=True)
    assert exc.value.error_code == ErrorCode.AMX_ERR_VAULT_KEY_MISSING


def test_preflight_negotiate_requirement_interactive_approval():
    """Verifies injectable requirement prompt function is used for interactive credential negotiation."""
    def mock_req_prompt(key_id, existing, kind):
        return "user-provided-secret", True

    engine = AeroInteractivePreflightEngine(requirement_prompt_fn=mock_req_prompt)
    req = CapabilityProviderRequirement(type="credential", id="CUSTOM_KEY")
    val, approved = engine.negotiate_requirement_with_fallback(req, None, non_interactive=False)
    assert val == "user-provided-secret"
    assert approved is True


def test_preflight_negotiate_requirement_interactive_rejection():
    """Verifies fallback returns None when user rejects a requirement."""
    def mock_req_prompt(key_id, existing, kind):
        return None, False

    engine = AeroInteractivePreflightEngine(requirement_prompt_fn=mock_req_prompt)
    req = CapabilityProviderRequirement(type="credential", id="REJECTED_KEY")
    val, approved = engine.negotiate_requirement_with_fallback(req, None, non_interactive=False)
    assert val is None
    assert approved is False
