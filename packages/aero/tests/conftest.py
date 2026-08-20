import sys
import os

# Appends src/ to sys.path so tests can import amx modules natively
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

# Tests must not spawn real MCP subprocesses (e.g. `npx`); tool execution is
# exercised explicitly via injected mock drivers in test_tool_execution.py.
os.environ.setdefault("AEROMESH_EXECUTE_TOOLS", "0")
