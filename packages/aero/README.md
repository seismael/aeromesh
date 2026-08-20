# Aero Engine (`aero` / `amx`)

The AeroMesh engine and CLI: parse, sign, verify, sandbox, and execute **DAM v0.1** declarative agent manifests.

## Capabilities

- **DAM v0.1 parser & validation** — `jsonschema`-validated manifest hydration.
- **Ed25519 attestation** — `amx keygen` / `amx sign` / `amx verify` with `.sig` sidecars.
- **Trusted install** — `amx install` verifies signatures against `registry/trusted/` before installing.
- **LLM-driven JIT synthesis** — synthesize a schema-valid agent manifest for any natural-language goal (offline template fallback).
- **Network sandbox** — `allowed_domains` enforced for remote (SSE) MCP endpoints.
- **DWM workflows** — DAG execution with cycle detection and async concurrency.
- **Multi-provider LLM binding** — DeepSeek, Anthropic, OpenAI, Gemini (real calls with a real key).

## Quickstart

```bash
pip install -e packages/aero
pytest packages/aero/tests
```
