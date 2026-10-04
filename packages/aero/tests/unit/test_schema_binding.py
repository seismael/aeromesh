"""Unit tests for AeroSchemaBindingService in aero.infrastructure.schema_binding."""

from aero.infrastructure.schema_binding import AeroSchemaBindingService

VALID_MANIFEST = """{
  "manifest_version": "0.1.0",
  "identity": { "id": "binding-agent", "name": "Binding Agent", "version": "1.0.0" },
  "capabilities": { "domain": "DevOps", "tags": ["devops"], "short_description": "Test binding", "evaluation_trigger": "Test" },
  "cognitive_runtime": { "persona": "Engineer", "success_criteria": "Done" },
  "requirements": { "providers": [] }
}"""


def test_schema_binding_service():
    service = AeroSchemaBindingService()
    info = service.get_schema_binding_info()

    assert "schema_uri" in info
    assert info["manifest_version"] == "0.2.0"
    assert info["schema_uri"].endswith(":0.2.0")
    assert info["supported_drivers"] == ["Driver.LangGraph"]
    assert info["production_transport"] == "stdio"
    assert info["development_only_transports"] == ["sse", "http"]

    annotated = service.validate_and_annotate_manifest(VALID_MANIFEST)
    assert annotated["is_valid"] is True
    assert annotated["agent_id"] == "binding-agent"
    assert annotated["domain"] == "DevOps"
