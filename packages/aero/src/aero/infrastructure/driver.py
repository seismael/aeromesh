"""LangGraph Execution Driver: runs a DAM v0.1 manifest's tools + LLM in a graph."""

import json
import os
import time
from typing import Any, Dict, List, Optional, TypedDict

import jsonschema
from langgraph.graph import END, StateGraph

from aero.domain.models import AgentManifest
from aero.infrastructure.diagnostics import AeroDiagnosticTracer
from aero.infrastructure.mcp import McpSseDriver, McpStdioDriver
from aero.infrastructure.providers import CognitiveProviderAdapter
from aero.infrastructure.sandbox import NetworkSandboxFirewall


class AgentState(TypedDict, total=False):
    intent: str
    agent_id: str
    step: str
    status: str
    todos: List[str]
    mcp_output: str
    tool_results: List[str]
    tools_called: int
    provider_id: str
    verified_result: str
    success_criteria_met: bool


class LangGraphExecutionDriver:
    """Executes a DAM v0.1 manifest: invoke declared tools, then reason over results."""

    def __init__(
        self,
        manifest: AgentManifest,
        credentials: Dict[str, str],
        tracer: AeroDiagnosticTracer = None,
        mcp_drivers: Optional[List[Any]] = None,
        execute_tools: Optional[bool] = None,
    ):
        self.manifest = manifest
        self.credentials = credentials
        self.tracer = tracer or AeroDiagnosticTracer(enabled=False)
        self.persona = manifest.cognitive_runtime.persona
        self.success_criteria = manifest.cognitive_runtime.success_criteria

        if execute_tools is None:
            # Real usage executes tools by default; tests can disable via env.
            execute_tools = os.environ.get("AEROMESH_EXECUTE_TOOLS", "1") != "0"
        self.execute_tools = execute_tools

        self.provider_adapter = CognitiveProviderAdapter(credentials=credentials)

        allowed_domains: List[str] = []
        self.required_tools: List[str] = []
        for p in manifest.providers:
            if p.allowed_domains:
                allowed_domains.extend(p.allowed_domains)
            if p.required_tools:
                self.required_tools.extend(p.required_tools)
        self.sandbox = NetworkSandboxFirewall(allowed_domains=allowed_domains)

        self.mcp_drivers: List[Any] = []
        if mcp_drivers is not None:
            self.mcp_drivers = list(mcp_drivers)
        else:
            self._init_mcp_drivers()

    def _init_mcp_drivers(self) -> None:
        """Instantiate MCP drivers for declared stdio and remote SSE requirements."""
        for p in self.manifest.providers:
            if p.type == "mcp" and p.command:
                self.mcp_drivers.append(
                    McpStdioDriver(
                        command=p.command,
                        args=p.args,
                        env=self.credentials,
                        timeout_sec=3.0,
                    )
                )
            elif p.type == "mcp" and p.uri and (
                p.transport == "sse" or str(p.uri).startswith("http")
            ):
                self.mcp_drivers.append(
                    McpSseDriver(
                        uri=p.uri, allowed_domains=self.sandbox.allowed_domains
                    )
                )

    def _execute_tools(self, intent: str) -> List[str]:
        """Invoke declared MCP tools and return their text results (best-effort)."""
        results: List[str] = []
        if not self.execute_tools or not self.mcp_drivers:
            return results

        for driver in self.mcp_drivers:
            name = getattr(driver, "command", None) or getattr(driver, "uri", "tool")
            try:
                driver.spawn()
                if hasattr(driver, "initialize"):
                    driver.initialize()
                elif hasattr(driver, "connect"):
                    driver.connect()
                for tool in driver.list_tools():
                    if not self.required_tools or tool.name in self.required_tools:
                        r = driver.call_tool(tool.name, {"query": intent})
                        results.append(f"[{tool.name}] {r.content}")
            except Exception as e:  # noqa: BLE001 — degrade gracefully
                results.append(f"[tool-unavailable:{name}] {e}")
            finally:
                try:
                    driver.close()
                except Exception:
                    pass
        return results

    def build_graph(self) -> StateGraph:
        workflow = StateGraph(AgentState)

        def planner_step(state):
            t0 = time.time()
            res = {
                "step": "planning",
                "status": "planned",
                "todos": ["Analyze intent", "Execute declared tools", "Verify result"],
            }
            if self.tracer.enabled:
                self.tracer.record_span(
                    event_type="NODE_ENTERED",
                    component="LangGraph.Planner",
                    duration_ms=(time.time() - t0) * 1000,
                )
            return res

        def execution_step(state):
            t0 = time.time()
            intent = state.get("intent", "")
            tool_results = self._execute_tools(intent)

            prompt = intent
            if tool_results:
                prompt += "\n\nTool results:\n" + "\n".join(tool_results)

            llm_output = self.provider_adapter.complete_prompt(
                system_prompt=self.persona,
                user_prompt=prompt,
            )
            res = {
                "step": "execution",
                "status": "executed",
                "mcp_output": llm_output,
                "tool_results": tool_results,
                "tools_called": len(tool_results),
                "provider_id": self.provider_adapter.active_provider_id,
            }
            if self.tracer.enabled:
                self.tracer.record_span(
                    event_type="MCP_TOOL_CALLED" if tool_results else "MCP_TOOL_SKIPPED",
                    component="LangGraph.Executor",
                    duration_ms=(time.time() - t0) * 1000,
                    metadata={
                        "tools_called": len(tool_results),
                        "provider": self.provider_adapter.active_provider_id,
                    },
                )
            return res

        def verification_step(state):
            t0 = time.time()
            output = state.get("mcp_output", "")
            tool_results = state.get("tool_results", [])
            # Non-vacuous: success requires non-empty output (LLM text or tool result).
            success = bool(output and output.strip()) or bool(tool_results)

            # Enforce the declared output_contract (JSON Schema) if present.
            contract = getattr(self.manifest.capabilities, "output_contract", None)
            if success and contract and output and output.strip():
                try:
                    data = json.loads(output)
                    jsonschema.validate(instance=data, schema=contract)
                except Exception:
                    success = False

            res = {
                "step": "verification",
                "status": "completed",
                "verified_result": output or "Success",
                "success_criteria_met": success,
            }
            if self.tracer.enabled:
                self.tracer.record_span(
                    event_type="CRITERIA_VERIFIED",
                    component="LangGraph.Verifier",
                    duration_ms=(time.time() - t0) * 1000,
                    metadata={"criteria": self.success_criteria, "met": success},
                )
            return res

        workflow.add_node("planner", planner_step)
        workflow.add_node("executor", execution_step)
        workflow.add_node("verifier", verification_step)

        workflow.set_entry_point("planner")
        workflow.add_edge("planner", "executor")
        workflow.add_edge("executor", "verifier")
        workflow.add_edge("verifier", END)

        return workflow.compile()

    def execute(self, user_intent: str) -> Dict[str, Any]:
        obs = getattr(self.manifest, "observability", None)
        if obs and obs.cost_limit_usd is not None:
            estimated_cost = 0.05
            if estimated_cost > obs.cost_limit_usd:
                from aero.domain.errors import (
                    AeroMeshDomainError,
                    ErrorCode,
                    ExitCode,
                )

                raise AeroMeshDomainError(
                    f"Execution cost (${estimated_cost:.2f}) exceeded observability USD budget limit (${obs.cost_limit_usd:.2f}).",
                    ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                    ExitCode.SCHEMA_VIOLATION,
                )

        app = self.build_graph()
        initial_state = {"intent": user_intent, "agent_id": self.manifest.identity.id}
        return app.invoke(initial_state)
