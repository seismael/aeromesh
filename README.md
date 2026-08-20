# AeroMesh — Declarative, Signed, Sandboxed Agents on Deep Agents

AeroMesh is a **declarative agent standard + a thin trust layer built on LangChain Deep Agents**. It does **not** implement an agent runtime — Deep Agents already does that (planning, subagents, skills, filesystem, HITL, memory). AeroMesh adds the four things Deep Agents does not give you:

1. **A declarative standard (DAM v0.1)** — describe an agent as a portable JSON manifest, not code or a fat prompt.
2. **LLM-driven synthesis** — turn a natural-language goal into a schema-valid manifest with a live model.
3. **A trusted marketplace** — Ed25519-signed manifests; `amx install` verifies the signer before running.
4. **A sandbox** — deny-by-default `allowed_domains` + an egress proxy around MCP tool subprocesses.

A DAM manifest **compiles into `create_deep_agent()`**, so you get Deep Agents' full runtime, plus AeroMesh's declaration/trust/sandbox on top.

---

## Why AeroMesh — the value on top of Deep Agents

Deep Agents gives you a *framework*. AeroMesh gives you a *format and a trust boundary*:

| Need | What AeroMesh adds |
|---|---|
| **Portability** | One manifest runs on DeepSeek / Anthropic / OpenAI / Gemini (native `init_chat_model`). |
| **No code** | Agents are declared as JSON; an LLM can author them (`amx run "<goal>"`). |
| **Distribution** | Git-as-registry: publish a manifest + public key, others `amx install` it. |
| **Trust** | "Download an agent and prove who signed it and that it wasn't tampered with." |
| **Safety** | An agent's `allowed_domains` is enforced on its MCP tool subprocesses. |

### Use cases

- **Enterprise agent governance** — a team maintains a signed registry of approved agents; engineers `amx install` and run them, knowing they are verified and sandboxed.
- **Portable, vendor-neutral agents** — the same manifest runs across model providers without code changes.
- **On-demand agent authoring** — "build me an agent that monitors server uptime" → a signed, runnable manifest in seconds.
- **Safe third-party agents** — fetch an agent, verify its signer, and run it with restricted egress ("npm for AI agents, with security").

---

## What works today (v0.1)

- **DAM v0.1 schema** — `jsonschema`-validated, machine-readable error codes (`AMX_ERR_*`).
- **Ed25519 attestation** — `amx keygen` / `sign` / `verify` (`.sig` sidecars).
- **Trusted install gating** — `amx install` verifies against `registry/trusted/<id>.pub`; refuses mismatches (`--insecure` opts out).
- **Real LLM** — native `init_chat_model` (DeepSeek/Anthropic/OpenAI/Gemini); no mocks, no canned output.
- **LLM-driven JIT synthesis** — `amx run "<natural-language goal>"` synthesizes a schema-valid manifest with a live model.
- **Real tool execution** — a manifest's `mcp` providers become real LangChain tools (`langchain-mcp-adapters`) and are passed to `create_deep_agent`.
- **`sub_agent` + `skill` providers** — mapped to Deep Agents subagents/skills.
- **Encrypted credentials** — OS-keyring-backed storage (`amx vault set`).
- **Sandbox** — deny-by-default network policy + egress proxy enforcing `allowed_domains`.
- **Output verification** — a manifest's `output_contract` (JSON Schema) is enforced via Deep Agents `RubricMiddleware`.

> **Honesty note:** a live provider key is required for real model calls; a running MCP server is required for real tool execution. There are **no fakes or mocks in production code** — test doubles exist only in `tests/`.

---

## Repository layout

```
aeromesh/
├── .agents/                Governance layer (AGENTS.md)
├── docs/                   Specifications (PRD, architecture, standard, security)
├── schemas/                DAM v0.1 JSON Schema
├── packages/
│   ├── aero/               The standard + CLI (amx) + trust/sandbox
│   └── sdk-python/         Embeddable Python SDK (aeromesh-sdk)
└── registry/
    ├── agents/             Agent manifests
    └── trusted/            Public keys for install verification
```

---

## Install & test

```bash
pip install -e packages/aero
pytest packages/aero/tests
```

---

## Quickstart (`amx`)

```bash
# Scaffold + validate a manifest
amx init my-custom-agent
amx validate registry/agents/postgres-performance-tuner.json

# Sign / verify (trust)
amx keygen
amx sign registry/agents/postgres-performance-tuner.json
amx verify registry/agents/postgres-performance-tuner.json

# Run a single agent
$env:DB_CONNECT_STRING="postgresql://localhost:5432/db"
amx run registry/agents/postgres-performance-tuner.json "Optimize slow join query"

# Run an unbounded natural-language goal (JIT synthesis with a live model)
amx run "Build an agent that monitors server uptime and alerts on downtime"
```

---

## The trust model

1. Authors `amx keygen` + `amx sign`, committing the manifest + `.sig` and public key to `registry/trusted/`.
2. Consumers `amx install`; the engine verifies the Ed25519 signature **and** the trusted signer.
3. At runtime, the agent's `allowed_domains` restricts its MCP tool egress via the proxy.

Self-contained, offline-capable — no external CA or transparency log required for v0.1.

---

## Architecture

`packages/aero/src/aero/`:

- `domain/` — models, error taxonomy, paths.
- `infrastructure/` — parser, Ed25519 attestation, key store, credential store, sandbox firewall, egress proxy.
- `services/` — Deep Agents runner (DAM → `create_deep_agent`), orchestrator, JIT synthesizer, discovery, trust.
- `presentation/` — CLI (`amx`) + Rich UI.

**Agent execution is delegated to Deep Agents.** AeroMesh is the declarative + trust + sandbox layer, not an agent runtime.

---

## Roadmap (not yet implemented)

- Hosted registry (today git-as-registry).
- Sigstore/cosign transparency-log attestation (today self-contained Ed25519).

## License

Apache License 2.0 — see [`LICENSE`](LICENSE).
