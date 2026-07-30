# Runtime MCP Driver & Dynamic JIT Builder Specification

**Document Version:** 1.0.0 (Authoritative Final Release)  
**Package Mapping:** `packages/mcp-driver` & `packages/jit-builder`  
**SLA Targets:** MCP Tool Timeout 30s | JIT Builder Retry Limit 3  

---

## 1. Executive Summary & Runtime Architecture

The runtime engine decouples tool execution from cognitive orchestration using two specialized subsystems:

1. **Runtime MCP Transport Driver (`packages/mcp-driver`)**: Manages external Model Context Protocol (MCP) servers operating over `stdio` subprocess pipes (`npx`, `python`, `uvx`) and `sse` HTTP streams using JSON-RPC 2.0.
2. **Dynamic JIT Builder (`packages/jit-builder`)**: Automatically synthesizes valid DAM v3.0 manifests on the fly when discovery searches return 0 matches.

---

## 2. MCP Transport Driver Architecture (`IMcpDriver`)

```python
# packages/mcp-driver/interfaces.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List

class IMcpDriver(ABC):
    """Abstract interface for stdio and sse MCP server transport daemons."""

    @abstractmethod
    async def start(self, command: str, args: List[str], env: Dict[str, str]) -> None:
        """Spawns background MCP server daemon process."""
        pass

    @abstractmethod
    async def list_tools(self) -> List[Dict[str, Any]]:
        """Queries available tools via JSON-RPC 2.0 ('tools/list')."""
        pass

    @abstractmethod
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any], timeout_sec: float = 30.0) -> Dict[str, Any]:
        """Executes a tool call with a hard 30-second timeout limit."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully terminates background subprocess."""
        pass
```

---

## 3. Dynamic JIT Builder Retry Loop

When a user intent yields 0 matches in the discovery index, the JIT Builder synthesizes a custom DAM v3.0 manifest:

```
                            ┌───────────────────────────┐
                            │ 0 Matches in Index Search │
                            └─────────────┬─────────────┘
                                          │
                                          ▼
                            ┌───────────────────────────┐
                            │ JIT LLM Compiler Attempt 1│
                            └─────────────┬─────────────┘
                                          │
                                          ▼
                            ┌───────────────────────────┐
                            │ JSON Schema Assertions    │
                            └─────────────┬─────────────┘
                                   │              │
                           (Valid) │              │ (Invalid)
                                   ▼              ▼
                       ┌───────────────┐  ┌───────────────────────────────────┐
                       │ Execute Agent │  │ Feed Schema Error Back to JIT LLM │
                       └───────────────┘  │ (Retry Loop: Max 3 Retries)      │
                                          └───────────────────────────────────┘
```
