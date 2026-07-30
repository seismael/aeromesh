"""Unit tests for McpStdioDriver JSON-RPC 2.0 stdio subprocess transport engine."""

import os
import sys
import json
import pytest
from aero.infrastructure.mcp import McpStdioDriver, McpToolDeclaration, McpToolResult
from aero.domain.errors import AeroMeshDomainError, ErrorCode

def test_mcp_tool_declaration_dataclass():
    tool = McpToolDeclaration(
        name="execute_query",
        description="Executes a PostgreSQL query",
        input_schema={"type": "object", "properties": {"sql": {"type": "string"}}}
    )
    assert tool.name == "execute_query"
    assert tool.description == "Executes a PostgreSQL query"
    assert "sql" in tool.input_schema["properties"]

def test_mcp_tool_result_dataclass():
    res = McpToolResult(tool_name="execute_query", content="CREATE INDEX idx_test ON test(col);", is_error=False)
    assert res.tool_name == "execute_query"
    assert res.content == "CREATE INDEX idx_test ON test(col);"
    assert res.is_error is False

def test_mcp_stdio_driver_mock_subprocess():
    # Helper python script acting as a mock JSON-RPC 2.0 MCP server
    mock_script = """
import sys, json

for line in sys.stdin:
    if not line.strip():
        continue
    req = json.loads(line)
    req_id = req.get("id")
    method = req.get("method")

    if method == "initialize":
        res = {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "Mock Server", "version": "1.0.0"}
            }
        }
        sys.stdout.write(json.dumps(res) + "\\n")
        sys.stdout.flush()
    elif method == "tools/list":
        res = {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "execute_query",
                        "description": "Executes SQL query",
                        "inputSchema": {"type": "object"}
                    }
                ]
            }
        }
        sys.stdout.write(json.dumps(res) + "\\n")
        sys.stdout.flush()
    elif method == "tools/call":
        params = req.get("params", {})
        res = {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": "Query result: 42 rows"}]
            }
        }
        sys.stdout.write(json.dumps(res) + "\\n")
        sys.stdout.flush()
"""

    driver = McpStdioDriver(command=sys.executable, args=["-c", mock_script])
    try:
        driver.spawn()
        driver.initialize()
        
        tools = driver.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "execute_query"

        result = driver.call_tool("execute_query", {"sql": "SELECT 42;"})
        assert result.tool_name == "execute_query"
        assert "Query result: 42 rows" in result.content
        assert result.is_error is False
    finally:
        driver.close()
