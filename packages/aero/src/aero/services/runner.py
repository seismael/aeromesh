"""AeroMesh runner: parse + resolve credentials + execute via Deep Agents."""

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from aero.domain.paths import get_aeromesh_home
from aero.infrastructure.parser import ManifestParser
from aero.infrastructure.vault import ZeroTrustVaultResolver
from aero.services.deepagents_runner import DeepAgentsExecutionDriver


class AeroAgentRunnerService:
    """Parses a DAM manifest, resolves credentials, executes via Deep Agents, checkpoints."""

    def __init__(
        self, parser: ManifestParser = None, vault: ZeroTrustVaultResolver = None
    ):
        self.parser = parser or ManifestParser()
        self.vault = vault or ZeroTrustVaultResolver()

    def get_checkpoints_dir(self) -> Path:
        cp_dir = get_aeromesh_home() / "checkpoints"
        cp_dir.mkdir(parents=True, exist_ok=True)
        return cp_dir

    def save_checkpoint(self, session_id: str, data: Dict[str, Any]) -> Path:
        cp_file = self.get_checkpoints_dir() / f"{session_id}.json"
        with open(cp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return cp_file

    def load_checkpoint(self, session_id: str) -> Optional[Dict[str, Any]]:
        cp_file = self.get_checkpoints_dir() / f"{session_id}.json"
        if not cp_file.exists():
            return None
        with open(cp_file, "r", encoding="utf-8") as f:
            return json.load(f)

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
            checkpoint = self.load_checkpoint(replay_session_id)
            if checkpoint:
                checkpoint["is_replayed"] = True
                return checkpoint

        if manifest_object:
            manifest = manifest_object
        else:
            manifest = self.parser.parse_file(manifest_path)

        if env_overrides:
            self.vault.override_env.update(env_overrides)

        credentials = self.vault.resolve_requirements(
            manifest.providers, non_interactive=non_interactive
        )

        driver = DeepAgentsExecutionDriver(manifest, credentials=credentials)
        result = driver.execute(user_intent)

        session_id = f"session-{manifest.identity.id}-{int(time.time())}"
        self.save_checkpoint(
            session_id,
            {
                "session_id": session_id,
                "agent_id": manifest.identity.id,
                "intent": user_intent,
                "execution_result": result,
                "credentials_resolved": list(credentials.keys()),
            },
        )

        return {
            "manifest": manifest,
            "credentials_resolved": list(credentials.keys()),
            "execution_result": result,
            "diagnostics": None,
            "session_id": session_id,
        }
