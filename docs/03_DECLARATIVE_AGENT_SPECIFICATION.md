# Declarative Agent Manifest (DAM) v0.1 Specification

**Status:** v0.1
**Single source of truth:** `schemas/declarative-agent.schema.json`

## 1. Purpose

DAM v0.1 is a JSON format for describing a portable, schema-validated AI agent. It captures *what* an agent is, *what it can do*, and *what it needs* — without binding it to a specific framework or vendor.

## 2. Top-level structure

```json
{
  "manifest_version": "0.1.0",
  "identity": { },
  "capabilities": { },
  "cognitive_runtime": { },
  "requirements": { "providers": [ ] },
  "swarm_topology": { },
  "observability": { }
}
```

## 3. Facets

### `identity`
`id` (kebab-case, unique), `name`, `version` (semver), optional `author`, `license`, `funding`.

### `capabilities`
`domain`, optional `sub_domain`, `tags[]`, `short_description`, `evaluation_trigger`, optional `input_contract`/`output_contract` (JSON Schemas).

### `cognitive_runtime`
`persona`, `success_criteria`, and optional `driver` (default `Driver.LangGraph`), `memory_policy`, `checkpoint_policy`.

### `requirements.providers[]`
Polymorphic capability requirements. Each has a `type` (`mcp`, `credential`, `security`, `sub_agent`, `skill`, `storage_adapter`, `custom_plugin`) and an `id`. Relevant fields:
- `mcp` — `command`, `args`, `transport` (`stdio` | `sse`), `uri`, `required_tools`.
- `credential` — `kind`, `fallback_action`.
- `security` — `isolation`, `allowed_domains[]`.

### `swarm_topology` (optional)
`pattern` (`hierarchical` | `pipeline` | `mesh_consensus` | `pub_sub`), `consensus_threshold`, `routing_key`.

### `observability` (optional)
`trace_level`, `cost_limit_usd`, `max_execution_steps`.

## 4. Validation

`jsonschema.validate` against `declarative-agent.schema.json`; violations raise `AMX_ERR_SCHEMA_VIOLATION` (exit 10). The schema uses `additionalProperties: false`.

## 5. Attestation

A manifest is attested by an Ed25519 signature over its canonical (sorted-key) JSON. The signature lives in a `<manifest>.sig` sidecar with `algorithm`, `sha256`, `public_key`, and `signature` fields.
