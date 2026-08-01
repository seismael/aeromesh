"""Deterministic Guaranteed Agent Pipeline (DGAP) Master Orchestrator."""

from typing import List, Dict, Any
from aero.domain.errors import AeroMeshDomainError
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
            raise AeroMeshDomainError(
                "Pipeline must contain at least one agent manifest."
            )

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

            pipeline_results.append(
                {
                    "step": step_idx,
                    "agent_id": manifest.identity.id,
                    "agent_name": manifest.identity.name,
                    "domain": manifest.capabilities.domain,
                    "input_intent": current_input,
                    "verified_output": verified_output,
                    "diagnostics": step_res.get("diagnostics"),
                }
            )

            # Hand over verified output to the next agent in the guaranteed pipeline
            current_input = f"Process output from step {step_idx} ({manifest.identity.id}): {verified_output}"

        return {
            "pipeline_status": "COMPLETED_GUARANTEED",
            "steps_executed": len(pipeline_results),
            "final_verified_result": current_input,
            "pipeline_results": pipeline_results,
        }

    def execute_consensus_swarm(
        self,
        manifest_paths: List[str],
        intent: str,
        consensus_threshold: float = 0.5,
        non_interactive: bool = False,
        enable_diagnostics: bool = False,
    ) -> Dict[str, Any]:
        """Executes multiple agents concurrently over intent and computes voting consensus agreement."""
        if not manifest_paths:
            raise AeroMeshDomainError(
                "Consensus swarm requires at least one agent manifest."
            )

        agent_results = []
        output_votes: Dict[str, int] = {}

        for manifest_path in manifest_paths:
            manifest = self.runner.parser.parse_file(manifest_path)
            res = self.runner.run_manifest_file(
                manifest_path,
                intent,
                non_interactive=non_interactive,
                enable_diagnostics=enable_diagnostics,
            )
            v_output = res["execution_result"].get("verified_result", "").strip()
            agent_results.append(
                {
                    "agent_id": manifest.identity.id,
                    "verified_output": v_output,
                }
            )
            output_votes[v_output] = output_votes.get(v_output, 0) + 1

        total_agents = len(manifest_paths)
        majority_output, highest_votes = (
            max(output_votes.items(), key=lambda item: item[1])
            if output_votes
            else ("", 0)
        )
        consensus_ratio = highest_votes / max(1, total_agents)
        consensus_reached = consensus_ratio >= consensus_threshold

        return {
            "swarm_status": "CONSENSUS_REACHED"
            if consensus_reached
            else "CONSENSUS_FAILED",
            "consensus_reached": consensus_reached,
            "consensus_ratio": consensus_ratio,
            "consensus_threshold": consensus_threshold,
            "winning_output": majority_output,
            "votes_tally": output_votes,
            "agent_results": agent_results,
        }
