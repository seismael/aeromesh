"""AeroMesh Embeddable Python SDK (`aeromesh-sdk`)."""

from typing import Dict, Any, Optional

from aero.services.orchestrator import AeroMasterOrchestrator
from aero.domain.models import AgentManifest, WorkflowManifest
from aero.domain.errors import AeroMeshDomainError


class AeroKernel:
    """Embeddable SDK for running DAM manifests and DWM workflows via Deep Agents."""

    def __init__(self, orchestrator: Optional[AeroMasterOrchestrator] = None):
        self.orchestrator = orchestrator or AeroMasterOrchestrator()

    def run_agent(
        self, manifest_path: str, user_intent: str, non_interactive: bool = True
    ) -> Dict[str, Any]:
        """Run a DAM v0.1 manifest (path/agent id) or a natural-language goal."""
        return self.orchestrator.dispatch(
            manifest_path, user_intent, non_interactive=non_interactive
        )

    def run_workflow(
        self, workflow_path: str, user_intent: str, non_interactive: bool = True
    ) -> Dict[str, Any]:
        """Run a DWM v0.1 workflow (path/id) or synthesize one from a goal."""
        from aero.domain.paths import resolve_workflow_manifest_path
        from aero.infrastructure.parser import WorkflowParser
        from aero.services.workflow_runner import WorkflowExecutionDriver
        from aero.services.workflow_synthesizer import WorkflowSynthesizer

        resolved = resolve_workflow_manifest_path(workflow_path)
        if resolved:
            workflow = WorkflowParser().parse_file(str(resolved))
        else:
            workflow = WorkflowSynthesizer().synthesize(workflow_path)

        driver = WorkflowExecutionDriver(workflow, non_interactive=non_interactive)
        return {
            "workflow_id": workflow.identity.id,
            "result": driver.execute(user_intent),
        }


__all__ = ["AeroKernel", "AgentManifest", "WorkflowManifest", "AeroMeshDomainError"]
