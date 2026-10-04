"""Manifest declarations must have implemented, safe semantics."""

import copy
import json

import pytest

from aero.infrastructure.parser import ManifestParser, WorkflowParser
from aero.domain.errors import AeroMeshDomainError


def minimal():
    return {
        "manifest_version": "0.2.0",
        "identity": {"id": "schema-test", "name": "Schema test", "version": "1.0.0"},
        "capabilities": {
            "domain": "test",
            "tags": [],
            "short_description": "test",
            "evaluation_trigger": "manual",
        },
        "cognitive_runtime": {"persona": "Test", "success_criteria": "Answer"},
        "requirements": {"providers": []},
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("driver", "Driver.WasmSandbox"),
        ("memory_policy", "CVM_LRU_PAGING"),
        ("checkpoint_policy", "ON_EVENT"),
    ],
)
def test_unsupported_runtime_policies_rejected(field, value):
    data = minimal()
    data["cognitive_runtime"][field] = value
    with pytest.raises(AeroMeshDomainError):
        ManifestParser().validate_dict(data)


def test_supported_version_and_defaults():
    result = ManifestParser().validate_dict(minimal())
    assert result.cognitive_runtime.memory_policy == "NATIVE"
    data = minimal()
    data["manifest_version"] = "99.0.0"
    with pytest.raises(AeroMeshDomainError):
        ManifestParser().validate_dict(data)


def test_contracts_cannot_fetch_external_schemas():
    data = minimal()
    data["capabilities"]["input_contract"] = {"$ref": "https://example.invalid/schema"}
    with pytest.raises(AeroMeshDomainError):
        ManifestParser().validate_dict(data)


def test_duplicate_json_keys_rejected():
    raw = json.dumps(minimal()).replace(
        '"manifest_version": "0.2.0"',
        '"manifest_version":"0.1.0","manifest_version":"0.2.0"',
    )
    with pytest.raises(AeroMeshDomainError):
        ManifestParser().parse_raw(raw)


def test_duplicate_provider_ids_rejected():
    data = minimal()
    data["requirements"]["providers"] = [{"type": "credential", "id": "TOKEN"}] * 2
    with pytest.raises(AeroMeshDomainError):
        ManifestParser().validate_dict(data)


def test_credential_binding_requires_declared_secret():
    data = minimal()
    data["requirements"]["providers"] = [
        {
            "type": "mcp",
            "id": "tool",
            "transport": "stdio",
            "command": "python",
            "credential_bindings": {"TOKEN": "UNDECLARED"},
        }
    ]
    with pytest.raises(AeroMeshDomainError):
        ManifestParser().validate_dict(data)


def test_budget_requires_explicit_prices_and_output_cap():
    data = minimal()
    data["observability"] = {"cost_limit_usd": 1}
    with pytest.raises(AeroMeshDomainError):
        ManifestParser().validate_dict(data)


def test_workflow_agent_reference_is_an_id_not_a_path():
    data = {
        "workflow_version": "0.2.0",
        "identity": {"id": "wf", "name": "Workflow", "version": "1.0.0"},
        "steps": [
            {"id": "step", "agent_id": "/tmp/self-signed.json", "intent": "Test"}
        ],
    }
    with pytest.raises(AeroMeshDomainError):
        WorkflowParser().validate_dict(data)


def test_dead_provider_and_swarm_features_rejected():
    for provider in ("skill", "custom_plugin", "storage_adapter", "security"):
        data = minimal()
        data["requirements"]["providers"] = [{"type": provider, "id": "unsupported"}]
        with pytest.raises(AeroMeshDomainError):
            ManifestParser().validate_dict(data)
    data = minimal()
    data["swarm_topology"] = {"pattern": "hierarchical", "consensus_threshold": 0.8}
    with pytest.raises(AeroMeshDomainError):
        ManifestParser().validate_dict(data)


@pytest.mark.parametrize(
    "contract",
    [
        {"$ref": "#/definitions/missing"},
        {
            "definitions": {"name": {"type": "string"}},
            "$ref": "#/definitions/name/type",
        },
        {"$ref": "#unsupported-anchor"},
        {"$anchor": "name", "type": "string"},
        {"definitions": {"bad~name": {}}, "$ref": "#/definitions/bad~name"},
        {"definitions": {"bad%name": {}}, "$ref": "#/definitions/bad%name"},
        {"allOf": [{}], "$ref": "#/allOf/01"},
        {"allOf": [{}], "$ref": "#/allOf/-"},
        {"$ref": "#"},
        {
            "definitions": {
                "a": {"$ref": "#/definitions/b"},
                "b": {"$ref": "#/definitions/a"},
            },
            "$ref": "#/definitions/a",
        },
    ],
)
def test_invalid_local_contract_references_fail_during_authoring(contract):
    data = minimal()
    data["capabilities"]["input_contract"] = contract
    with pytest.raises(AeroMeshDomainError, match="contract"):
        ManifestParser().validate_dict(data)


@pytest.mark.parametrize(
    "contract,valid,invalid",
    [
        (
            {
                "definitions": {"a/b~c": {"type": "string"}},
                "$ref": "#/definitions/a~1b~0c",
            },
            "value",
            3,
        ),
        (
            {
                "definitions": {"with space": {"type": "string"}},
                "$ref": "#/definitions/with%20space",
            },
            "value",
            3,
        ),
        (
            {"definitions": {"allowed": True}, "$ref": "#/definitions/allowed"},
            {"anything": True},
            None,
        ),
        (
            {
                "allOf": [{"type": "integer"}],
                "properties": {"nested": {"$ref": "#/allOf/0"}},
            },
            1,
            "no",
        ),
    ],
)
def test_valid_local_pointer_references_preserve_draft7_behavior(
    contract, valid, invalid
):
    import jsonschema

    data = minimal()
    data["capabilities"]["output_contract"] = contract
    ManifestParser().validate_dict(data)
    validator = jsonschema.Draft7Validator(contract)
    validator.validate(valid)
    if invalid is not None:
        assert not validator.is_valid(invalid)


def test_finite_recursive_structure_remains_supported():
    import jsonschema

    contract = {
        "type": "object",
        "required": ["value"],
        "properties": {"value": {"type": "string"}, "child": {"$ref": "#"}},
        "additionalProperties": False,
    }
    data = minimal()
    data["capabilities"]["input_contract"] = contract
    ManifestParser().validate_dict(data)
    validator = jsonschema.Draft7Validator(contract)
    validator.validate({"value": "parent", "child": {"value": "child"}})
    assert not validator.is_valid({"value": "parent", "child": {"value": 3}})


def test_workflow_input_step_name_is_reserved():
    workflow = {
        "workflow_version": "0.2.0",
        "identity": {"id": "wf", "name": "Workflow", "version": "1.0.0"},
        "steps": [{"id": "input", "agent_id": "reader", "intent": "Read"}],
    }
    with pytest.raises(AeroMeshDomainError, match="reserved"):
        WorkflowParser().validate_dict(workflow)
