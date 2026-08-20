"""Compile a DWM workflow into a LangGraph StateGraph of Deep Agents.

This does NOT hand-roll an orchestration engine: the workflow DAG becomes a
LangGraph graph whose nodes are Deep Agents (built from each referenced DAM
manifest). Independent steps run in parallel; `depends_on` edges enforce order.
"""

from typing import Annotated, Any, Dict, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.domain.models import WorkflowManifest
from aero.domain.paths import resolve_agent_manifest_path
from aero.infrastructure.parser import ManifestParser
from aero.services.deepagents_runner import DeepAgentsExecutionDriver


def _merge_outputs(left: Optional[Dict[str, str]], right: Dict[str, str]) -> Dict[str, str]:
    """LangGraph reducer: accumulate per-step results without losing parallel writes."""
    merged = dict(left or {})
    merged.update(right or {})
    return merged


def render_intent(intent: str, outputs: Dict[str, str]) -> str:
    """Inject upstream step results into a step's intent via {step_id} placeholders."""
    for dep_id, result in outputs.items():
        intent = intent.replace("{" + dep_id + "}", str(result or ""))
    return intent


class WorkflowState(TypedDict):
    intent: str
    outputs: Annotated[Dict[str, str], _merge_outputs]


class WorkflowExecutionDriver:
    """Executes a DWM workflow as a DAG of Deep Agents."""

    def __init__(
        self,
        workflow: WorkflowManifest,
        vault: Any = None,
        non_interactive: bool = True,
        parser: Any = None,
        model: Any = None,
    ):
        self.workflow = workflow
        self.parser = parser or ManifestParser()
        self.non_interactive = non_interactive
        self.model = model
        if vault is None:
            from aero.infrastructure.vault import ZeroTrustVaultResolver

            vault = ZeroTrustVaultResolver()
        self.vault = vault
        self._agents = self._resolve_agents()

    def _resolve_agents(self) -> Dict[str, Any]:
        agents: Dict[str, Any] = {}
        for step in self.workflow.steps:
            if step.agent_id in agents:
                continue
            resolved = resolve_agent_manifest_path(step.agent_id)
            if resolved is None:
                raise AeroMeshDomainError(
                    f"Workflow step '{step.id}' references unknown agent "
                    f"'{step.agent_id}'.",
                    ErrorCode.AMX_ERR_DISCOVERY_NO_MATCH,
                    ExitCode.DISCOVERY_NO_MATCH,
                )
            agents[step.agent_id] = self.parser.parse_file(str(resolved))
        return agents

    def _make_node(self, step: Any):
        def node(state: Dict[str, Any]) -> Dict[str, Any]:
            outputs = dict(state.get("outputs") or {})
            intent = render_intent(step.intent, outputs)

            manifest = self._agents[step.agent_id]
            credentials = self.vault.resolve_requirements(
                manifest.providers, non_interactive=self.non_interactive
            )
            driver = DeepAgentsExecutionDriver(
                manifest, credentials=credentials, model=self.model
            )
            try:
                result = driver.execute(
                    intent,
                    thread_id=f"wf-{self.workflow.identity.id}-{step.id}",
                )
            finally:
                driver.close()
            return {"outputs": {step.id: str(result.get("verified_result") or "")}}

        return node

    def _build_graph(self) -> Any:
        steps = self.workflow.steps
        dependents = {s.id: [] for s in steps}
        for s in steps:
            for dep in s.depends_on:
                dependents[dep].append(s.id)

        graph = StateGraph(WorkflowState)
        for s in steps:
            graph.add_node(s.id, self._make_node(s))

        for s in steps:
            for dep in s.depends_on:
                graph.add_edge(dep, s.id)
            if not s.depends_on:
                graph.add_edge(START, s.id)
            if not dependents[s.id]:
                graph.add_edge(s.id, END)

        return graph.compile()

    def execute(self, intent: str) -> Dict[str, Any]:
        graph = self._build_graph()
        state = graph.invoke({"intent": intent, "outputs": {}})
        outputs = dict(state.get("outputs") or {})

        final = None
        if self.workflow.output and self.workflow.output in outputs:
            final = outputs[self.workflow.output]
        return {
            "workflow_id": self.workflow.identity.id,
            "outputs": outputs,
            "verified_result": final if final is not None else outputs,
        }
