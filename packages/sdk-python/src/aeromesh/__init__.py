"""AeroMesh Embeddable Python Kernel SDK (`aeromesh-sdk`)."""

from typing import Dict, Any, Optional
from aero.services.orchestrator import AeroMasterOrchestrator
from aero.domain.models import AgentManifest
from aero.domain.errors import AeroMeshDomainError

class AeroKernel:
    """Embeddable SDK class for executing Declarative Agent Manifests natively inside Python applications."""

    def __init__(self, orchestrator: Optional[AeroMasterOrchestrator] = None):
        self.orchestrator = orchestrator or AeroMasterOrchestrator()

    def run_agent(self, manifest_path: str, user_intent: str, non_interactive: bool = True) -> Dict[str, Any]:
        """Runs a DAM v3.0 manifest natively and returns execution results."""
        return self.orchestrator.dispatch(manifest_path, user_intent, non_interactive=non_interactive)

    def run_workflow(self, workflow_path: str, non_interactive: bool = True) -> Dict[str, Any]:
        """Runs a DWM v1.0 workflow.json file natively."""
        return self.orchestrator.dispatch(workflow_path, non_interactive=non_interactive)

__all__ = ["AeroKernel", "AgentManifest", "AeroMeshDomainError"]
