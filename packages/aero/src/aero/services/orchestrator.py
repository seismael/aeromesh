"""Resolve explicit agent targets; author unsigned drafts only on request."""

from pathlib import Path
from typing import Any, Dict, Optional, Union

from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.domain.paths import resolve_agent_manifest_path
from aero.services.runner import AeroAgentRunnerService
from aero.services.synthesizer import JitSynthesizer


class AeroMasterOrchestrator:
    def __init__(self, synthesizer: Optional[JitSynthesizer] = None):
        self.runner = AeroAgentRunnerService()
        self.synthesizer = synthesizer or JitSynthesizer()

    def dispatch(
        self,
        target: Union[str, Any],
        intent: Optional[str] = None,
        non_interactive: bool = False,
        enable_diagnostics: bool = False,
        development: bool = False,
        synthesize: bool = False,
    ) -> Dict[str, Any]:
        target_str = str(target)
        if synthesize:
            if not development:
                raise AeroMeshDomainError(
                    "Running a generated unsigned draft requires explicit development mode.",
                    ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                    ExitCode.SCHEMA_VIOLATION,
                )
            if intent is not None:
                raise AeroMeshDomainError(
                    "Supply the synthesis goal as the target, without a separate intent.",
                    ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                    ExitCode.SCHEMA_VIOLATION,
                )
            manifest = self.synthesizer.synthesize(target_str)
            if manifest.providers:
                raise AeroMeshDomainError(
                    "Automatic draft execution permits only tool-free manifests.",
                    ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                    ExitCode.SCHEMA_VIOLATION,
                )
            result = self.runner.run_manifest_file(
                None,
                target_str,
                non_interactive=non_interactive,
                manifest_object=manifest,
                development=True,
                enable_diagnostics=enable_diagnostics,
            )
            return {"mode": "JIT_AGENT", "result": result}

        resolved = resolve_agent_manifest_path(target_str)
        if resolved is None:
            raise AeroMeshDomainError(
                f"Agent target '{target_str}' was not found. Use explicit synthesis to author a draft.",
                ErrorCode.AMX_ERR_DISCOVERY_NO_MATCH,
                ExitCode.DISCOVERY_NO_MATCH,
            )
        if intent is None:
            raise AeroMeshDomainError(
                "Intent string is required to run an agent.",
                ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                ExitCode.SCHEMA_VIOLATION,
            )
        expected_id = (
            None if Path(target_str).is_file() else target_str.removesuffix(".json")
        )
        result = self.runner.run_manifest_file(
            str(resolved),
            intent,
            non_interactive=non_interactive,
            development=development,
            enable_diagnostics=enable_diagnostics,
            expected_id=expected_id,
        )
        return {"mode": "AGENT", "result": result}
