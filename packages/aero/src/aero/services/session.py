"""Persistent session registry: maps run session ids to Deep Agents thread ids.

A "session" is one conversation thread. The Deep Agents checkpointer (SQLite)
is the source of truth for the conversation state; this registry stores the
lightweight metadata needed to list sessions and resume a thread across CLI
invocations (session_id -> agent_id, thread_id, intent, timestamps).
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from aero.domain.paths import get_aeromesh_home


class SessionRegistry:
    """JSON-backed registry of run sessions under ``AEROMESH_HOME``."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or get_aeromesh_home()

    def _file(self) -> Path:
        return self.base_dir / "sessions.json"

    def _load(self) -> Dict[str, Dict[str, Any]]:
        f = self._file()
        if not f.exists():
            return {}
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self, sessions: Dict[str, Dict[str, Any]]) -> None:
        f = self._file()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(sessions, indent=2), encoding="utf-8")

    def record(
        self,
        session_id: str,
        *,
        agent_id: str,
        thread_id: str,
        intent: str,
        **extra: Any,
    ) -> None:
        sessions = self._load()
        entry = sessions.get(session_id, {})
        entry.update(
            {
                "session_id": session_id,
                "agent_id": agent_id,
                "thread_id": thread_id,
                "intent": intent,
                "updated_at": time.time(),
            }
        )
        entry.setdefault("created_at", time.time())
        entry.update(extra)
        sessions[session_id] = entry
        self._save(sessions)

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self._load().get(session_id)

    def list(self) -> List[Dict[str, Any]]:
        sessions = list(self._load().values())
        sessions.sort(key=lambda s: s.get("updated_at", 0), reverse=True)
        return sessions
