# Product Requirements Document: AeroMesh (v0.1)

**Status:** v0.1 — matches the implemented engine.

## 1. Vision

AeroMesh is a **declarative agent standard (DAM v0.1) + a thin runtime**. Three problems, three pillars:

1. **Portability** — describe an agent once as a schema-validated JSON manifest, so you don't rebuild it per framework or per task.
2. **On-demand synthesis** — for a goal no existing agent covers, an LLM synthesizes a schema-valid manifest.
3. **Trust** — agents are Ed25519-signed; `amx install` verifies signatures against `registry/trusted/`; `allowed_domains` sandboxes remote tool endpoints.

## 2. The DAM v0.1 manifest facets

1. `identity` — id, name, version, author, license, funding.
2. `capabilities` — domain, sub_domain, tags, short_description, evaluation_trigger, input/output contracts.
3. `cognitive_runtime` — driver, persona, success_criteria, memory_policy, checkpoint_policy.
4. `requirements.providers` — mcp, credential, security, sub_agent, skill, storage_adapter, custom_plugin.
5. `swarm_topology` — pattern, consensus_threshold, routing_key.
6. `observability` — trace_level, cost_limit_usd, max_execution_steps.

Schema: `schemas/declarative-agent.schema.json`.

## 3. Machine-readable error taxonomy

| Code | Exit | Meaning |
|---|---|---|
| `AMX_SUCCESS` | 0 | success |
| `AMX_ERR_SCHEMA_VIOLATION` | 10 | schema/parse failure |
| `AMX_ERR_VAULT_KEY_MISSING` | 20 | required credential missing |
| `AMX_ERR_DOMAIN_BLOCKED` | 21 | sandbox allowlist violation |
| `AMX_ERR_DISCOVERY_NO_MATCH` | 30 | no matching agent found |
| `AMX_ERR_MCP_SPAWN_FAILED` | 40 | MCP subprocess failure |
| `AMX_ERR_MCP_TIMEOUT` | 41 | MCP timeout |
| `AMX_ERR_JIT_BUILD_FAILED` | 50 | JIT synthesis failure |

## 4. Trust model

Self-contained Ed25519: `amx keygen` → `amx sign` (`.sig` sidecar) → `amx verify` → `amx install` (refuses unverified marketplace agents). No external CA or transparency log in v0.1.

## 5. Non-functional targets

- Manifest schema validation: sub-millisecond.
- Manifest size: < 10 KB.
- No secrets committed or logged.
