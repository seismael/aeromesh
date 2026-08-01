"""Schema Binding & IntelliSense Metadata Infrastructure Service for IDEs & Studio Tools."""

import os
import json
from typing import Dict, Any, Optional, List
from aero.infrastructure.parser import SCHEMA_PATH, ManifestParser

class AeroSchemaBindingService:
    """Provides schema validation, field hover tooltips, and IntelliSense binding metadata."""

    def __init__(self, parser: Optional[ManifestParser] = None):
        self.parser = parser or ManifestParser()

    def get_schema_binding_info(self) -> Dict[str, Any]:
        """Returns standard DAM v3.0 JSON Schema URI and description metadata."""
        return {
            "schema_uri": "https://schemas.aeromesh.dev/v3.0/declarative-agent.schema.json",
            "local_schema_path": os.path.abspath(SCHEMA_PATH),
            "manifest_version": "3.0.0",
            "supported_drivers": ["Driver.LangGraph", "Driver.LangChain", "Driver.CustomCDI"],
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
