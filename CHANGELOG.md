# Changelog

All notable changes to AeroMesh are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

> **Versioning note:** AeroMesh versions the **software** (this changelog) and the
> **DAM/DWM standards** separately. The standards are `v0.1`. The software was
> briefly released as `1.0.0` and then **retracted to `0.1.0`** to honestly reflect
> the project's maturity (egress-only sandbox, self-contained attestation, no
> hosted registry). See the README "Versioning" section.

## [0.1.0] — 2026-08-20

### Architecture
- Compile **DAM v0.1** manifests into **LangChain Deep Agents** (`create_deep_agent`)
  instead of a hand-rolled engine; removed the redundant engine/orchestration modules.
- **Workflows (DWM v0.1)** — a signed DAG of verified agents compiled into a
  LangGraph `StateGraph` of Deep Agents.

### Added
- **DAM v0.1** declarative agent standard (schema + parser + validation).
- **DWM v0.1** declarative workflow standard (schema + parser + DAG validation:
  unique ids, referential integrity, cycle detection).
- **Ed25519 trust** — `amx keygen`/`sign`/`verify`, verified `install` gating,
  revocation (`amx revoke`), and a **signed registry** (`.sig` sidecars +
  `registry/trusted/`).
- **Workflows** — `amx workflow init/sign/verify/install/run/share/revoke`, with
  **recursive trust** (a workflow installs only when the workflow *and* every
  referenced agent verify) and **JIT workflow synthesis** (`amx workflow run "<goal>"`).
- **LLM-driven JIT synthesis** for agents (`amx run "<goal>"`) — real model, no fallback.
- **Real MCP tools** via `langchain-mcp-adapters` (declared tools are hard requirements).
- **Sandbox** — deny-by-default `allowed_domains` + egress proxy on MCP subprocesses.
- **Output verification** via Deep Agents `RubricMiddleware`.
- **Persistent sessions** — SQLite checkpointer/store; `amx history` + `amx run --replay` (resume).
- **Real BM25 search** (`amx search`); **registry index** (`amx index`).
- **Encrypted credentials** and **encrypted signing key** at rest (OS keyring).
- **Live-model CI** (`packages/aero/tests_live/`, secret-gated GitHub Actions job).
- `sub_agent` + `skill` providers; observability (`max_execution_steps`, `cost_limit_usd`).
- Python SDK: `AeroKernel.run_agent` / `run_workflow`.

### Security
- Signing private keys encrypted at rest; trusted keys revocable.
- MCP connection failures surfaced (never silently degraded to LLM-only).
- Recursive workflow trust composes a verified workflow out of verified agents.

### Fixed
- `manifest_version` normalized `3.0.0` → `0.1.0` (the "3.0.0" standard never existed).
- `amx install` preserves the `.sig` sidecar so installed artifacts stay verifiable.
- Clean async shutdown (no "pending task" warnings) and resume-from-file-path sessions.
