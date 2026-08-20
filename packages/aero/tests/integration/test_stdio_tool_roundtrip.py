"""End-to-end test: a real stdio MCP server round-trip through the execution driver."""

import sys

from aero.infrastructure.driver import LangGraphExecutionDriver
from aero.infrastructure.parser import ManifestParser

# A minimal JSON-RPC 2.0 MCP server written line-by-line to avoid escaping issues.
SERVER_LINES = [
    "import sys, json",
    "while True:",
    "    line = sys.stdin.readline()",
    "    if not line:",
    "        break",
    "    req = json.loads(line.strip())",
    "    rid = req.get('id')",
    "    method = req.get('method')",
    "    if method == 'notifications/initialized':",
    "        continue",
    "    if method == 'initialize':",
    "        result = {'protocolVersion': '2024-11-05', 'serverInfo': {'name': 'mock', 'version': '1.0.0'}}",
    "    elif method == 'tools/list':",
    "        result = {'tools': [{'name': 'echo_tool', 'description': 'echo', 'inputSchema': {'type': 'object'}}]}",
    "    elif method == 'tools/call':",
    "        result = {'content': [{'type': 'text', 'text': 'REAL TOOL OUTPUT'}], 'isError': False}",
    "    else:",
    "        result = {}",
    "    sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': rid, 'result': result}) + '\\n')",
    "    sys.stdout.flush()",
]


def test_stdio_mcp_tool_roundtrip(tmp_path):
    server_path = tmp_path / "mock_mcp_server.py"
    server_path.write_text("\n".join(SERVER_LINES) + "\n", encoding="utf-8")

    manifest = ManifestParser().validate_dict(
        {
            "manifest_version": "0.1.0",
            "identity": {"id": "stdio-e2e", "name": "E2E", "version": "0.1.0"},
            "capabilities": {
                "domain": "E2E",
                "tags": ["e2e"],
                "short_description": "d",
                "evaluation_trigger": "e",
            },
            "cognitive_runtime": {"persona": "p", "success_criteria": "s"},
            "requirements": {
                "providers": [
                    {
                        "type": "mcp",
                        "id": "m",
                        "transport": "stdio",
                        "command": sys.executable,
                        "args": [str(server_path)],
                        "required_tools": ["echo_tool"],
                    }
                ]
            },
        }
    )

    driver = LangGraphExecutionDriver(manifest, credentials={}, execute_tools=True)
    result = driver.execute("run the echo tool")

    assert result["tools_called"] == 1
    assert any("REAL TOOL OUTPUT" in r for r in result["tool_results"])
