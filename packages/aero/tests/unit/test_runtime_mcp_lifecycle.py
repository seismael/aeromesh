"""Real stdio MCP process lifecycle coverage; no paid model or network required."""

import sys
from typing import ClassVar

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from aero.infrastructure.parser import ManifestParser
from aero.services.deepagents_runner import DeepAgentsExecutionDriver


class ParallelToolModel(BaseChatModel):
    observed: ClassVar[list] = []
    max_tokens: int = 128

    @property
    def _llm_type(self):
        return "parallel-tool-offline"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        results = [m for m in messages if isinstance(m, ToolMessage)]
        if not results:
            response = AIMessage(
                content="",
                tool_calls=[
                    {"id": str(i), "name": "server__ping", "args": {"value": i}}
                    for i in (1, 2)
                ],
            )
        else:
            ParallelToolModel.observed = results
            response = AIMessage(content="Both real tool calls completed.")
        return ChatResult(generations=[ChatGeneration(message=response)])


def test_parallel_tools_share_one_live_mcp_process_and_cleanup(tmp_path):
    marker = tmp_path / "starts.txt"
    server = tmp_path / "server.py"
    server.write_text("""import asyncio, os, sys
from mcp.server.fastmcp import FastMCP
with open(sys.argv[1], 'a') as f: f.write(str(os.getpid()) + '\\n')
app = FastMCP('test')
@app.tool()
async def ping(value: int) -> str:
    await asyncio.sleep(0.02)
    return str(value)
app.run(transport='stdio')
""")
    manifest = ManifestParser().validate_dict(
        {
            "manifest_version": "1.0.0",
            "identity": {"id": "parallel", "name": "Parallel", "version": "1.0.0"},
            "capabilities": {
                "domain": "test",
                "tags": [],
                "short_description": "test",
                "evaluation_trigger": "test",
            },
            "cognitive_runtime": {
                "persona": "Call the ping tool twice.",
                "success_criteria": "Get both results.",
            },
            "requirements": {
                "providers": [
                    {
                        "type": "mcp",
                        "id": "server",
                        "transport": "stdio",
                        "command": sys.executable,
                        "args": [str(server), str(marker)],
                        "required_tools": ["ping"],
                    }
                ]
            },
        }
    )
    d = DeepAgentsExecutionDriver(
        manifest,
        model=ParallelToolModel(),
        development=True,
        checkpointer=InMemorySaver(),
        store=InMemoryStore(),
    )
    try:
        result = d.execute("Use both tools concurrently")
        assert result["execution_success"] is True
        # Discovery and both calls must use one retained session, not three spawns.
        assert len(marker.read_text().splitlines()) == 1
    finally:
        d.close()
    assert d._mcp_sessions.closed
