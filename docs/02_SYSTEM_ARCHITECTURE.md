# System Architecture: AeroMesh (v0.1)

**Status:** v0.1 — matches the implemented code (built on LangChain Deep Agents).

## 1. Overview

AeroMesh is a **declarative, signed, sandboxed standard that compiles into Deep Agents**. It does not implement an agent runtime.

```
DAM v0.1 manifest ──▶ services/deepagents_runner.py ──▶ create_deep_agent()
                        │                                ├─ planning (TodoList)
                        │                                ├─ subagents (sub_agent providers)
                        │                                ├─ skills (skill providers)
                        │                                ├─ MCP tools (mcp providers)
                        │                                └─ filesystem / memory / HITL
                        │
   (AeroMesh adds on top)  Ed25519 sign/verify · JIT synthesis · marketplace · sandbox/egress
```

## 2. Layered code (`packages/aero/src/aero/`)

```
presentation/    CLI (amx) + Rich terminal UI
    │
services/        deepagents_runner (DAM → create_deep_agent), orchestrator,
                 JIT synthesizer, discovery, trust
    │
infrastructure/  parser, Ed25519 attestation, key store, credential store,
                 sandbox firewall, egress proxy
    │
domain/          models, error taxonomy (AMX_ERR_*), OS-agnostic paths
```

Dependency direction: `presentation → services → infrastructure → domain`. The `domain` layer has zero vendor dependencies.

## 3. Execution flow (`amx run`)

1. **Parse** — validate the manifest against the DAM v0.1 schema.
2. **Resolve credentials** — via the vault (env / OS keyring / config, with explicit approval in interactive sessions).
3. **Compile** — `deepagents_runner.manifest_to_deepagent_kwargs()` maps the manifest to `create_deep_agent()`:
   - `identity.name` → `name`; `cognitive_runtime.persona` → `system_prompt`.
   - `cognitive_runtime.driver`/env → `model` (native `init_chat_model`).
   - `mcp` providers → LangChain tools (`langchain-mcp-adapters`).
   - `sub_agent` providers → Deep Agents subagents; `skill` providers → skills.
4. **Execute** — Deep Agents runs the agent (planning, tools, subagents, HITL).
5. **Checkpoint** — save a session checkpoint.

## 4. JIT synthesis flow

For a natural-language goal, `JitSynthesizer` prompts a live model to emit a DAM v0.1 manifest, then schema-validates it with retry-on-error feedback. There is no synthetic fallback — without a provider key, synthesis raises a clear error.

## 5. Trust flow

1. Authors: `amx keygen` (Ed25519) → `amx sign` (`.sig` sidecar) → commit public key to `registry/trusted/`.
2. Consumers: `amx install` verifies the signature **and** the trusted signer.

## 6. Sandbox

`allowed_domains` is deny-by-default. A local egress proxy is injected into MCP tool subprocesses (`HTTP_PROXY`/`HTTPS_PROXY`) so their outbound HTTP(S) is gated by the allowlist.

## 7. What is intentionally NOT here

AeroMesh is **not** an agent runtime, LLM provider layer, or MCP transport — those come from Deep Agents / LangChain / `langchain-mcp-adapters`. There is no hand-rolled engine, no "cognitive virtual memory", no multi-language SDK suite beyond `sdk-python`, and no hosted marketplace.
