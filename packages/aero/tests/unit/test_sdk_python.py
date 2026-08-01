"""Unit tests for AeroKernel in packages/sdk-python."""

import pytest
import sys
from pathlib import Path

# Add sdk-python/src to sys.path for testing
sdk_path = Path(__file__).resolve().parents[4] / "packages" / "sdk-python" / "src"
if str(sdk_path) not in sys.path:
    sys.path.insert(0, str(sdk_path))

from aeromesh import AeroKernel

def test_aerokernel_sdk():
    kernel = AeroKernel()
    kernel.orchestrator.runner.vault.override_env["DB_CONNECT_STRING"] = "postgresql://localhost:5432/test"

    res = kernel.run_agent("registry/agents/postgres-performance-tuner.json", "Analyze slow query", non_interactive=True)
    assert res["mode"] == "AGENT"
    assert "result" in res
