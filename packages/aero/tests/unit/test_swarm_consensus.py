"""Unit tests for Multi-Agent Consensus Swarms in aero.services.pipeline."""

import pytest
from aero.services.pipeline import DeterministicPipelineOrchestrator

def test_consensus_swarm_execution():
    orchestrator = DeterministicPipelineOrchestrator()
    orchestrator.runner.vault.override_env.update({
        "DB_CONNECT_STRING": "postgresql://localhost:5432/test",
        "GITHUB_TOKEN": "ghp_1234567890abcdef",
    })

    manifest_paths = [
        "registry/agents/postgres-performance-tuner.json",
        "registry/agents/enterprise-security-auditor.json",
    ]
    res = orchestrator.execute_consensus_swarm(
        manifest_paths,
        "Analyze security and performance",
        consensus_threshold=0.5,
        non_interactive=True,
    )
    assert "consensus_reached" in res
    assert res["swarm_status"] in ("CONSENSUS_REACHED", "CONSENSUS_FAILED")
    assert len(res["agent_results"]) == 2
