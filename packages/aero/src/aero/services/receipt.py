"""Minimal execution evidence; never persist prompts, outputs, or credentials."""

import math
import time
from importlib.metadata import PackageNotFoundError, version
from functools import lru_cache

from aero.infrastructure.attestation import canonicalize, sha256_hex
from typing import Any, Dict, Optional


@lru_cache(maxsize=1)
def runtime_versions():
    runtime = {}
    for distribution in (
        "aero",
        "deepagents",
        "langchain",
        "langgraph",
        "langchain-mcp-adapters",
    ):
        try:
            runtime[distribution] = version(distribution)
        except PackageNotFoundError:
            runtime[distribution] = "source-or-unavailable"
    return runtime


def make_receipt(
    *,
    execution_id: str,
    session_id: str,
    artifact_sha256: str,
    status: str,
    started_at: float,
    development: bool,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[BaseException] = None,
    model: Optional[str] = None,
    release_digest: Optional[str] = None,
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    result = result or {}
    source = result.get("token_usage") or result.get("usage") or {}
    usage = (
        {
            key: value
            for key, value in source.items()
            if key in {"input_tokens", "output_tokens", "total_tokens", "cached_tokens"}
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value >= 0
        }
        if isinstance(source, dict)
        else {}
    )
    cost = source.get("estimated_cost_usd") if isinstance(source, dict) else None
    if (
        not isinstance(cost, (int, float))
        or isinstance(cost, bool)
        or not math.isfinite(cost)
        or cost < 0
    ):
        cost = None
    return {
        "receipt_version": "1",
        "execution_id": execution_id,
        "session_id": session_id,
        "artifact_sha256": artifact_sha256,
        "release_digest": release_digest,
        "policy_sha256": sha256_hex(canonicalize(policy))
        if policy is not None
        else None,
        "runtime": dict(runtime_versions()),
        "status": status,
        "development": development,
        "started_at": started_at,
        "finished_at": time.time(),
        "model": model or result.get("model"),
        "usage": usage,
        "usage_reported": bool(usage),
        "execution_success": status == "completed"
        and error is None
        and result.get("execution_success") is True,
        "usage_complete": source.get("usage_complete")
        if isinstance(source, dict)
        else None,
        "estimated_cost_usd": cost,
        "billing_guarantee": False,
        "output_valid": result.get("output_valid"),
        "task_assessment": "unverified",
        "error_code": getattr(getattr(error, "error_code", None), "value", None)
        if error
        else None,
        "error_type": type(error).__name__ if error else None,
    }
