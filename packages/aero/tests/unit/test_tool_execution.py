"""Tests that the execution driver actually invokes declared MCP tools."""

import pytest

from aero.infrastructure.driver import LangGraphExecutionDriver
from aero.infrastructure.mcp import McpToolResult
from aero.infrastructure.parser import ManifestParser

MANIFEST = {
    "manifest_version": "0.1.0",
    "identity": {"id": "tool-agent", "name": "Tool Agent", "version": "0.1.0"},
    "capabilities": {
        "domain": "Tools",
        "tags": ["tools"],
        "short_description": "Tool test",
        "evaluation_trigger": "Test",
    },
    "cognitive_runtime": {
        "persona": "You are a tool-using agent.",
        "success_criteria": "Use tools",
    },
    "requirements": {
        "providers": [
            {
                "type": "mcp",
                "id": "test-mcp",
                "transport": "stdio",
                "command": "echo",
                "required_tools": ["execute_query"],
            }
        ]
    },
}


class MockToolDriver:
    """Matches the McpStdioDriver tool surface for tests."""

    def __init__(self, tools, fail=False):
        self.tools = tools
        self.fail = fail
        self.spawned = False
        self.calls = []
        self.closed = False

    def spawn(self):
        self.spawned = True

    def initialize(self):
        return {}

    def list_tools(self):
        if self.fail:
            raise RuntimeError("boom")
        return self.tools

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return McpToolResult(tool_name=name, content=f"result-for-{name}")

    def close(self):
        self.closed = True


def _make_driver(tools, execute_tools=True, fail=False):
    manifest = ManifestParser().validate_dict(MANIFEST)
    driver = LangGraphExecutionDriver(
        manifest,
        credentials={},
        mcp_drivers=[MockToolDriver(tools, fail=fail)],
        execute_tools=execute_tools,
    )
    return driver


def test_driver_invokes_declared_tools_and_flows_results():
    from aero.infrastructure.mcp import McpToolDeclaration

    tools = [
        McpToolDeclaration(name="execute_query", description="run sql"),
        McpToolDeclaration(name="explain_query", description="explain sql"),
    ]
    mock = MockToolDriver(tools)
    driver = LangGraphExecutionDriver(
        ManifestParser().validate_dict(MANIFEST),
        credentials={},
        mcp_drivers=[mock],
        execute_tools=True,
    )

    result = driver.execute("SELECT 1")

    assert mock.spawned is True
    assert mock.calls == [("execute_query", {"query": "SELECT 1"})]
    # Only the required tool is invoked, not every tool the server exposes.
    assert mock.calls[0][0] == "execute_query"
    assert result["tool_results"] == ["[execute_query] result-for-execute_query"]
    assert result["tools_called"] == 1
    assert result["success_criteria_met"] is True


def test_driver_degrades_gracefully_when_tool_fails():
    manifest = ManifestParser().validate_dict(MANIFEST)
    mock = MockToolDriver([], fail=True)
    driver = LangGraphExecutionDriver(
        manifest, credentials={}, mcp_drivers=[mock], execute_tools=True
    )

    result = driver.execute("SELECT 1")

    assert any("tool-unavailable" in r for r in result["tool_results"])
    # LLM output (mock fallback) is still non-empty, so execution still succeeds.
    assert result["success_criteria_met"] is True


def test_driver_skips_tools_when_disabled():
    mock = MockToolDriver([])
    driver = LangGraphExecutionDriver(
        ManifestParser().validate_dict(MANIFEST),
        credentials={},
        mcp_drivers=[mock],
        execute_tools=False,
    )

    result = driver.execute("SELECT 1")

    assert mock.spawned is False
    assert result["tool_results"] == []
    assert result["tools_called"] == 0
