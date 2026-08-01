"""Unit tests for Hybrid Swarm Synthesis in AeroGoalDecompositionEngine."""

import pytest
from aero.services.decomposition import AeroGoalDecompositionEngine

def test_hybrid_swarm_synthesis():
    engine = AeroGoalDecompositionEngine()
    # Compound goal with known agent (security audit) AND unknown sub-goal (generate custom PDF)
    checklist = engine.decompose_goal("Audit workspace secrets and generate custom executive PDF summary")

    assert len(checklist.matched_agent_ids) >= 2
    assert "enterprise-security-auditor" in checklist.matched_agent_ids
    assert any(m.identity.id.startswith("jit-") for m in checklist.matched_manifests)
    assert checklist.is_jit_synthesized is True
