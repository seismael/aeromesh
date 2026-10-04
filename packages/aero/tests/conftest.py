import os
import sys

import pytest

# Appends src/ to sys.path so tests can import amx modules natively
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)


@pytest.fixture(autouse=True)
def _isolate_aeromesh_home(tmp_path_factory, monkeypatch):
    """Isolate all AeroMesh state (checkpoints, memory, sessions, keys) per test.

    Prevents tests from writing SQLite checkpoints / session metadata into the
    real user AppData directory.
    """
    monkeypatch.setenv("AEROMESH_HOME", str(tmp_path_factory.mktemp("aeromesh-home")))


# ---------------------------------------------------------------------------
# Test doubles (fakes/mocks live ONLY here, never in production code).
# ---------------------------------------------------------------------------
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class FakeChatModel(BaseChatModel):
    """Deterministic fake chat model (implements bind_tools as a no-op)."""

    response: str = "[offline] deterministic response"

    @property
    def _llm_type(self) -> str:
        return "fake-chat-model"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=self.response))]
        )

    def bind_tools(self, tools, **kwargs):
        return self


@pytest.fixture
def offline_runtime(monkeypatch):
    """Opt in to a deterministic LLM; all runtime and MCP code stays real."""
    import aero.services.deepagents_runner as runtime

    model = FakeChatModel()
    monkeypatch.setattr(runtime, "resolve_model", lambda credentials=None: model)
    return model


@pytest.fixture
def mock_mcp_tools(monkeypatch):
    """Explicitly skip MCP discovery only in tests that do not exercise tools."""
    import aero.services.deepagents_runner as runtime

    monkeypatch.setattr(runtime, "build_mcp_tools", lambda *args, **kwargs: [])


@pytest.fixture(autouse=True)
def _isolated_key_storage(monkeypatch):
    """Exercise real credential/encryption code without touching the OS keyring."""
    import keyring

    secrets = {}
    monkeypatch.setattr(
        keyring, "get_password", lambda service, key: secrets.get((service, key))
    )
    monkeypatch.setattr(
        keyring,
        "set_password",
        lambda service, key, value: secrets.__setitem__((service, key), value),
    )
    monkeypatch.setattr(
        keyring,
        "delete_password",
        lambda service, key: secrets.pop((service, key), None),
    )
