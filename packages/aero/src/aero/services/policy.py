"""Independent, deny-by-default operator grants for an approved release.

Package declarations request capabilities; only this operator-controlled policy
can grant them. Networked tools are intentionally unsupported by release v1.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import jsonschema

from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.infrastructure.parser import strict_json, _read_manifest

_STRING_SET = {
    "type": "array",
    "items": {"type": "string", "minLength": 1},
    "uniqueItems": True,
}
_POLICY_SCHEMA = {
    "type": "object",
    "required": ["policy_version"],
    "additionalProperties": False,
    "properties": {
        "policy_version": {"const": "1"},
        "allowed_credentials": _STRING_SET,
        "providers": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "required": ["image", "tools"],
                "additionalProperties": False,
                "properties": {
                    "image": {
                        "type": "string",
                        "pattern": "^[a-z0-9][a-z0-9._:/-]*@sha256:[a-f0-9]{64}$",
                    },
                    "tools": _STRING_SET,
                    "credential_bindings": {
                        "type": "object",
                        "additionalProperties": {"type": "string", "minLength": 1},
                    },
                },
            },
        },
    },
}


def _deny(message: str) -> None:
    raise AeroMeshDomainError(
        message, ErrorCode.AMX_ERR_DOMAIN_BLOCKED, ExitCode.DOMAIN_BLOCKED
    )


def validate_policy(data: dict[str, Any]) -> dict[str, Any]:
    """Reject unknown grant syntax; absent grants always mean deny."""
    try:
        jsonschema.validate(data, _POLICY_SCHEMA)
    except jsonschema.ValidationError as exc:
        _deny(f"Invalid operator policy: {exc.message}")
    return data


def load_policy(path: str | Path) -> dict[str, Any]:
    try:
        data = strict_json(_read_manifest(str(path)))
    except (OSError, ValueError) as exc:
        _deny(f"Cannot read operator policy: {exc}")
    return validate_policy(data)


def requested_capabilities(release: dict[str, Any]) -> dict[str, Any]:
    """Stable capability inventory suitable for machine-readable release diffs."""
    images, credentials, bindings, domains, endpoints = (
        set(),
        set(),
        set(),
        set(),
        set(),
    )
    tools: dict[str, set[str]] = {}
    for record in release["agents"].values():
        for provider in record["manifest"]["requirements"]["providers"]:
            if provider["type"] == "credential":
                credentials.add(provider["id"])
            elif provider["type"] == "mcp":
                if provider.get("image"):
                    images.add(provider["image"])
                if provider.get("uri"):
                    endpoints.add(provider["uri"])
                domains.update(provider.get("allowed_domains", []))
                tools.setdefault(provider["id"], set()).update(
                    provider.get("required_tools", [])
                )
                for env_name, credential in provider.get(
                    "credential_bindings", {}
                ).items():
                    credentials.add(credential)
                    bindings.add(f"{provider['id']}:{env_name}={credential}")
    return {
        "images": sorted(images),
        "credentials": sorted(credentials),
        "tools": {name: sorted(values) for name, values in sorted(tools.items())},
        "credential_bindings": sorted(bindings),
        "domains": sorted(domains),
        "endpoints": sorted(endpoints),
    }


def check_policy(release: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    """Return effective requested capabilities, or reject any ungranted request."""
    validate_policy(policy)
    requested = requested_capabilities(release)
    # v1 isolation is deliberately network-none; a grant cannot enable a feature
    # that the production runtime does not enforce.
    if requested["domains"] or requested["endpoints"]:
        _deny(
            "Operator policy cannot grant network access: release v1 supports network-none tools only."
        )
    denied_credentials = set(requested["credentials"]) - set(
        policy.get("allowed_credentials", [])
    )
    if denied_credentials:
        _deny(
            f"Operator policy does not grant credentials: {', '.join(sorted(denied_credentials))}"
        )
    for record in release["agents"].values():
        for provider in record["manifest"]["requirements"]["providers"]:
            if provider["type"] != "mcp":
                continue
            grant = policy.get("providers", {}).get(provider["id"])
            if grant is None:
                _deny(
                    f"Operator policy does not grant MCP provider {provider['id']!r}."
                )
            if provider.get("image") != grant["image"]:
                _deny(
                    f"Operator policy does not grant this image for provider {provider['id']!r}."
                )
            denied_tools = set(provider["required_tools"]) - set(grant["tools"])
            if denied_tools:
                _deny(
                    f"Operator policy does not grant tools for {provider['id']}: {', '.join(sorted(denied_tools))}"
                )
            allowed = grant.get("credential_bindings", {})
            for env_name, credential in provider.get("credential_bindings", {}).items():
                if allowed.get(env_name) != credential:
                    _deny(
                        f"Operator policy does not grant credential binding {provider['id']}:{env_name}={credential}"
                    )
    return requested
