"""Unit tests for 2-Tier Discovery Search Engine in aero.services.discovery."""

import pytest
from pathlib import Path
from aero.services.discovery import AeroDiscoveryEngine

def test_discovery_engine_indexing_and_tier1_search():
    import shutil
    tmp_path = Path.cwd() / ".test_tmp_discovery"
    tmp_path.mkdir(exist_ok=True)
    try:
        agent_json = tmp_path / "test-db-tuner.json"
        agent_json.write_text("""{
  "manifest_version": "3.0.0",
  "identity": {
    "id": "test-db-tuner",
    "name": "Database Query Tuner",
    "version": "1.0.0"
  },
  "capabilities": {
    "domain": "Database Engineering",
    "tags": ["postgres", "sql"],
    "short_description": "Analyzes slow database queries.",
    "evaluation_trigger": "Use for slow database queries."
  },
  "cognitive_runtime": {
    "persona": "Database Administrator",
    "success_criteria": "Tuned SQL query"
  },
  "requirements": {
    "providers": []
  }
}""", encoding="utf-8")

        engine = AeroDiscoveryEngine()
        records = engine.build_registry_index(extra_paths=[tmp_path])

        assert len(records) >= 1
        found_rec = [r for r in records if r.id == "test-db-tuner"]
        assert len(found_rec) == 1

        results = engine.search_tier1_fast("test-db-tuner database query optimization", records)
        assert len(results) >= 1
        top_match = results[0]
        assert top_match.record.id == "test-db-tuner"
        assert top_match.search_tier == "TIER_1_VECTOR_INDEX"
        assert top_match.match_score > 0.3
    finally:
        if tmp_path.exists():
            shutil.rmtree(tmp_path, ignore_errors=True)
