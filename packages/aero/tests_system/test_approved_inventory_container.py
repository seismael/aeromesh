"""Exercise the shipped example through approval and a real offline MCP image."""

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from langchain_core.tools import ToolException

from aero.domain import paths
from aero.infrastructure.attestation import generate_keypair, sign_manifest_dict
from aero.infrastructure.parser import ManifestParser
from aero.services.deepagents_runner import build_mcp_tools
from aero.services.preflight import preflight
from aero.services.releases import approve_release, load_approved_release


pytestmark = pytest.mark.docker
EXAMPLE = Path(__file__).resolve().parents[3] / "examples" / "dependency-inventory"


def test_approved_inventory_release_calls_real_offline_tool(tmp_path, monkeypatch):
    image = os.environ.get("AEROMESH_INVENTORY_IMAGE")
    if not image or not shutil.which("docker"):
        message = "Build the example and set AEROMESH_INVENTORY_IMAGE to its local registry digest"
        if os.environ.get("AEROMESH_REQUIRE_DOCKER_TESTS") == "1":
            pytest.fail(message)
        pytest.skip(message)

    monkeypatch.setenv("AEROMESH_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("AEROMESH_MODEL", "openai:preflight-does-not-call-models")
    prepared = tmp_path / "review"
    result = subprocess.run(
        [sys.executable, str(EXAMPLE / "prepare_release.py"),
         "--image", image, "--output-dir", str(prepared)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
    release_path = prepared / "inventory.release.json"
    policy_path = prepared / "inventory.policy.json"
    raw = json.loads(release_path.read_text())

    # Real signatures and independent policy approval; this transport gate uses
    # an ephemeral signer directly, so it needs neither an OS keyring nor a model.
    private, public = generate_keypair()
    release_path.with_suffix(".json.sig").write_text(
        json.dumps(sign_manifest_dict(raw, private)), encoding="utf-8"
    )
    trusted = paths.get_aeromesh_trusted_dir()
    trusted.mkdir(parents=True)
    (trusted / f"{raw['identity']['id']}.pub").write_bytes(public)
    digest = approve_release(release_path, policy_path)
    approved = load_approved_release(digest)
    report = preflight(digest, probe_tools=True)
    assert report["ready"] and not report["model_service_verified"]
    assert report["agents"][0]["observed_tools"] == [
        "inventory__inventory_requirements_text"
    ]

    callbacks = []
    try:
        manifest = ManifestParser().validate_dict(approved.entry_data)
        tools = build_mcp_tools(manifest, development=False, cleanup_callbacks=callbacks)
        assert [tool.name for tool in tools] == ["inventory__inventory_requirements_text"]

        async def exercise():
            for text, count, unpinned in (
                ("requests==2.34.2\nrich>=15\n", 2, 1),
                ("packaging==26.3\n", 1, 0),
            ):
                response = await tools[0].ainvoke({"requirements_text": text})
                output = response[0]["text"] if isinstance(response, list) else response
                actual = json.loads(output)
                assert actual["path"] == "<provided>"
                assert actual["dependency_count"] == count
                assert actual["unpinned_count"] == unpinned
                assert actual["sha256"] == hashlib.sha256(text.encode()).hexdigest()
            with pytest.raises(ToolException, match="pip options"):
                await tools[0].ainvoke({"requirements_text": "-r /etc/passwd"})

        asyncio.run(asyncio.wait_for(exercise(), timeout=45))
    finally:
        for callback in reversed(callbacks):
            callback()
