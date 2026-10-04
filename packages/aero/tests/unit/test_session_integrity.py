"""Session metadata must survive concurrent writes without leaking task data."""

import json
from concurrent.futures import ThreadPoolExecutor

from aero.services.session import SessionRegistry


def test_concurrent_session_updates_are_transactional(tmp_path):
    def write(i):
        SessionRegistry(tmp_path).record(
            str(i), agent_id="worker", thread_id=str(i), intent="sensitive request"
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(write, range(40)))
    registry = SessionRegistry(tmp_path)
    assert len(registry.list()) == 40
    assert all("intent" not in item for item in registry.list())
    assert (tmp_path / "sessions.sqlite").exists()


def test_legacy_registry_is_migrated_without_sensitive_intent(tmp_path):
    (tmp_path / "sessions.json").write_text(
        json.dumps(
            {
                "old": {
                    "session_id": "old",
                    "agent_id": "worker",
                    "thread_id": "old",
                    "intent": "secret",
                    "created_at": 1,
                }
            }
        )
    )
    record = SessionRegistry(tmp_path).get("old")
    assert record["session_id"] == "old"
    assert "intent" not in record
    assert record["resume_supported"] is False


def test_same_session_cannot_execute_concurrently(tmp_path):
    import pytest
    from aero.domain.errors import AeroMeshDomainError

    registry = SessionRegistry(tmp_path)
    with registry.execution_lock("same-thread"):
        with pytest.raises(AeroMeshDomainError, match="already executing"):
            with SessionRegistry(tmp_path).execution_lock("same-thread"):
                pytest.fail("Concurrent access acquired the session lock")
    with registry.execution_lock("same-thread"):
        pass
