"""Unit tests for AeroSchemaBindingService in aero.infrastructure.schema_binding."""

import pytest
from aero.infrastructure.schema_binding import AeroSchemaBindingService

VALID_MANIFEST = """{
  "manifest_version": "3.0.0",
  "identity": { "id": "binding-agent", "name": "Binding Agent", "version": "1.0.0" },
  "capabilities": { "domain": "DevOps", "tags": ["devops"], "short_description": "Test binding", "evaluation_trigger": "Test" },
  "cognitive_runtime": { "persona": "Engineer", "success_criteria": "Done" },
  "requirements": { "providers": [] }
}"""

def test_schema_binding_service():
    service = AeroSchemaBindingService()
    info = service.get_schema_binding_info()

    assert "schema_uri" in info
    assert info["manifest_version"] == "3.0.0"

    annotated = service.validate_and_annotate_manifest(VALID_MANIFEST)
    assert annotated["is_valid"] is True
    assert annotated["agent_id"] == "binding-agent"
    assert annotated["domain"] == "DevOps"
