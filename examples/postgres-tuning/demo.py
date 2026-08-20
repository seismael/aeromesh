"""Golden-path demo: run an agent that actually invokes a real (over-the-wire)
stdio MCP tool and returns a concrete recommendation.

Run from the repo root:  python examples/postgres-tuning/demo.py
"""

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "packages", "aero", "src"))

from aero.infrastructure.driver import LangGraphExecutionDriver  # noqa: E402
from aero.infrastructure.parser import ManifestParser  # noqa: E402

SERVER = os.path.join(os.path.dirname(__file__), "mock_postgres_mcp.py")

MANIFEST = {
    "manifest_version": "0.1.0",
    "identity": {"id": "golden-postgres-tuner", "name": "Golden Postgres Tuner", "version": "0.1.0"},
    "capabilities": {
        "domain": "Database Engineering",
        "tags": ["postgres", "tuning"],
        "short_description": "Explains a slow query and recommends an index.",
        "evaluation_trigger": "Tune a slow query",
    },
    "cognitive_runtime": {
        "persona": "You are a principal PostgreSQL database reliability engineer.",
        "success_criteria": "Produce a concrete index recommendation from the explain plan.",
    },
    "requirements": {
        "providers": [
            {
                "type": "mcp",
                "id": "postgres-mcp",
                "transport": "stdio",
                "command": sys.executable,
                "args": [SERVER],
                "required_tools": ["explain_query"],
            }
        ]
    },
}


def main():
    manifest = ManifestParser().validate_dict(MANIFEST)
    driver = LangGraphExecutionDriver(manifest, credentials={}, execute_tools=True)
    result = driver.execute("Explain SELECT * FROM orders WHERE user_id = 42")

    print("Tool results (from the real stdio MCP server):")
    for r in result.get("tool_results", []):
        print("  -", r)
    print("Verified result:", result.get("verified_result"))
    print("success_criteria_met:", result.get("success_criteria_met"))
    assert result.get("tools_called") == 1
    assert any("CREATE INDEX" in r for r in result.get("tool_results", []))


if __name__ == "__main__":
    main()
    print("\nGOLDEN PATH: OK")
