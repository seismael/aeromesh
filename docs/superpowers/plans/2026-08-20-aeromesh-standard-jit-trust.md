# AeroMesh v0.1 Implementation Plan

> **For agentic workers:** executed inline with TDD (red → green → commit) in dependency order.

**Goal:** Ship the refocused AeroMesh v0.1 (honest standard + real JIT synthesis + Ed25519 trusted marketplace + enforced sandbox) with docs aligned and the full test suite green.

**Tech stack:** Python 3.11+, `jsonschema`, `cryptography` (Ed25519), `langgraph` (internal driver), `rich`.

---

## Phase 0 — Groundwork

- [ ] 0.1 Add `cryptography` dependency to `packages/aero/pyproject.toml`.
- [ ] 0.2 Fix schema `$id` and add `0.1.0` branding; update `schema_binding.py` URI.
- [ ] 0.3 Update package `__init__.py` version → `0.1.0`.

## Phase 1 — Ed25519 attestation (trust pillar)

- [ ] 1.1 `aero/infrastructure/attestation.py`: `generate_keypair`, `sign_bytes`, `verify_bytes`, `canonicalize`, `sign_manifest_file`, `verify_manifest_file`, key storage helpers.
- [ ] 1.2 Tests `tests/unit/test_attestation.py` (red → green): sign/verify round-trip, tamper detection, canonicalization stability.
- [ ] 1.3 CLI: `amx keygen`, `amx sign`, `amx verify` (+ tests).

## Phase 2 — Trusted install / share

- [ ] 2.1 `registry/trusted/` trust store + `amx install` verifies before copy (refuse unsigned; `--insecure` opt-out).
- [ ] 2.2 `amx share` emits a signed bundle (manifest + sha256 + signature + public key).
- [ ] 2.3 Replace "Sigstore" wording in `guardian.py`, `cli.py`, docs.

## Phase 3 — Real LLM-driven JIT synthesis

- [ ] 3.1 `aero/services/synthesizer.py`: `JitSynthesizer.synthesize(goal, adapter)` — LLM-first, schema-validate, retry w/ feedback, template fallback.
- [ ] 3.2 Tests (red → green): returns schema-valid manifest; falls back with warning when mock key.
- [ ] 3.3 Wire into `decomposition.py`; fix hybrid-goal dispatch in `orchestrator.py`.

## Phase 4 — Enforced sandbox

- [ ] 4.1 Wire `NetworkSandboxFirewall` into `providers.py` outbound calls (and MCP-SSE).
- [ ] 4.2 Test: blocked domain raises `AMX_ERR_DOMAIN_BLOCKED`; allowed passes.

## Phase 5 — Bug fixes

- [ ] 5.1 Fix hybrid-JIT `synthesized_manifest=None` crash (covered in 3.3, verified here).
- [ ] 5.2 Shutdown `ThreadPoolExecutor` + fix asyncio task cleanup in `workflow.py`.
- [ ] 5.3 Make LLM provider call real-by-default; mock only behind explicit offline flag.

## Phase 6 — Docs/markdown alignment & cleanup

- [ ] 6.1 Rewrite `README.md` (refocused positioning, honest capabilities, no fake badges).
- [ ] 6.2 Rewrite `docs/01`, `docs/02`, `docs/03`, `docs/06` to match reality; remove fictional claims.
- [ ] 6.3 Rewrite `.agents/AGENTS.md` governance to match the refocused scope.
- [ ] 6.4 Remove/mark vscode-extension stub; align `packages/*/README.md`.

## Phase 7 — Final verification

- [ ] 7.1 Full suite green (`pytest packages/aero/tests`), no asyncio/thread warnings.
- [ ] 7.2 `amx keygen/sign/verify/install/run "<nl goal>"` manual smoke.
- [ ] 7.3 Commit, merge-ready.
