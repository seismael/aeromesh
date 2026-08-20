# Aero Engine (`aero` / `amx`)

The AeroMesh CLI: parse, sign, verify, sandbox, and run **DAM v0.1** declarative agent manifests — compiled into LangChain Deep Agents.

## Capabilities

- **DAM v0.1 parser & validation** — `jsonschema`-validated manifest hydration.
- **Ed25519 attestation** — `amx keygen` / `amx sign` / `amx verify` (`.sig` sidecars).
- **Trusted install** — `amx install` verifies signatures against `registry/trusted/` before installing.
- **LLM-driven JIT synthesis** — synthesize a schema-valid manifest from a live model (no synthetic fallback).
- **Real tool execution** — `mcp` providers become real LangChain tools via `langchain-mcp-adapters`.
- **Sandbox** — deny-by-default `allowed_domains` + egress proxy on MCP tool subprocesses.
- **Encrypted credentials** — OS-keyring-backed storage (`amx vault set`).
- **Native providers** — DeepSeek / Anthropic / OpenAI / Gemini via `init_chat_model` (real calls).

## Quickstart

```bash
pip install -e packages/aero
pytest packages/aero/tests
```
