"""Live integration test against a real LLM provider — no mocks, no fakes.

Run explicitly (or in CI when the provider-key secret is present):

    $env:DEEPSEEK_API_KEY = "..."   # or set it as a user/system env var
    pytest packages/aero/tests_live -q
"""

import os

import pytest

from aero.infrastructure.parser import ManifestParser
from aero.services.deepagents_runner import DeepAgentsExecutionDriver

MANIFEST = {
    "manifest_version": "0.1.0",
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
    },
    "requirements": {"providers": []},
}


@pytest.mark.live
def test_live_deepseek_echo():
    """A real DeepSeek call through the real Deep Agents runner returns PONG."""
    if not os.environ.get("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY not set; skipping live test")

    manifest = ManifestParser().validate_dict(MANIFEST)
    driver = DeepAgentsExecutionDriver(manifest)
    try:
        result = driver.execute("Reply with exactly the word PONG.")
    finally:
        driver.close()

    output = str(result.get("verified_result") or "").upper()
    assert "PONG" in output
