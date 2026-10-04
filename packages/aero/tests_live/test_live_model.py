"""Live integration test against a real LLM provider — no mocks, no fakes.

Run explicitly (or manually dispatch CI's protected live-model job):

    $env:DEEPSEEK_API_KEY = "..."   # or set it as a user/system env var
    pytest packages/aero/tests_live -q
"""

import os

import pytest

from aero.infrastructure.parser import ManifestParser
from aero.services.deepagents_runner import DeepAgentsExecutionDriver

MANIFEST = {
    "manifest_version": "1.0.0",
    "identity": {"id": "live-echo", "name": "Live Echo", "version": "1.0.0"},
    "capabilities": {
        "domain": "General",
        "tags": ["live"],
        "short_description": "Minimal live model test agent.",
        "evaluation_trigger": "test",
    },
    "cognitive_runtime": {
        "persona": (
            "You are a minimal test agent. Reply with exactly the word PONG "
            "and nothing else."
        ),
        "success_criteria": "PONG",
        "checkpoint_policy": "DISABLED",
    },
    "requirements": {"providers": []},
    "observability": {
        "max_execution_steps": 8,
        "max_model_calls": 2,
        "max_output_tokens": 128,
    },
}


@pytest.mark.live
def test_live_deepseek_echo():
    """A real DeepSeek call through the real Deep Agents runner returns PONG."""
    if not os.environ.get("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY not set; skipping live test")

    manifest = ManifestParser().validate_dict(MANIFEST)
    # This test checks the live provider/runtime, not signed release installation.
    driver = DeepAgentsExecutionDriver(manifest, development=True)
    try:
        result = driver.execute("Reply with exactly the word PONG.")
    finally:
        driver.close()

    output = str(result.get("output") or "").upper()
    assert output.strip() == "PONG"
    assert result["execution_success"] is True
    assert result["success_criteria_met"] is None
