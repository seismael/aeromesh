"""The manifest cannot grant host execution or inherit unrelated credentials."""

from types import SimpleNamespace
from pathlib import Path
import subprocess

import pytest

from aero.domain.errors import AeroMeshDomainError
from aero.infrastructure.tool_execution import build_stdio_connection


IMAGE = "registry.example/tool@sha256:" + "a" * 64


def provider(**changes):
    values = dict(
        id="example",
        command=None,
        args=[],
        uri=None,
        image=IMAGE,
        allowed_domains=[],
        credential_bindings={},
    )
    values.update(changes)
    return SimpleNamespace(**values)


def test_production_connection_is_confined_and_scopes_credentials(monkeypatch):
    monkeypatch.setattr(
        "aero.infrastructure.tool_execution.shutil.which", lambda _: "/usr/bin/docker"
    )
    monkeypatch.setenv("UNRELATED_SECRET", "do-not-pass")
    cleanup = []
    conn = build_stdio_connection(
        provider(credential_bindings={"SERVICE_TOKEN": "service-key"}),
        {"service-key": "secret", "other": "other-secret"},
        cleanup_callbacks=cleanup,
    )
    args = conn["args"]
    for required in (
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--user=65532:65532",
        "--pids-limit=64",
        "--memory=256m",
        "--cpus=1",
        "--pull=never",
    ):
        assert required in args
    assert IMAGE in args
    assert not any(arg.startswith("--name=") for arg in args)
    assert any(arg.startswith("--label=aeromesh.owner=") for arg in args)
    assert conn["env"]["SERVICE_TOKEN"] == "secret"
    assert "UNRELATED_SECRET" not in conn["env"] and "other" not in conn["env"]
    assert "secret" not in args and "other-secret" not in args
    assert "--env=SERVICE_TOKEN" in args
    assert len(cleanup) == 1
    config = Path(
        next(arg.split("=", 1)[1] for arg in args if arg.startswith("--config="))
    )
    assert config.is_dir() and not list(config.iterdir())
    assert conn["session_kwargs"]["read_timeout_seconds"].total_seconds() == 60
    # Unit test owns the temporary config even though Docker is not invoked.
    monkeypatch.setattr(
        "aero.infrastructure.tool_execution.subprocess.run", lambda *a, **k: None
    )
    cleanup[0]()
    assert not config.exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"image": "registry.example/tool:latest"},
        {"image": None},
        {"command": "sh"},
        {"allowed_domains": ["api.example.com"]},
        {"uri": "https://example.com/mcp"},
        {"credential_bindings": {"PATH": "secret"}},
        {"credential_bindings": {"LD_PRELOAD": "secret"}},
        {"credential_bindings": {"PYTHONPATH": "secret"}},
    ],
)
def test_production_fails_closed_on_unenforceable_configuration(monkeypatch, changes):
    monkeypatch.setattr(
        "aero.infrastructure.tool_execution.shutil.which", lambda _: "/usr/bin/docker"
    )
    with pytest.raises(AeroMeshDomainError):
        build_stdio_connection(provider(**changes), {"secret": "value"})


def test_missing_binding_cannot_be_resolved_from_environment(monkeypatch):
    monkeypatch.setenv("service-key", "ambient-secret")
    with pytest.raises(AeroMeshDomainError, match="service-key"):
        build_stdio_connection(
            provider(credential_bindings={"TOKEN": "service-key"}), {}
        )


def test_adapter_environment_expansion_cannot_read_unbound_secrets(monkeypatch):
    monkeypatch.setenv("UNBOUND_SECRET", "ambient-secret")
    value = "prefix-${UNBOUND_SECRET}"
    with pytest.raises(AeroMeshDomainError, match="interpolation") as exc:
        build_stdio_connection(
            provider(credential_bindings={"TOKEN": "service-key"}),
            {"service-key": value},
        )
    assert value not in str(exc.value) and "ambient-secret" not in str(exc.value)


def test_development_execution_is_explicit_warned_and_minimal(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "unrelated-provider-key")
    monkeypatch.setenv("PYTHONPATH", "untrusted-import-path")
    with pytest.warns(RuntimeWarning, match="host process"):
        conn = build_stdio_connection(
            provider(image=None, command="python", args=["-V"]), {}, development=True
        )
    assert conn["command"] == "python" and conn["args"] == ["-V"]
    assert "OPENAI_API_KEY" not in conn["env"] and "PYTHONPATH" not in conn["env"]


def test_cleanup_removes_only_its_owned_container(monkeypatch):
    monkeypatch.setattr(
        "aero.infrastructure.tool_execution.shutil.which", lambda _: "/usr/bin/docker"
    )
    calls = []
    container_ids = ["a" * 64, "b" * 64]

    def docker_run(*args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(
            args[0],
            0,
            stdout=("\n".join(container_ids).encode() if "ps" in args[0] else b""),
        )

    monkeypatch.setattr("aero.infrastructure.tool_execution.subprocess.run", docker_run)
    cleanup = []
    conn = build_stdio_connection(provider(), {}, cleanup_callbacks=cleanup)
    cleanup[0]()
    owner = next(
        arg.removeprefix("--label=")
        for arg in conn["args"]
        if arg.startswith("--label=aeromesh.owner=")
    )
    assert f"label={owner}" in calls[0][0][0]
    assert calls[1][0][0][-5:] == ["rm", "--force", "--volumes", *container_ids]
    assert calls[0][1]["timeout"] <= 10


def test_cleanup_reports_failure_without_echoing_process_output(monkeypatch):
    monkeypatch.setattr(
        "aero.infrastructure.tool_execution.shutil.which", lambda _: "/usr/bin/docker"
    )
    monkeypatch.setattr(
        "aero.infrastructure.tool_execution.subprocess.run",
        lambda *a, **kw: subprocess.CompletedProcess(
            [], 1, stderr=b"daemon unavailable: sensitive-details"
        ),
    )
    callbacks = []
    build_stdio_connection(provider(), {}, cleanup_callbacks=callbacks)
    with pytest.warns(RuntimeWarning, match="Could not confirm cleanup") as warnings:
        callbacks[0]()
    assert "sensitive-details" not in str(warnings[0].message)
