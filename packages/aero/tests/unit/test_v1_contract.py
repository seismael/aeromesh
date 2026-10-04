"""The first published format has one version and no ineffective controls."""

import json
from pathlib import Path

import pytest

from aero.domain.errors import AeroMeshDomainError
from aero.infrastructure.parser import (
    ManifestParser,
    WorkflowParser,
    strict_json_value,
)
from aero.services.synthesizer import manifest_to_dict


def agent():
    return {
        "manifest_version": "1.0.0",
        "identity": {"id": "first-agent", "name": "First agent", "version": "1.0.0"},
        "capabilities": {
            "domain": "testing", "tags": [], "short_description": "Contract test",
            "evaluation_trigger": "manual",
        },
        "cognitive_runtime": {"persona": "Answer clearly", "success_criteria": "Answer"},
        "requirements": {"providers": []},
    }


@pytest.mark.parametrize("version", ["0.1.0", "0.2.0", "1", "1.0", "1.0.1", "2.0.0"])
def test_only_published_version_is_accepted(version):
    data = agent()
    data["manifest_version"] = version
    workflow = {
        "workflow_version": version,
        "identity": data["identity"],
        "steps": [{"id": "step", "agent_id": "first-agent", "intent": "Answer"}],
    }
    for parser, document in ((ManifestParser(), data), (WorkflowParser(), workflow)):
        with pytest.raises(AeroMeshDomainError):
            parser.validate_dict(document)


@pytest.mark.parametrize("transport", ["http", "sse"])
@pytest.mark.parametrize(
    "field,value", [("args", ["--read-only"]), ("allowed_domains", ["example.com"]),
                    ("credential_bindings", {"TOKEN": "secret"})]
)
def test_remote_providers_reject_unimplemented_controls(transport, field, value):
    data = agent()
    data["requirements"]["providers"] = [
        {"type": "credential", "id": "secret"},
        {"type": "mcp", "id": "remote", "transport": transport,
         "uri": "https://example.com/mcp", field: value},
    ]
    with pytest.raises(AeroMeshDomainError):
        ManifestParser().validate_dict(data)


def test_remote_provider_round_trip_has_no_unsupported_default_controls():
    data = agent()
    data["requirements"]["providers"] = [
        {"type": "mcp", "id": "remote", "transport": "http",
         "uri": "https://example.com/mcp", "required_tools": ["read"]},
    ]
    parsed = ManifestParser().validate_dict(data)
    serialized = manifest_to_dict(parsed)
    assert serialized["requirements"] == data["requirements"]
    assert ManifestParser().validate_dict(serialized) == parsed


def test_unspecified_artifact_license_is_not_invented():
    parsed = ManifestParser().validate_dict(agent())
    assert parsed.identity.license is None
    assert "license" not in manifest_to_dict(parsed)["identity"]
    workflow = WorkflowParser().validate_dict({
        "workflow_version": "1.0.0", "identity": agent()["identity"],
        "steps": [{"id": "step", "agent_id": "first-agent", "intent": "Answer"}],
    })
    assert workflow.identity.license is None


def test_credentials_reject_unimplemented_fallback_control():
    data = agent()
    data["requirements"]["providers"] = [
        {"type": "credential", "id": "secret", "fallback_action": "prompt_user"},
    ]
    with pytest.raises(AeroMeshDomainError):
        ManifestParser().validate_dict(data)


@pytest.mark.parametrize("raw", ["1e309", "-1e309", '[{"nested": 1e309}]', '{"nested": -1e309}'])
def test_json_rejects_exponent_overflow_at_every_depth(raw):
    with pytest.raises(AeroMeshDomainError, match="Non-finite"):
        strict_json_value(raw)


def test_contract_data_and_property_names_are_not_schema_keywords():
    data = agent()
    contract = {
        "type": "object",
        "properties": {"$ref": {"type": "string"}, "$id": {"type": "integer"}},
        "enum": [{"$ref": "https://example.com/data", "$id": 1}],
        "const": {"$ref": "https://example.com/data", "$id": 1},
        "examples": [{"$ref": "ordinary data", "$id": "ordinary data"}],
    }
    data["capabilities"]["output_contract"] = contract
    assert ManifestParser().validate_dict(data).capabilities.output_contract == contract


@pytest.mark.parametrize(
    "contract", [
        {"properties": {"value": {"$ref": "https://example.com/schema"}}},
        {"items": [{"$ref": "https://example.com/schema"}]},
        {"dependencies": {"value": {"$ref": "https://example.com/schema"}}},
        {"if": {"$ref": "https://example.com/schema"}},
        {"allOf": [{"$ref": "https://example.com/schema"}]},
    ],
)
def test_nested_schema_references_still_reject_network_access(contract):
    data = agent()
    data["capabilities"]["input_contract"] = contract
    with pytest.raises(AeroMeshDomainError, match="local JSON Pointer"):
        ManifestParser().validate_dict(data)


def test_shipped_examples_and_catalog_digests_match_v1():
    import hashlib

    root = Path(__file__).resolve().parents[4]
    index = json.loads((root / "registry/index.json").read_text())
    for record in index["agents"]:
        path = root / record["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
        assert ManifestParser().parse_file(str(path)).manifest_version == "1.0.0"
    for path in (root / "registry/workflows").glob("*.json"):
        assert WorkflowParser().parse_file(str(path)).workflow_version == "1.0.0"
