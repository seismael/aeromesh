# Aero Engine (`aero` / `amx`)

The AeroMesh CLI validates, approves, and runs declarative agent releases compiled
into LangChain Deep Agents. Version 0.2.0 tightens trust and runtime capability
checks; unsupported declarations fail instead of being silently ignored.

## Capabilities

- **Manifest validation** — bundled JSON Schemas work in an installed wheel.
- **Ed25519 attestation** — `amx keygen` / `amx sign` / `amx verify` (`.sig` sidecars).
- **Release verification** — installation and normal execution require explicitly approved trust.
- **LLM-driven JIT synthesis** — synthesize a schema-valid manifest from a live model (no synthetic fallback).
- **Real tool execution** — `mcp` providers become real LangChain tools via `langchain-mcp-adapters`.
- **Isolation** — approved container execution is distinct from explicit host development mode. A proxy environment is not process isolation.
- **Encrypted credentials** — OS-keyring-backed storage (`amx vault set`).
- **Native providers** — DeepSeek / Anthropic / OpenAI / Gemini via `init_chat_model` (real calls).

## Quickstart

```bash
python -m pip install -c constraints/ci-python.txt -e 'packages/aero[dev]'
pytest packages/aero/tests
pytest packages/aero/tests_system -m 'not docker'
python examples/dependency-inventory/smoke.py
```

See the repository README for the supported manifest subset, migration, trust
setup, isolation requirements, and release checks. The real MCP example works
offline; agent reasoning requires a configured model provider. Passing an output
schema does not establish that an agent's substantive conclusion is correct.
