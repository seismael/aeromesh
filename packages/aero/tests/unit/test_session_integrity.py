"""Session metadata must survive concurrent writes without leaking task data."""

import sqlite3

import pytest
from concurrent.futures import ThreadPoolExecutor

from aero.services.session import SessionRegistry


def test_concurrent_session_updates_are_transactional(tmp_path):
    def write(i):
        SessionRegistry(tmp_path).record(
            str(i), agent_id="worker", thread_id=str(i)
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(write, range(40)))
    registry = SessionRegistry(tmp_path)
    assert len(registry.list()) == 40
    assert all("intent" not in item for item in registry.list())
    assert (tmp_path / "sessions.sqlite").exists()


def test_session_registry_accepts_only_safe_metadata(tmp_path):
    registry = SessionRegistry(tmp_path)
    with pytest.raises(ValueError, match="Unsupported session metadata fields"):
        registry.record(
            "session", agent_id="worker", thread_id="session", intent="secret request"
        )
    assert registry.get("session") is None


def test_session_storage_has_only_v1_tables(tmp_path):
    assert SessionRegistry(tmp_path).list() == []
    with sqlite3.connect(tmp_path / "sessions.sqlite") as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert tables == {"sessions", "snapshots", "receipts"}


def test_same_session_cannot_execute_concurrently(tmp_path):
    from aero.domain.errors import AeroMeshDomainError

    registry = SessionRegistry(tmp_path)
    with registry.execution_lock("same-thread"):
        with pytest.raises(AeroMeshDomainError, match="already executing"):
            with SessionRegistry(tmp_path).execution_lock("same-thread"):
                pytest.fail("Concurrent access acquired the session lock")
    with registry.execution_lock("same-thread"):
        pass
