"""Schema Binding & IntelliSense Metadata Infrastructure Service for IDEs & Studio Tools."""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from aero.infrastructure.parser import ManifestParser


class AeroSchemaBindingService:
    """Provides schema validation, field hover tooltips, and IntelliSense binding metadata."""

    def __init__(self, parser: Optional[ManifestParser] = None):
        self.parser = parser or ManifestParser()

    def get_schema_binding_info(self) -> Dict[str, Any]:
        """Describe the shipped schema and the actual production boundary."""
        schema = json.loads(Path(self.parser.schema_path).read_text(encoding="utf-8"))
        versions = schema["properties"]["manifest_version"]["enum"]
        return {
            "schema_uri": schema["$id"],
            "local_schema_path": os.path.abspath(self.parser.schema_path),
            "manifest_version": max(
                versions, key=lambda v: tuple(map(int, v.split(".")))
            ),
            "accepted_manifest_versions": versions,
            "supported_drivers": [
                "Driver.LangGraph",
            ],
            "supported_transports": ["stdio", "sse", "http"],
            "production_transport": "stdio",
            "production_isolation": "digest-pinned-container-network-none",
            "development_only_transports": ["sse", "http"],
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
