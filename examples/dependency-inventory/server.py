"""Read a requirements file and expose its actual contents over stdio MCP.

This inventory is deterministic and offline. It does not assess vulnerabilities,
resolve transitive dependencies, execute requirements, or download packages.
"""

import argparse
import hashlib
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

MAX_INPUT_BYTES = 1024 * 1024


def inventory(root: Path, relative_path: str) -> dict:
    root = root.resolve(strict=True)
    requested = Path(relative_path)
    if requested.is_absolute():
        raise ValueError("Use a path relative to the configured input directory")
    source = (root / requested).resolve(strict=True)
    if not source.is_relative_to(root) or not source.is_file():
        raise ValueError("Input must be a file inside the configured input directory")
    # Read no more than the accepted limit, even if the file grows concurrently.
    with source.open("rb") as stream:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("Input exceeds the 1 MiB inventory limit")
    dependencies = []
    for number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        # This example deliberately accepts PEP 508 lines, not pip directives.
        if value.startswith("-") or value.endswith("\\"):
            raise ValueError(
                f"Line {number}: pip options and continuations are unsupported"
            )
        try:
            requirement = Requirement(value)
        except InvalidRequirement as exc:
            raise ValueError(f"Line {number}: invalid PEP 508 requirement") from exc
        specifiers = list(requirement.specifier)
        exact_pin = (
            requirement.url is None
            and len(specifiers) == 1
            and specifiers[0].operator == "=="
            and "*" not in specifiers[0].version
        )
        dependencies.append(
            {
                "name": canonicalize_name(requirement.name),
                "specifier": str(requirement.specifier),
                "extras": sorted(requirement.extras),
                "marker": str(requirement.marker) if requirement.marker else None,
                "direct_url": requirement.url,
                "exact_version_pin": exact_pin,
                "line": number,
            }
        )
    dependencies.sort(key=lambda item: (item["name"], item["line"]))
    return {
        "path": source.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "dependency_count": len(dependencies),
        "unpinned_count": sum(not item["exact_version_pin"] for item in dependencies),
        "dependencies": dependencies,
        "scope": "Declared dependencies only; no vulnerability or transitive analysis.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    if not root.is_dir():
        parser.error("--root must be a directory")
    server = FastMCP("aeromesh-dependency-inventory", log_level="ERROR")

    @server.tool()
    def inventory_requirements(path: str = "requirements.txt") -> dict:
        """Inventory PEP 508 dependency lines within the configured input directory."""
        return inventory(root, path)

    server.run(transport="stdio")


if __name__ == "__main__":
    main()
