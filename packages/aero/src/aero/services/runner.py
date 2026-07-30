"""AERO Agent Runner Orchestration Service."""

import time
from typing import Dict, Any
from aero.infrastructure.parser import ManifestParser
from aero.infrastructure.vault import ZeroTrustVaultResolver
from aero.infrastructure.driver import LangGraphExecutionDriver
from aero.infrastructure.diagnostics import AeroDiagnosticTracer

class AeroAgentRunnerService:
    """Orchestrates parsing, security resolution, and driver execution."""

    def __init__(self, parser: ManifestParser = None, vault: ZeroTrustVaultResolver = None):
        self.parser = parser or ManifestParser()
        self.vault = vault or ZeroTrustVaultResolver()

    def run_manifest_file(
        self,
        manifest_path: str,
        user_intent: str,
        env_overrides: Dict[str, str] = None,
        non_interactive: bool = False,
        enable_diagnostics: bool = False,
    ) -> Dict[str, Any]:
        tracer = AeroDiagnosticTracer(enabled=enable_diagnostics)

        t0 = time.time()
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
        credentials = self.vault.resolve_requirements(manifest.providers, non_interactive=non_interactive)
        if tracer.enabled:
            tracer.record_span(
                event_type="RESOLVE_VAULT",
                component="ZeroTrustVaultResolver",
                duration_ms=(time.time() - t0) * 1000,
                metadata={"resolved_count": len(credentials)},
            )

        driver = LangGraphExecutionDriver(manifest, credentials, tracer=tracer)
        result = driver.execute(user_intent)

        return {
            "manifest": manifest,
            "credentials_resolved": list(credentials.keys()),
            "execution_result": result,
            "diagnostics": tracer.get_summary() if enable_diagnostics else None,
        }
