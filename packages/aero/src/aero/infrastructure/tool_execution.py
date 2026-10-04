"""Compile stdio MCP launch settings into an explicit execution boundary.

Trusted execution supports locally available, digest-pinned Linux containers with
no network. Host commands are an explicitly unsafe development capability. A
proxy environment variable is never presented as isolation of a host process.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
import warnings
from collections.abc import Callable, Mapping
from datetime import timedelta
from typing import Any

from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode


_IMAGE = re.compile(r"[a-z0-9][a-z0-9._:/-]*@sha256:[0-9a-f]{64}\Z")
_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_RESERVED = {
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "ENV",
    "BASH_ENV",
    "ZDOTDIR",
    "IFS",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "TEMP",
    "TMP",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "NODE_OPTIONS",
    "NODE_PATH",
    "RUBYOPT",
    "RUBYLIB",
    "PERL5OPT",
    "PERL5LIB",
    "CLASSPATH",
    "JAVA_TOOL_OPTIONS",
    "_JAVA_OPTIONS",
    "JDK_JAVA_OPTIONS",
}
_RESERVED_PREFIXES = ("LD_", "DYLD_", "PYTHON", "DOCKER_", "DOTNET_", "BASH_FUNC_")


def _reject(message: str) -> None:
    raise AeroMeshDomainError(
        message, ErrorCode.AMX_ERR_MCP_SPAWN_FAILED, ExitCode.MCP_SPAWN_FAILED
    )


def validate_credential_bindings(bindings: Mapping[str, str] | None) -> None:
    """Validate binding names without reading credentials or requiring Docker."""
    bindings = bindings or {}
    if not isinstance(bindings, dict):
        _reject(
            "credential_bindings must map environment names to credential identifiers."
        )
    for name, credential_id in bindings.items():
        upper = name.upper() if isinstance(name, str) else ""
        if (
            not isinstance(name, str)
            or not _ENV_NAME.fullmatch(name)
            or upper in _RESERVED
            or upper.startswith(_RESERVED_PREFIXES)
        ):
            _reject(
                f"Credential binding uses reserved or invalid environment name: {name!r}."
            )
        if (
            not isinstance(credential_id, str)
            or not credential_id
            or "\x00" in credential_id
        ):
            _reject(
                "Credential bindings must reference nonempty credential identifiers without NUL bytes."
            )


def validate_stdio_provider(provider: Any, *, development: bool = False) -> None:
    """Pure launch-contract preflight, shared by release approval and execution."""
    validate_credential_bindings(getattr(provider, "credential_bindings", None))
    command = getattr(provider, "command", None)
    image = getattr(provider, "image", None)
    args = getattr(provider, "args", None) or []
    if not isinstance(args, list) or not all(
        isinstance(arg, str) and "\x00" not in arg for arg in args
    ):
        _reject("MCP arguments must be a list of strings without NUL bytes.")
    if development and command and not image:
        if not isinstance(command, str) or "\x00" in command:
            _reject("MCP command must be a string without NUL bytes.")
        if getattr(provider, "uri", None):
            _reject("A host MCP command cannot also declare a remote URI.")
        return
    if not isinstance(image, str) or not _IMAGE.fullmatch(image):
        _reject(
            "Trusted stdio MCP execution requires a locally available image pinned as repository@sha256:<digest>. "
            "Use explicit development mode for host commands."
        )
    if command or getattr(provider, "uri", None):
        _reject(
            "Container MCP providers use image entrypoints and cannot also declare command or uri."
        )
    if getattr(provider, "allowed_domains", None):
        _reject(
            "Container MCP execution currently enforces network=none; networked container tools are unsupported."
        )


def _scoped_credentials(
    provider: Any, credentials: Mapping[str, str]
) -> dict[str, str]:
    bindings = getattr(provider, "credential_bindings", None) or {}
    scoped = {}
    for name, credential_id in bindings.items():
        if not isinstance(credential_id, str) or credential_id not in credentials:
            _reject(
                f"Missing explicitly bound credential '{credential_id}' for tool '{provider.id}'."
            )
        value = credentials[credential_id]
        if not isinstance(value, str) or "\x00" in value:
            _reject(f"Credential '{credential_id}' must be a string without NUL bytes.")
        if re.search(r"\$\{[^}]+\}", value):
            # langchain-mcp-adapters expands this syntax against os.environ and
            # logs unresolved values. Reject rather than leak or alter a secret.
            _reject(
                f"Credential '{credential_id}' contains unsupported environment interpolation syntax."
            )
        scoped[name] = value
    return scoped


def _process_environment() -> dict[str, str]:
    # Docker itself is trusted; only --env names below reach its container.
    # Never inherit provider keys, proxy settings, language hooks, or Docker
    # endpoints from the parent. The MCP SDK also inherits its small safe list.
    return {
        name: os.environ[name]
        for name in ("PATH", "SYSTEMROOT", "WINDIR")
        if name in os.environ
    }


def build_stdio_connection(
    provider: Any,
    credentials: Mapping[str, str] | None = None,
    *,
    development: bool = False,
    cleanup_callbacks: list[Callable[[], None]] | None = None,
) -> dict[str, Any]:
    """Return a langchain-mcp-adapters connection with scoped credentials.

    The owning driver must invoke ``cleanup_callbacks`` in its finalizer, even
    after connection discovery fails. ``--rm`` covers normal termination; the
    finalizer also removes a container whose MCP child ignored stdin shutdown.
    Images must already exist locally: task execution never downloads code.
    """
    validate_stdio_provider(provider, development=development)
    scoped = _scoped_credentials(provider, credentials or {})
    command = getattr(provider, "command", None)
    image = getattr(provider, "image", None)
    args = list(getattr(provider, "args", None) or [])
    if development and command and not image:
        warnings.warn(
            f"Development MCP '{provider.id}' runs as a host process without filesystem or network isolation.",
            RuntimeWarning,
            stacklevel=2,
        )
        return {
            "transport": "stdio",
            "command": command,
            "args": args,
            "env": {**_process_environment(), **scoped},
            "session_kwargs": {"read_timeout_seconds": timedelta(seconds=60)},
        }
    docker = shutil.which("docker")
    if not docker:
        _reject(
            "Docker is required for trusted tool execution; install a local Linux-container Docker engine."
        )
    if cleanup_callbacks is None:
        _reject("Container execution requires an explicit cleanup_callbacks owner.")
    endpoint = (
        "npipe:////./pipe/docker_engine"
        if os.name == "nt"
        else "unix:///var/run/docker.sock"
    )
    # A user's Docker config can silently inject its proxy credentials into
    # containers. An empty per-launch config prevents that additional channel.
    docker_config = tempfile.TemporaryDirectory(prefix="amx-docker-config-")
    docker_prefix = [docker, f"--host={endpoint}", f"--config={docker_config.name}"]
    process_env = _process_environment()
    try:
        # Docker creates writable anonymous volumes from image VOLUME metadata,
        # even with --read-only. Reject those images so all writable storage stays
        # inside the explicitly size-bounded tmpfs mounts.
        inspected = subprocess.run(
            [
                *docker_prefix,
                "image",
                "inspect",
                "--format",
                "{{json .Config.Volumes}}",
                image,
            ],
            env=process_env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
        if inspected.returncode != 0:
            _reject(
                "Pinned tool image is unavailable or cannot be inspected by the local Docker engine."
            )
        volumes = json.loads(inspected.stdout)
        if volumes is not None and volumes != {}:
            _reject(
                "Tool images must not declare volumes; image volumes bypass the read-only filesystem boundary."
            )
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError) as exc:
        docker_config.cleanup()
        _reject(
            f"Cannot verify pinned tool image storage configuration: {type(exc).__name__}."
        )
    except BaseException:
        docker_config.cleanup()
        raise
    # MCP adapters can open multiple simultaneous stateless sessions using the
    # same connection. Let Docker allocate names and clean up by an unguessable
    # connection ownership label instead of assigning one colliding fixed name.
    owner = uuid.uuid4().hex

    def owned_containers() -> list[str]:
        inventory = subprocess.run(
            [
                *docker_prefix,
                "ps",
                "--all",
                "--quiet",
                "--no-trunc",
                "--filter",
                f"label=aeromesh.owner={owner}",
            ],
            env=process_env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
        if getattr(inventory, "returncode", 0) != 0:
            _reject(
                f"Could not confirm cleanup of MCP owner '{owner}'; Docker inventory failed."
            )
        ids = (getattr(inventory, "stdout", None) or b"").decode("ascii").split()
        if not all(re.fullmatch(r"[0-9a-f]{64}", item) for item in ids):
            _reject(
                f"Could not confirm cleanup of MCP owner '{owner}'; invalid container inventory."
            )
        return ids

    def cleanup() -> None:
        try:
            ids = owned_containers()
            if not ids:
                return
            subprocess.run(
                [*docker_prefix, "rm", "--force", "--volumes", *ids],
                env=process_env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=10,
                check=False,
            )
            # A concurrent --rm may make removal return nonzero. Re-inventory
            # confirms actual absence and cannot hide mixed removal failures.
            if owned_containers():
                _reject(
                    f"Could not confirm cleanup of MCP owner '{owner}'; Docker removal failed."
                )
        except (OSError, subprocess.TimeoutExpired, UnicodeError) as exc:
            _reject(
                f"Could not confirm cleanup of MCP owner '{owner}': {type(exc).__name__}."
            )
        finally:
            docker_config.cleanup()

    if cleanup_callbacks is not None:
        cleanup_callbacks.append(cleanup)
    docker_args = [
        *docker_prefix[1:],
        "run",
        "--rm",
        "--interactive",
        "--init",
        "--pull=never",
        "--log-driver=none",
        f"--label=aeromesh.owner={owner}",
        "--label=aeromesh.managed=true",
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--user=65532:65532",
        "--pids-limit=64",
        "--memory=256m",
        "--memory-swap=256m",
        "--cpus=1",
        "--ulimit=nofile=256:256",
        "--stop-timeout=2",
        "--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777",
        "--workdir=/tmp",
        "--env=HOME=/tmp",
        "--env=TMPDIR=/tmp",
        *[f"--env={name}" for name in sorted(scoped)],
        image,
        *args,
    ]
    return {
        "transport": "stdio",
        "command": docker,
        "args": docker_args,
        "env": {**process_env, **scoped},
        "session_kwargs": {"read_timeout_seconds": timedelta(seconds=60)},
    }
