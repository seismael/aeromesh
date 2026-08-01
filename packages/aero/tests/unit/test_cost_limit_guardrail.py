"""Unit tests for ObservabilityProfile.cost_limit_usd budget guardrail in driver.py."""

import pytest
from aero.domain.models import ObservabilityProfile
from aero.infrastructure.driver import LangGraphExecutionDriver
from aero.infrastructure.parser import ManifestParser
from aero.domain.errors import AeroMeshDomainError

MANIFEST_WITH_LOW_BUDGET = """{
  "manifest_version": "3.0.0",
  "identity": { "id": "low-budget-agent", "name": "Low Budget Agent", "version": "1.0.0" },
  "capabilities": { "domain": "Finance", "tags": ["cost"], "short_description": "Low budget test", "evaluation_trigger": "Test" },
  "cognitive_runtime": { "persona": "Trader", "success_criteria": "Done" },
  "observability": { "trace_level": "info", "cost_limit_usd": 0.01 },
  "requirements": { "providers": [] }
}"""

def test_cost_limit_guardrail_exceeded():
    parser = ManifestParser()
    manifest = parser.parse_raw(MANIFEST_WITH_LOW_BUDGET)

    driver = LangGraphExecutionDriver(manifest=manifest, credentials={})
    with pytest.raises(AeroMeshDomainError) as exc_info:
        driver.execute("Perform high cost analysis")

    assert "exceeded observability USD budget limit" in str(exc_info.value)
