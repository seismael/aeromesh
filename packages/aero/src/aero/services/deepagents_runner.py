"""Compile verified DAM manifests into Deep Agents with explicit runtime contracts."""

import asyncio
import hashlib
import json
import os
import re
import threading
import uuid
import warnings
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import jsonschema
from referencing.exceptions import Unresolvable
from langchain_core.callbacks import BaseCallbackHandler
from langchain.agents.middleware import AgentMiddleware

from aero.domain.models import AgentManifest
from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.domain.paths import get_aeromesh_home, resolve_agent_manifest_path

DEFAULT_MAX_STEPS = 40
DEFAULT_MAX_MODEL_CALLS = 40
DEFAULT_MAX_OUTPUT_TOKENS = 4096
DEFAULT_EXECUTION_TIMEOUT_SECONDS = 900
PROVIDER_MODEL_STRINGS = {
    "deepseek": "deepseek:deepseek-chat",
    "openai": "openai:gpt-4o",
    "anthropic": "anthropic:claude-3-5-sonnet-20241022",
    "gemini": "google_genai:gemini-2.5-flash",
}
PROVIDER_ENV_VARS = {
    "deepseek": "DEEPSEEK_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


def _error(message: str, schema: bool = False) -> AeroMeshDomainError:
    return AeroMeshDomainError(
        message,
        ErrorCode.AMX_ERR_SCHEMA_VIOLATION
        if schema
        else ErrorCode.AMX_ERR_PROVIDER_FAILED,
        ExitCode.SCHEMA_VIOLATION if schema else ExitCode.PROVIDER_FAILED,
    )


def _contract_error(message):
    return AeroMeshDomainError(
        message, ErrorCode.AMX_ERR_CONTRACT_VIOLATION, ExitCode.CONTRACT_VIOLATION
    )


def _budget_error(message):
    return AeroMeshDomainError(
        message, ErrorCode.AMX_ERR_BUDGET_EXCEEDED, ExitCode.BUDGET_EXCEEDED
    )


def _json_value(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError(f"Non-finite JSON value: {value}")

    return json.loads(text, object_pairs_hook=unique, parse_constant=invalid)


def _validate_input(manifest, value):
    contract = manifest.capabilities.input_contract
    if contract is None:
        return value
    try:
        validator = jsonschema.Draft7Validator(contract)
        if isinstance(value, str) and not validator.is_valid(value):
            value = _json_value(value)
        # Python callers must still supply values representable by strict JSON.
        json.dumps(value, allow_nan=False)
        validator.validate(value)
    except (
        ValueError,
        TypeError,
        RecursionError,
        Unresolvable,
        jsonschema.ValidationError,
        jsonschema.SchemaError,
    ) as exc:
        raise _contract_error(
            f"Agent input contract violation: {getattr(exc, 'message', str(exc))}"
        ) from exc
    return value


def _validate_output(manifest, result):
    messages = result.get("messages") or []
    final = messages[-1] if messages else None
    if final is not None and (
        getattr(final, "type", None) != "ai" or getattr(final, "tool_calls", None)
    ):
        raise _error("Agent did not produce a completed final assistant answer.")
    final_text = getattr(final, "content", "")
    if isinstance(final_text, list):
        final_text = "".join(
            b.get("text", "")
            for b in final_text
            if isinstance(b, dict) and b.get("type") == "text"
        )
    if not isinstance(final_text, str) or not final_text.strip():
        raise _error("Agent returned an empty final answer.")
    contract = manifest.capabilities.output_contract
    if contract is None:
        return final_text, None, None
    try:
        structured = _json_value(final_text)
        jsonschema.Draft7Validator(contract).validate(structured)
    except (
        ValueError,
        RecursionError,
        Unresolvable,
        jsonschema.ValidationError,
        jsonschema.SchemaError,
    ) as exc:
        raise _contract_error(
            f"Agent output contract violation: {getattr(exc, 'message', str(exc))}"
        ) from exc
    return final_text, structured, True


class TokenUsageCounter(BaseCallbackHandler):
    """Usage ledger that refuses model calls before configured limits are exceeded.

    Reservations use UTF-8 request bytes plus an overhead allowance as a conservative
    token *estimate*. Explicit user-supplied prices and provider output caps are not
    billing guarantees. Concurrent subagent reservations share one locked ledger.
    """

    raise_error = True

    def __init__(self, observability: Any = None):
        self.input_tokens = 0
        self.output_tokens = 0
        self.model_calls = 0
        self.estimated_input_tokens = 0
        self.estimated_output_tokens = 0
        self.observability = observability
        self._lock = threading.Lock()
        self._reservations = {}
        self._used_cost = 0.0
        self._reserved_cost = 0.0
        self._missing_usage = False

    def _get(self, name, default=None):
        value = getattr(self.observability, name, None)
        return default if value is None else value

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        params = kwargs.get("invocation_params") or {}
        max_output = self._get("max_output_tokens", DEFAULT_MAX_OUTPUT_TOKENS)
        limit = self._get("cost_limit_usd")
        declared_caps = [
            params[k]
            for k in ("max_tokens", "max_output_tokens", "max_completion_tokens")
            if isinstance(params.get(k), int)
        ]
        if limit is not None and (not declared_caps or min(declared_caps) > max_output):
            raise _budget_error(
                "Monetary budget requires an enforced maximum output token setting on every model call."
            )
        payload = {
            "messages": [[m.model_dump() for m in batch] for batch in messages],
            "settings": params,
        }
        estimated_input = (
            len(json.dumps(payload, default=str, ensure_ascii=False).encode("utf-8"))
            + 256
        )
        input_price = self._get("input_price_per_million")
        output_price = self._get("output_price_per_million")
        if limit is not None and (input_price is None or output_price is None):
            raise _budget_error(
                "Monetary budget requires explicit input_price_per_million and output_price_per_million."
            )
        cost = (
            estimated_input * (input_price or 0) + max_output * (output_price or 0)
        ) / 1_000_000
        with self._lock:
            if self.model_calls >= self._get(
                "max_model_calls", DEFAULT_MAX_MODEL_CALLS
            ):
                raise _budget_error(
                    "Maximum model call budget reached before the next invocation."
                )
            if (
                limit is not None
                and self._used_cost + self._reserved_cost + cost > limit
            ):
                raise _budget_error(
                    "Estimated next model call exceeds the remaining monetary budget; invocation refused."
                )
            self.model_calls += 1
            self._reserved_cost += cost
            self._reservations[run_id] = (cost, estimated_input, max_output)

    def on_llm_end(self, response, *, run_id=None, **kwargs):
        used_input = used_output = 0
        observed = False
        for group in response.generations:
            for gen in group:
                usage = getattr(getattr(gen, "message", None), "usage_metadata", None)
                if usage:
                    observed = True
                    used_input += usage.get("input_tokens", 0)
                    used_output += usage.get("output_tokens", 0)
        with self._lock:
            reserved, estimated_input, estimated_output = self._reservations.pop(
                run_id, (0, 0, 0)
            )
            self._reserved_cost -= reserved
            self.input_tokens += used_input
            self.output_tokens += used_output
            self.estimated_input_tokens += used_input if observed else estimated_input
            self.estimated_output_tokens += (
                used_output if observed else estimated_output
            )
            self._missing_usage |= not observed
            if observed:
                self._used_cost += (
                    used_input * self._get("input_price_per_million", 0)
                    + used_output * self._get("output_price_per_million", 0)
                ) / 1_000_000
            else:
                # Missing provider usage never frees the reservation for more calls.
                self._used_cost += reserved

    def on_llm_error(self, error, *, run_id=None, **kwargs):
        with self._lock:
            reserved, estimated_input, estimated_output = self._reservations.pop(
                run_id, (0, 0, 0)
            )
            self._reserved_cost -= reserved
            self._used_cost += reserved
            self.estimated_input_tokens += estimated_input
            self.estimated_output_tokens += estimated_output
            self._missing_usage = True

    def report(self):
        priced = (
            self._get("input_price_per_million") is not None
            and self._get("output_price_per_million") is not None
        )
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
            "model_calls": self.model_calls,
            "usage_complete": not self._missing_usage,
            "estimated_cost_usd": round(self._used_cost + self._reserved_cost, 8)
            if priced
            else None,
            "pricing_source": "explicit_configuration" if priced else None,
            "billing_guarantee": False,
        }


class OutputTokenLimitMiddleware(AgentMiddleware):
    """Bound each ordinary agent model call, including delegated agent models."""

    def __init__(self, maximum: int):
        self.maximum = maximum

    def _request(self, request):
        settings = dict(request.model_settings)
        # init_chat_model provider adapters accept max_tokens; Google uses its alias.
        fields = getattr(type(request.model), "model_fields", {})
        settings[
            "max_output_tokens" if "max_output_tokens" in fields else "max_tokens"
        ] = self.maximum
        return request.override(model_settings=settings)

    def wrap_model_call(self, request, handler):
        return handler(self._request(request))

    async def awrap_model_call(self, request, handler):
        return await handler(self._request(request))


def default_checkpoint_db() -> Path:
    return get_aeromesh_home() / "checkpoints.sqlite"


def default_store_db() -> Path:
    return get_aeromesh_home() / "memory.sqlite"


@asynccontextmanager
async def _sqlite_setup_lock(path):
    """Serialize native schema migrations across processes and driver threads."""
    handle = path.with_suffix(path.suffix + ".setup.lock").open("a+b")
    acquired = False
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            lock = lambda: msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            unlock = lambda: msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            lock = lambda: fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            unlock = lambda: fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        deadline = asyncio.get_running_loop().time() + 30
        while True:
            try:
                lock()
                acquired = True
                break
            except (BlockingIOError, OSError):
                if asyncio.get_running_loop().time() >= deadline:
                    raise _error(
                        "Timed out waiting for checkpoint database initialization."
                    )
                await asyncio.sleep(0.05)
        yield
    finally:
        if acquired:
            unlock()
        handle.close()


async def build_async_checkpointer(db_path: Optional[Path] = None) -> Any:
    import aiosqlite
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    path = db_path or default_checkpoint_db()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(path), timeout=30, isolation_level=None)
    try:
        saver = AsyncSqliteSaver(conn)
        async with _sqlite_setup_lock(path):
            await saver.setup()
        return saver
    except BaseException:
        await conn.close()
        raise


async def build_async_store(db_path: Optional[Path] = None) -> Any:
    import aiosqlite
    from langgraph.store.sqlite.aio import AsyncSqliteStore

    path = db_path or default_store_db()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(path), timeout=30, isolation_level=None)
    try:
        store = AsyncSqliteStore(conn)
        async with _sqlite_setup_lock(path):
            await store.setup()
        return store
    except BaseException:
        await conn.close()
        raise


def resolve_configured_model(credentials: Optional[Dict[str, str]] = None) -> Any:
    """An explicit model wins; ambiguous provider environments fail visibly."""
    from langchain.chat_models import init_chat_model

    credentials = credentials or {}
    selected = os.environ.get("AEROMESH_MODEL")
    if selected:
        if ":" not in selected or not all(selected.split(":", 1)):
            raise _error("AEROMESH_MODEL must use provider:model syntax.", schema=True)
        provider = selected.split(":", 1)[0]
        key_name = PROVIDER_ENV_VARS.get(
            "gemini" if provider == "google_genai" else provider
        )
        key = (
            credentials.get(key_name) or os.environ.get(key_name) if key_name else None
        )
        return init_chat_model(selected, **({"api_key": key} if key else {}))
    available = [
        (p, credentials.get(k) or os.environ.get(k))
        for p, k in PROVIDER_ENV_VARS.items()
        if credentials.get(k) or os.environ.get(k)
    ]
    if len(available) != 1:
        raise _error(
            "Set AEROMESH_MODEL=provider:model; automatic selection requires exactly one configured provider."
        )
    provider, key = available[0]
    return init_chat_model(PROVIDER_MODEL_STRINGS[provider], api_key=key)


def resolve_model(credentials: Optional[Dict[str, str]] = None) -> Any:
    return resolve_configured_model(credentials)


def _validate_supported_manifest(manifest: AgentManifest):
    from aero.infrastructure.parser import validate_contract_definition

    for contract in (
        manifest.capabilities.input_contract,
        manifest.capabilities.output_contract,
    ):
        if contract is not None:
            try:
                validate_contract_definition(contract)
            except (AeroMeshDomainError, RecursionError, Unresolvable) as exc:
                raise _contract_error(
                    f"Agent contract definition is invalid: {exc}"
                ) from exc
    unsupported = {p.type for p in manifest.providers} - {
        "mcp",
        "credential",
        "sub_agent",
    }
    if unsupported:
        raise _error(
            f"Unsupported provider types: {sorted(unsupported)}; bundled skills are not implemented.",
            schema=True,
        )
    runtime = manifest.cognitive_runtime
    if (
        runtime.driver != "Driver.LangGraph"
        or runtime.memory_policy not in {"NATIVE", "EPHEMERAL_STREAM"}
        or runtime.checkpoint_policy not in {"ON_STEP", "DISABLED"}
    ):
        raise _error(
            "Unsupported runtime driver, memory policy, or checkpoint policy.",
            schema=True,
        )


def mcp_connections(
    manifest: AgentManifest,
    credentials=None,
    *,
    development=False,
    cleanup_callbacks=None,
):
    from aero.infrastructure.tool_execution import build_stdio_connection

    connections = {}
    for provider in manifest.providers:
        if provider.type != "mcp":
            continue
        if provider.id in connections:
            raise _error(f"Duplicate MCP provider id: {provider.id}", schema=True)
        if provider.command or getattr(provider, "image", None):
            connection = build_stdio_connection(
                provider,
                credentials or {},
                development=development,
                cleanup_callbacks=cleanup_callbacks,
            )
            if (
                development
                and provider.command
                and not getattr(provider, "image", None)
            ):
                if cleanup_callbacks is None:
                    raise _error(
                        "MCP connections require a cleanup_callbacks owner for their execution resources."
                    )
                from aero.infrastructure.egress_proxy import LocalEgressProxy

                proxy = LocalEgressProxy(allowed_domains=provider.allowed_domains or [])
                cleanup_callbacks.append(proxy.stop)
                proxy.start()
                connection["env"].update(proxy.proxy_env())
            connections[provider.id] = connection
        elif provider.uri and provider.transport in ("sse", "http"):
            if not development:
                raise _error(
                    "Remote SSE providers have no enforced isolation boundary; use an approved container or explicit development mode."
                )
            if getattr(provider, "credential_bindings", None):
                raise _error(
                    "Remote credential bindings are not implemented; environment bindings apply to stdio providers only.",
                    schema=True,
                )
            warnings.warn(
                f"Development remote MCP {provider.id!r} has no enforced network or server isolation.",
                RuntimeWarning,
                stacklevel=2,
            )
            connections[provider.id] = {
                "transport": "sse" if provider.transport == "sse" else "http",
                "url": provider.uri,
                "session_kwargs": {"read_timeout_seconds": timedelta(seconds=60)},
            }
        else:
            raise _error(
                f"MCP provider {provider.id!r} has no supported executable connection.",
                schema=True,
            )
    return connections


async def _load_mcp_tools(manifest, connections, session_stack=None):
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(connections=connections)
    result = []
    model_names = set()
    for provider in manifest.providers:
        if provider.type != "mcp":
            continue
        try:
            if session_stack is None:
                tools = await client.get_tools(server_name=provider.id)
            else:
                from langchain_mcp_adapters.tools import load_mcp_tools

                session = await session_stack.enter_async_context(
                    client.session(provider.id)
                )
                tools = await load_mcp_tools(session)
        except Exception as exc:
            raise AeroMeshDomainError(
                f"Failed to connect to MCP provider {provider.id!r}: {type(exc).__name__}",
                ErrorCode.AMX_ERR_MCP_SPAWN_FAILED,
                ExitCode.MCP_SPAWN_FAILED,
            ) from exc
        available = {tool.name for tool in tools}
        required = set(provider.required_tools or [])
        if required - available:
            raise AeroMeshDomainError(
                f"MCP provider {provider.id!r} is missing required tools: {sorted(required - available)}",
                ErrorCode.AMX_ERR_MCP_SPAWN_FAILED,
                ExitCode.MCP_SPAWN_FAILED,
            )
        if len(available) != len(tools):
            raise _error(f"MCP provider {provider.id!r} returned duplicate tool names.")
        for tool in tools:
            if required and tool.name not in required:
                continue
            original = tool.name
            full_name = f"{provider.id}__{original}"
            name = re.sub(r"[^A-Za-z0-9_-]", "_", full_name)
            if len(name) > 64 or name != full_name:
                name = (
                    name[:49]
                    + "_"
                    + hashlib.sha256(full_name.encode()).hexdigest()[:14]
                )
            if name in model_names:
                raise _error(
                    f"MCP tool name collision after namespacing: {name!r}; use distinct provider identifiers."
                )
            model_names.add(name)
            # The callable captures the original MCP name; only its model-facing name changes.
            result.append(
                tool.model_copy(
                    update={
                        "name": name,
                        "metadata": {
                            **(tool.metadata or {}),
                            "mcp_provider": provider.id,
                            "mcp_tool": original,
                        },
                    }
                )
            )
    return result


class _MCPSessions:
    """Own long-lived MCP sessions in one task, as required by AnyIO scopes."""

    def __init__(self, loop):
        self.loop = loop
        self.queue = asyncio.Queue()
        self.closed = False
        self.task = loop.create_task(self._own_sessions())

    async def _own_sessions(self):
        try:
            async with AsyncExitStack() as stack:
                while True:
                    item = await self.queue.get()
                    if item is None:
                        return
                    manifest, connections, future = item
                    try:
                        tools = await _load_mcp_tools(manifest, connections, stack)
                    except Exception as exc:
                        if not future.done():
                            future.set_exception(exc)
                    else:
                        if not future.done():
                            future.set_result(tools)
        finally:
            self.closed = True

    async def open(self, manifest, connections):
        if self.closed:
            raise _error("MCP session owner has closed.")
        future = self.loop.create_future()
        await self.queue.put((manifest, connections, future))
        return await asyncio.wait_for(future, timeout=60)

    async def close(self):
        if not self.task.done():
            await self.queue.put(None)
            try:
                await asyncio.wait_for(asyncio.shield(self.task), timeout=5)
            except (TimeoutError, asyncio.CancelledError):
                self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)


def build_mcp_tools(
    manifest,
    credentials=None,
    *,
    development=False,
    cleanup_callbacks=None,
    session_manager=None,
):
    if cleanup_callbacks is None and any(p.type == "mcp" for p in manifest.providers):
        raise _error(
            "MCP tool construction requires an explicit cleanup_callbacks owner."
        )
    owned_callbacks = [] if cleanup_callbacks is None else cleanup_callbacks
    try:
        connections = mcp_connections(
            manifest,
            credentials,
            development=development,
            cleanup_callbacks=owned_callbacks,
        )
        if session_manager is not None and connections:
            return session_manager.loop.run_until_complete(
                session_manager.open(manifest, connections)
            )

        async def discover():
            return await asyncio.wait_for(
                _load_mcp_tools(manifest, connections), timeout=60
            )

        return asyncio.run(discover()) if connections else []
    except TimeoutError as exc:
        raise AeroMeshDomainError(
            "MCP discovery exceeded its 60-second deadline.",
            ErrorCode.AMX_ERR_MCP_TIMEOUT,
            ExitCode.MCP_TIMEOUT,
        ) from exc


def build_output_instructions(manifest: AgentManifest) -> Optional[str]:
    """Output instructions only; verification is performed by jsonschema, not an LLM."""
    contract = manifest.capabilities.output_contract
    if contract is None:
        return None
    return "Return ONLY valid JSON satisfying this JSON Schema: " + json.dumps(contract)


def manifest_to_deepagent_kwargs(manifest, credentials=None, tools=None, model=None):
    _validate_supported_manifest(manifest)
    prompt = f"{manifest.cognitive_runtime.persona}\n\nTask completion criteria:\n{manifest.cognitive_runtime.success_criteria}\nReport incomplete work and evidence limitations explicitly."
    contract_prompt = build_output_instructions(manifest)
    if contract_prompt:
        prompt += "\n\n" + contract_prompt
    kwargs = {
        "name": manifest.identity.name,
        "system_prompt": prompt,
        "model": model if model is not None else resolve_model(credentials),
    }
    if tools:
        kwargs["tools"] = tools
    return kwargs


def _canonical_digest(data):
    from aero.infrastructure.attestation import canonicalize

    return hashlib.sha256(canonicalize(data)).hexdigest()


class DeepAgentsExecutionDriver:
    """Compile trusted artifacts; execute with deterministic shape validation."""

    def __init__(
        self,
        manifest,
        credentials=None,
        mcp_tools=None,
        model=None,
        checkpointer=None,
        store=None,
        *,
        development=False,
        approved_manifest_path=None,
        approved_release=None,
    ):
        self.manifest = manifest
        self.credentials = credentials or {}
        self.development = development
        self.approved_release = approved_release
        self._cleanup_callbacks = []
        self._loop = None
        self._closed = False
        self.checkpointer = None
        self.store = None
        self._owned_backends = []
        self._model_override = model
        self._mcp_sessions = None
        self._approved_manifest_path = approved_manifest_path
        self._compiled_manifests = {}
        try:
            if development and approved_release is not None:
                raise _error(
                    "An approved release cannot run with development mode enabled.",
                    schema=True,
                )
            self._verify_root(approved_manifest_path)
            _validate_supported_manifest(self.manifest)
            self._require_capability_approval(self.manifest)
            self._loop = asyncio.new_event_loop()
            self._mcp_sessions = _MCPSessions(self._loop)
            runtime = self.manifest.cognitive_runtime
            self._ephemeral = (
                runtime.checkpoint_policy == "DISABLED"
                or runtime.memory_policy == "EPHEMERAL_STREAM"
            )
            if self._ephemeral:
                from langgraph.checkpoint.memory import InMemorySaver
                from langgraph.store.memory import InMemoryStore

                self.checkpointer = InMemorySaver()
                self.store = InMemoryStore()
            else:
                self.checkpointer = checkpointer
                if self.checkpointer is None:
                    self.checkpointer = self._loop.run_until_complete(
                        build_async_checkpointer()
                    )
                    self._owned_backends.append(self.checkpointer)
                self.store = store
                if self.store is None:
                    self.store = self._loop.run_until_complete(build_async_store())
                    self._owned_backends.append(self.store)
            self.agent = self._compile(self.manifest, (), mcp_tools)
        except BaseException:
            self.close()
            raise

    def _verify_root(self, path):
        from aero.infrastructure.parser import ManifestParser

        if self.approved_release is not None:
            from aero.services.releases import load_approved_release

            self.approved_release = load_approved_release(self.approved_release.digest)
            data = self.approved_release.agent_data.get(self.manifest.identity.id)
            if data is None:
                raise _error("Agent is absent from the approved release.")
        elif path is not None:
            from aero.services.trust import require_trusted_manifest

            data = require_trusted_manifest(path, self.manifest.identity.id)
        elif self.development:
            return
        else:
            raise _error(
                "Production execution requires a trusted manifest path or approved release; use explicit development mode for unsigned manifests."
            )
        fresh = ManifestParser().validate_dict(data)
        if fresh != self.manifest:
            raise _error(
                "Manifest changed after approval/resolution; refusing execution."
            )
        self.manifest = fresh

    def _child_manifest(self, provider):
        from aero.infrastructure.parser import ManifestParser

        if self.approved_release is not None:
            data = self.approved_release.agent_data.get(provider.agent_id)
            if data is None:
                raise _error(
                    f"Subagent {provider.agent_id!r} is outside the approved release."
                )
        else:
            path = resolve_agent_manifest_path(provider.agent_id)
            if path is None:
                raise _error(f"Unknown subagent {provider.agent_id!r}.")
            if self.development:
                data = json.loads(path.read_text(encoding="utf-8"))
            else:
                from aero.services.trust import require_trusted_manifest

                data = require_trusted_manifest(str(path), provider.agent_id)
        pin = getattr(provider, "agent_sha256", None)
        if not self.development and not pin:
            raise _error(
                f"Subagent {provider.agent_id!r} requires an immutable agent_sha256 pin."
            )
        if pin and _canonical_digest(data) != pin:
            raise _error(
                f"Subagent {provider.agent_id!r} does not match its agent_sha256 pin."
            )
        return ManifestParser().validate_dict(data)

    def _compile(self, manifest, ancestry, injected_tools=None):
        from deepagents import create_deep_agent
        from deepagents.backends import StateBackend

        identity = manifest.identity.id
        if identity in ancestry:
            raise _error(
                f"Subagent cycle detected: {' -> '.join((*ancestry, identity))}",
                schema=True,
            )
        _validate_supported_manifest(manifest)
        self._require_capability_approval(manifest)
        self._compiled_manifests[identity] = manifest
        credentials = dict(self.credentials)
        if ancestry:
            from aero.infrastructure.vault import ZeroTrustVaultResolver

            needed = [
                p
                for p in manifest.providers
                if p.type == "credential" and p.id not in credentials
            ]
            if needed:
                credentials.update(
                    ZeroTrustVaultResolver().resolve_requirements(
                        needed, non_interactive=True
                    )
                )
        tools = injected_tools
        if tools is None:
            tools = build_mcp_tools(
                manifest,
                credentials,
                development=self.development,
                cleanup_callbacks=self._cleanup_callbacks,
                session_manager=self._mcp_sessions,
            )
        model = (
            self._model_override
            if self._model_override is not None
            else resolve_model(credentials)
        )
        maximum = (
            getattr(manifest.observability, "max_output_tokens", None)
            or DEFAULT_MAX_OUTPUT_TOKENS
        )
        root_maximum = (
            getattr(self.manifest.observability, "max_output_tokens", None)
            or DEFAULT_MAX_OUTPUT_TOKENS
        )
        maximum = min(maximum, root_maximum)
        # Native helper/summarization calls also inherit provider-level output caps.
        fields = getattr(type(model), "model_fields", {})
        if "max_tokens" in fields:
            model = model.model_copy(update={"max_tokens": maximum})
        elif "max_output_tokens" in fields:
            model = model.model_copy(update={"max_output_tokens": maximum})
        kwargs = manifest_to_deepagent_kwargs(
            manifest, credentials, tools=tools, model=model
        )
        if not ancestry:
            self._model_name = (
                getattr(model, "model_name", None)
                or getattr(model, "model", None)
                or getattr(model, "_llm_type", None)
            )
        subagents = []
        for provider in manifest.providers:
            if provider.type == "sub_agent":
                child = self._child_manifest(provider)
                description = (
                    provider.delegation_purpose or child.capabilities.short_description
                )
                if child.capabilities.input_contract is not None:
                    description += "\nPass the task as JSON matching: " + json.dumps(
                        child.capabilities.input_contract
                    )
                subagents.append(
                    {
                        "name": child.identity.id,
                        "description": description,
                        "runnable": self._child_runnable(
                            child, self._compile(child, (*ancestry, identity))
                        ),
                    }
                )
        if subagents:
            kwargs["subagents"] = subagents
        kwargs["middleware"] = [OutputTokenLimitMiddleware(maximum)]
        # Native filesystem tools are virtual; host access exists only through
        # explicitly declared MCP providers and their separate isolation boundary.
        return create_deep_agent(
            **kwargs,
            backend=StateBackend(),
            checkpointer=self.checkpointer if not ancestry else False,
            store=self.store,
        )

    def _require_capability_approval(self, manifest):
        if (
            not self.development
            and self.approved_release is None
            and any(p.type in {"mcp", "credential"} for p in manifest.providers)
        ):
            raise AeroMeshDomainError(
                "Tool and credential capabilities require an approved release and operator policy.",
                ErrorCode.AMX_ERR_POLICY_VIOLATION,
                ExitCode.POLICY_VIOLATION,
            )

    def _child_runnable(self, manifest, graph):
        from langchain_core.runnables import RunnableLambda
        from langchain_core.runnables.config import merge_configs

        async def invoke(state, config):
            messages = state.get("messages") or []
            message = messages[-1] if messages else None
            value = (
                message.get("content", "")
                if isinstance(message, dict)
                else getattr(message, "content", "")
            )
            _validate_input(manifest, value)
            scoped = TokenUsageCounter(manifest.observability)
            result = await graph.ainvoke(
                state, config=merge_configs(config, {"callbacks": [scoped]})
            )
            _validate_output(manifest, result)
            return result

        return RunnableLambda(invoke)

    def _revalidate_execution(self):
        self._verify_root(self._approved_manifest_path)
        seen = set()

        def visit(manifest):
            if manifest.identity.id in seen:
                return
            seen.add(manifest.identity.id)
            for provider in manifest.providers:
                if provider.type == "sub_agent":
                    child = self._child_manifest(provider)
                    if child != self._compiled_manifests.get(child.identity.id):
                        raise _error(
                            "Subagent changed after compilation; refusing execution."
                        )
                    visit(child)

        visit(self.manifest)

    def execute(self, user_intent, thread_id=None):
        if self._closed:
            raise _error("Execution driver is closed.")
        try:
            self._revalidate_execution()
            payload = _validate_input(self.manifest, user_intent)
            if self._ephemeral:
                thread_id = f"ephemeral-{uuid.uuid4().hex}"
            else:
                thread_id = (
                    thread_id
                    or f"session-{self.manifest.identity.id}-{uuid.uuid4().hex}"
                )
            counter = TokenUsageCounter(self.manifest.observability)
            config = {
                "configurable": {"thread_id": thread_id},
                "recursion_limit": getattr(
                    self.manifest.observability, "max_execution_steps", None
                )
                or DEFAULT_MAX_STEPS,
                "max_concurrency": 4,
                "callbacks": [counter],
            }
            text = payload if isinstance(payload, str) else json.dumps(payload)
            try:
                timeout = float(
                    os.environ.get(
                        "AEROMESH_EXECUTION_TIMEOUT_SECONDS",
                        DEFAULT_EXECUTION_TIMEOUT_SECONDS,
                    )
                )
                if not 0 < timeout <= 3600:
                    raise ValueError("out of range")
            except ValueError as exc:
                raise _error(
                    "AEROMESH_EXECUTION_TIMEOUT_SECONDS must be positive and at most 3600.",
                    schema=True,
                ) from exc
            try:
                result = self._loop.run_until_complete(
                    asyncio.wait_for(
                        self.agent.ainvoke(
                            {"messages": [{"role": "user", "content": text}]},
                            config=config,
                        ),
                        timeout=timeout,
                    )
                )
            except TimeoutError as exc:
                raise _error(
                    f"Agent execution exceeded its {timeout:g}-second deadline."
                ) from exc
            final_text, structured, output_valid = _validate_output(
                self.manifest, result
            )
            return {
                "agent_id": self.manifest.identity.id,
                "thread_id": thread_id,
                "result": final_text,
                "verified_result": final_text,
                "structured_output": structured,
                "execution_completed": True,
                "execution_success": True,
                "output_valid": output_valid,
                "task_assessment": "unverified",
                "success_criteria_met": None,
                "usage": counter.report(),
                "model": self._model_name,
                "persistence": "ephemeral" if self._ephemeral else "checkpointed",
            }
        except BaseException:
            self.close()
            raise

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._loop is not None and not self._loop.is_closed():

            async def shutdown():
                if self._mcp_sessions is not None:
                    await self._mcp_sessions.close()
                tasks = [
                    t for t in asyncio.all_tasks() if t is not asyncio.current_task()
                ]
                for task in tasks:
                    task.cancel()
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                connections = [
                    getattr(b, "conn", None) for b in reversed(self._owned_backends)
                ]
                await asyncio.gather(
                    *(conn.close() for conn in connections if conn is not None),
                    return_exceptions=True,
                )

            try:
                self._loop.run_until_complete(shutdown())
            except Exception:
                pass
            finally:
                self._loop.close()
        for cleanup in reversed(self._cleanup_callbacks):
            try:
                cleanup()
            except Exception:
                pass
        self._cleanup_callbacks.clear()
