"""Verified execution, immutable session snapshots, explicit resume, and receipts."""

import time
from copy import copy
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.infrastructure.attestation import canonicalize, sha256_hex
from aero.infrastructure.parser import ManifestParser
from aero.infrastructure.vault import ZeroTrustVaultResolver
from aero.services import trust
from aero.services.deepagents_runner import DeepAgentsExecutionDriver
from aero.services.receipt import make_receipt
from aero.services.session import SessionRegistry


def _failure(message):
    return AeroMeshDomainError(
        message, ErrorCode.AMX_ERR_SCHEMA_VIOLATION, ExitCode.SCHEMA_VIOLATION
    )


class AeroAgentRunnerService:
    """Record exact approved content before execution and reverify before resume."""

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
        return f"{agent_id}-{uuid.uuid4().hex}"

    def _load(self, path, development, expected_id=None):
        if not path:
            raise _failure("Execution requires a manifest path.")
        if not development:
            return trust.require_trusted_manifest(str(path), expected_id=expected_id)
        try:
            from aero.infrastructure.parser import strict_json

            raw = strict_json(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise _failure("Manifest could not be read as valid JSON.") from exc
        if expected_id and raw.get("identity", {}).get("id") != expected_id:
            raise _failure(
                "Manifest identity does not match the requested agent identity."
            )
        return raw

    def run_manifest_file(
        self,
        manifest_path: Optional[str],
        user_intent: str,
        env_overrides: Dict[str, str] = None,
        non_interactive: bool = False,
        enable_diagnostics: bool = False,
        manifest_object: Optional[Any] = None,
        replay_session_id: Optional[str] = None,
        development: bool = False,
        approved_release: Any = None,
        expected_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if replay_session_id:
            return self._resume_session(
                replay_session_id,
                user_intent,
                non_interactive,
                development=development,
                enable_diagnostics=enable_diagnostics,
                env_overrides=env_overrides,
            )
        if approved_release is not None:
            if development:
                raise _failure(
                    "Approved release execution and development mode are mutually exclusive."
                )
            from aero.services.releases import load_approved_release

            approved_release = load_approved_release(approved_release.digest)
            raw = approved_release.entry_data
            manifest_path = str(approved_release.entry_path)
        elif manifest_object is not None:
            if not development:
                raise _failure(
                    "Unsigned in-memory manifests require explicit development mode."
                )
            from aero.services.synthesizer import manifest_to_dict, persist_draft

            raw = manifest_to_dict(manifest_object)
            self.parser.validate_dict(raw)
            manifest_path = str(persist_draft(raw))
        else:
            raw = self._load(manifest_path, development, expected_id=expected_id)
        manifest = self.parser.validate_dict(raw)
        if expected_id is not None and manifest.identity.id != expected_id:
            raise _failure(
                "Catalog reference resolved to a different artifact identity."
            )
        digest = self.sessions.snapshot(raw)
        session_id = self._new_session_id(manifest.identity.id)
        self.sessions.record(
            session_id,
            agent_id=manifest.identity.id,
            thread_id=session_id,
            manifest_path=str(Path(manifest_path).resolve()),
            manifest_sha256=digest,
            development=development,
            release_digest=getattr(approved_release, "digest", None),
            status="prepared",
            resume_supported=(
                manifest.cognitive_runtime.checkpoint_policy != "DISABLED"
                and manifest.cognitive_runtime.memory_policy != "EPHEMERAL_STREAM"
            ),
        )
        return self._execute(
            manifest,
            user_intent,
            session_id,
            manifest_path,
            digest,
            non_interactive,
            development,
            approved_release,
            enable_diagnostics,
            env_overrides,
            resumed=False,
        )

    def _execute(
        self,
        manifest,
        intent,
        session_id,
        manifest_path,
        digest,
        non_interactive,
        development,
        approved_release,
        diagnostics,
        env_overrides,
        resumed,
    ):
        with self.sessions.execution_lock(session_id):
            return self._execute_locked(
                manifest,
                intent,
                session_id,
                manifest_path,
                digest,
                non_interactive,
                development,
                approved_release,
                diagnostics,
                env_overrides,
                resumed,
            )

    def _execute_locked(
        self,
        manifest,
        intent,
        session_id,
        manifest_path,
        digest,
        non_interactive,
        development,
        approved_release,
        diagnostics,
        env_overrides,
        resumed,
    ):
        execution_id = uuid.uuid4().hex
        started = time.time()
        result = None
        error = None
        driver = None
        self.sessions.record(
            session_id,
            agent_id=manifest.identity.id,
            thread_id=session_id,
            status="running",
            execution_id=execution_id,
        )
        vault = copy(self.vault)
        vault.override_env = {**self.vault.override_env, **(env_overrides or {})}
        try:
            if (
                not development
                and approved_release is None
                and any(
                    provider.type in {"mcp", "credential"}
                    for provider in manifest.providers
                )
            ):
                raise _failure(
                    "Tool and credential access requires an approved release with independent operator policy."
                )
            credentials = vault.resolve_requirements(
                manifest.providers, non_interactive=non_interactive
            )
            driver = DeepAgentsExecutionDriver(
                manifest,
                credentials=credentials,
                development=development,
                approved_manifest_path=None if development else str(manifest_path),
                approved_release=approved_release,
            )
            result = driver.execute(intent, thread_id=session_id)
            if (
                result.get("execution_success") is not True
                or result.get("output_valid") is False
            ):
                raise AeroMeshDomainError(
                    "Execution did not complete successfully.",
                    ErrorCode.AMX_ERR_PROVIDER_FAILED,
                    ExitCode.PROVIDER_FAILED,
                )
        except BaseException as exc:
            error = exc
            raise
        finally:
            try:
                if driver is not None:
                    driver.close()
            except BaseException as cleanup_error:
                if error is None:
                    error = cleanup_error
                    raise
            finally:
                status = "failed" if error else "completed"
                self.sessions.record(
                    session_id,
                    agent_id=manifest.identity.id,
                    thread_id=session_id,
                    status=status,
                    error_code=getattr(
                        getattr(error, "error_code", None), "value", None
                    ),
                )
                receipt = make_receipt(
                    execution_id=execution_id,
                    session_id=session_id,
                    artifact_sha256=digest,
                    status=status,
                    started_at=started,
                    development=development,
                    result=result,
                    error=error,
                    release_digest=getattr(approved_release, "digest", None),
                    policy=getattr(approved_release, "policy", None),
                )
                self.sessions.write_receipt(receipt)
        response = {
            "manifest": manifest,
            "credentials_resolved": list(credentials.keys()),
            "execution_result": result,
            "diagnostics": receipt if diagnostics else None,
            "session_id": session_id,
            "execution_id": execution_id,
            "receipt": receipt,
        }
        if resumed:
            response["is_resumed"] = True
        return response

    def _resume_session(
        self,
        session_id,
        user_intent,
        non_interactive,
        *,
        development=False,
        enable_diagnostics=False,
        env_overrides=None,
    ):
        session = self.sessions.get(session_id)
        if not session:
            raise AeroMeshDomainError(
                f"Unknown session '{session_id}' (run `amx history` to list sessions).",
                ErrorCode.AMX_ERR_DISCOVERY_NO_MATCH,
                ExitCode.DISCOVERY_NO_MATCH,
            )
        if not session.get("resume_supported") or not session.get("manifest_sha256"):
            raise _failure(
                "This session has no resumable immutable manifest/checkpoint; start a new run."
            )
        if session.get("development") != development:
            raise _failure(
                "Resume must explicitly use the same trust/development mode as the original run."
            )
        release = None
        path = session.get("manifest_path")
        if session.get("release_digest"):
            from aero.services.releases import load_approved_release

            release = load_approved_release(session["release_digest"])
            raw = release.entry_data
            path = str(release.entry_path)
        else:
            raw = self._load(path, development, expected_id=session["agent_id"])
        if sha256_hex(canonicalize(raw)) != session["manifest_sha256"]:
            raise _failure(
                "Manifest changed since this session started; start a new run of the approved release."
            )
        snapshot = self.sessions.get_snapshot(session["manifest_sha256"])
        manifest = self.parser.validate_dict(snapshot)
        return self._execute(
            manifest,
            user_intent or "Continue.",
            session_id,
            path,
            session["manifest_sha256"],
            non_interactive,
            development,
            release,
            enable_diagnostics,
            env_overrides,
            resumed=True,
        )

    def list_sessions(self):
        return self.sessions.list()
