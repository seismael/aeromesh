# Product Requirements Document (PRD): AeroMesh Ecosystem

**Document Version:** 1.0.0 (Authoritative Final Release)  
**Status:** Approved Product & System Requirement Specification  
**Target Platform:** AeroMesh Open-Source Ecosystem  

---

## 1. Executive Summary & Product Vision

### 1.1 Vision Statement
AeroMesh is an open-source, ultra-lightweight **Cognitive Operating Kernel and Decentralized Agent Marketplace Ecosystem** that empowers autonomous AI orchestrators to dynamically discover, fetch, sandbox, authenticate, and execute specialized micro-agents in real time.

By standardizing agents as **Declarative Agent Manifests (DAM v3.0)**—text-only JSON configurations under 10KB—AeroMesh eliminates multi-gigabyte container overhead, slow startup latencies, and vendor lock-in.

### 1.2 Core Problem Statement
Current AI agent engineering is trapped between two flawed paradigms:
1. **The Monolithic Prompt Monolith**: Single-agent prompts loaded with dozens of tools suffer from **attention dilution**, context drift, exponential token cost inflation, and severe hallucination rates.
2. **Heavy Multi-Agent Framework Container Bloat**: Frameworks force developers to hard-code Python routing logic and package agents inside heavy multi-gigabyte Docker environments.

### 1.3 The AeroMesh Solution
AeroMesh treats agents as lightweight, text-based declarative metadata schemas executed by a decoupled **Cognitive Kernel (`packages/core-kernel`)** and **Command Line Interface (`packages/cli-engine`)**.

---

## 2. Standard Contract Facets (DAM v3.0)

AeroMesh standardizes agent configurations into five orthogonal contract facets:

1. **`identity`**: `id`, `name`, `version`, `author`, `license`, `funding`.
2. **`capabilities`**: `domain`, `sub_domain`, `tags`, `short_description`, `evaluation_trigger`, `input_contract` (JSON Schema), `output_contract` (JSON Schema).
3. **`cognitive_runtime`**: Pluggable CDI driver (`Driver.LangGraph`, `Driver.WasmSandbox`, `Driver.NativeAsync`, `Driver.RemoteModel`), `persona`, `success_criteria`, `memory_policy` (`CVM_LRU_PAGING`).
4. **`requirements`**: Polymorphic capability provider adapters (`providers`: `mcp`, `credential`, `security`, `sub_agent`, `skill`, `storage_adapter`, `custom_plugin`).
5. **`swarm_topology`**: Multi-agent swarm patterns (`hierarchical`, `pipeline`, `mesh_consensus`, `pub_sub`).

---

## 3. Horizontal Ecosystem Scope & Packages (`packages/`)

The platform comprises ten horizontal projects organized in an enterprise monorepo:

1. **Multi-Language Core Kernel SDKs** (`packages/sdk-python`, `packages/sdk-typescript`, `packages/sdk-go`)
2. **AeroMesh Visual Studio** (`packages/studio-web`) - Drag-and-drop web builder.
3. **VS Code & IDE Extension** (`packages/vscode-extension`) - Live DAM schema IntelliSense & debugger.
4. **Agent Testing & Benchmarking Harness** (`packages/test-harness`) - Mock MCP driver testing.
5. **AeroMesh Desktop Application** (`packages/desktop-app`) - Cross-platform Tauri desktop UI.
6. **AeroMesh Web Hub & Marketplace** (`packages/web-hub` / `aeromesh.dev`) - Web registry & documentation.
7. **Cloud Serverless Daemon** (`packages/cloud-daemon`) - Headless background runner for cron/webhooks.
8. **Enterprise MCP Gateway** (`packages/mcp-gateway`) - Enterprise Go proxy with OAuth2 IAM mapping.
9. **Security Attestation & Guardian Scanner** (`packages/guardian-scanner`) - Static analysis & Sigstore signer.
10. **Telemetry & Evaluation Framework** (`packages/telemetry-eval`) - OpenTelemetry tracing & cost tracker.

---

## 4. Machine-Readable Error Taxonomy (`AMX_ERR_*`)

| Error Code String | Exit Code | Trigger Category | Description |
| :--- | :--- | :--- | :--- |
| `AMX_SUCCESS` | `0` | Success | Lifecycle executed cleanly matching success criteria. |
| `AMX_ERR_SCHEMA_VIOLATION` | `10` | Manifest Parsing | JSON manifest failed `declarative-agent.schema.json` validation. |
| `AMX_ERR_VAULT_KEY_MISSING` | `20` | Security & Auth | Required credential absent in non-interactive mode. |
| `AMX_ERR_DOMAIN_BLOCKED` | `21` | Security Firewall | Network request violated `allowed_domains`. |
| `AMX_ERR_DISCOVERY_NO_MATCH` | `30` | Discovery Engine | Tier 1 & Tier 2 search returned 0 matches and JIT compiler disabled. |
| `AMX_ERR_MCP_SPAWN_FAILED` | `40` | MCP Transport | Failed to execute stdio command (`npx`, `python`, `uvx`). |
| `AMX_ERR_MCP_TIMEOUT` | `41` | MCP Transport | MCP tool invocation timed out (>30s limit). |
| `AMX_ERR_JIT_BUILD_FAILED` | `50` | Dynamic Builder | JIT LLM compiler failed to synthesize manifest after 3 retries. |

---

## 5. Non-Functional Requirements & Performance SLAs

| Category | Requirement / SLA Metric | Target Value |
| :--- | :--- | :--- |
| **Latency** | Manifest Structural Schema Validation | < 1 ms |
| **Latency** | Tier 1 Vector Registry Search | < 5 ms |
| **Latency** | Full Agent Boot Time (Local stdio MCP) | < 100 ms |
| **Memory** | CLI Operating Memory Footprint | < 30 MB RAM |
| **Artifact Size** | Declarative Agent Manifest JSON Size | < 10 KB |
| **Security** | Zero Secret Exposure SLA | 0 secrets logged or committed |
