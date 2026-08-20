# AGENTS.md: AeroMesh Repository Governance

**Applies to:** all AI agents and engineers working on AeroMesh.

---

## 1. What this project is

AeroMesh is a **declarative agent standard (DAM v0.1) + a trust/sandbox layer built on LangChain Deep Agents**. The product pillars are:

1. **Portable agent manifests** — describe an agent as schema-validated JSON, not code.
2. **LLM-driven JIT synthesis** — synthesize an agent manifest for any natural-language goal.
3. **Trusted marketplace** — Ed25519-signed manifests, verified on install against `registry/trusted/`.
4. **Sandbox** — deny-by-default `allowed_domains` + egress proxy on MCP tool subprocesses.

**Agent execution is delegated to Deep Agents (`create_deep_agent`).** AeroMesh does not implement its own agent runtime, LLM providers, or MCP transport — those come from Deep Agents / LangChain / `langchain-mcp-adapters`.

## 2. Non-negotiables

- **Correct architecture.** The DAM manifest compiles into `create_deep_agent()` (`services/deepagents_runner.py`). Do not reintroduce a hand-rolled engine.
- **No fakes/mocks in production.** Fakes and mocks live **only in `tests/`** (see `tests/conftest.py`). Production code is always real: `resolve_model` uses native `init_chat_model`; MCP tools use `langchain-mcp-adapters`.
- **Honest claims.** Docs and code describe what actually works. No "Sigstore" (self-contained Ed25519), no "OpenAgent Standard v3.0" (DAM v0.1), no fictional packages.
- **TDD.** Failing test first → minimal code → green.
- **Verify before claiming done.** Run `pytest packages/aero/tests` and confirm green.
- **Keep docs in sync.** A behavior change must update `README.md`/`docs/` in the same change.

## 3. Repository layout

```
aeromesh/
├── .agents/                Governance layer (this file)
├── docs/                   Specifications (PRD, architecture, standard, security)
├── schemas/                DAM v0.1 JSON Schema
├── packages/
│   ├── aero/               Standard + CLI (amx) + trust/sandbox — layered src/aero/{domain,services,presentation,infrastructure}
│   └── sdk-python/         Embeddable Python SDK
└── registry/
    ├── agents/             Agent manifests
    └── trusted/            Public keys for install verification
```

## 4. Code standards

- **Layered architecture** under `packages/aero/src/aero/`:
  - `domain/` — models, error taxonomy (`AMX_ERR_*`), paths. Zero vendor deps.
  - `infrastructure/` — parser, Ed25519 attestation, key store, credential store, sandbox firewall, egress proxy.
  - `services/` — Deep Agents runner, orchestrator, JIT synthesizer, discovery, trust.
  - `presentation/` — CLI (`amx`) + terminal UI.
- **One responsibility per module.** The runner compiles + executes; the trust service signs/verifies; the synthesizer authors manifests.
- **OS-agnostic paths** via `aero.domain.paths.get_aeromesh_home()` (respects `AEROMESH_HOME`).

## 5. Security rules

- **No plaintext secrets in manifests or commits.** The static scanner and tests must catch `sk_live_` / `ghp_` / `AKIA`.
- **Install trust gate.** `amx install` verifies signatures against `registry/trusted/`; do not weaken it.
- **Sandbox enforcement.** `allowed_domains` must be enforced on MCP tool egress via the proxy.

## 6. Communication

- Be brief and high-signal.
- Cite exact file paths.
- Never claim completion without running the verification command.
