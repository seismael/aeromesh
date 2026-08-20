"""Schema Binding & IntelliSense Metadata Infrastructure Service for IDEs & Studio Tools."""

import os
from typing import Dict, Any, Optional
from aero.infrastructure.parser import SCHEMA_PATH, ManifestParser


class AeroSchemaBindingService:
    """Provides schema validation, field hover tooltips, and IntelliSense binding metadata."""

    def __init__(self, parser: Optional[ManifestParser] = None):
        self.parser = parser or ManifestParser()

    def get_schema_binding_info(self) -> Dict[str, Any]:
        """Returns DAM v0.1 JSON Schema identifier and description metadata."""
        return {
            "schema_uri": "urn:aeromesh:schemas:declarative-agent:0.1.0",
            "local_schema_path": os.path.abspath(SCHEMA_PATH),
            "manifest_version": "0.1.0",
            "supported_drivers": [
                "Driver.LangGraph",
                "Driver.LangChain",
                "Driver.CustomCDI",
            ],
            "supported_transports": ["stdio", "sse", "http"],
        }

    def validate_and_annotate_manifest(self, raw_json: str) -> Dict[str, Any]:
        """Validates manifest and generates annotated metadata for editor tooltips."""
        manifest = self.parser.parse_raw(raw_json)
        return {
            "is_valid": True,
            "agent_id": manifest.identity.id,
            "version": manifest.identity.version,
            "domain": manifest.capabilities.domain,
            "provider_count": len(manifest.providers),
            "schema_binding": self.get_schema_binding_info(),
        }
