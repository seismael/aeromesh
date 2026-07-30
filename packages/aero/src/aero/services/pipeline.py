"""Deterministic Guaranteed Agent Pipeline (DGAP) Master Orchestrator."""

from typing import List, Dict, Any
from aero.domain.errors import AeroMeshDomainError
from aero.domain.models import AgentManifest
from aero.services.runner import AeroAgentRunnerService

class DeterministicPipelineOrchestrator:
    """Master orchestrator executing contract-validated guaranteed agent pipelines."""

    def __init__(self, runner_service: AeroAgentRunnerService = None):
        self.runner = runner_service or AeroAgentRunnerService()

    def execute_pipeline(
        self,
        manifest_paths: List[str],
        initial_intent: str,
        non_interactive: bool = False,
        enable_diagnostics: bool = False,
    ) -> Dict[str, Any]:
        """Executes a sequence of guaranteed agents step-by-step with output verification."""
        if not manifest_paths:
            raise AeroMeshDomainError("Pipeline must contain at least one agent manifest.")

        pipeline_results = []
        current_input = initial_intent

        for step_idx, manifest_path in enumerate(manifest_paths, start=1):
            manifest = self.runner.parser.parse_file(manifest_path)
            
            # Step execution
            step_res = self.runner.run_manifest_file(
                manifest_path,
                current_input,
                non_interactive=non_interactive,
                enable_diagnostics=enable_diagnostics,
            )

            verified_output = step_res["execution_result"].get("verified_result", "")
            
            pipeline_results.append({
                "step": step_idx,
                "agent_id": manifest.identity.id,
                "agent_name": manifest.identity.name,
                "domain": manifest.capabilities.domain,
                "input_intent": current_input,
                "verified_output": verified_output,
                "diagnostics": step_res.get("diagnostics"),
            })

            # Hand over verified output to the next agent in the guaranteed pipeline
            current_input = f"Process output from step {step_idx} ({manifest.identity.id}): {verified_output}"

        return {
            "pipeline_status": "COMPLETED_GUARANTEED",
            "steps_executed": len(pipeline_results),
            "final_verified_result": current_input,
            "pipeline_results": pipeline_results,
        }
