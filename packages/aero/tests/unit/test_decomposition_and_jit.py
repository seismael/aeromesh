"""Unit tests for AeroGoalDecompositionEngine & JIT Agent Manifest Synthesizer."""

import os
import json
import pytest
from aero.services.decomposition import AeroGoalDecompositionEngine
from aero.domain.models import AgentManifest
from aero.domain.errors import AeroMeshDomainError

def test_decompose_known_single_agent_goal():
    engine = AeroGoalDecompositionEngine()
    checklist = engine.decompose_goal("Optimize PostgreSQL database query SELECT * FROM users")
    
    assert checklist.goal == "Optimize PostgreSQL database query SELECT * FROM users"
    assert "postgres-performance-tuner" in checklist.matched_agent_ids
    assert "DB_CONNECT_STRING" in [c.id for c in checklist.required_credentials]

def test_decompose_multi_agent_composite_goal():
    engine = AeroGoalDecompositionEngine()
    checklist = engine.decompose_goal("Analyze slow DB query and audit GitHub repository aeromesh/aero for exposed secrets")
    
    assert len(checklist.matched_agent_ids) == 2
    assert "postgres-performance-tuner" in checklist.matched_agent_ids
    assert "enterprise-security-auditor" in checklist.matched_agent_ids
    req_ids = [c.id for c in checklist.required_credentials]
    assert "DB_CONNECT_STRING" in req_ids
    assert "GITHUB_TOKEN" in req_ids

def test_decompose_unknown_goal_jit_synthesis():
    engine = AeroGoalDecompositionEngine()
    checklist = engine.decompose_goal("Build a real-time anomaly detector for IoT temperature sensors")
    
    assert checklist.is_jit_synthesized is True
    assert checklist.synthesized_manifest is not None
    assert isinstance(checklist.synthesized_manifest, AgentManifest)
    assert checklist.synthesized_manifest.identity.id.startswith("jit-")

def test_fallback_negotiation_on_rejection():
    engine = AeroGoalDecompositionEngine()
    checklist = engine.decompose_goal("Optimize PostgreSQL database query SELECT * FROM users")
    
    # User rejects DB_CONNECT_STRING
    fallback_plan = engine.negotiate_fallback(checklist, rejected_key_id="DB_CONNECT_STRING")
    
    assert fallback_plan.is_degraded is True
    assert fallback_plan.active_agent_id != "postgres-performance-tuner"
    assert "offline" in fallback_plan.description.lower() or "degraded" in fallback_plan.description.lower()
