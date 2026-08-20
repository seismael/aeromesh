import os
import sys

# Appends src/ to sys.path so tests can import amx modules natively
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

# Tests must not spawn real MCP subprocesses (e.g. `npx`).
os.environ.setdefault("AEROMESH_EXECUTE_TOOLS", "0")

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


# Inject the fake model so tests never hit a real LLM provider.
import aero.services.deepagents_runner as _dgr

_dgr.resolve_model = lambda credentials=None: FakeChatModel()
