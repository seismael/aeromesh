# Ecosystem Integration Topology & Development Roadmap

> **Status: roadmap — partially shipped.** This is the delivery plan, not a
> completion report. Only Phase 1 is shipped in v1.0.0; later phases are deferred
> or were removed in the Deep Agents refactor. See `README.md`, `CHANGELOG.md`,
> and `SECURITY.md` for the authoritative current state.

**Document Version:** 1.0.0 (roadmap)  
**Execution Strategy:** 5-Phase Incremental Delivery Plan  
**Status:** Phase 1 shipped ✅ · Phases 2–5 deferred / removed (see below)

---

## 1. Ecosystem Data Contracts & Integration Topology

All shipped modules interact through typed data contracts in `packages/aero`:

```mermaid
graph TD
    User([User / Developer]) -->|amx run intent| CLI[packages/aero CLI]
    Developer([Agent Author]) -->|Manifest Init| Init[amx init]

    Init -->|Generates agent.json| Registry[Git Registry: registry/agents/]
    CLI -->|Searches local index| Registry
    CLI -->|Resolves Secrets| Vault[OS-keyring Credential Store]
    CLI -->|Compiles DAM -> Deep Agents| Driver[create_deep_agent + MCP tools]
    Driver -->|allowlist| Sandbox[Egress Proxy]
```

---

## 2. 5-Phase Execution Roadmap — honest status

| Phase | Scope | Status |
|---|---|---|
| 1. Standalone `amx` CLI + DAM v0.1 core | CLI, DAM schema/parser, Deep Agents execution, Ed25519 trust + revocation, encrypted vault, egress sandbox | **SHIPPED** ✅ |
| 2. Git-as-registry marketplace + search | `amx share`/`install` (shipped); `amx search` (keyword-only, shipped); hosted marketplace + 2-tier vector index (deferred) | **PARTIAL** |
| 3. Developer tools | VS Code extension (stub `package.json` only); test harness (removed); Sigstore transparency-log bundle (deferred) | **DEFERRED** |
| 4. Multi-language SDKs + session replay | Python SDK (shipped, thin); TS/Go SDKs (deferred); real session persistence/replay (see `docs/15`) | **PARTIAL** |
| 5. Workflows + swarm consensus | `amx workflow` / `amx pipeline` removed in the refactor; orchestration is delegated to Deep Agents subagents/planning | **REMOVED** |

---

## 3. Verification

- **Offline test suite:** 85 passed (real code; test doubles are confined to
  `tests/conftest.py`).
- **Live-model CI:** deferred — needs a real provider key and a real MCP server
  in CI (see `SECURITY.md` / roadmap).
