"""Aero Master Orchestrator Facade Service for AeroMesh."""

import os
import json
from typing import Dict, Any, List, Union
from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.domain.paths import get_aeromesh_agents_dir
from aero.services.runner import AeroAgentRunnerService
from aero.services.pipeline import DeterministicPipelineOrchestrator
from aero.services.workflow import AeroWorkflowEngine

class AeroMasterOrchestrator:
    """Unified Facade Master Orchestrator for all Agent, Pipeline, and Mesh Workflow executions."""

    def __init__(self, max_workers: int = 10):
        self.runner = AeroAgentRunnerService()
        self.pipeline_orchestrator = DeterministicPipelineOrchestrator(runner_service=self.runner)
        self.workflow_engine = AeroWorkflowEngine(runner_service=self.runner, max_workers=max_workers)

    def dispatch(
        self,
        target: Union[str, List[str]],
        intent: str = None,
        non_interactive: bool = False,
        enable_diagnostics: bool = False,
    ) -> Dict[str, Any]:
        """Auto-detects execution mode and dispatches target request to the optimal engine."""

        # Mode 1: List of agent manifests passed -> Linear DGAP Pipeline
        if isinstance(target, list):
            if not intent:
                raise AeroMeshDomainError(
                    "Intent string is required for pipeline execution.",
                    ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                    ExitCode.SCHEMA_VIOLATION,
                )
            return {
                "mode": "PIPELINE",
                "result": self.pipeline_orchestrator.execute_pipeline(
                    target, intent, non_interactive=non_interactive, enable_diagnostics=enable_diagnostics
                )
            }

        target_str = str(target).strip()

        # Resolve local store path fallback for single agent ID
        if not os.path.exists(target_str):
            local_store_path = get_aeromesh_agents_dir() / f"{target_str}.json"
            if local_store_path.exists():
                target_str = str(local_store_path)

        if not os.path.exists(target_str):
            raise AeroMeshDomainError(
                f"Target file or agent ID not found: '{target_str}'",
                ErrorCode.AMX_ERR_DISCOVERY_NO_MATCH,
                ExitCode.DISCOVERY_NO_MATCH,
            )

        # Mode 2: Inspect JSON content to detect Workflow vs Single Agent
        try:
            with open(target_str, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise AeroMeshDomainError(
                f"Failed to parse JSON file '{target_str}': {str(e)}",
                ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                ExitCode.SCHEMA_VIOLATION,
            )

        if "workflow_version" in data or ("identity" in data and "steps" in data):
            # Mode 2A: Declarative Mesh Workflow (DWM v1.0)
            return {
                "mode": "WORKFLOW",
                "result": self.workflow_engine.execute_workflow(
                    target_str, non_interactive=non_interactive, enable_diagnostics=enable_diagnostics
                )
            }
        else:
            # Mode 2B: Single Declarative Agent Manifest
            if not intent:
                raise AeroMeshDomainError(
                    "Intent string is required for single agent execution.",
                    ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                    ExitCode.SCHEMA_VIOLATION,
                )
            return {
                "mode": "AGENT",
                "result": self.runner.run_manifest_file(
                    target_str, intent, non_interactive=non_interactive, enable_diagnostics=enable_diagnostics
                )
            }
