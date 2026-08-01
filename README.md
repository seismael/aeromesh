# AeroMesh: Open Autonomous AI Agent Engine & Declarative Swarm Ecosystem

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![DAM v3.0 Standard](https://img.shields.io/badge/Schema-DAM_v3.0-green.svg)](schemas/declarative-agent.schema.json)
[![DWM v1.0 Standard](https://img.shields.io/badge/Schema-DWM_v1.0-green.svg)](schemas/declarative-workflow.schema.json)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](packages/aero)
[![GitHub Repository](https://img.shields.io/badge/GitHub-seismael%2Faeromesh-black.svg?logo=github)](https://github.com/seismael/aeromesh)
[![Tests](https://img.shields.io/badge/tests-100_passed-brightgreen.svg)](packages/aero/tests)

**AeroMesh** is an open-source, enterprise-grade autonomous AI agent engine and declarative swarm ecosystem built on the **Declarative Agent Manifest (DAM v3.0)** and **Declarative Mesh Workflows (DWM v1.0)** standards. Powered by **Aero Engine (`amx`)**, it decouples agent capabilities from proprietary vendor lock-in, enabling deterministic pipelines, reusable mesh workflows, multi-agent consensus voting swarms, and OS-agnostic execution.

---

## ✨ Key Features & Breakthrough Capabilities

- **🏛️ Unified Master Orchestrator (`AeroMasterOrchestrator`)**: Auto-detects single agents, linear pipelines, DAG workflows, and raw natural language goals, dispatching to optimal engines with zero halts.
- **🐝 Autonomous Hybrid Swarm Synthesis**: Parses complex multi-domain prompts (e.g. *"Audit repository secrets AND generate custom PDF summary"*), matches pre-built registry agents for known sub-goals, dynamically synthesizes JIT manifests for unhandled clauses, and executes unified swarms.
- **🗳️ Multi-Agent Voting Consensus Swarms**: Computes majority voting agreement across multi-agent swarms before executing critical DDL queries or monetary transfers to eliminate LLM hallucinations.
- **🤖 Background Workflow Daemon (`amx workflow daemon`)**: Runs background crontab daemons polling `~/.aeromesh/schedules.json` and executing due workflow jobs automatically.
- **🔐 Zero-Trust Vault Cascade & Explicit Human Approval**: 5-layer credential resolution cascade (Override -> Process Env -> Vault Keyring -> User Home Config -> Desktop Fallback). In interactive human sessions, it requires explicit approval before consuming sensitive keys.
- **📦 Sigstore Cryptographic Attestations (`amx export-bundle`)**: Generates SHA-256 digital signatures and cryptographically signed manifest bundles for secure software distribution.
- **🛡️ Network Proxy Sandbox Firewall**: Enforces host domain allowlisting (`allowed_domains`), blocking unauthorized data exfiltration attempts.
- **🔌 Dual Stdio & Remote SSE MCP Transport**: Spawns local subprocess stdio MCP servers AND connects to remote HTTP Server-Sent Events (`http+sse`) microservices seamlessly.
- **🔍 Sub-5ms 2-Tier Discovery Search (`amx search`)**: Sub-5ms keyword and cognitive search index backed by local AppData caching (`~/.aeromesh/cache/index.json`).
- **📜 Session Checkpoints & Time-Travel Replay (`amx run --replay <id>`)**: Saves execution checkpoints to `%LOCALAPPDATA%\AeroMesh\checkpoints\` for deterministic time-travel session debugging.
- **💵 Token Cost & USD Budget Guardrail**: Enforces `manifest.observability.cost_limit_usd` budget thresholds, halting execution before budget overruns occur.
- **🐍 Embeddable Multi-Language SDKs (`packages/sdk-python`)**: Lightweight embeddable Python SDK (`from aeromesh import AeroKernel`) to embed the kernel directly into custom software applications.
- **🌐 OS-Agnostic AppData Standards**: Dynamic AppData path resolution across Windows (`%LOCALAPPDATA%\AeroMesh`), macOS (`~/Library/Application Support/AeroMesh`), Linux (`$XDG_DATA_HOME/aeromesh`), or `~/.aeromesh`.

---

## 🏛️ Monorepo Repository Topology

```
aeromesh/
├── .agents/                    <-- Single Source of Governance Layer (AGENTS.md)
├── docs/                       <-- Authoritative Master Specifications (01_PRD to 13_ENV)
├── schemas/                    <-- JSON Schemas (DAM v3.0 & DWM v1.0)
├── packages/                   <-- Enterprise Monorepo Packages
│   ├── aero/                   <-- Standalone Aero Agent Kernel (`aero` / `amx`)
│   ├── sdk-python/             <-- Embeddable Python Kernel SDK (`aeromesh-sdk`)
│   └── vscode-extension/       <-- VS Code IDE Plugin & Schema Validator Manifest
├── registry/                   <-- Git-as-a-Registry Agent Templates & Workflows
│   ├── agents/                 <-- Pre-built Production Agent Manifests
│   └── workflows/              <-- Declarative Mesh Workflows (DWM v1.0)
├── CONTRIBUTING.md             <-- Open-Source Contribution & Development Guide
├── LICENSE                     <-- Apache License 2.0
└── README.md                   <-- Master Ecosystem Architecture & Quickstart Guide
```

---

## 💻 Installation & Testing

### Installation
```bash
# Clone the repository
git clone https://github.com/seismael/aeromesh.git
cd aeromesh

# Install aero package in editable mode
pip install -e packages/aero
```

### Running Test Suite
```bash
# Run all 100 unit, integration, and production resilience stress tests
pytest packages/aero/tests
```

---

## 🚀 Quickstart CLI Command Reference (`amx`)

### 1. Scaffold a New Agent Manifest
```bash
amx init my-custom-agent
```

### 2. Validate DAM v3.0 Schema
```bash
amx validate registry/agents/postgres-performance-tuner.json
```

### 3. Guardian Security Scan & Sigstore Attestation
```bash
amx audit registry/agents/postgres-performance-tuner.json
amx export-bundle registry/agents/postgres-performance-tuner.json
```

### 4. Pre-Flight Security Vault Audit
```bash
amx vault check registry/agents/postgres-performance-tuner.json
```

### 5. Search Registry & AppData Store (<5ms SLA)
```bash
amx search "Postgres SQL query optimization"
```

### 6. Run Single Declarative Agent
```bash
$env:DB_CONNECT_STRING="postgresql://localhost:5432/production"
amx run registry/agents/postgres-performance-tuner.json "Optimize slow join query" --diagnostics
```

### 7. Run Unbounded Natural Language Prompt (JIT Builder)
```bash
amx run "Analyze microservices latency spikes, audit Redis cache hit ratios, and patch Kubernetes deployment"
```

### 8. Run Multi-Agent Swarm Pipeline (DGAP)
```bash
amx pipeline registry/agents/postgres-performance-tuner.json registry/agents/enterprise-security-auditor.json --intent "Tune DB and audit repo secrets" --diagnostics
```

### 9. Declarative Mesh Workflows & Background Daemon (DWM v1.0)
```bash
# Run multi-agent workflow mesh
amx workflow run registry/workflows/enterprise-cloud-migration-and-compliance-swarm.json --diagnostics

# Schedule recurring crontab workflow & launch background daemon
amx workflow schedule registry/workflows/x-trending-content-autopilot.json
amx workflow list
amx workflow daemon
```

### 10. Inspect History & Replay Session Checkpoints
```bash
# List past session checkpoints
amx history

# Replay saved session checkpoint deterministically
amx run registry/agents/postgres-performance-tuner.json "Replay" --replay session-postgres-performance-tuner-1785591737
```

### 11. Install & Share Agents
```bash
# Install to local store (~/.aeromesh/agents/)
amx install my-custom-agent.agent.json

# Share agent to public registry (Generates SHA-256 PR payload)
amx share registry/agents/postgres-performance-tuner.json
```

---

## 🐍 Embeddable Python SDK Quickstart (`aeromesh-sdk`)

```python
from aeromesh import AeroKernel

kernel = AeroKernel()

# Run a declarative agent manifest natively inside Python apps
res = kernel.run_agent("registry/agents/postgres-performance-tuner.json", "Optimize slow query")
print("Verified Result:", res["result"]["execution_result"]["verified_result"])
```

---

## 📚 Master Architecture Specifications

All technical specifications are organized in the [`docs/`](docs) directory:

- [`01_PRD_PRODUCT_REQUIREMENTS_DOCUMENT.md`](docs/01_PRD_PRODUCT_REQUIREMENTS_DOCUMENT.md) - Vision & Product Requirements
- [`02_SYSTEM_ARCHITECTURE.md`](docs/02_SYSTEM_ARCHITECTURE.md) - System Architecture & Master Orchestrator
- [`03_DECLARATIVE_AGENT_SPECIFICATION.md`](docs/03_DECLARATIVE_AGENT_SPECIFICATION.md) - DAM v3.0 OpenAgent Specification
- [`04_USER_INTERFACE_AND_CLI_PRESENTATION.md`](docs/04_USER_INTERFACE_AND_CLI_PRESENTATION.md) - Rich Terminal UI & Interactive Prompts
- [`04_CLI_ENGINE_SPECIFICATION.md`](docs/04_CLI_ENGINE_SPECIFICATION.md) - CLI Engine Command Reference
- [`05_DISCOVERY_AND_MARKETPLACE_REGISTRY.md`](docs/05_DISCOVERY_AND_MARKETPLACE_REGISTRY.md) - Marketplace Registry & 2-Tier Search Index
- [`06_SECURITY_VAULT_AND_SANDBOXING.md`](docs/06_SECURITY_VAULT_AND_SANDBOXING.md) - Zero-Trust Vault & Sandbox Firewall
- [`07_RUNTIME_MCP_AND_DYNAMIC_BUILDER.md`](docs/07_RUNTIME_MCP_AND_DYNAMIC_BUILDER.md) - Model Context Protocol & JIT Builder
- [`08_HORIZONTAL_ECOSYSTEM_PROJECTS_AND_TOOLS.md`](docs/08_HORIZONTAL_ECOSYSTEM_PROJECTS_AND_TOOLS.md) - Horizontal Ecosystem Projects & Tools
- [`09_ECOSYSTEM_INTEGRATION_AND_DEVELOPMENT_ROADMAP.md`](docs/09_ECOSYSTEM_INTEGRATION_AND_DEVELOPMENT_ROADMAP.md) - Strategic Roadmap & Milestones
- [`10_DECLARATIVE_MESH_WORKFLOWS_AND_SCHEDULING.md`](docs/10_DECLARATIVE_MESH_WORKFLOWS_AND_SCHEDULING.md) - Mesh Workflows & Crontab Scheduling
- [`13_WORKSPACE_AND_PACKAGE_ENVIRONMENT_STRUCTURE.md`](docs/13_WORKSPACE_AND_PACKAGE_ENVIRONMENT_STRUCTURE.md) - Monorepo Package Environment

---

## 🤝 Contributing

We welcome contributions of all kinds! Read our [**Contributing Guide (`CONTRIBUTING.md`)**](CONTRIBUTING.md) for full development setup and Pull Request guidelines.

---

## 📄 License

Distributed under the **Apache License 2.0**. See [`LICENSE`](LICENSE) for details.
