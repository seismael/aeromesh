"""Real Linux-container boundary checks; no network or fake Docker daemon.

CI preloads busybox and sets AEROMESH_TEST_IMAGE to its repository@sha256 digest.
Local runs skip explicitly when that prerequisite or the Docker daemon is absent.
"""

from __future__ import annotations

import json
import asyncio
import os
from pathlib import Path
import shutil
import subprocess
import time
from types import SimpleNamespace

import pytest

from aero.infrastructure.tool_execution import build_stdio_connection


pytestmark = pytest.mark.docker


@pytest.fixture(scope="module")
def container_image():
    def unavailable(message):
        if os.environ.get("AEROMESH_REQUIRE_DOCKER_TESTS") == "1":
            pytest.fail(message)
        pytest.skip(message)

    docker = shutil.which("docker")
    image = os.environ.get("AEROMESH_TEST_IMAGE", "")
    if not docker or "@sha256:" not in image:
        unavailable(
            "Requires Docker and preloaded digest-pinned AEROMESH_TEST_IMAGE (busybox)"
        )
    try:
        info = subprocess.run(
            [
                docker,
                "--host=unix:///var/run/docker.sock",
                "info",
                "--format",
                "{{.OSType}}",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        unavailable("Local Docker daemon unavailable")
    if info.returncode or info.stdout.strip() != "linux":
        unavailable("Local Linux-container Docker daemon unavailable")
    present = subprocess.run(
        [docker, "--host=unix:///var/run/docker.sock", "image", "inspect", image],
        capture_output=True,
        timeout=10,
    )
    if present.returncode:
        unavailable("AEROMESH_TEST_IMAGE has not been pulled locally")
    return image


def _provider(image, script, **changes):
    values = dict(
        id="isolation-probe",
        image=image,
        command=None,
        uri=None,
        args=["sh", "-c", script],
        allowed_domains=[],
        credential_bindings={},
    )
    values.update(changes)
    return SimpleNamespace(**values)


def _run(image, script, credentials=None, **changes):
    callbacks = []
    conn = build_stdio_connection(
        _provider(image, script, **changes), credentials, cleanup_callbacks=callbacks
    )
    try:
        return subprocess.run(
            [conn["command"], *conn["args"]],
            env=conn["env"],
            capture_output=True,
            text=True,
            timeout=20,
        )
    finally:
        for cleanup in reversed(callbacks):
            cleanup()


def test_container_enforces_filesystem_identity_privileges_and_network(
    container_image, tmp_path
):
    marker = tmp_path / "host-secret"
    marker.write_text("must not be mounted")
    script = f"""
set -eu
[ "$(id -u)" = 65532 ]
[ ! -e '{marker}' ]
! touch /rootfs-write-probe 2>/dev/null
touch /tmp/permitted-scratch
[ "$(awk '$2 == "/" {{print $4}}' /proc/mounts | cut -d, -f1)" = ro ]
grep -Eq '^NoNewPrivs:[[:space:]]+1$' /proc/self/status
grep -Eq '^CapEff:[[:space:]]+0000000000000000$' /proc/self/status
[ ! -e /sys/class/net/eth0 ]
[ ! -S /var/run/docker.sock ]
echo boundary-verified
"""
    result = _run(container_image, script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "boundary-verified"


def test_container_receives_only_bound_host_credentials(container_image, monkeypatch):
    monkeypatch.setenv("UNRELATED_SECRET", "must-not-cross-boundary")
    script = 'set -eu; [ "$SERVICE_TOKEN" = test-value ]; [ -z "${UNRELATED_SECRET:-}" ]; [ -z "${OTHER_TOKEN:-}" ]; echo scoped'
    result = _run(
        container_image,
        script,
        {"service": "test-value", "OTHER_TOKEN": "unrelated"},
        credential_bindings={"SERVICE_TOKEN": "service"},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "scoped"


def test_native_mcp_protocol_discovery_and_parallel_calls_cross_production_container_boundary(
    container_image, monkeypatch
):
    """No mocks: schema -> production Docker connection -> native MCP -> tool call."""
    from aero.infrastructure.parser import ManifestParser
    from aero.services.deepagents_runner import build_mcp_tools

    script = (Path(__file__).parent / "fixtures" / "mcp_boundary.sh").read_text()
    monkeypatch.setenv("UNRELATED_SECRET", "must-not-cross-boundary")
    manifest = ManifestParser().validate_dict(
        {
            "manifest_version": "1.0.0",
            "identity": {
                "id": "container-protocol",
                "name": "Container protocol",
                "version": "1.0.0",
            },
            "capabilities": {
                "domain": "Test",
                "tags": [],
                "short_description": "Actual isolated MCP integration",
                "evaluation_trigger": "manual",
            },
            "cognitive_runtime": {
                "persona": "Inspect actual isolation.",
                "success_criteria": "Checked by deterministic assertions.",
            },
            "requirements": {
                "providers": [
                    {
                        "type": "mcp",
                        "id": "isolated",
                        "transport": "stdio",
                        "image": container_image,
                        "args": ["sh", "-c", script],
                        "required_tools": ["inspect_boundary"],
                        "credential_bindings": {"SERVICE_TOKEN": "service"},
                    },
                    {"type": "credential", "id": "service"},
                ]
            },
        }
    )
    callbacks = []
    try:
        tools = build_mcp_tools(
            manifest,
            {"service": "fixture-token", "OTHER_TOKEN": "unrelated"},
            development=False,
            cleanup_callbacks=callbacks,
        )
        assert [tool.name for tool in tools] == ["isolated__inspect_boundary"]
        assert tools[0].metadata["mcp_provider"] == "isolated"
        assert tools[0].metadata["mcp_tool"] == "inspect_boundary"

        async def calls():
            return await asyncio.wait_for(
                asyncio.gather(tools[0].ainvoke({}), tools[0].ainvoke({})), timeout=30
            )

        for response in asyncio.run(calls()):
            text = response[0]["text"] if isinstance(response, list) else response
            assert text == "uid=65532;network=none;rootfs=ro;bound=true;unbound=absent"
            assert "fixture-token" not in text and "must-not-cross-boundary" not in text
    finally:
        for cleanup in reversed(callbacks):
            cleanup()


def test_parallel_sessions_have_no_name_collision_and_cleanup_confirms_limits(
    container_image,
):
    callbacks = []
    conn = build_stdio_connection(
        _provider(container_image, "sleep 300"), {}, cleanup_callbacks=callbacks
    )
    args = conn["args"]
    owner = next(
        arg.removeprefix("--label=")
        for arg in args
        if arg.startswith("--label=aeromesh.owner=")
    )
    prefix = [conn["command"], args[0], args[1]]
    inventory_command = [
        *prefix,
        "ps",
        "--all",
        "--quiet",
        "--no-trunc",
        "--filter",
        f"label={owner}",
    ]
    children = [
        subprocess.Popen(
            [conn["command"], *args],
            env=conn["env"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(2)
    ]
    try:
        deadline = time.monotonic() + 10
        details = None
        while time.monotonic() < deadline:
            inventory = subprocess.run(
                inventory_command, capture_output=True, text=True, timeout=5
            )
            ids = inventory.stdout.split()
            if len(ids) == 2:
                inspected = subprocess.run(
                    [*prefix, "inspect", *ids],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if inspected.returncode == 0:
                    details = json.loads(inspected.stdout)
                    if all(item["State"]["Running"] for item in details):
                        break
            for child in children:
                if child.poll() is not None:
                    pytest.fail(child.communicate()[1].decode())
            time.sleep(0.1)
        assert details is not None and len(details) == 2
        for item in details:
            assert item["State"]["Running"]
            config = item["HostConfig"]
            assert config["NetworkMode"] == "none"
            assert config["ReadonlyRootfs"]
            assert config["PidsLimit"] == 64 and config["Memory"] == 256 * 1024 * 1024
            assert config["NanoCpus"] == 1_000_000_000
            assert config["LogConfig"]["Type"] == "none"
            assert not config["Binds"]
            assert all(mount["Type"] != "volume" for mount in item["Mounts"])
            assert item["Config"]["User"] == "65532:65532"
        for cleanup in reversed(callbacks):
            cleanup()
        for child in children:
            child.communicate(timeout=10)
        absent = subprocess.run(inventory_command, capture_output=True, timeout=5)
        assert absent.returncode == 0 and not absent.stdout.strip()
    finally:
        for cleanup in reversed(callbacks):
            cleanup()
        for child in children:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=10)
