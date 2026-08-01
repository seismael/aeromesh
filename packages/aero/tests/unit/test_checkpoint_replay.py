"""Unit tests for AeroAgentRunnerService checkpointing and time-travel replay."""

import pytest
from pathlib import Path
from aero.services.runner import AeroAgentRunnerService

MANIFEST_TEXT = """{
  "manifest_version": "3.0.0",
  "identity": { "id": "test-replay-agent", "name": "Replay Agent", "version": "1.0.0" },
  "capabilities": { "domain": "Testing", "tags": ["test"], "short_description": "Replay test", "evaluation_trigger": "Test" },
  "cognitive_runtime": { "persona": "Tester", "success_criteria": "Done" },
  "requirements": { "providers": [] }
}"""

def test_runner_checkpoint_and_replay():
    import shutil
    tmp_path = Path.cwd() / ".test_tmp_replay"
    tmp_path.mkdir(exist_ok=True)
    try:
        fpath = tmp_path / "agent.json"
        fpath.write_text(MANIFEST_TEXT, encoding="utf-8")

        runner = AeroAgentRunnerService()
        res1 = runner.run_manifest_file(str(fpath), "Run initial execution pass", non_interactive=True)

        assert "session_id" in res1
        session_id = res1["session_id"]

        # Now test replaying session checkpoint
        res2 = runner.run_manifest_file(str(fpath), "Run initial execution pass", replay_session_id=session_id)
        assert res2.get("is_replayed") is True
        assert res2["session_id"] == session_id
        assert res2["agent_id"] == "test-replay-agent"
    finally:
        if tmp_path.exists():
            shutil.rmtree(tmp_path, ignore_errors=True)
