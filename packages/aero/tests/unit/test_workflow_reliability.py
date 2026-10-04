"""Regression guarantees at real LangGraph dependency and run boundaries."""

import json

import pytest

from aero.domain.errors import AeroMeshDomainError
from aero.infrastructure.parser import WorkflowParser
from aero.services import workflow_runner


def workflow(tmp_path, monkeypatch, steps):
    payload = {
        "manifest_version": "0.1.0",
        "identity": {"id": "worker", "name": "Worker", "version": "1.0.0"},
        "capabilities": {
            "domain": "test",
            "tags": [],
            "short_description": "test",
            "evaluation_trigger": "test",
        },
        "cognitive_runtime": {"persona": "test", "success_criteria": "test"},
        "requirements": {"providers": []},
    }
    path = tmp_path / "worker.json"
    path.write_text(json.dumps(payload))
    monkeypatch.setattr(workflow_runner, "resolve_agent_manifest_path", lambda _: path)
    return WorkflowParser().validate_dict(
        {
            "workflow_version": "0.1.0",
            "identity": {"id": "pipeline", "name": "Pipeline", "version": "1.0.0"},
            "steps": [{"agent_id": "worker", **step} for step in steps],
            "output": steps[-1]["id"],
        }
    )


def install_driver(monkeypatch, calls, fail=None):
    class Driver:
        def __init__(self, *args, **kwargs):
            pass

        def execute(self, intent, thread_id=None):
            calls.append((intent, thread_id))
            if fail and fail in intent:
                return {"verified_result": "failed", "execution_success": False}
            return {
                "verified_result": "evidence",
                "execution_success": True,
                "execution_completed": True,
                "output_valid": None,
            }

        def close(self):
            pass

    monkeypatch.setattr(workflow_runner, "DeepAgentsExecutionDriver", Driver)


def test_fanin_waits_for_all_dependencies_and_executes_once(tmp_path, monkeypatch):
    wf = workflow(
        tmp_path,
        monkeypatch,
        [
            {"id": "a", "intent": "FIRST"},
            {"id": "b", "intent": "SECOND", "depends_on": ["a"]},
            {"id": "join", "intent": "JOIN", "depends_on": ["a", "b"]},
        ],
    )
    calls = []
    install_driver(monkeypatch, calls)
    result = workflow_runner.WorkflowExecutionDriver(wf, development=True).execute(
        "ROOT request"
    )
    assert len(calls) == 3
    join = json.loads(calls[-1][0])
    assert join["workflow_input"] == "ROOT request"
    assert set(join["dependency_outputs"]) == {"a", "b"}
    assert result["execution_success"] is True


def test_run_threads_are_unique_and_inputs_limited_to_dependencies(
    tmp_path, monkeypatch
):
    wf = workflow(
        tmp_path,
        monkeypatch,
        [
            {"id": "a", "intent": "A"},
            {"id": "other", "intent": "OTHER"},
            {"id": "b", "intent": "B", "depends_on": ["a"]},
        ],
    )
    calls = []
    install_driver(monkeypatch, calls)
    driver = workflow_runner.WorkflowExecutionDriver(wf, development=True)
    first = driver.execute("first")
    second = driver.execute("second")
    assert first["execution_id"] != second["execution_id"]
    assert len({thread for _, thread in calls}) == 6
    for intent, _ in calls:
        parsed = json.loads(intent)
        if parsed["task"] == "B":
            assert set(parsed["dependency_outputs"]) == {"a"}


def test_failed_predecessor_prevents_downstream_execution(tmp_path, monkeypatch):
    wf = workflow(
        tmp_path,
        monkeypatch,
        [
            {"id": "a", "intent": "FAIL"},
            {"id": "b", "intent": "NEVER", "depends_on": ["a"]},
        ],
    )
    calls = []
    install_driver(monkeypatch, calls, fail="FAIL")
    with pytest.raises(AeroMeshDomainError):
        workflow_runner.WorkflowExecutionDriver(wf, development=True).execute("request")
    assert len(calls) == 1


def test_approved_workflow_runs_exact_release_without_source_registry(
    tmp_path, monkeypatch
):
    from aero.infrastructure.attestation import generate_keypair, sign_manifest_dict
    from aero.services import trust
    from aero.services.releases import (
        build_release,
        approve_release,
        load_approved_release,
    )
    from aero.services.session import SessionRegistry
    from dataclasses import asdict

    wf = workflow(
        tmp_path,
        monkeypatch,
        [
            {"id": "a", "intent": "FIRST"},
            {"id": "b", "intent": "SECOND", "depends_on": ["a"]},
        ],
    )
    raw = asdict(wf)
    raw["identity"] = {
        key: value for key, value in raw["identity"].items() if value is not None
    }
    raw["steps"] = [
        {key: value for key, value in step.items() if value is not None}
        for step in raw["steps"]
    ]
    source = tmp_path / "workflow.json"
    source.write_text(json.dumps(raw))
    release = build_release(source)
    release_path = tmp_path / "release.json"
    release_path.write_text(json.dumps(release))
    private, public = generate_keypair()
    public_path = tmp_path / "author.pub"
    public_path.write_bytes(public)
    release_path.with_suffix(".json.sig").write_text(
        json.dumps(sign_manifest_dict(release, private))
    )
    trust.trust_key("pipeline", public_path)
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({"policy_version": "1"}))
    approved = load_approved_release(approve_release(release_path, policy))
    source.unlink()
    (tmp_path / "worker.json").unlink()
    monkeypatch.setattr(
        workflow_runner,
        "resolve_agent_manifest_path",
        lambda _: pytest.fail("Release escaped into mutable registry"),
    )
    calls = []
    install_driver(monkeypatch, calls)
    driver = workflow_runner.WorkflowExecutionDriver(
        WorkflowParser().validate_dict(approved.entry_data), approved_release=approved
    )
    assert len(driver.preflight()["agents"]) == 2
    result = driver.execute("request")
    assert len(calls) == 2
    receipts = SessionRegistry().receipts(result["execution_id"])
    assert len(receipts) == 3
    assert all(receipt["release_digest"] == approved.digest for receipt in receipts)
    assert all(receipt["policy_sha256"] for receipt in receipts)


def test_parallel_native_runtimes_use_isolated_threads(
    tmp_path, monkeypatch, offline_runtime
):
    wf = workflow(
        tmp_path,
        monkeypatch,
        [
            {"id": "a", "intent": "FIRST"},
            {"id": "b", "intent": "SECOND"},
            {"id": "join", "intent": "JOIN", "depends_on": ["a", "b"]},
        ],
    )
    result = workflow_runner.WorkflowExecutionDriver(wf, development=True).execute(
        "request"
    )
    assert result["execution_success"] is True
    assert set(result["outputs"]) == {"a", "b", "join"}
