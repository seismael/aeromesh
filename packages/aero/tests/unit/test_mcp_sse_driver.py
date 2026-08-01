"""Unit tests for McpSseDriver in aero.infrastructure.mcp."""

import pytest
from aero.infrastructure.mcp import McpSseDriver

def test_mcp_sse_driver():
    driver = McpSseDriver(uri="https://mcp.aeromesh.dev/sse", bearer_token="test_token")
    driver.connect()
    assert driver.is_connected is True

    tools = driver.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "remote_cloud_query"

    res = driver.call_tool("remote_cloud_query", {"query": "test"})
    assert "SSE Remote result" in res.content
    assert res.is_error is False

    driver.close()
    assert driver.is_connected is False
