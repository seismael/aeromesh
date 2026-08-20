# System Architecture: AeroMesh (v0.1)

**Status:** v0.1 — matches the implemented code.

## 1. Overview

AeroMesh is a layered Python engine under `packages/aero/src/aero/`:

```
presentation/   CLI (amx) + Rich terminal UI
    │
services/       orchestrator, pipeline, workflow, discovery, synthesizer (JIT), preflight, trust
    │
infrastructure/ parser, attestation (Ed25519), keystore, providers, MCP drivers, sandbox, diagnostics, LangGraph driver
    │
domain/         dataclass models, error taxonomy (AMX_ERR_*), OS-agnostic paths
```

Dependency direction: `presentation → services → infrastructure → domain`. The `domain` layer has zero vendor dependencies.

## 2. Execution flow (`amx run`)

1. **Parse** — validate the manifest against the DAM v0.1 schema, hydrate into dataclasses.
2. **Preflight** — ensure a provider and required credentials are available (offline fallback if none).
3. **Resolve credentials** — via the vault resolver (env/config/credential-file, with explicit approval in interactive sessions).
4. **Execute** — the LangGraph driver runs plan → execute → verify:
   - **execute** invokes the manifest's declared MCP tools (`required_tools`) over stdio/SSE, then feeds the tool results back into the LLM prompt;
   - **verify** marks success based on non-empty output (non-vacuous).
5. **Checkpoint** — save a session checkpoint for replay.

## 3. JIT synthesis flow

For an unbounded natural-language goal:

1. `AeroGoalDecompositionEngine` decomposes the goal and matches known registry agents by keyword.
2. Unhandled clauses are synthesized by `JitSynthesizer`: the LLM emits a JSON manifest, which is schema-validated with retry-on-error feedback.
3. Without a live provider key, a deterministic template manifest is used instead.

## 4. Trust flow

1. Authors: `amx keygen` (Ed25519) → `amx sign` (`.sig` sidecar) → commit public key to `registry/trusted/`.
2. Consumers: `amx install` verifies the signature **and** that it matches the trusted key for that agent id.

## 5. Concurrency

`AeroWorkflowEngine` executes workflow DAGs with `asyncio` + a `ThreadPoolExecutor`. Dependent steps await their prerequisites; failures propagate to dependents (no deadlocks); the pool is shut down on close.

## 6. What is intentionally NOT here

LangGraph is an **internal driver only**. There is no event bus, no "cognitive virtual memory", no multi-language SDK suite beyond `sdk-python`, and no hosted marketplace — these were aspirational and are tracked in the roadmap, not claimed as shipped.
