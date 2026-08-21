# AeroMesh — Declarative, Signed, Sandboxed Agents on Deep Agents

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](packages/aero)
[![Built on Deep Agents](https://img.shields.io/badge/built_on-Deep_Agents-black.svg)](https://github.com/langchain-ai/deepagents)

> **"npm for AI agents, with security"** — a declarative agent standard + a trust/sandbox layer on top of LangChain Deep Agents.

AeroMesh is a **declarative agent standard + a thin trust layer built on LangChain Deep Agents**. It does **not** implement an agent runtime, model-provider layer, or MCP transport — Deep Agents / LangChain already do all of that (models via `init_chat_model`, MCP tools via `langchain-mcp-adapters`, plus planning, subagents, skills, filesystem, HITL, memory). AeroMesh adds the five things Deep Agents does **not** give you:

1. **A declarative standard (DAM v0.1)** — describe an agent as a portable JSON manifest, not code or a fat prompt.
2. **LLM-driven synthesis** — turn a natural-language goal into a schema-valid manifest with a live model.
3. **A trusted marketplace** — Ed25519-signed manifests; `amx install` verifies the signer before running.
4. **Composable workflows (DWM v0.1)** — sign and run multi-agent DAGs built from already-verified agents, with recursive trust.
5. **A sandbox** — deny-by-default `allowed_domains` + an egress proxy around MCP tool subprocesses.

A DAM manifest **compiles into `create_deep_agent()`**, so you get Deep Agents' full runtime, plus AeroMesh's declaration/trust/sandbox on top.

---

## How it's used — three experiences

**1. Author an agent** — sign & ship:

```bash
amx init my-code-reviewer        # scaffold a manifest (JSON, not code)
# edit my-code-reviewer.agent.json
amx keygen                       # create your signing identity (encrypted)
amx sign my-code-reviewer.json   # sign it
amx share my-code-reviewer.json  # signed payload for the registry
```

**2. Consume an agent** — verify & run:

```bash
amx install postgres-performance-tuner     # verifies signature + trusted signer
amx run postgres-performance-tuner "Optimize my slow query"
```

**3. Zero-code** — let the LLM author it:

```bash
amx run "build me an agent that reviews code for security vulnerabilities"
```

The full end-to-end walkthrough (what happens under the hood at each step, and
why) → [`docs/15_USER_EXPERIENCE_AND_WORKFLOWS.md`](docs/15_USER_EXPERIENCE_AND_WORKFLOWS.md).

---

## Why AeroMesh — the value on top of Deep Agents

Deep Agents gives you a *framework*. AeroMesh gives you a *format and a trust boundary*:

| Need | What AeroMesh adds |
|---|---|
| **Provider-agnostic manifest** | The manifest never hardcodes a provider — the model is resolved from your environment at run time (a Deep Agents capability; AeroMesh keeps it out of the manifest). |
| **No code** | Agents are declared as JSON; an LLM can author them (`amx run "<goal>"`). |
| **Distribution** | Git-as-registry: publish a manifest + public key, others `amx install` it. |
| **Trust** | "Download an agent and prove who signed it and that it wasn't tampered with." |
| **Safety** | An agent's `allowed_domains` is enforced on its MCP tool subprocesses. |

### Use cases

- **Enterprise agent governance** — a team maintains a signed registry of approved agents; engineers `amx install` and run them, knowing they are verified and sandboxed.
- **Provider-agnostic agents** — the same manifest runs unchanged across any model provider Deep Agents supports.
- **On-demand agent authoring** — "build me an agent that monitors server uptime" → a signed, runnable manifest in seconds.
- **Safe third-party agents** — fetch an agent, verify its signer, and run it with restricted egress.

**Who it's for:** platform/DevEx teams, security teams, agent builders, and enterprises that want agents treated as signed, auditable, sandboxed artifacts.

---

## Differentiation — why not just MCP or Deep Agents?

AeroMesh is **not a competitor** to MCP or Deep Agents — it's the missing layer on top of both:

| Capability | MCP | Deep Agents | AeroMesh |
|---|---|---|---|
| Tool protocol | ✅ | — | consumes MCP |
| Agent runtime | — | ✅ | delegates to it |
| **Declarative agent format (DAM)** | ❌ | ❌ | ✅ |
| **Signed distribution + verification** | ❌ | ❌ | ✅ |
| **Sandboxed execution of third-party agents** | ❌ | ❌ | ✅ |
| **LLM-authored agents (JIT)** | ❌ | ❌ | ✅ |

Full pitch → [`docs/14_ADOPTION_AND_VALUE_PROPOSITION.md`](docs/14_ADOPTION_AND_VALUE_PROPOSITION.md).

---

## What works today

- **DAM v0.1 schema** — `jsonschema`-validated, machine-readable error codes (`AMX_ERR_*`).
- **Ed25519 attestation** — `amx keygen` / `sign` / `verify` (`.sig` sidecars).
- **Trusted install gating** — `amx install` verifies against `registry/trusted/<id>.pub`; refuses mismatches (`--insecure` opts out).
- **Real LLM** — native `init_chat_model` (DeepSeek/Anthropic/OpenAI/Gemini); no mocks, no canned output.
- **LLM-driven JIT synthesis** — `amx run "<natural-language goal>"` synthesizes a schema-valid manifest with a live model.
- **Real tool execution** — a manifest's `mcp` providers become real LangChain tools (`langchain-mcp-adapters`) and are passed to `create_deep_agent`.
- **`sub_agent` + `skill` providers** — mapped to Deep Agents subagents/skills.
- **Encrypted credentials** — OS-keyring-backed storage (`amx vault set`).
- **Sandbox** — deny-by-default `allowed_domains` enforced via an HTTP(S) egress proxy on MCP tool subprocesses (**egress allowlisting, not full OS process isolation**).
- **Output verification** — a manifest's `output_contract` (JSON Schema) is enforced via Deep Agents `RubricMiddleware`.
- **Workflows (DWM v0.1)** — a signed DAG of verified agents compiled into a LangGraph `StateGraph` (`amx workflow ...`); `install` enforces recursive trust (the workflow **and** every referenced agent).

> **Honesty note:** a live provider key is required for real model calls; a running MCP server is required for real tool execution. There are **no fakes or mocks in production code** — test doubles exist only in `tests/`.

---

## Repository layout

```
aeromesh/
├── .agents/                Governance layer (AGENTS.md)
├── docs/                   Specifications (PRD, architecture, standard, security)
├── schemas/                DAM + DWM JSON Schemas
├── packages/
│   ├── aero/               Standard + CLI (amx) + trust/sandbox (tests/, tests_live/)
│   └── sdk-python/         Embeddable Python SDK (aeromesh-sdk)
├── scripts/                seed_registry.py (sign + publish trusted keys)
└── registry/
    ├── agents/             Agent manifests (+ .sig sidecars)
    ├── workflows/          Workflow manifests (+ .sig sidecars)
    ├── trusted/            Public keys for install verification
    ├── revoked/            Revoked-key markers
    └── index.json          Searchable agent catalog
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

# Compose a workflow of verified agents (sign, install, run)
amx workflow sign my-pipeline.workflow.json
amx workflow install my-pipeline.workflow.json
amx workflow run my-pipeline.workflow.json "Run the audit, then tune the DB"

# Or let the LLM author the workflow from a goal (JIT synthesis)
amx workflow run "Build a workflow that audits my repo then tunes the flagged queries"
```

---

## The trust model

1. Authors `amx keygen` + `amx sign`, committing the manifest + `.sig` and public key to `registry/trusted/`.
2. Consumers `amx install`; the engine verifies the Ed25519 signature **and** the trusted signer.
3. Workflows (`amx workflow install`) apply the same check to the workflow **and** to every agent it references (recursive trust).
4. At runtime, the agent's `allowed_domains` restricts its MCP tools' **HTTP(S)** egress via the proxy (egress allowlisting — see `SECURITY.md` for the honest isolation boundary).

Self-contained, offline-capable — no external CA or transparency log required.

---

## Architecture

`packages/aero/src/aero/`:

- `domain/` — models, error taxonomy, paths.
- `infrastructure/` — parser, Ed25519 attestation, key store, credential store, sandbox firewall, egress proxy.
- `services/` — Deep Agents runner (DAM → `create_deep_agent`), orchestrator, JIT synthesizer, discovery, trust.
- `presentation/` — CLI (`amx`) + Rich UI.

**Agent execution is delegated to Deep Agents.** AeroMesh is the declarative + trust + sandbox layer, not an agent runtime.

---

## Roadmap & deferred items

The authoritative shipped-vs-deferred list (with *why* and *how to do it later*)
is in [`docs/16_ROADMAP_AND_DEFERRED.md`](docs/16_ROADMAP_AND_DEFERRED.md). In brief, the deferred items are:

- **Full OS-level sandbox** (container/gVisor/Firecracker) — today HTTP(S) egress allowlisting only.
- **Sigstore transparency-log attestation** — today self-contained Ed25519.
- **Hosted marketplace web hub** — today git-as-registry (`registry/index.json` + `registry/agents/`).
- **Semantic/embedding search** — today real BM25 lexical search.
- **Multi-language SDKs + a real VS Code extension** — today a thin Python SDK + stub extension.

## Versioning

AeroMesh versions **two axes separately**:

| Axis | What it versions | Current |
|---|---|---|
| **Software** (`amx`, `aero`, `sdk-python`) | the tool itself (semver) | `0.1.0` |
| **DAM standard** (`manifest_version`) | the agent manifest format | `0.1.0` |
| **DWM standard** (`workflow_version`) | the workflow manifest format | `0.1.0` |

A manifest declares which standard it targets; the tool reports both — `amx version`
→ `aero 0.1.0 (DAM v0.1 · DWM v0.1)`. The software and the standards evolve
independently: a future `amx` can support DAM `v0.1` and `v0.2` at once. (An early
`1.0.0` was retracted in favor of `0.1.0` to reflect actual maturity.)

## License

Apache License 2.0 — see [`LICENSE`](LICENSE).
