"""Prepare reviewable inventory artifacts; no signing, approval or execution.

Requires the installed AeroMesh v1 runtime. The image reference is supplied by
the operator after separate provisioning and is validated, never pulled here.
"""

import argparse
import json
from pathlib import Path
import re

from aero.domain.errors import AeroMeshDomainError
from aero.services.policy import check_policy
from aero.services.releases import build_release

MAX_INPUT_BYTES = 1024 * 1024
IMAGE_PATTERN = re.compile(r"[a-z0-9][a-z0-9._:/-]*@sha256:[a-f0-9]{64}")


def prepare_release(image: str, output_dir: Path) -> dict[str, Path]:
    """Create a new directory containing a draft, unsigned release and policy.

    Existing directories and files are never replaced. Failed preparation
    removes only files this invocation created, then its directory if empty.
    """
    if not IMAGE_PATTERN.fullmatch(image):
        raise ValueError("--image must be a repository@sha256:<64 lowercase hex> reference")
    output_dir = Path(output_dir)
    manifest = {
        "manifest_version": "1.0.0",
        "identity": {
            "id": "dependency-inventory",
            "name": "Dependency inventory",
            "version": "1.0.0",
        },
        "capabilities": {
            "domain": "Software engineering",
            "tags": ["inventory", "dependencies"],
            "short_description": "Inventory supplied Python dependency declarations offline.",
            "evaluation_trigger": "Inventory dependency text",
            "input_contract": {
                "type": "object",
                "required": ["requirements_text"],
                "additionalProperties": False,
                "properties": {
                    "requirements_text": {"type": "string", "maxLength": MAX_INPUT_BYTES}
                },
            },
            "output_contract": {
                "type": "object",
                "required": [
                    "path", "sha256", "dependency_count", "unpinned_count",
                    "dependencies", "scope",
                ],
                "additionalProperties": False,
                "properties": {
                    "path": {"const": "<provided>"},
                    "sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                    "dependency_count": {"type": "integer", "minimum": 0},
                    "unpinned_count": {"type": "integer", "minimum": 0},
                    "dependencies": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": [
                                "name", "specifier", "extras", "marker", "direct_url",
                                "exact_version_pin", "line",
                            ],
                            "additionalProperties": False,
                            "properties": {
                                "name": {"type": "string", "minLength": 1},
                                "specifier": {"type": "string"},
                                "extras": {"type": "array", "items": {"type": "string"}},
                                "marker": {"type": ["string", "null"]},
                                "direct_url": {"type": ["string", "null"]},
                                "exact_version_pin": {"type": "boolean"},
                                "line": {"type": "integer", "minimum": 1},
                            },
                        },
                    },
                    "scope": {
                        "const": "Declared dependencies only; no vulnerability or transitive analysis."
                    },
                },
            },
        },
        "cognitive_runtime": {
            "persona": (
                "Pass the supplied requirements_text unchanged to "
                "inventory__inventory_requirements_text. Return that tool's complete "
                "JSON result without alteration. Do not infer vulnerabilities."
            ),
            "success_criteria": "Return the observed inventory; no security assessment.",
            "checkpoint_policy": "DISABLED",
        },
        "requirements": {
            "providers": [{
                "type": "mcp", "id": "inventory", "transport": "stdio",
                "image": image,
                "required_tools": ["inventory_requirements_text"],
                "credential_bindings": {},
            }]
        },
        "observability": {
            "max_execution_steps": 12, "max_model_calls": 4, "max_output_tokens": 4096,
        },
    }
    policy = {
        "policy_version": "1",
        "allowed_credentials": [],
        "providers": {"inventory": {
            "image": image, "tools": ["inventory_requirements_text"],
            "credential_bindings": {},
        }},
    }
    paths = {
        "manifest": output_dir / "inventory.agent.json",
        "release": output_dir / "inventory.release.json",
        "policy": output_dir / "inventory.policy.json",
    }
    created = []

    def write(path: Path, data: dict) -> None:
        with path.open("x", encoding="utf-8") as stream:
            created.append(path)
            json.dump(data, stream, indent=2, ensure_ascii=False)
            stream.write("\n")

    output_dir.mkdir()  # Exclusive creation also refuses existing empty folders.
    try:
        write(paths["manifest"], manifest)
        release = build_release(paths["manifest"])
        check_policy(release, policy)
        write(paths["release"], release)
        write(paths["policy"], policy)
    except BaseException:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        try:
            output_dir.rmdir()
        except OSError:
            pass  # Preserve any independently created files.
        raise
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        paths = prepare_release(args.image, args.output_dir)
    except (ValueError, OSError, AeroMeshDomainError) as exc:
        parser.exit(1, f"Preparation failed: {exc}\n")
    print(json.dumps({name: str(path) for name, path in paths.items()}, indent=2))
    print("Review every file. The release is unsigned and unapproved.")


if __name__ == "__main__":
    main()
