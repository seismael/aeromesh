"""Thin SDK over the same verified execution paths as the CLI."""

__version__ = "1.0.0"

from pathlib import Path
from typing import Any, Dict, Optional

from aero.domain.models import AgentManifest, WorkflowManifest
from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.services.orchestrator import AeroMasterOrchestrator


class AeroKernel:
    def __init__(self, orchestrator: Optional[AeroMasterOrchestrator] = None):
        self.orchestrator = orchestrator or AeroMasterOrchestrator()

    def run_agent(
        self,
        manifest_path: str,
        user_intent: Any,
        non_interactive: bool = True,
        *,
        development: bool = False,
        synthesize: bool = False,
    ) -> Dict[str, Any]:
        return self.orchestrator.dispatch(
            manifest_path,
            user_intent,
            non_interactive=non_interactive,
            development=development,
            synthesize=synthesize,
        )

    def run_workflow(
        self,
        workflow_path: str,
        user_intent: Any,
        non_interactive: bool = True,
        *,
        development: bool = False,
    ) -> Dict[str, Any]:
        from aero.domain.paths import resolve_workflow_manifest_path
        from aero.infrastructure.parser import WorkflowParser
        from aero.services.workflow_runner import WorkflowExecutionDriver
        from aero.services import trust

        resolved = resolve_workflow_manifest_path(workflow_path)
        if resolved is None:
            raise AeroMeshDomainError(
                "Workflow not found",
                ErrorCode.AMX_ERR_DISCOVERY_NO_MATCH,
                ExitCode.DISCOVERY_NO_MATCH,
            )
        parser = WorkflowParser()
        expected_id = (
            None
            if Path(workflow_path).is_file()
            else str(workflow_path).removesuffix(".json")
        )
        workflow = (
            parser.parse_file(str(resolved))
            if development
            else parser.validate_dict(
                trust.require_trusted_manifest(str(resolved), expected_id=expected_id)
            )
        )
        if expected_id is not None and workflow.identity.id != expected_id:
            raise AeroMeshDomainError(
                "Catalog reference resolved to a different artifact identity.",
                ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                ExitCode.SCHEMA_VIOLATION,
            )
        driver = WorkflowExecutionDriver(
            workflow,
            non_interactive=non_interactive,
            development=development,
            manifest_path=str(resolved),
        )
        return {
            "workflow_id": workflow.identity.id,
            "result": driver.execute(user_intent),
        }

    def run_release(self, release: str, user_intent: Any) -> Dict[str, Any]:
        from aero.services.releases import load_approved_release
        from aero.infrastructure.parser import WorkflowParser
        from aero.services.runner import AeroAgentRunnerService
        from aero.services.workflow_runner import WorkflowExecutionDriver

        approved = load_approved_release(release)
        if approved.data["entry"]["kind"] == "workflow":
            workflow = WorkflowParser().validate_dict(approved.entry_data)
            return WorkflowExecutionDriver(
                workflow,
                manifest_path=str(approved.entry_path),
                approved_release=approved,
                non_interactive=True,
            ).execute(user_intent)
        return AeroAgentRunnerService().run_manifest_file(
            str(approved.entry_path),
            user_intent,
            approved_release=approved,
            non_interactive=True,
        )


__all__ = ["AeroKernel", "AgentManifest", "WorkflowManifest", "AeroMeshDomainError"]
