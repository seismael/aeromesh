"""The manifest cannot grant host execution or inherit unrelated credentials."""

from types import SimpleNamespace
from pathlib import Path
import subprocess

import pytest

from aero.domain.errors import AeroMeshDomainError
from aero.infrastructure.tool_execution import build_stdio_connection


IMAGE = "registry.example/tool@sha256:" + "a" * 64


@pytest.fixture(autouse=True)
def local_image_metadata(monkeypatch):
    monkeypatch.setattr(
        "aero.infrastructure.tool_execution.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, stdout=b"null"
        ),
    )


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
    removed = False

    def docker_run(*args, **kwargs):
        nonlocal removed
        if "inspect" in args[0]:
            return subprocess.CompletedProcess(args[0], 0, stdout=b"null")
        calls.append((args, kwargs))
        if "rm" in args[0]:
            removed = True
        return subprocess.CompletedProcess(
            args[0],
            0,
            stdout=(
                "\n".join(container_ids).encode()
                if "ps" in args[0] and not removed
                else b""
            ),
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
    assert "ps" in calls[2][0][0]


def test_cleanup_reports_failure_without_echoing_process_output(monkeypatch):
    monkeypatch.setattr(
        "aero.infrastructure.tool_execution.shutil.which", lambda _: "/usr/bin/docker"
    )
    monkeypatch.setattr(
        "aero.infrastructure.tool_execution.subprocess.run",
        lambda *a, **kw: (
            subprocess.CompletedProcess(a[0], 0, stdout=b"null")
            if "inspect" in a[0]
            else subprocess.CompletedProcess(
                [], 1, stderr=b"daemon unavailable: sensitive-details"
            )
        ),
    )
    callbacks = []
    build_stdio_connection(provider(), {}, cleanup_callbacks=callbacks)
    with pytest.raises(AeroMeshDomainError, match="Could not confirm cleanup") as error:
        callbacks[0]()
    assert "sensitive-details" not in str(error.value)


@pytest.mark.parametrize(
    "metadata", [b'{"/data":{}}', b"[]", b'"invalid"', b"not-json"]
)
def test_image_volumes_and_invalid_inspection_fail_before_container_launch(
    monkeypatch, metadata
):
    monkeypatch.setattr(
        "aero.infrastructure.tool_execution.shutil.which", lambda _: "/usr/bin/docker"
    )
    calls = []

    def inspect(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=metadata)

    monkeypatch.setattr("aero.infrastructure.tool_execution.subprocess.run", inspect)
    callbacks = []
    with pytest.raises(AeroMeshDomainError, match="volumes|storage configuration"):
        build_stdio_connection(provider(), {}, cleanup_callbacks=callbacks)
    assert len(calls) == 1 and "inspect" in calls[0]
    assert callbacks == []
    config = Path(
        next(
            arg.removeprefix("--config=")
            for arg in calls[0]
            if arg.startswith("--config=")
        )
    )
    assert not config.exists()


def test_unavailable_local_image_does_not_run_or_leak_inspection_details(monkeypatch):
    monkeypatch.setattr(
        "aero.infrastructure.tool_execution.shutil.which", lambda _: "/usr/bin/docker"
    )
    monkeypatch.setattr(
        "aero.infrastructure.tool_execution.subprocess.run",
        lambda *a, **kw: subprocess.CompletedProcess(
            a[0], 1, stderr=b"sensitive-daemon-details"
        ),
    )
    with pytest.raises(AeroMeshDomainError, match="unavailable") as error:
        build_stdio_connection(provider(), {}, cleanup_callbacks=[])
    assert "sensitive-daemon-details" not in str(error.value)


@pytest.mark.parametrize("survivors", [b"", b"b" * 64])
def test_cleanup_confirms_absence_after_racing_or_mixed_removal(monkeypatch, survivors):
    monkeypatch.setattr(
        "aero.infrastructure.tool_execution.shutil.which", lambda _: "/usr/bin/docker"
    )
    inventories = iter([b"a" * 64 + b"\n" + b"b" * 64, survivors])

    def command(args, **kwargs):
        if "inspect" in args:
            return subprocess.CompletedProcess(args, 0, stdout=b"null")
        if "ps" in args:
            return subprocess.CompletedProcess(args, 0, stdout=next(inventories))
        return subprocess.CompletedProcess(
            args, 1, stderr=b"No such container: first; failed removing second"
        )

    monkeypatch.setattr("aero.infrastructure.tool_execution.subprocess.run", command)
    cleanup = []
    build_stdio_connection(provider(), {}, cleanup_callbacks=cleanup)
    if survivors:
        with pytest.raises(AeroMeshDomainError, match="Docker removal failed"):
            cleanup[0]()
    else:
        cleanup[0]()
