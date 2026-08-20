# AeroMesh v0.1 — Standard + JIT Synthesis + Trusted Marketplace (Design Spec)

**Date:** 2026-08-20
**Status:** Approved
**Branch:** `feat/standard-jit-trust-v0.1`

## 1. Goal

Refocus AeroMesh from "a LangGraph orchestrator with extra steps" into the one thing that is genuinely non-redundant: **a standard for declaring agents, a way for an LLM to synthesize them on demand, and a way to trust them when you download someone else's.** All other claims are de-emphasized or removed.

## 2. Locked decisions (user-approved)

1. **Trust:** self-contained **Ed25519** signing/verification (no external Sigstore infra).
2. **Marketplace:** **git-as-registry** — `registry/` carries signed manifests + trusted public keys.
3. **JIT synthesis:** **LLM-first**, with deterministic template fallback (explicit warning) when no provider key.
4. **LangGraph:** kept as an **internal execution driver only**; removed from marketing/docs as a headline.

## 3. Product pillars (what "done" means)

### Pillar A — Honest standard (DAM v0.1.0)
- Schema stays the single source of truth.
- `manifest_version` examples move from `3.0.0` → `0.1.0`; branding "DAM v0.1".
- Fix dead `$id` / `schema_uri` URLs to honest, documented values.
- Rewrite `docs/03_DECLARATIVE_AGENT_SPECIFICATION.md` as an actual spec (normative, not marketing).

### Pillar B — Real LLM-driven JIT synthesis
- New `aero/services/synthesizer.py` (JitSynthesizer): prompts the model to emit a schema-valid manifest for a goal; validates with `jsonschema`; retries up to 3 with the validation error fed back.
- Falls back to the deterministic template **only when no provider key exists**, and logs a visible degradation warning.
- Fix the hybrid-goal crash (known agent + unknown clause) so `amx run "<natural language>"` works end-to-end.

### Pillar C — Trusted marketplace (Ed25519)
- New `aero/infrastructure/attestation.py`:
  - `keygen()` → Ed25519 keypair to `~/.aeromesh/keys/`.
  - `sign_manifest(manifest_path, key)` → canonical-JSON signature (SHA-256 + Ed25519).
  - `verify_manifest(manifest_path, public_key)` → bool.
  - Signed bundle format for `share`.
- Registry trust store: `registry/trusted/<agent_id>.pub` (or a `trusted_keys.json`).
- `amx install` **refuses unverified agents** (with explicit `--insecure` opt-out).
- `amx keygen`, `amx sign`, `amx verify` CLI commands.
- Replace all "Sigstore" wording with honest "Ed25519 attestation".

### Pillar D — Enforced network sandbox
- `NetworkSandboxFirewall` is wired into every real outbound call (provider API calls, MCP-SSE).
- `allowed_domains` is actually enforced; violations raise `AMX_ERR_DOMAIN_BLOCKED`.

## 4. Bug fixes
1. Hybrid-JIT crash (`synthesized_manifest=None` → `AttributeError`).
2. `ThreadPoolExecutor` never shut down + asyncio `Task was destroyed but it is pending` leaks in `workflow.py`.
3. Mock-first LLM: real provider call by default; mock only behind an explicit offline flag/env.

## 5. Cleanup (removals)
- Remove fake "Sigstore" / "cryptographic attestation" wording → Ed25519.
- Remove fictional architecture claims: C-Bus, CVM virtual memory, `CBusStream`, `ISecureVault`/`IMcpDriver`/`ICognitiveDriver` interfaces, the "10 packages" list, `core-kernel`/`cli-engine` paths.
- Remove "DGAP guaranteed pipeline" and "consensus voting eliminates hallucinations" marketing (keep pipeline/workflow as thin composition utilities).
- Remove static "100 tests passed" badge; replace with honest language.
- Remove non-existent vscode-extension schema references or mark the extension as a stub.

## 6. Testing strategy (TDD)
- Every new module has failing tests first (red → green).
- Tests assert **real behavior**: a signed manifest verifies; a tampered manifest fails; an LLM-driven JIT returns schema-valid output; a blocked domain raises; install refuses unsigned.
- Existing 100-test suite must stay green throughout.

## 7. Out of scope for v0.1
- HTTP registry server.
- Sigstore/cosign transparency logs.
- Multi-language SDKs beyond Python.
- Actual agent *marketplace hosting* (only the trust mechanism + git registry now).
