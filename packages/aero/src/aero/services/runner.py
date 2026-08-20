"""AERO Agent Runner Orchestration Service."""

import time
from typing import Dict, Any, Optional
from aero.infrastructure.parser import ManifestParser
from aero.infrastructure.vault import ZeroTrustVaultResolver
from aero.infrastructure.driver import LangGraphExecutionDriver
from aero.infrastructure.diagnostics import AeroDiagnosticTracer

import json
from pathlib import Path
from aero.domain.paths import get_aeromesh_home


class AeroAgentRunnerService:
    """Orchestrates parsing, security resolution, driver execution, and checkpointing."""

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
        if replay_session_id:
            checkpoint = self.load_checkpoint(replay_session_id)
            if checkpoint:
                checkpoint["is_replayed"] = True
                return checkpoint

        tracer = AeroDiagnosticTracer(enabled=enable_diagnostics)

        t0 = time.time()
        if manifest_object:
            manifest = manifest_object
        else:
            manifest = self.parser.parse_file(manifest_path)
        if tracer.enabled:
            tracer.record_span(
                event_type="PARSE_MANIFEST",
                component="ManifestParser",
                duration_ms=(time.time() - t0) * 1000,
                metadata={"agent_id": manifest.identity.id},
            )

        if env_overrides:
            self.vault.override_env.update(env_overrides)

        t0 = time.time()
        credentials = self.vault.resolve_requirements(
            manifest.providers, non_interactive=non_interactive
        )
        if tracer.enabled:
            tracer.record_span(
                event_type="RESOLVE_VAULT",
                component="ZeroTrustVaultResolver",
                duration_ms=(time.time() - t0) * 1000,
                metadata={"resolved_count": len(credentials)},
            )

        driver = LangGraphExecutionDriver(
            manifest, credentials, tracer=tracer, execute_tools=execute_tools
        )
        result = driver.execute(user_intent)

        res_dict = {
            "manifest": manifest,
            "credentials_resolved": list(credentials.keys()),
            "execution_result": result,
            "diagnostics": tracer.get_summary() if enable_diagnostics else None,
        }

        # Auto-save session checkpoint
        session_id = f"session-{manifest.identity.id}-{int(time.time())}"
        checkpoint_data = {
            "session_id": session_id,
            "agent_id": manifest.identity.id,
            "intent": user_intent,
            "execution_result": result,
            "credentials_resolved": list(credentials.keys()),
        }
        self.save_checkpoint(session_id, checkpoint_data)
        res_dict["session_id"] = session_id

        return res_dict
