# Golden-path demo: Postgres query tuning

This example demonstrates the core loop end-to-end:

1. A **DAM v0.1 manifest** declares an MCP tool (`explain_query`) over **stdio**.
2. The engine **spawns the real MCP server subprocess**, performs the JSON-RPC
   handshake, and **actually calls the declared tool**.
3. The tool's result (a concrete index recommendation) flows back into the agent output.

The MCP server (`mock_postgres_mcp.py`) is a real JSON-RPC 2.0 stdio server — the
same transport a production Postgres MCP server uses — backed by canned data so it
runs offline with no database or API key.

## Run

```bash
python examples/postgres-tuning/demo.py
```

Expected: the tool is invoked once, its `CREATE INDEX` recommendation appears in
the output, and `success_criteria_met` is `True`.

> Note: the LLM reasoning layer still requires a live provider API key. This demo
> focuses on the **tool-execution** loop, which works offline via the mock model.
