"""One-time author step: sign every registry agent + workflow and publish keys.

Generates an Ed25519 keypair if none exists, signs all ``registry/agents/*.json``
and ``registry/workflows/*.json`` manifests, and copies the author public key to
``registry/trusted/<id>.pub`` so ``amx install`` / ``amx workflow install`` can
verify them.

Usage:
    python scripts/seed_registry.py
"""

import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "packages" / "aero" / "src")
)

from aero.domain.paths import (  # noqa: E402
    get_aeromesh_home,
    get_aeromesh_workspace_registry_dir,
    get_aeromesh_workspace_trusted_dir,
    get_aeromesh_workspace_workflows_dir,
)
from aero.infrastructure import keystore  # noqa: E402
from aero.infrastructure.parser import ManifestParser, WorkflowParser  # noqa: E402
from aero.services import trust  # noqa: E402


def main() -> None:
    pub_path = get_aeromesh_home() / "keys" / f"{keystore.DEFAULT_KEY_NAME}.pub"
    if not pub_path.exists():
        print("Generating Ed25519 keypair...")
        keystore.generate_and_store_keypair()
    public_key = pub_path.read_bytes()

    trusted_dir = get_aeromesh_workspace_trusted_dir()
    trusted_dir.mkdir(parents=True, exist_ok=True)

    agent_parser = ManifestParser()
    workflow_parser = WorkflowParser()

    artifacts = []
    for f in sorted(get_aeromesh_workspace_registry_dir().glob("*.json")):
        artifacts.append((agent_parser.parse_file(str(f)).identity.id, f))
    for f in sorted(get_aeromesh_workspace_workflows_dir().glob("*.json")):
        artifacts.append((workflow_parser.parse_file(str(f)).identity.id, f))

    for artifact_id, path in artifacts:
        trust.sign_manifest_file(str(path))
        (trusted_dir / f"{artifact_id}.pub").write_bytes(public_key)
        print(f"  signed + trusted: {artifact_id}")

    print(f"\nDone: {len(artifacts)} artifacts signed; trusted keys in {trusted_dir}")


if __name__ == "__main__":
    main()
