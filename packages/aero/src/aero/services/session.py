"""Transactional session metadata and immutable manifest snapshots.

Conversation content remains in the runtime checkpointer. This registry does not
store user intents, model output, credentials, or exception messages.
"""

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from aero.domain.paths import get_aeromesh_home
from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.infrastructure.attestation import canonicalize, sha256_hex


class SessionRegistry:
    """SQLite registry safe for concurrent processes and interrupted writes."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir) if base_dir is not None else get_aeromesh_home()

    @contextmanager
    def execution_lock(self, session_id: str):
        """Prevent concurrent checkpoint mutation; OS releases locks on crashes."""
        directory = self.base_dir / "session-locks"
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = directory / sha256_hex(session_id.encode("utf-8"))
        with path.open("a+b") as handle:
            if os.name == "nt":
                import msvcrt

                handle.seek(0, 2)
                if handle.tell() == 0:
                    handle.write(b"0")
                    handle.flush()
                handle.seek(0)
                lock = lambda: msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                unlock = lambda: msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                lock = lambda: fcntl.flock(
                    handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
                )
                unlock = lambda: fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            try:
                lock()
            except OSError as exc:
                raise AeroMeshDomainError(
                    "This session is already executing; retry after its current run finishes.",
                    ErrorCode.AMX_ERR_PROVIDER_FAILED,
                    ExitCode.PROVIDER_FAILED,
                ) from exc
            try:
                yield
            finally:
                unlock()

    @contextmanager
    def _connect(self):
        self.base_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        connection = sqlite3.connect(self.base_dir / "sessions.sqlite", timeout=30)
        os.chmod(self.base_dir / "sessions.sqlite", 0o600)
        try:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS snapshots (digest TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS receipts (id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY)"
            )
            connection.commit()
            connection.execute("BEGIN IMMEDIATE")
            self._migrate(connection)
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _migrate(self, connection):
        if connection.execute(
            "SELECT 1 FROM metadata WHERE key='legacy_migrated'"
        ).fetchone():
            return
        legacy = self.base_dir / "sessions.json"
        if legacy.exists():
            # Corruption must be visible; silently resetting session history loses evidence.
            entries = json.loads(legacy.read_text(encoding="utf-8"))
            if not isinstance(entries, dict):
                raise ValueError("Legacy session registry must be a JSON object")
            for session_id, entry in entries.items():
                clean = {
                    key: entry[key]
                    for key in (
                        "agent_id",
                        "thread_id",
                        "created_at",
                        "updated_at",
                        "manifest_path",
                    )
                    if key in entry
                }
                clean.update(
                    session_id=session_id, resume_supported=False, status="legacy"
                )
                connection.execute(
                    "INSERT OR IGNORE INTO sessions VALUES (?, ?)",
                    (session_id, json.dumps(clean)),
                )
        connection.execute("INSERT INTO metadata VALUES ('legacy_migrated')")

    def snapshot(self, manifest: Dict[str, Any]) -> str:
        raw = canonicalize(manifest)
        digest = sha256_hex(raw)
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO snapshots VALUES (?, ?)",
                (digest, raw.decode("utf-8")),
            )
        return digest

    def get_snapshot(self, digest: str) -> Dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM snapshots WHERE digest=?", (digest,)
            ).fetchone()
        if row is None:
            raise ValueError("Session manifest snapshot is missing")
        payload = json.loads(row[0])
        if sha256_hex(canonicalize(payload)) != digest:
            raise ValueError("Session manifest snapshot failed its integrity check")
        return payload

    def record(
        self,
        session_id: str,
        *,
        agent_id: str,
        thread_id: str,
        intent: str = "",
        **extra: Any,
    ) -> None:
        del intent  # Kept for source compatibility, intentionally never persisted.
        allowed = {
            "manifest_path",
            "manifest_sha256",
            "development",
            "release_digest",
            "status",
            "error_code",
            "execution_id",
            "resume_supported",
            "kind",
        }
        unknown = set(extra) - allowed
        if unknown:
            raise ValueError(f"Unsupported session metadata fields: {sorted(unknown)}")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM sessions WHERE id=?", (session_id,)
            ).fetchone()
            entry = json.loads(row[0]) if row else {}
            now = time.time()
            entry.update(
                session_id=session_id,
                agent_id=agent_id,
                thread_id=thread_id,
                updated_at=now,
                **extra,
            )
            entry.setdefault("created_at", now)
            connection.execute(
                "INSERT INTO sessions VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                (session_id, json.dumps(entry)),
            )

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM sessions WHERE id=?", (session_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def list(self) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            sessions = [
                json.loads(row[0])
                for row in connection.execute("SELECT payload FROM sessions")
            ]
        return sorted(
            sessions, key=lambda item: item.get("updated_at", 0), reverse=True
        )

    def write_receipt(self, receipt: Dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO receipts VALUES (?, ?)",
                (receipt["execution_id"], json.dumps(receipt)),
            )

    def receipts(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            rows = [
                json.loads(row[0])
                for row in connection.execute("SELECT payload FROM receipts")
            ]
        return [
            row
            for row in rows
            if session_id is None or row.get("session_id") == session_id
        ]
