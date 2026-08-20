# AeroMesh — Declarative Agents, Synthesized on Demand, Signed & Sandboxed

AeroMesh is a **declarative agent standard + a thin runtime** that solves three real problems:

1. **Don't rebuild agents every time** — describe an agent once as a portable JSON manifest (**DAM v0.1**), not as bespoke code or a fat prompt.
2. **Let the LLM build agents on the fly** — for a goal no existing agent covers, AeroMesh synthesizes a schema-valid manifest from a live model (with a deterministic offline fallback).
3. **Trust agents you didn't write** — manifests are **Ed25519-signed**, and `amx install` refuses unverified marketplace agents; the runtime enforces each agent's `allowed_domains` sandbox.

The engine (`amx`) validates, signs, verifies, sandboxes, and executes these manifests — individually, in pipelines, or as workflow DAGs.

---

## What actually works today (v0.1)

- **DAM v0.1 manifest schema** — `jsonschema`-validated, with machine-readable error codes (`AMX_ERR_*`).
- **Ed25519 attestation** — `amx keygen` / `amx sign` / `amx verify`, with `<manifest>.sig` sidecars.
- **Trusted install gating** — `amx install` verifies a marketplace agent's signature against `registry/trusted/<id>.pub` and refuses mismatches (`--insecure` opts out).
- **LLM-driven JIT synthesis** — `amx run "<natural-language goal>"` decomposes the goal, reuses registry agents where they match, and synthesizes a schema-valid manifest for the rest when a live provider key is present (template fallback offline).
- **Network sandbox** — a manifest's `allowed_domains` is enforced for remote (SSE) MCP tool endpoints.
- **Workflows (DWM)** — DAG execution with cycle detection, dependency-aware async concurrency, and crontab scheduling.
- **Multi-provider LLM binding** — DeepSeek, Anthropic, OpenAI, Gemini (real API calls when a real key is set; mock only for clearly-marked test keys).

> **Honesty note:** `amx run` requires a live provider API key to actually call a model. Without one, execution falls back to a clearly-marked offline stub. The mock-first behavior of earlier versions is gone.

---

## Repository layout

```
aeromesh/
├── .agents/                Governance layer (AGENTS.md)
├── docs/                   Design specs, PRD, architecture
├── schemas/                DAM v0.1 & DWM v1.0 JSON Schemas
├── packages/
│   ├── aero/               The engine + CLI (amx)
│   └── sdk-python/         Embeddable Python SDK (aeromesh-sdk)
└── registry/
    ├── agents/             Signed agent manifests
    ├── workflows/          Declarative workflow DAGs
    └── trusted/            Public keys for install verification
```

---

## Install

```bash
pip install -e packages/aero
```

## Test

```bash
pytest packages/aero/tests
```

---

## Quickstart (`amx`)

```bash
# Scaffold a new manifest
amx init my-custom-agent

# Validate against the DAM v0.1 schema
amx validate registry/agents/postgres-performance-tuner.json

# Generate a signing key, sign, and verify
amx keygen
amx sign registry/agents/postgres-performance-tuner.json
amx verify registry/agents/postgres-performance-tuner.json

# Run a single agent (set the required credential first)
$env:DB_CONNECT_STRING="postgresql://localhost:5432/db"
amx run registry/agents/postgres-performance-tuner.json "Optimize slow join query"

# Run an unbounded natural-language goal (JIT synthesis)
amx run "Analyze slow Postgres queries AND generate a security audit report"

# Run a pipeline / workflow
amx pipeline registry/agents/postgres-performance-tuner.json registry/agents/enterprise-security-auditor.json --intent "Tune DB and audit secrets"
amx workflow run registry/workflows/enterprise-cloud-migration-and-compliance-swarm.json
```

---

## The trust model

1. Authors run `amx keygen` and `amx sign`, committing the manifest + `.sig` and their public key to `registry/trusted/`.
2. Consumers run `amx install`; the engine verifies the manifest's Ed25519 signature **and** that it was produced by the trusted key for that agent id.
3. At runtime, the agent's `allowed_domains` restrict its remote tool endpoints.

This is a self-contained, offline-capable trust model (no external CA or transparency log required for v0.1).

---

## Architecture (honest summary)

`packages/aero/src/aero/` is a layered codebase:

- `domain/` — dataclass models, error taxonomy, path resolution.
- `infrastructure/` — schema parser, Ed25519 attestation, key store, provider adapter, MCP drivers, sandbox firewall, diagnostics, LangGraph driver.
- `services/` — orchestrator, pipeline, workflow engine, discovery, JIT synthesizer, preflight, trust.
- `presentation/` — CLI (`amx`) and Rich terminal UI.

LangGraph is used as an **internal execution driver only** — it is not the product and not a headline feature.

---

## Roadmap (not yet implemented)

- HTTP marketplace registry (today it's git-as-registry).
- Sigstore/cosign transparency-log attestation (today it's self-contained Ed25519).
- OS-keyring-backed secret storage (today credentials are stored locally in plaintext under `~/.aeromesh/`).
- Real per-tool process isolation / a true egress proxy (today the firewall gates remote MCP endpoints, not arbitrary subprocess network).

See `docs/` for detailed specifications.

## License

Apache License 2.0 — see [`LICENSE`](LICENSE).
