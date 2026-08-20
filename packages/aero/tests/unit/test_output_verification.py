"""Tests that verification enforces the manifest's output_contract (non-vacuous)."""

import json

from aero.infrastructure.driver import LangGraphExecutionDriver
from aero.infrastructure.parser import ManifestParser

CONTRACT = {
    "type": "object",
    "required": ["result"],
    "properties": {"result": {"type": "string"}},
}


def _manifest_with_contract(contract):
    capabilities = {
        "domain": "C",
        "tags": ["c"],
        "short_description": "d",
        "evaluation_trigger": "e",
    }
    if contract is not None:
        capabilities["output_contract"] = contract
    return ManifestParser().validate_dict(
        {
            "manifest_version": "0.1.0",
            "identity": {"id": "contract-agent", "name": "C", "version": "0.1.0"},
            "capabilities": capabilities,
            "cognitive_runtime": {"persona": "p", "success_criteria": "s"},
            "requirements": {"providers": []},
        }
    )


def test_verification_passes_when_output_matches_contract(monkeypatch):
    driver = LangGraphExecutionDriver(
        _manifest_with_contract(CONTRACT), credentials={}, execute_tools=False
    )
    monkeypatch.setattr(
        driver.provider_adapter,
        "complete_prompt",
        lambda *a, **k: json.dumps({"result": "ok"}),
    )
    result = driver.execute("task")
    assert result["success_criteria_met"] is True


def test_verification_fails_when_output_violates_contract(monkeypatch):
    driver = LangGraphExecutionDriver(
        _manifest_with_contract(CONTRACT), credentials={}, execute_tools=False
    )
    # Not valid JSON for the contract -> verification must fail.
    monkeypatch.setattr(
        driver.provider_adapter, "complete_prompt", lambda *a, **k: "not json"
    )
    result = driver.execute("task")
    assert result["success_criteria_met"] is False


def test_verification_without_contract_uses_nonempty_check(monkeypatch):
    manifest = _manifest_with_contract(None)
    driver = LangGraphExecutionDriver(manifest, credentials={}, execute_tools=False)
    monkeypatch.setattr(
        driver.provider_adapter, "complete_prompt", lambda *a, **k: "some text"
    )
    result = driver.execute("task")
    assert result["success_criteria_met"] is True
