"""Aero Master Orchestrator Facade Service for AeroMesh."""

import os
import json
from typing import Dict, Any, List, Union, Optional
from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.domain.paths import get_aeromesh_agents_dir, resolve_agent_manifest_path
from aero.services.runner import AeroAgentRunnerService
from aero.services.pipeline import DeterministicPipelineOrchestrator
from aero.services.workflow import AeroWorkflowEngine
from aero.services.preflight import AeroInteractivePreflightEngine
from aero.services.decomposition import AeroGoalDecompositionEngine

class AeroMasterOrchestrator:
    """Unified Facade Master Orchestrator for all Agent, Pipeline, Mesh Workflow, and JIT Natural Language executions."""

    def __init__(
        self,
        max_workers: int = 10,
        preflight_engine: Optional[AeroInteractivePreflightEngine] = None,
        decomposition_engine: Optional[AeroGoalDecompositionEngine] = None,
    ):
        self.runner = AeroAgentRunnerService()
        self.pipeline_orchestrator = DeterministicPipelineOrchestrator(runner_service=self.runner)
        self.workflow_engine = AeroWorkflowEngine(runner_service=self.runner, max_workers=max_workers)
        self.preflight = preflight_engine or AeroInteractivePreflightEngine()
        self.decomposition = decomposition_engine or AeroGoalDecompositionEngine()

    def dispatch(
        self,
        target: Union[str, List[str]],
        intent: str = None,
        non_interactive: bool = False,
        enable_diagnostics: bool = False,
    ) -> Dict[str, Any]:
        """Auto-detects execution mode and dispatches target request to the optimal engine."""

        # Pre-Flight Check: Ensure an active LLM provider key is configured
        self.preflight.ensure_default_provider(non_interactive=non_interactive)

        # Mode 1: List of agent manifests passed -> Linear DGAP Pipeline
        if isinstance(target, list):
            if not intent:
                raise AeroMeshDomainError(
                    "Intent string is required for pipeline execution.",
                    ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                    ExitCode.SCHEMA_VIOLATION,
                )
            resolved_targets = []
            for manifest_target in target:
                resolved = resolve_agent_manifest_path(str(manifest_target))
                if not resolved:
                    raise AeroMeshDomainError(
                        f"Pipeline target manifest '{manifest_target}' not found.",
                        ErrorCode.AMX_ERR_DISCOVERY_NO_MATCH,
                        ExitCode.DISCOVERY_NO_MATCH,
                    )
                manifest = self.runner.parser.parse_file(str(resolved))
                self.preflight.verify_agent_feasibility(manifest, intent)
                resolved_targets.append(str(resolved))

            return {
                "mode": "PIPELINE",
                "result": self.pipeline_orchestrator.execute_pipeline(
                    resolved_targets, intent, non_interactive=non_interactive, enable_diagnostics=enable_diagnostics
                )
            }

        target_str = str(target).strip()

        # Mode 2: Resolve agent file or ID via Dual Registry Resolution
        resolved_path = resolve_agent_manifest_path(target_str)
        if not resolved_path:
            if target_str.endswith(".json") or target_str.endswith(".yaml") or "/" in target_str or "\\" in target_str:
                raise AeroMeshDomainError(
                    f"Target file or agent ID not found: '{target_str}'",
                    ErrorCode.AMX_ERR_DISCOVERY_NO_MATCH,
                    ExitCode.DISCOVERY_NO_MATCH,
                )

            # Mode 3: Natural Language Goal Decomposition & JIT Agent Manifest Synthesis
            checklist = self.decomposition.decompose_goal(target_str)
            if not non_interactive:
                from aero.presentation.ui import AeroTerminalUI
                AeroTerminalUI.render_requirements_checklist(checklist)

            if checklist.is_jit_synthesized:
                # Execute JIT synthesized manifest
                self.preflight.verify_agent_feasibility(checklist.synthesized_manifest, target_str)
                res = self.runner.run_manifest_file(
                    None,
                    target_str,
                    non_interactive=non_interactive,
                    enable_diagnostics=enable_diagnostics,
                    manifest_object=checklist.synthesized_manifest,
                )
                return {"mode": "JIT_AGENT", "result": res, "checklist": checklist}
            elif len(checklist.matched_manifests) > 1:
                # Composite Swarm Pipeline
                agent_paths = [str(resolve_agent_manifest_path(m_id)) for m_id in checklist.matched_agent_ids]
                res = self.pipeline_orchestrator.execute_pipeline(
                    agent_paths, target_str, non_interactive=non_interactive, enable_diagnostics=enable_diagnostics
                )
                return {"mode": "PIPELINE", "result": res, "checklist": checklist}
            else:
                # Matched Single Registry Agent
                target_str = str(resolve_agent_manifest_path(checklist.matched_agent_ids[0]))

        # Mode 4: Inspect JSON content to detect Workflow vs Single Agent
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
            manifest = self.runner.parser.parse_file(target_str)
            self.preflight.verify_agent_feasibility(manifest, intent)

            return {
                "mode": "AGENT",
                "result": self.runner.run_manifest_file(
                    target_str, intent, non_interactive=non_interactive, enable_diagnostics=enable_diagnostics
                )
            }
