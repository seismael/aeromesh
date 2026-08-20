# Aero Agent Engine (`aero` / `amx`) Specification

> **Status:** superseded by `README.md` for the shipped v0.1 CLI. References to "DAM v3.0" and "Sigstore" below are stale — the engine is DAM v0.1 and uses Ed25519 attestation (`amx keygen`/`sign`/`verify`).

**Document Version:** 1.0.0 (Authoritative Final Release)  
**Package Name:** `packages/aero`  
**Executable Command:** `amx`  
**Terminal UI Framework:** Python `rich`  
**Default Driver:** LangGraph Execution Driver (`Driver.LangGraph`)  

---

## 1. Executive Summary: The Aero Standalone Agent Engine

`aero` is the standalone cognitive agent engine of the AeroMesh ecosystem.

To deliver a world-class developer experience, AeroMesh decouples **Terminal Presentation & Command Management (`packages/aero`)** from **Cognitive Graph Execution (`Driver.LangGraph`)**.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                         AERO STANDALONE AGENT ENGINE (`aero` / `amx`)                  │
│                         (packages/aero - Rich UI & API Interfaces)                     │
│                                                                                        │
│ • CLI Command Parsing (`amx run`, `amx search`, `amx validate`, `amx history`)         │
│ • Rich Terminal Layout (Colored Panels, Status Spinners, Tables, Syntax Highlighting)  │
│ • Interactive Key Vault Credentials Prompting & Explicit Human User Approvals          │
│ • Local Git-as-a-Registry Index Ingestion (~/.aeromesh/cache/index.json)               │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ (Passes Manifest + Credentials)
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│               LANGGRAPH EXECUTION ENGINE DRIVER (`Driver.LangGraph`)                   │
│                                                                                        │
│ • StateGraph Node Execution & Task Planning                                            │
│ • Network Proxy Sandbox Firewall & Allowed Domains Filtering                           │
│ • Sigstore Cryptographic Attestation & Session Checkpoint Time-Travel Replay           │
│ • Dual Stdio & Remote HTTP SSE MCP Tool Transport Drivers                              │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Complete CLI Command Reference (`amx`)

### 2.1 Manifest Scaffolding & Validation Commands
- **`amx init <agent_id>`**: Scaffolds a new DAM v3.0 boilerplate `agent.json` manifest.
- **`amx validate <manifest>`**: Validates a DAM v3.0 manifest against JSON Schema.
- **`amx audit <manifest>`**: Runs static security scanner for hardcoded keys and outputs Sigstore attestation.
- **`amx export-bundle <manifest>`**: Generates cryptographically signed Sigstore SHA-256 JSON bundle.
- **`amx vault check <manifest>`**: Pre-flight security vault audit for required credentials.

### 2.2 Execution & Orchestration Commands
- **`amx run <manifest> "<intent>"`**: Runs single agent or natural language JIT prompt (`--diagnostics`, `--non-interactive`, `--replay <session_id>`).
- **`amx pipeline <manifest_1> <manifest_2> ... --intent "<intent>"`**: Runs multi-agent linear or consensus voting swarm pipeline.
- **`amx search "<query>"`**: Performs sub-5ms 2-tier search discovery across local AppData store & workspace registry.
- **`amx history`**: Lists past session execution checkpoints from AppData directory.

### 2.3 Declarative Mesh Workflow Commands (DWM v1.0)
- **`amx workflow run <workflow.json>`**: Executes multi-agent async DAG workflow mesh.
- **`amx workflow schedule <workflow.json>`**: Registers crontab schedule into `~/.aeromesh/schedules.json`.
- **`amx workflow list`**: Lists all registered scheduled workflows.
- **`amx workflow daemon`**: Launches background crontab daemon polling due workflow jobs.

### 2.4 Registry Management Commands
- **`amx install <manifest>`**: Installs agent to local store (`~/.aeromesh/agents/`).
- **`amx share <manifest>`**: Generates registry Pull Request payload JSON.
- **`amx version`**: Displays engine version and OpenAgent standard metadata.

---

## 3. Exit Code Error Taxonomy (`AMX_ERR_*`)

- **Exit 0**: `SUCCESS`
- **Exit 10**: `AMX_ERR_SCHEMA_VIOLATION` (Invalid schema syntax or broken cyclic DAG)
- **Exit 20**: `AMX_ERR_VAULT_KEY_MISSING` (Missing required credential key)
- **Exit 30**: `AMX_ERR_DISCOVERY_NO_MATCH` (Agent manifest not found)
- **Exit 40**: `AMX_ERR_DOMAIN_BLOCKED` (Sandbox proxy firewall blocked domain)
