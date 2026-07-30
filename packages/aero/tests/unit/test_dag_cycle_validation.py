"""Unit tests for AeroWorkflowEngine DAG topological validation and cycle detection."""

import os
import json
import shutil
import pytest
from aero.services.workflow import AeroWorkflowEngine
from aero.domain.errors import AeroMeshDomainError, ErrorCode

SCRATCH_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".test_scratch")

@pytest.fixture(autouse=True)
def scratch_dir():
    abs_dir = os.path.abspath(SCRATCH_DIR)
    os.makedirs(abs_dir, exist_ok=True)
    yield abs_dir
    shutil.rmtree(abs_dir, ignore_errors=True)

def test_workflow_valid_dag(scratch_dir):
    wf_path = os.path.join(scratch_dir, "valid_dag.json")
    wf_data = {
        "workflow_version": "1.0.0",
        "identity": {"id": "valid-dag", "name": "Valid DAG Workflow"},
        "steps": [
            {"id": "step1", "agent_id": "postgres-performance-tuner", "intent": "step 1", "depends_on": []},
            {"id": "step2", "agent_id": "enterprise-security-auditor", "intent": "step 2", "depends_on": ["step1"]},
        ]
    }
    with open(wf_path, "w", encoding="utf-8") as f:
        json.dump(wf_data, f)

    engine = AeroWorkflowEngine()
    validated = engine.validate_workflow_file(wf_path)
    assert validated["identity"]["id"] == "valid-dag"

def test_workflow_missing_dependency_step_id(scratch_dir):
    wf_path = os.path.join(scratch_dir, "missing_dep.json")
    wf_data = {
        "workflow_version": "1.0.0",
        "identity": {"id": "missing-dep", "name": "Missing Dep Workflow"},
        "steps": [
            {"id": "step1", "agent_id": "postgres-performance-tuner", "intent": "step 1", "depends_on": ["non_existent_step"]},
        ]
    }
    with open(wf_path, "w", encoding="utf-8") as f:
        json.dump(wf_data, f)

    engine = AeroWorkflowEngine()
    with pytest.raises(AeroMeshDomainError) as exc:
        engine.validate_workflow_file(wf_path)
    assert exc.value.error_code == ErrorCode.AMX_ERR_SCHEMA_VIOLATION
    assert "non_existent_step" in exc.value.message

def test_workflow_direct_cycle_detection(scratch_dir):
    wf_path = os.path.join(scratch_dir, "cycle_direct.json")
    wf_data = {
        "workflow_version": "1.0.0",
        "identity": {"id": "cycle-direct", "name": "Direct Cycle Workflow"},
        "steps": [
            {"id": "stepA", "agent_id": "postgres-performance-tuner", "intent": "step A", "depends_on": ["stepB"]},
            {"id": "stepB", "agent_id": "enterprise-security-auditor", "intent": "step B", "depends_on": ["stepA"]},
        ]
    }
    with open(wf_path, "w", encoding="utf-8") as f:
        json.dump(wf_data, f)

    engine = AeroWorkflowEngine()
    with pytest.raises(AeroMeshDomainError) as exc:
        engine.validate_workflow_file(wf_path)
    assert exc.value.error_code == ErrorCode.AMX_ERR_SCHEMA_VIOLATION
    assert "cyclic dependency" in exc.value.message.lower()

def test_workflow_indirect_3_node_cycle_detection(scratch_dir):
    wf_path = os.path.join(scratch_dir, "cycle_indirect.json")
    wf_data = {
        "workflow_version": "1.0.0",
        "identity": {"id": "cycle-indirect", "name": "Indirect Cycle Workflow"},
        "steps": [
            {"id": "step1", "agent_id": "agent1", "intent": "1", "depends_on": ["step3"]},
            {"id": "step2", "agent_id": "agent2", "intent": "2", "depends_on": ["step1"]},
            {"id": "step3", "agent_id": "agent3", "intent": "3", "depends_on": ["step2"]},
        ]
    }
    with open(wf_path, "w", encoding="utf-8") as f:
        json.dump(wf_data, f)

    engine = AeroWorkflowEngine()
    with pytest.raises(AeroMeshDomainError) as exc:
        engine.validate_workflow_file(wf_path)
    assert exc.value.error_code == ErrorCode.AMX_ERR_SCHEMA_VIOLATION
    assert "cyclic dependency" in exc.value.message.lower()
