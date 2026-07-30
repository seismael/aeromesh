# Declarative Agent Manifest (DAM v3.0) Specification

**Document Version:** 1.0.0 (Authoritative Final Release)  
**Specification Standard:** AeroMesh OpenAgent Standard (DAM v3.0)  
**Reference Schema:** [`schemas/declarative-agent.schema.json`](file:///c:/dev/projects/aeromesh/schemas/declarative-agent.schema.json)  

---

## 1. Executive Overview

The **Declarative Agent Manifest (DAM v3.0)** is an open, machine-readable specification format for defining specialized AI agents as lightweight, text-only configuration artifacts (<10KB).

DAM v3.0 decouples an agent's **contract facets** and **capability requirements** from the underlying execution framework, enabling zero-overhead distribution, instant microsecond validation, and universal portability across local machines, cloud environments, and CI/CD pipelines.

---

## 2. Standard Contract Facets

A compliant DAM v3.0 document consists of five standard contract facets:

```
┌────────────────────────────────────────────────────────┐
│             DAM v3.0 STANDARD CONTRACT FACETS          │
├────────────────────────────────────────────────────────┤
│ 1. IDENTITY         : id, name, version, author, funding│
├────────────────────────────────────────────────────────┤
│ 2. CAPABILITIES     : domain, tags, trigger, contracts │
├────────────────────────────────────────────────────────┤
│ 3. COGNITIVE_RUNTIME: driver, persona, criteria, paging│
├────────────────────────────────────────────────────────┤
│ 4. REQUIREMENTS     : polymorphic capability providers │
├────────────────────────────────────────────────────────┤
│ 5. SWARM_TOPOLOGY   : pattern (hierarchical, pipeline) │
└────────────────────────────────────────────────────────┘
```

### 2.1 Identity Facet (`identity`)
- `id` (*String*, Required): Unique, URL-safe identifier (`^[a-z0-9-_]+$`).
- `name` (*String*, Required): Human-readable title.
- `version` (*String*, Required): Semantic version string (`1.0.0`).
- `author` (*String*, Optional): Maintainer or organization name.
- `license` (*String*, Optional): SPDX license identifier (`MIT`).
- `funding` (*Object*, Optional): Sponsorship link (`{"url": "https://github.com/sponsors/aeromesh", "type": "github"}`).

### 2.2 Capabilities Facet (`capabilities`)
- `domain` (*String*, Required): Top-level operational domain (`Database Engineering`).
- `tags` (*Array of Strings*, Required): Tag keywords for Tier 1 vector search index.
- `short_description` (*String*, Required): Functional summary for vector matching.
- `evaluation_trigger` (*String*, Required): Explicit invocation triggers and exclusion criteria.
- `input_contract` (*Object*, Optional): JSON Schema validating task payload.
- `output_contract` (*Object*, Optional): JSON Schema validating agent output.

### 2.3 Cognitive Runtime Facet (`cognitive_runtime`)
- `driver` (*String*, Required): Pluggable CDI driver (`Driver.LangGraph`, `Driver.WasmSandbox`, `Driver.NativeAsync`, `Driver.RemoteModel`).
- `persona` (*String*, Required): Direct system prompt directives injected into context.
- `success_criteria` (*String*, Required): Condition for task completion.
- `memory_policy` (*String*, Optional): Context paging policy (`CVM_LRU_PAGING`, `FULL_CONTEXT`).

### 2.4 Polymorphic Requirements Facet (`requirements.providers`)
Every requirement is declared as a polymorphic **Capability Provider**:

| Provider `type` | Adapter Function | Description |
| :--- | :--- | :--- |
| `mcp` | `IMcpDriver` | Mounts `stdio` or `sse` MCP tool servers. |
| `credential` | `ISecureVault` | Resolves secrets via shell env, OS keyring, or HashiCorp Vault. |
| `security` | `NetworkSandboxFirewall` | Enforces network domain allowlists (`allowed_domains`) and sandboxing. |
| `sub_agent` | `ISubAgentDelegator` | Dynamically provisions child DAM manifests for delegation. |
| `skill` | `INativeSkill` | Executes local microsecond code routines (e.g. `text-diff-generation`). |
| `storage_adapter` | `IStorageAdapter` | Binds external storage backends (Redis, PostgreSQL, S3). |

### 2.5 Swarm Topology Facet (`swarm_topology`)
- `pattern` (*String*, Optional): Multi-agent topology Enum `["hierarchical", "pipeline", "mesh_consensus", "pub_sub"]`.

---

## 3. Canonical Manifest Example

```json
{
  "manifest_version": "3.0.0",
  "identity": {
    "id": "postgres-performance-tuner",
    "name": "PostgreSQL Query Analyzer & Index Tuner",
    "version": "1.0.0",
    "author": "AeroMesh Community",
    "license": "MIT"
  },
  "capabilities": {
    "domain": "Database Engineering",
    "tags": ["postgres", "sql-optimization"],
    "short_description": "Examines slow SQL queries and outputs index creation scripts.",
    "evaluation_trigger": "Use when database queries are slow. Do NOT use for database backups."
  },
  "cognitive_runtime": {
    "driver": "Driver.LangGraph",
    "persona": "You are a Principal Database Reliability Engineer.",
    "success_criteria": "Must produce verified SQL DDL optimization scripts.",
    "memory_policy": "CVM_LRU_PAGING"
  },
  "requirements": {
    "providers": [
      {
        "type": "mcp",
        "id": "postgres-mcp",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres"],
        "required_tools": ["execute_query", "explain_query"]
      },
      {
        "type": "credential",
        "id": "DB_CONNECT_STRING",
        "kind": "connection_string",
        "fallback_action": "prompt_user"
      },
      {
        "type": "security",
        "id": "network-firewall",
        "isolation": "sandbox",
        "allowed_domains": ["*.postgresql.org", "github.com"]
      }
    ]
  },
  "swarm_topology": {
    "pattern": "hierarchical"
  }
}
```
