# Discovery Engine & Marketplace Registry Specification

> **Status:** aspirational roadmap. The shipped v0.1 implements local/git-as-registry discovery + Ed25519 install verification (see `README.md`, `docs/06`). References to "DAM v3.0" and "Sigstore" are future work.

**Document Version:** 1.0.0 (Authoritative Final Release)  
**Pattern:** Decentralized Git-as-a-Registry & Local AppData Store (`packages/discovery-index`)  
**Search Performance SLA:** Tier 1 Vector Filtering < 5ms  

---

## 1. Executive Summary: Local Store vs. Global Registry Architecture

AeroMesh decouples local agent execution from global community sharing:

1. **User Home Local Runtime Store (`~/.aeromesh/agents/`)**:
   - Stores locally created, installed (`amx install`), or JIT-synthesized agent manifests on the user's specific machine.
   - Looked up first by `amx run <agent_id>`.
2. **Global Marketplace Registry (`registry/agents/` & `aeromesh/registry`)**:
   - Master public Git repository of community-published declarative agent manifests available for sharing.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ USER HOME LOCAL RUNTIME STORE (`~/.aeromesh/agents/`)                                  │
│                                                                                        │
│ • Local Private Agents & JIT-Compiled Manifests                                       │
│ • Installed Agents (`amx install <manifest.json>`)                                     │
│ • Looked up first by `amx run <agent_id>`                                              │
└───────────────────────────▲────────────────────────────────────────────┘
                            │
               amx install  │  amx share
              (Downloads)   │  (Generates PR Payload)
                            │
┌───────────────────────────┴────────────────────────────────────────────┐
│ GLOBAL MARKETPLACE REGISTRY (`registry/agents/` & GitHub aeromesh/registry)             │
│                                                                                        │
│ • Community-Published DAM v3.0 Agent Manifests                                         │
│ • Central `index.json` 2-Tier Search Registry Index                                     │
│ • Sigstore Attested & Security Guardian Scanned                                       │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. CLI Share & Install Subcommands

### 2.1 `amx install <manifest_file>`
Installs a declarative agent manifest into the user's local store (`~/.aeromesh/agents/<agent_id>.json`).
Once installed, the agent can be executed directly by its simple ID:
```bash
amx install my_agent.json
amx run my_agent "Analyze database query"
```

### 2.2 `amx share <manifest_file>`
Validates a local manifest against `declarative-agent.schema.json`, calculates its SHA-256 cryptographic hash, and outputs a formatted registry pull request payload for community sharing:
```json
{
  "id": "postgres-performance-tuner",
  "version": "1.0.0",
  "title": "PostgreSQL Query Analyzer & Index Tuner",
  "domain": "Database Engineering",
  "tags": ["postgres", "sql-optimization"],
  "short_description": "Examines slow SQL queries and outputs index creation DDL scripts.",
  "evaluation_trigger": "Use when database queries are slow.",
  "sha256": "a3f5c71b8e9d...",
  "pull_request_target": "registry/agents/postgres-performance-tuner.json"
}
```
