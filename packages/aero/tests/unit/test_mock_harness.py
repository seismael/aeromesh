"""Unit tests for Mock MCP Harness in aero.infrastructure.harness."""

import pytest
from aero.infrastructure.harness import MockMcpDriver

def test_mock_mcp_driver():
    driver = MockMcpDriver()
    driver.spawn()
    assert driver.is_spawned is True

    tools_res = driver.send_request("tools/list")
    assert len(tools_res["result"]["tools"]) == 2

    call_res = driver.send_request("tools/call", {"name": "execute_query"})
    assert "Mock result for tool execute_query" in call_res["result"]["content"][0]["text"]
