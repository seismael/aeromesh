"""Real local MCP integration; deliberately outside tests/conftest.py substitutes."""

import asyncio
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


REPO = Path(__file__).resolve().parents[3]
EXAMPLE = REPO / "examples" / "dependency-inventory"


def payload(response):
    return response.structuredContent or json.loads(response.content[0].text)


def test_documented_offline_example():
    result = subprocess.run(
        [sys.executable, str(EXAMPLE / "smoke.py")],
        cwd=EXAMPLE,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["dependency_count"] == 3
    assert payload["unpinned_count"] == 1
    assert (
        payload["sha256"]
        == hashlib.sha256(
            (EXAMPLE / "fixtures" / "requirements.txt").read_bytes()
        ).hexdigest()
    )


def test_real_transport_reads_changes_and_rejects_out_of_scope_paths(tmp_path):
    root = tmp_path / "input"
    root.mkdir()
    requirements = root / "requirements.txt"
    requirements.write_text("requests==2.34.2\nrich>=15\n", encoding="utf-8")
    secret = tmp_path / "secret.txt"
    secret.write_text("DO_NOT_READ_SENTINEL", encoding="utf-8")

    async def exercise():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=[str(EXAMPLE / "server.py"), "--root", str(root)],
            env={},
        )
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                response = await session.call_tool(
                    "inventory_requirements", {"path": "requirements.txt"}
                )
                assert not response.isError
                result = payload(response)
                assert result["dependency_count"] == 2
                assert result["unpinned_count"] == 1
                requirements.write_text("packaging==26.3\n", encoding="utf-8")
                updated = await session.call_tool(
                    "inventory_requirements", {"path": "requirements.txt"}
                )
                assert payload(updated)["dependency_count"] == 1
                assert payload(updated)["sha256"] != result["sha256"]
                for path in ("../secret.txt", str(secret)):
                    rejected = await session.call_tool(
                        "inventory_requirements", {"path": path}
                    )
                    assert rejected.isError
                    assert "DO_NOT_READ_SENTINEL" not in rejected.model_dump_json()
                requirements.write_text("-r ../secret.txt\n", encoding="utf-8")
                invalid = await session.call_tool(
                    "inventory_requirements", {"path": "requirements.txt"}
                )
                assert invalid.isError
                requirements.write_bytes(b"x" * (1024 * 1024 + 1))
                oversized = await session.call_tool(
                    "inventory_requirements", {"path": "requirements.txt"}
                )
                assert oversized.isError

    asyncio.run(exercise())


def test_production_adapter_discovers_and_invokes_real_mcp_tool(tmp_path, monkeypatch):
    """Exercise AeroMesh mapping and tool loading without a substitute model."""
    from aero.infrastructure.parser import ManifestParser
    from aero.services.deepagents_runner import build_mcp_tools

    monkeypatch.setenv("AEROMESH_HOME", str(tmp_path / "home"))
    manifest = ManifestParser().validate_dict(
        {
            "manifest_version": "1.0.0",
            "identity": {
                "id": "system-inventory",
                "name": "System inventory",
                "version": "1.0.0",
            },
            "capabilities": {
                "domain": "Test",
                "tags": [],
                "short_description": "MCP adapter integration",
                "evaluation_trigger": "manual",
            },
            "cognitive_runtime": {
                "persona": "Inventory declared dependencies.",
                "success_criteria": "Checked by assertions.",
            },
            "requirements": {
                "providers": [
                    {
                        "type": "mcp",
                        "id": "inventory",
                        "transport": "stdio",
                        "command": sys.executable,
                        "args": [
                            str(EXAMPLE / "server.py"),
                            "--root",
                            str(EXAMPLE / "fixtures"),
                        ],
                        "required_tools": ["inventory_requirements"],
                        "credential_bindings": {},
                    }
                ]
            },
        }
    )
    cleanup_callbacks = []
    try:
        tools = build_mcp_tools(
            manifest, development=True, cleanup_callbacks=cleanup_callbacks
        )
        assert [tool.name for tool in tools] == ["inventory__inventory_requirements"]
        response = asyncio.run(tools[0].ainvoke({"path": "requirements.txt"}))
        # LangChain MCP adapters preserve MCP text content as content blocks.
        text = response[0]["text"] if isinstance(response, list) else response
        result = json.loads(text)
        assert result["dependency_count"] == 3
        assert result["unpinned_count"] == 1
    finally:
        for cleanup in reversed(cleanup_callbacks):
            cleanup()
