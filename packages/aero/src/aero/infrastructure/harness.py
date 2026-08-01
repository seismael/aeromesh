"""Mock MCP Subprocess Stdio Driver Implementation for Testing Harness."""

from typing import Dict, Any, List, Optional
from aero.infrastructure.mcp import McpToolDeclaration

class MockMcpDriver:
    """Mock MCP Stdio Driver for deterministic unit testing without spawning OS subprocesses."""

    def __init__(self, registered_tools: Optional[List[McpToolDeclaration]] = None):
        self.registered_tools = registered_tools or [
            McpToolDeclaration(name="execute_query", description="Execute SQL query", input_schema={"type": "object"}),
            McpToolDeclaration(name="explain_query", description="Explain SQL query", input_schema={"type": "object"}),
        ]
        self.is_spawned = False

    def spawn(self) -> None:
        self.is_spawned = True

    def send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "tools": [
                        {
                            "name": t.name,
                            "description": t.description,
                            "inputSchema": t.input_schema,
                        }
                        for t in self.registered_tools
                    ]
                },
            }
        elif method == "tools/call":
            params = params or {}
            tname = params.get("name", "unknown")
            return {
                "jsonrpc": "2.0",
                "id": 2,
                "result": {
                    "content": [{"type": "text", "text": f"Mock result for tool {tname}"}],
                    "isError": False,
                },
            }
        return {"jsonrpc": "2.0", "id": 99, "result": {}}

    def close(self) -> None:
        self.is_spawned = False
