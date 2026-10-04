"""Exercise the real MCP transport without requiring a model or credentials."""

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def inspect_inventory():
    example = Path(__file__).resolve().parent
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(example / "server.py"), "--root", str(example / "fixtures")],
        env={},
    )
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert [tool.name for tool in tools.tools] == ["inventory_requirements"]
            response = await session.call_tool(
                "inventory_requirements", {"path": "requirements.txt"}
            )
            if response.isError:
                raise RuntimeError("Inventory MCP tool failed")
            result = response.structuredContent
            if not result:
                result = json.loads(response.content[0].text)
            assert result["dependency_count"] == 3, result
            assert result["unpinned_count"] == 1, result
            print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(inspect_inventory())
