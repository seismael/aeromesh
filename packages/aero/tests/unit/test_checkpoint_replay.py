"""Unit tests for AeroAgentRunnerService session persistence and resume."""

import pytest

from aero.domain.errors import AeroMeshDomainError
from aero.domain.paths import get_aeromesh_agents_dir, get_aeromesh_home
from aero.services.runner import AeroAgentRunnerService

MANIFEST_TEXT = """{
  "manifest_version": "0.1.0",
  "identity": { "id": "test-replay-agent", "name": "Replay Agent", "version": "1.0.0" },
  "capabilities": { "domain": "Testing", "tags": ["test"], "short_description": "Replay test", "evaluation_trigger": "Test" },
  "cognitive_runtime": { "persona": "Tester", "success_criteria": "Done" },
  "requirements": { "providers": [] }
}"""


def _install_agent():
    """Put the manifest into the local agents store so it is resolvable by id."""
    agents_dir = get_aeromesh_agents_dir()
    agents_dir.mkdir(parents=True, exist_ok=True)
    target = agents_dir / "test-replay-agent.json"
    target.write_text(MANIFEST_TEXT, encoding="utf-8")
    return target


def test_runner_session_persists_and_resumes(tmp_path):
    fpath = tmp_path / "agent.json"
    fpath.write_text(MANIFEST_TEXT, encoding="utf-8")
    _install_agent()

    runner = AeroAgentRunnerService()
    res1 = runner.run_manifest_file(
        str(fpath), "Run initial execution pass", non_interactive=True
    )
    session_id = res1["session_id"]
    assert session_id

    # State is persisted to disk (not in-memory).
    checkpoint_db = get_aeromesh_home() / "checkpoints.sqlite"
    assert checkpoint_db.exists()
    assert checkpoint_db.stat().st_size > 0

    # Session is recorded and listed.
    listed = runner.list_sessions()
    assert any(s["session_id"] == session_id for s in listed)

    # Resume continues the same thread (same session/thread id, same agent).
    res2 = runner.run_manifest_file(
        str(fpath), "Follow up", replay_session_id=session_id
    )
    assert res2.get("is_resumed") is True
    assert res2["session_id"] == session_id
    assert res2["manifest"].identity.id == "test-replay-agent"


def test_runner_resume_unknown_session_raises():
    runner = AeroAgentRunnerService()
    with pytest.raises(AeroMeshDomainError):
        runner.run_manifest_file(None, "x", replay_session_id="does-not-exist")


def test_runner_resume_from_direct_path_without_install(tmp_path):
    """Resume works even when the agent is not installed/registered — the runner
    records the exact manifest path at run time and reuses it on resume."""
    fpath = tmp_path / "agent.json"
    fpath.write_text(MANIFEST_TEXT, encoding="utf-8")
    # NOTE: do not install the agent to the store.

    runner = AeroAgentRunnerService()
    res1 = runner.run_manifest_file(str(fpath), "go", non_interactive=True)
    session_id = res1["session_id"]

    res2 = runner.run_manifest_file(str(fpath), "again", replay_session_id=session_id)
    assert res2.get("is_resumed") is True
    assert res2["session_id"] == session_id
    assert res2["manifest"].identity.id == "test-replay-agent"
