"""Unit tests for Aero Domain Models and Error Taxonomy."""

import pytest
from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.domain.models import (
    AgentIdentity,
    AgentCapabilities,
    CognitiveRuntimeProfile,
    CapabilityProviderRequirement,
    AgentManifest,
)

def test_domain_error_formatting():
    err = AeroMeshDomainError(
        message="Manifest failed schema assertion",
        error_code=ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
        exit_code=ExitCode.SCHEMA_VIOLATION,
    )
    assert err.exit_code == 10
    assert err.error_code == "AMX_ERR_SCHEMA_VIOLATION"
    assert "[AMX_ERR_SCHEMA_VIOLATION] (Exit 10): Manifest failed schema assertion" in str(err)

def test_agent_manifest_dataclass_immutability():
    identity = AgentIdentity(id="test-agent", name="Test Agent", version="1.0.0")
    caps = AgentCapabilities(
        domain="Testing",
        tags=["test"],
        short_description="Test agent description",
        evaluation_trigger="Trigger on test",
    )
    runtime = CognitiveRuntimeProfile(persona="Tester", success_criteria="Pass test")
    provider = CapabilityProviderRequirement(type="mcp", id="test-mcp")

    manifest = AgentManifest(
        manifest_version="3.0.0",
        identity=identity,
        capabilities=caps,
        cognitive_runtime=runtime,
        providers=[provider],
    )

    assert manifest.identity.id == "test-agent"
    assert manifest.providers[0].type == "mcp"
    
    # Assert immutability (frozen dataclass)
    with pytest.raises(AttributeError):
        manifest.manifest_version = "4.0.0"
