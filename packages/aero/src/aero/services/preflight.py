"""Preflight approved configuration without paying for a model invocation."""

from __future__ import annotations

import os
import shutil
from typing import Any

from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.domain import paths
from aero.infrastructure.parser import ManifestParser, WorkflowParser, strict_json
from aero.infrastructure.tool_execution import (
    validate_stdio_provider,
    validate_credential_bindings,
)
from aero.infrastructure.vault import ZeroTrustVaultResolver
from aero.services import trust


def preflight(
    target: str, *, development: bool = False, probe_tools: bool = False
) -> dict[str, Any]:
    def fail(message):
        raise AeroMeshDomainError(
            message, ErrorCode.AMX_ERR_POLICY_VIOLATION, ExitCode.POLICY_VIOLATION
        )

    resolved = paths.resolve_agent_manifest_path(
        target
    ) or paths.resolve_workflow_manifest_path(target)
    approved = None
    raw = None
    if resolved:
        raw = strict_json(resolved.read_text(encoding="utf-8"))
    if raw is None or "release_version" in raw:
        if development:
            fail("Release preflight always requires an approved release")
        from aero.services.releases import load_approved_release

        approved = load_approved_release(target)
        raw = approved.entry_data
        resolved = approved.entry_path
    elif not development:
        raw = trust.require_trusted_manifest(str(resolved))
    if "workflow_version" in raw:
        from aero.services.workflow_runner import WorkflowExecutionDriver

        workflow = WorkflowParser().validate_dict(raw)
        driver = WorkflowExecutionDriver(
            workflow,
            development=development,
            manifest_path=str(resolved),
            approved_release=approved,
        )
        workflow_report = driver.preflight()
        if approved:
            manifests = [
                ManifestParser().validate_dict(value)
                for value in approved.agent_data.values()
            ]
        else:
            manifests = [entry[0] for entry in driver._resolve_agents().values()]
    else:
        manifests = [ManifestParser().validate_dict(raw)]
        workflow_report = None
        if approved:
            manifests = [
                ManifestParser().validate_dict(value)
                for value in approved.agent_data.values()
            ]
    if approved is None:
        from aero.infrastructure.attestation import canonicalize, sha256_hex

        closure = {}
        active = set()

        def visit(manifest):
            identity = manifest.identity.id
            if identity in active:
                fail(f"Subagent cycle at {identity}")
            if identity in closure:
                return
            active.add(identity)
            for provider in manifest.providers:
                if provider.type != "sub_agent":
                    continue
                path = paths.resolve_agent_manifest_path(provider.agent_id)
                if path is None:
                    fail(f"Missing referenced agent {provider.agent_id}")
                raw_child = (
                    strict_json(path.read_text(encoding="utf-8"))
                    if development
                    else trust.require_trusted_manifest(str(path), provider.agent_id)
                )
                if raw_child.get("identity", {}).get("id") != provider.agent_id:
                    fail("Referenced agent identity mismatch")
                if not development and not provider.agent_sha256:
                    fail(f"Referenced agent {provider.agent_id} is not pinned")
                if (
                    provider.agent_sha256
                    and sha256_hex(canonicalize(raw_child)) != provider.agent_sha256
                ):
                    fail(f"Referenced agent {provider.agent_id} digest mismatch")
                visit(ManifestParser().validate_dict(raw_child))
            active.remove(identity)
            closure[identity] = manifest

        for manifest in manifests:
            visit(manifest)
        manifests = list(closure.values())
    from aero.services.deepagents_runner import PROVIDER_ENV_VARS

    configured = [p for p, key in PROVIDER_ENV_VARS.items() if os.environ.get(key)]
    model = os.environ.get("AEROMESH_MODEL")
    if model and (
        ":" not in model or not all(part.strip() for part in model.split(":", 1))
    ):
        fail("AEROMESH_MODEL must use nonempty provider:model syntax")
    if not model and len(configured) != 1:
        fail(
            "Set AEROMESH_MODEL=provider:model or configure exactly one supported provider"
        )
    reports = []
    vault = ZeroTrustVaultResolver()
    for manifest in manifests:
        if (
            not development
            and approved is None
            and any(p.type in {"mcp", "credential"} for p in manifest.providers)
        ):
            fail("Tools and credentials require an independently approved release")
        tool_descriptions = []
        for provider in manifest.providers:
            if provider.type != "mcp":
                continue
            validate_credential_bindings(provider.credential_bindings)
            if provider.transport == "stdio":
                validate_stdio_provider(provider, development=development)
                if provider.image and not shutil.which("docker"):
                    fail("Docker is unavailable for the pinned tool image")
                if provider.command and not shutil.which(provider.command):
                    fail(f"Tool executable unavailable: {provider.command}")
            elif not development:
                fail("Remote MCP endpoints are unsupported in trusted execution")
            tool_descriptions.append(
                {
                    "provider": provider.id,
                    "image": provider.image,
                    "required_tools": provider.required_tools,
                    "credential_names": sorted(provider.credential_bindings.values()),
                }
            )
        credentials = vault.resolve_requirements(
            manifest.providers, non_interactive=True
        )
        observed = None
        if probe_tools:
            from aero.services.deepagents_runner import build_mcp_tools

            cleanup = []
            try:
                tools = build_mcp_tools(
                    manifest,
                    credentials,
                    development=development,
                    cleanup_callbacks=cleanup,
                )
                observed = [t.name for t in tools]
            finally:
                for callback in reversed(cleanup):
                    callback()
        reports.append(
            {
                "agent_id": manifest.identity.id,
                "tools": tool_descriptions,
                "observed_tools": observed,
            }
        )
    # A named model's actual endpoint/authentication is verified when invoked;
    # do not claim credentials or paid service availability from this static check.
    return {
        "ready": True,
        "scope": "local configuration and optional MCP discovery; model service not contacted",
        "development": development,
        "release_digest": getattr(approved, "digest", None),
        "agents": reports,
        "workflow": workflow_report,
        "model": model,
        "model_service_verified": False,
    }
