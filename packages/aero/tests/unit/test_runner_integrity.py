import json

import pytest

from aero.domain.errors import AeroMeshDomainError
from aero.services import runner as runner_module
from aero.services.runner import AeroAgentRunnerService
from aero.services.session import SessionRegistry


@pytest.fixture
def manifest_file(tmp_path):
    raw = {
        "manifest_version": "1.0.0",
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
    path.write_text(json.dumps(raw))
    return path


def fake_driver(monkeypatch, fail=False):
    class Driver:
        def __init__(self, *args, **kwargs):
            pass

        def execute(self, intent, thread_id=None):
            registry = SessionRegistry()
            record = registry.get(thread_id)
            assert (
                registry.get_snapshot(record["manifest_sha256"])["identity"]["id"]
                == "worker"
            )
            if fail:
                raise RuntimeError("SECRET in provider failure")
            return {
                "output": "SECRET answer",
                "execution_success": True,
                "token_usage": {"input_tokens": 1},
            }

        def close(self):
            pass

    monkeypatch.setattr(runner_module, "DeepAgentsExecutionDriver", Driver)


def test_snapshot_precedes_execution_and_receipt_does_not_leak_content(
    monkeypatch, manifest_file
):
    fake_driver(monkeypatch)
    runner = AeroAgentRunnerService()
    result = runner.run_manifest_file(
        str(manifest_file), "SECRET intent", development=True
    )
    assert result["execution_id"]
    registry = SessionRegistry()
    receipts = registry.receipts(result["session_id"])
    assert len(receipts) == 1
    assert receipts[0]["status"] == "completed"
    assert "SECRET" not in json.dumps(receipts) + json.dumps(registry.list())


def test_failure_is_recorded_without_exception_message(monkeypatch, manifest_file):
    fake_driver(monkeypatch, fail=True)
    with pytest.raises(RuntimeError):
        AeroAgentRunnerService().run_manifest_file(
            str(manifest_file), "SECRET intent", development=True
        )
    registry = SessionRegistry()
    assert registry.list()[0]["status"] == "failed"
    assert registry.receipts()[0]["error_type"] == "RuntimeError"
    assert "SECRET" not in json.dumps(registry.receipts())


def test_failed_cleanup_marks_successful_model_run_failed(monkeypatch, manifest_file):
    fake_driver(monkeypatch)

    def broken_close(self):
        raise RuntimeError("SECRET cleanup detail")

    monkeypatch.setattr(runner_module.DeepAgentsExecutionDriver, "close", broken_close)
    with pytest.raises(RuntimeError, match="cleanup"):
        AeroAgentRunnerService().run_manifest_file(
            str(manifest_file), "task", development=True
        )
    registry = SessionRegistry()
    assert registry.list()[0]["status"] == "failed"
    receipt = registry.receipts()[0]
    assert receipt["status"] == "failed"
    assert receipt["execution_success"] is False
    assert "SECRET" not in json.dumps(receipt)


def test_resume_refuses_manifest_drift(monkeypatch, manifest_file):
    fake_driver(monkeypatch)
    runner = AeroAgentRunnerService()
    result = runner.run_manifest_file(str(manifest_file), "run", development=True)
    raw = json.loads(manifest_file.read_text())
    raw["cognitive_runtime"]["persona"] = "Changed behavior"
    manifest_file.write_text(json.dumps(raw))
    with pytest.raises(AeroMeshDomainError, match="changed"):
        runner.run_manifest_file(
            None, "continue", replay_session_id=result["session_id"], development=True
        )


def test_unsigned_execution_is_not_implicitly_trusted(manifest_file):
    with pytest.raises(AeroMeshDomainError):
        AeroAgentRunnerService().run_manifest_file(str(manifest_file), "run")


def test_signed_privileged_manifest_requires_operator_release_before_vault(
    monkeypatch, manifest_file
):
    raw = json.loads(manifest_file.read_text())
    raw["requirements"]["providers"] = [{"type": "credential", "id": "SECRET"}]
    manifest_file.write_text(json.dumps(raw))
    monkeypatch.setattr(
        runner_module.trust, "require_trusted_manifest", lambda *args, **kwargs: raw
    )
    runner = AeroAgentRunnerService()
    monkeypatch.setattr(
        runner.vault,
        "resolve_requirements",
        lambda *args, **kwargs: pytest.fail(
            "Resolved secret before operator authorization"
        ),
    )
    with pytest.raises(AeroMeshDomainError, match="approved release"):
        runner.run_manifest_file(str(manifest_file), "run")


def test_concurrent_runs_do_not_share_credential_overrides(monkeypatch, manifest_file):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    barrier = Barrier(2)

    class Vault:
        override_env = {"BASE": "base"}

        def resolve_requirements(self, *args, **kwargs):
            barrier.wait(timeout=5)
            resolved = dict(self.override_env)
            barrier.wait(timeout=5)
            return resolved

    class Driver:
        def __init__(self, manifest, credentials=None, **kwargs):
            self.credentials = credentials

        def execute(self, *args, **kwargs):
            return {
                "execution_success": True,
                "output": self.credentials["TOKEN"],
            }

        def close(self):
            pass

    monkeypatch.setattr(runner_module, "DeepAgentsExecutionDriver", Driver)
    vault = Vault()
    runner = AeroAgentRunnerService(vault=vault)

    def run(token):
        return runner.run_manifest_file(
            str(manifest_file), "run", development=True, env_overrides={"TOKEN": token}
        )["execution_result"]["output"]

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(run, ["first", "second"]))
    assert results == ["first", "second"]
    assert vault.override_env == {"BASE": "base"}


def test_resume_rechecks_real_signer_revocation(monkeypatch, manifest_file, tmp_path):
    from aero.infrastructure.attestation import generate_keypair, sign_manifest_dict
    from aero.services import trust

    raw = json.loads(manifest_file.read_text())
    private, public = generate_keypair()
    public_path = tmp_path / "author.pub"
    public_path.write_bytes(public)
    manifest_file.with_suffix(".json.sig").write_text(
        json.dumps(sign_manifest_dict(raw, private))
    )
    trust.trust_key("worker", public_path)
    fake_driver(monkeypatch)
    runner = AeroAgentRunnerService()
    result = runner.run_manifest_file(str(manifest_file), "run")
    assert trust.revoke_key("worker")
    with pytest.raises(AeroMeshDomainError, match="REVOKED"):
        runner.run_manifest_file(None, "resume", replay_session_id=result["session_id"])


def test_resigned_manifest_cannot_change_an_existing_session(
    monkeypatch, manifest_file, tmp_path
):
    from aero.infrastructure.attestation import generate_keypair, sign_manifest_dict
    from aero.services import trust

    raw = json.loads(manifest_file.read_text())
    private, public = generate_keypair()
    public_path = tmp_path / "author.pub"
    public_path.write_bytes(public)
    manifest_file.with_suffix(".json.sig").write_text(
        json.dumps(sign_manifest_dict(raw, private))
    )
    trust.trust_key("worker", public_path)
    fake_driver(monkeypatch)
    runner = AeroAgentRunnerService()
    result = runner.run_manifest_file(str(manifest_file), "run")
    raw["cognitive_runtime"]["persona"] = "updated approved persona"
    manifest_file.write_text(json.dumps(raw))
    manifest_file.with_suffix(".json.sig").write_text(
        json.dumps(sign_manifest_dict(raw, private))
    )
    with pytest.raises(AeroMeshDomainError, match="changed"):
        runner.run_manifest_file(None, "resume", replay_session_id=result["session_id"])
