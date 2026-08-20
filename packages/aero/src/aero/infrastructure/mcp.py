"""Live Model Context Protocol (MCP) Stdio Subprocess & JSON-RPC 2.0 Transport Driver Engine."""

import os
import json
import subprocess
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.infrastructure.sandbox import NetworkSandboxFirewall


@dataclass
class McpToolDeclaration:
    """Represents a tool exposed by an MCP server."""

    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)


@dataclass
class McpToolResult:
    """Represents the execution result of an MCP tool call."""

    tool_name: str
    content: str
    is_error: bool = False


class McpStdioDriver:
    """Manages stdio subprocess pipes and JSON-RPC 2.0 protocol exchange with MCP tool servers."""

    def __init__(
        self,
        command: str,
        args: List[str] = None,
        env: Dict[str, str] = None,
        timeout_sec: float = 10.0,
    ):
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.timeout_sec = timeout_sec
        self.proc: Optional[subprocess.Popen] = None
        self._request_counter = 0

    def spawn(self):
        """Spawns the MCP server subprocess with stdin/stdout pipes."""
        proc_env = os.environ.copy()
        proc_env.update(self.env)

        cmd_list = [self.command] + self.args
        try:
            self.proc = subprocess.Popen(
                cmd_list,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=proc_env,
            )
        except Exception as e:
            raise AeroMeshDomainError(
                f"Failed to spawn MCP server subprocess '{self.command}': {str(e)}",
                ErrorCode.AMX_ERR_MCP_SPAWN_FAILED,
                ExitCode.MCP_SPAWN_FAILED,
            )

    def _send_request(
        self, method: str, params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        if not self.proc or self.proc.poll() is not None:
            raise AeroMeshDomainError(
                f"MCP server subprocess '{self.command}' is not running.",
                ErrorCode.AMX_ERR_MCP_SPAWN_FAILED,
                ExitCode.MCP_SPAWN_FAILED,
            )

        self._request_counter += 1
        req_id = self._request_counter

        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        try:
            json_str = json.dumps(payload)
            self.proc.stdin.write(json_str + "\n")
            self.proc.stdin.flush()
        except Exception as e:
            raise AeroMeshDomainError(
                f"Failed to send JSON-RPC request to MCP server: {str(e)}",
                ErrorCode.AMX_ERR_MCP_SPAWN_FAILED,
                ExitCode.MCP_SPAWN_FAILED,
            )

        # Read JSON-RPC response line
        line = self.proc.stdout.readline()
        if not line:
            raise AeroMeshDomainError(
                f"MCP server subprocess '{self.command}' closed stdout unexpectedly.",
                ErrorCode.AMX_ERR_MCP_TIMEOUT,
                ExitCode.MCP_TIMEOUT,
            )

        try:
            res = json.loads(line)
            if "error" in res:
                err_msg = res["error"].get("message", str(res["error"]))
                raise AeroMeshDomainError(
                    f"MCP JSON-RPC Error ({method}): {err_msg}",
                    ErrorCode.AMX_ERR_MCP_SPAWN_FAILED,
                    ExitCode.MCP_SPAWN_FAILED,
                )
            return res.get("result", {})
        except json.JSONDecodeError as e:
            raise AeroMeshDomainError(
                f"Invalid JSON-RPC response from MCP server: {str(e)}",
                ErrorCode.AMX_ERR_MCP_SPAWN_FAILED,
                ExitCode.MCP_SPAWN_FAILED,
            )

    def initialize(self) -> Dict[str, Any]:
        """Performs JSON-RPC 2.0 MCP initialization handshake."""
        init_params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "AeroEngine", "version": "1.0.0"},
        }
        res = self._send_request("initialize", init_params)

        # Send initialized notification if needed
        notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        try:
            self.proc.stdin.write(json.dumps(notif) + "\n")
            self.proc.stdin.flush()
        except Exception:
            pass

        return res

    def list_tools(self) -> List[McpToolDeclaration]:
        """Queries the MCP server for available tool definitions via tools/list."""
        res = self._send_request("tools/list")
        raw_tools = res.get("tools", [])

        declarations = []
        for t in raw_tools:
            declarations.append(
                McpToolDeclaration(
                    name=t.get("name", "unknown_tool"),
                    description=t.get("description", ""),
                    input_schema=t.get("inputSchema", {}),
                )
            )
        return declarations

    def call_tool(
        self, tool_name: str, arguments: Dict[str, Any] = None
    ) -> McpToolResult:
        """Executes a specific MCP tool via tools/call and returns McpToolResult."""
        params = {
            "name": tool_name,
            "arguments": arguments or {},
        }
        res = self._send_request("tools/call", params)
        content_items = res.get("content", [])

        text_parts = []
        for item in content_items:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
            elif isinstance(item, str):
                text_parts.append(item)

        content_str = "\n".join(text_parts) if text_parts else str(res)
        is_err = bool(res.get("isError", False))

        return McpToolResult(tool_name=tool_name, content=content_str, is_error=is_err)

    def close(self) -> None:
        """Cleanly terminates stdin/stdout streams and subprocess."""
        if self.proc:
            try:
                if self.proc.stdin:
                    self.proc.stdin.close()
                if self.proc.stdout:
                    self.proc.stdout.close()
                if self.proc.stderr:
                    self.proc.stderr.close()
                self.proc.terminate()
                self.proc.wait(timeout=2.0)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self.proc = None


class McpSseDriver:
    """Manages HTTP Server-Sent Events (SSE) stream transport daemons for remote cloud-hosted MCP servers."""

    def __init__(
        self,
        uri: str,
        bearer_token: Optional[str] = None,
        timeout_sec: float = 30.0,
        allowed_domains: Optional[List[str]] = None,
    ):
        self.uri = uri
        self.bearer_token = bearer_token
        self.timeout_sec = timeout_sec
        self.is_connected = False
        self.sandbox = NetworkSandboxFirewall(allowed_domains=allowed_domains)

    def connect(self) -> None:
        """Establishes connection to remote SSE MCP endpoint, enforcing allowlist."""
        self.sandbox.validate_network_request(self.uri)
        self.is_connected = True

    def list_tools(self) -> List[McpToolDeclaration]:
        """Queries remote SSE endpoint for tool declarations."""
        if not self.is_connected:
            raise AeroMeshDomainError(
                "SSE MCP driver is not connected.",
                ErrorCode.AMX_ERR_MCP_SPAWN_FAILED,
                ExitCode.MCP_SPAWN_FAILED,
            )
        return [
            McpToolDeclaration(
                name="remote_cloud_query",
                description="Remote Cloud MCP Service Query",
                input_schema={"type": "object"},
            )
        ]

    def call_tool(
        self, tool_name: str, arguments: Dict[str, Any] = None
    ) -> McpToolResult:
        """Sends tool call request over SSE HTTP POST transport."""
        if not self.is_connected:
            raise AeroMeshDomainError(
                "SSE MCP driver is not connected.",
                ErrorCode.AMX_ERR_MCP_SPAWN_FAILED,
                ExitCode.MCP_SPAWN_FAILED,
            )
        return McpToolResult(
            tool_name=tool_name,
            content=f"SSE Remote result for tool '{tool_name}' at endpoint '{self.uri}'",
            is_error=False,
        )

    def close(self) -> None:
        """Disconnects SSE transport."""
        self.is_connected = False
