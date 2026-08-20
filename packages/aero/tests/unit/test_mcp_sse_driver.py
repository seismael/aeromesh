"""Unit tests for McpSseDriver in aero.infrastructure.mcp."""

import pytest
from aero.infrastructure.mcp import McpSseDriver
from aero.domain.errors import AeroMeshDomainError, ErrorCode

def test_mcp_sse_driver():
    driver = McpSseDriver(
        uri="https://mcp.aeromesh.dev/sse",
        bearer_token="test_token",
        allowed_domains=["mcp.aeromesh.dev"],
    )
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


def test_mcp_sse_driver_blocks_disallowed_domain():
    driver = McpSseDriver(
        uri="https://evil.example.com/sse", allowed_domains=["good.example.com"]
    )
    with pytest.raises(AeroMeshDomainError) as exc:
        driver.connect()
    assert exc.value.error_code == ErrorCode.AMX_ERR_DOMAIN_BLOCKED
    assert driver.is_connected is False


def test_mcp_sse_driver_allows_listed_domain():
    driver = McpSseDriver(
        uri="https://good.example.com/sse", allowed_domains=["good.example.com"]
    )
    driver.connect()
    assert driver.is_connected is True
