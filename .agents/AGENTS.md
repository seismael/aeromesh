# AGENTS.md: AeroMesh Repository Governance

**Applies to:** all AI agents and engineers working on AeroMesh.

---

## 1. What this project is

AeroMesh is a **declarative agent standard (DAM v0.1) + a thin runtime**. The product pillars are:

1. **Portable agent manifests** — describe an agent as schema-validated JSON, not bespoke code.
2. **LLM-driven JIT synthesis** — synthesize an agent manifest for any natural-language goal.
3. **Trusted marketplace** — Ed25519-signed manifests, verified on install against `registry/trusted/`.

LangGraph is an **internal execution driver only** — not a headline feature. Keep it that way.

## 2. Non-negotiables

- **Honest claims.** Docs and code must describe what actually works. No "Sigstore" (we use self-contained Ed25519), no "OpenAgent Standard v3.0" (we are DAM v0.1), no fictional packages or abstractions.
- **TDD.** Write the failing test first, watch it fail, implement the minimum, watch it pass.
- **Verify before claiming done.** Run `pytest packages/aero/tests` and confirm green before any completion claim.
- **Keep docs in sync.** A code change that changes behavior must update the corresponding `docs/` and `README.md` in the same change.

## 3. Repository layout

```
aeromesh/
├── .agents/                Governance layer (this file)
├── docs/                   Specifications (PRD, architecture, standard, security)
├── schemas/                DAM v0.1 & DWM JSON Schemas (single source of truth)
├── packages/
│   ├── aero/               Engine + CLI (amx) — layered src/aero/{domain,services,presentation,infrastructure}
│   └── sdk-python/         Embeddable Python SDK
└── registry/
    ├── agents/             Agent manifests
    ├── workflows/          Workflow DAGs
    └── trusted/            Public keys for install verification
```

## 4. Code standards

- **Layered architecture** under `packages/aero/src/aero/`:
  - `domain/` — dataclass models, error taxonomy (`AMX_ERR_*`), paths. Zero vendor deps.
  - `infrastructure/` — parser, attestation (Ed25519), keystore, providers, MCP drivers, sandbox, diagnostics, LangGraph driver.
  - `services/` — orchestrator, pipeline, workflow, discovery, synthesizer (JIT), preflight, trust.
  - `presentation/` — CLI (`amx`) and terminal UI.
- **One responsibility per module.** Parsers parse; vaults resolve secrets; drivers execute; the trust service signs/verifies.
- **OS-agnostic paths** via `aero.domain.paths.get_aeromesh_home()` (respects `AEROMESH_HOME`).

## 5. Security rules

- **No plaintext secrets in manifests or commits.** The static scanner and tests must catch `sk_live_` / `ghp_` / `AKIA`.
- **Install trust gate.** `amx install` verifies signatures against `registry/trusted/`; do not weaken it without a documented reason.
- **Sandbox enforcement.** `allowed_domains` must be enforced on remote (SSE) MCP endpoints.

## 6. Communication

- Be brief and high-signal.
- Cite exact file paths.
- Never claim a task is complete without running the verification command.
