"""Minimal stdio MCP server simulating a PostgreSQL EXPLAIN tool (golden-path demo).

This is a real JSON-RPC 2.0 server over stdin/stdout — the same transport a real
MCP tool server uses — but backed by canned data so it runs anywhere offline.
"""

import json
import sys

EXPLAIN = {
    "plan": "Seq Scan on orders  (cost=0.00..12345.67 rows=100000 width=16)",
    "recommendation": "CREATE INDEX idx_orders_user_id ON orders(user_id);",
}


def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        req = json.loads(line.strip())
        rid = req.get("id")
        method = req.get("method")

        if method == "notifications/initialized":
            continue
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "mock-postgres", "version": "0.1.0"},
            }
        elif method == "tools/list":
            result = {
                "tools": [
                    {"name": "explain_query", "description": "Explain a SQL query",
                     "inputSchema": {"type": "object"}},
                    {"name": "execute_query", "description": "Execute a SQL query",
                     "inputSchema": {"type": "object"}},
                ]
            }
        elif method == "tools/call":
            result = {
                "content": [{"type": "text", "text": json.dumps(EXPLAIN)}],
                "isError": False,
            }
        else:
            result = {}

        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": rid, "result": result}) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
