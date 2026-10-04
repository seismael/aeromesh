"""Ask a real configured model to use the local inventory MCP tool.

Run only after reviewing server.py. --development is deliberately required
because this example starts a trusted local Python process on the host.
"""

import argparse
import json
import sys
from pathlib import Path

from aero.infrastructure.parser import ManifestParser
from aero.services.deepagents_runner import DeepAgentsExecutionDriver


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", action="store_true", required=True)
    args = parser.parse_args()
    example = Path(__file__).resolve().parent
    manifest = ManifestParser().validate_dict(
        {
            "manifest_version": "1.0.0",
            "identity": {
                "id": "dependency-inventory",
                "name": "Dependency inventory",
                "version": "1.0.0",
            },
            "capabilities": {
                "domain": "Software engineering",
                "tags": ["inventory", "dependencies"],
                "short_description": "Inventory declared Python dependencies from a local file.",
                "evaluation_trigger": "Inventory dependencies",
                "output_contract": {
                    "type": "object",
                    "required": ["dependency_count", "unpinned_count", "sha256"],
                    "properties": {
                        "dependency_count": {"type": "integer", "minimum": 0},
                        "unpinned_count": {"type": "integer", "minimum": 0},
                        "sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                    },
                },
            },
            "cognitive_runtime": {
                "persona": "Use inventory__inventory_requirements to inspect requirements.txt. Return the tool's JSON result without alteration. Do not infer vulnerabilities.",
                "success_criteria": "Return the observed inventory; no security assessment.",
                "checkpoint_policy": "DISABLED",
            },
            "requirements": {
                "providers": [
                    {
                        "type": "mcp",
                        "id": "inventory",
                        "transport": "stdio",
                        "command": sys.executable,
                        "args": [
                            str(example / "server.py"),
                            "--root",
                            str(example / "fixtures"),
                        ],
                        "required_tools": ["inventory_requirements"],
                        "credential_bindings": {},
                    }
                ]
            },
            "observability": {"max_execution_steps": 12},
        }
    )
    driver = DeepAgentsExecutionDriver(manifest, development=args.development)
    try:
        result = driver.execute(
            "Inventory requirements.txt using the inventory__inventory_requirements tool."
        )
        print(json.dumps(result, indent=2, default=str))
    finally:
        driver.close()


if __name__ == "__main__":
    main()
