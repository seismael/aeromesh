"""AeroMesh master orchestrator: resolve a manifest or synthesize one, then run.

The heavy lifting (planning, subagents, skills, filesystem, HITL) is delegated to
LangChain Deep Agents; this module only decides *what* to run and compiles it.
"""

from typing import Any, Dict, Optional, Union

from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.domain.paths import resolve_agent_manifest_path
from aero.services.runner import AeroAgentRunnerService
from aero.services.synthesizer import JitSynthesizer


class AeroMasterOrchestrator:
    """Unified facade: run a DAM manifest, agent id, or a natural-language goal."""

    def __init__(self, synthesizer: Optional[JitSynthesizer] = None):
        self.runner = AeroAgentRunnerService()
        self.synthesizer = synthesizer or JitSynthesizer()

    def dispatch(
        self,
        target: Union[str, Any],
        intent: Optional[str] = None,
        non_interactive: bool = False,
        enable_diagnostics: bool = False,
    ) -> Dict[str, Any]:
        del enable_diagnostics  # Deep Agents has its own tracing (LangSmith)

        target_str = str(target)

        # Mode 1: a resolvable manifest path or agent id.
        resolved = resolve_agent_manifest_path(target_str)
        if resolved:
            if intent is None:
                raise AeroMeshDomainError(
                    "Intent string is required to run an agent.",
                    ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                    ExitCode.SCHEMA_VIOLATION,
                )
            result = self.runner.run_manifest_file(
                str(resolved),
                intent,
                non_interactive=non_interactive,
            )
            return {"mode": "AGENT", "result": result}

        # Mode 2: a natural-language goal -> synthesize a manifest, then run it.
        manifest = self.synthesizer.synthesize(target_str)
        result = self.runner.run_manifest_file(
            None,
            target_str,
            non_interactive=non_interactive,
            manifest_object=manifest,
        )
        mode = "JIT_AGENT" if manifest.identity.id.startswith("jit-") else "AGENT"
        return {"mode": mode, "result": result}
