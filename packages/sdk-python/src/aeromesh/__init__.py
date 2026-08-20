"""AeroMesh Embeddable Python SDK (`aeromesh-sdk`)."""

from typing import Dict, Any, Optional

from aero.services.orchestrator import AeroMasterOrchestrator
from aero.domain.models import AgentManifest
from aero.domain.errors import AeroMeshDomainError


class AeroKernel:
    """Embeddable SDK for executing DAM v0.1 manifests via Deep Agents."""

    def __init__(self, orchestrator: Optional[AeroMasterOrchestrator] = None):
        self.orchestrator = orchestrator or AeroMasterOrchestrator()

    def run_agent(
        self, manifest_path: str, user_intent: str, non_interactive: bool = True
    ) -> Dict[str, Any]:
        """Run a DAM v0.1 manifest (path/agent id) or a natural-language goal."""
        return self.orchestrator.dispatch(
            manifest_path, user_intent, non_interactive=non_interactive
        )


__all__ = ["AeroKernel", "AgentManifest", "AeroMeshDomainError"]
