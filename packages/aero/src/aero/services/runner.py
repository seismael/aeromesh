"""AeroMesh runner: parse + resolve credentials + execute via Deep Agents."""

import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.domain.paths import resolve_agent_manifest_path
from aero.infrastructure.parser import ManifestParser
from aero.infrastructure.vault import ZeroTrustVaultResolver
from aero.services.deepagents_runner import DeepAgentsExecutionDriver
from aero.services.session import SessionRegistry


class AeroAgentRunnerService:
    """Parses a DAM manifest, resolves credentials, executes via Deep Agents, and
    records the session so it can be resumed across CLI invocations.

    The Deep Agents checkpointer (SQLite) persists the conversation; the session
    registry maps a session id to its thread id and agent for listing/resume.
    """

    def __init__(
        self,
        parser: ManifestParser = None,
        vault: ZeroTrustVaultResolver = None,
        sessions: SessionRegistry = None,
    ):
        self.parser = parser or ManifestParser()
        self.vault = vault or ZeroTrustVaultResolver()
        self.sessions = sessions or SessionRegistry()

    @staticmethod
    def _new_session_id(agent_id: str) -> str:
        return f"{agent_id}-{int(time.time())}-{uuid.uuid4().hex[:8]}"

    def run_manifest_file(
        self,
        manifest_path: Optional[str],
        user_intent: str,
        env_overrides: Dict[str, str] = None,
        non_interactive: bool = False,
        enable_diagnostics: bool = False,
        manifest_object: Optional[Any] = None,
        replay_session_id: Optional[str] = None,
        execute_tools: Optional[bool] = None,
    ) -> Dict[str, Any]:
        del enable_diagnostics, execute_tools  # handled natively by Deep Agents

        if replay_session_id:
            return self._resume_session(
                replay_session_id, user_intent, non_interactive=non_interactive
            )

        if manifest_object:
            manifest = manifest_object
        else:
            manifest = self.parser.parse_file(manifest_path)

        if env_overrides:
            self.vault.override_env.update(env_overrides)

        credentials = self.vault.resolve_requirements(
            manifest.providers, non_interactive=non_interactive
        )

        session_id = self._new_session_id(manifest.identity.id)
        thread_id = session_id
        driver = DeepAgentsExecutionDriver(manifest, credentials=credentials)
        try:
            result = driver.execute(user_intent, thread_id=thread_id)
        finally:
            driver.close()

        self.sessions.record(
            session_id,
            agent_id=manifest.identity.id,
            thread_id=thread_id,
            intent=user_intent,
            manifest_path=manifest_path,
        )

        return {
            "manifest": manifest,
            "credentials_resolved": list(credentials.keys()),
            "execution_result": result,
            "diagnostics": None,
            "session_id": session_id,
        }

    def _resume_session(
        self, session_id: str, user_intent: Optional[str], non_interactive: bool
    ) -> Dict[str, Any]:
        session = self.sessions.get(session_id)
        if not session:
            raise AeroMeshDomainError(
                f"Unknown session '{session_id}' (run `amx history` to list sessions).",
                ErrorCode.AMX_ERR_DISCOVERY_NO_MATCH,
                ExitCode.DISCOVERY_NO_MATCH,
            )

        agent_id = session["agent_id"]
        thread_id = session["thread_id"]

        # Prefer the exact manifest path recorded at run time, then fall back to
        # resolving the agent id (installed/registry agents).
        resolved = None
        recorded_path = session.get("manifest_path")
        if recorded_path:
            p = Path(recorded_path)
            if p.exists():
                resolved = p
        if resolved is None:
            resolved = resolve_agent_manifest_path(agent_id)
        if not resolved:
            raise AeroMeshDomainError(
                f"Cannot resume session '{session_id}': manifest for agent "
                f"'{agent_id}' not found.",
                ErrorCode.AMX_ERR_DISCOVERY_NO_MATCH,
                ExitCode.DISCOVERY_NO_MATCH,
            )

        manifest = self.parser.parse_file(str(resolved))
        credentials = self.vault.resolve_requirements(
            manifest.providers, non_interactive=non_interactive
        )

        intent = user_intent or "Continue."
        driver = DeepAgentsExecutionDriver(manifest, credentials=credentials)
        try:
            result = driver.execute(intent, thread_id=thread_id)
        finally:
            driver.close()

        self.sessions.record(
            session_id,
            agent_id=agent_id,
            thread_id=thread_id,
            intent=intent,
            manifest_path=session.get("manifest_path"),
        )

        return {
            "manifest": manifest,
            "credentials_resolved": list(credentials.keys()),
            "execution_result": result,
            "diagnostics": None,
            "session_id": session_id,
            "is_resumed": True,
        }

    def list_sessions(self):
        return self.sessions.list()
