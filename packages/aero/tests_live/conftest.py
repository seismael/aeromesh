"""Live-test fixtures. Deliberately does NOT patch the model or MCP tools —
these tests hit a real provider."""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))


@pytest.fixture(autouse=True)
def _isolate_aeromesh_home(tmp_path_factory, monkeypatch):
    """Keep live-run state (SQLite checkpoints/memory) out of real AppData."""
    monkeypatch.setenv("AEROMESH_HOME", str(tmp_path_factory.mktemp("aeromesh-live-home")))
