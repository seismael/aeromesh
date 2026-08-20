# Changelog

All notable changes to AeroMesh are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed
- `amx init` now scaffolds `manifest_version: "0.1.0"` (was the non-existent
  `"3.0.0"`); the schema description, registry manifests, and test fixtures were
  normalized to DAM v0.1.

### Changed
- **Real session persistence**: the Deep Agents checkpointer and store are now
  SQLite-backed (`~/.aeromesh/checkpoints.sqlite` + `memory.sqlite`) instead of
  in-memory, so conversations survive process restarts.
- `amx run --replay <session>` now **resumes** the session's thread (continuing
  the conversation) instead of re-reading a stale JSON result blob. `amx history`
  lists recorded sessions from the session registry.

### Docs
- Rewrote `docs/09` to report honest phase status (Phase 1 shipped; Phases 2–5
  deferred/removed) instead of "ALL 5 PHASES 100% IMPLEMENTED".
- Corrected stale honesty notes in `docs/06` (OS-keyring credential encryption
  and the egress proxy are shipped, not roadmap) and clarified the DAM v0.1 vs
  software 1.0.0 versioning in `SECURITY.md`/`CONTRIBUTING.md`.

## [1.0.0] — 2026-08-20

### Architecture
- Refactored AeroMesh to compile **DAM v0.1** manifests into **LangChain Deep
  Agents** (`create_deep_agent`) instead of a hand-rolled engine.
- Removed the redundant hand-rolled engine (`providers`, `driver`, `mcp`,
  `harness`, `diagnostics`) and orchestration (`pipeline`, `workflow`,
  `decomposition`, `preflight`).

### Added
- **DAM v0.1** declarative manifest standard (schema + parser + validation).
- **Ed25519 trust**: `amx keygen` / `sign` / `verify`, verified `install` gating,
  and **key revocation** (`amx revoke`).
- **Encrypted signing key** at rest (Fernet + OS keyring).
- **Encrypted credentials** (OS keyring, `amx vault set`).
- **LLM-driven JIT synthesis** (native `init_chat_model`, strictly LLM-driven —
  no synthetic fallback).
- **Real MCP tools** via `langchain-mcp-adapters` (declared tools are a hard
  requirement; failures surface as clear errors).
- **Sandbox**: deny-by-default `allowed_domains` + egress proxy on MCP subprocesses.
- **Output verification** via Deep Agents `RubricMiddleware` (`output_contract`).
- **Persistence**: checkpointer + store wired (session resume, HITL, memory,
  multi-turn conversation).
- **Observability enforcement**: `max_execution_steps` (recursion limit) and
  `cost_limit_usd` (token accounting).
- `sub_agent` + `skill` providers mapped to Deep Agents subagents/skills.
- CI workflow (GitHub Actions, Python 3.11–3.13).

### Changed
- Providers resolved via native `init_chat_model` (DeepSeek/Anthropic/OpenAI/Gemini).
- Removed `amx pipeline` and `amx workflow` commands and the SDK `run_workflow`.
- Fakes/mocks confined to `tests/`; production code is always real.

### Security
- Signing private keys are no longer stored in plaintext.
- Trusted keys can now be revoked.
- MCP connection failures are surfaced (never silently degraded to LLM-only).
