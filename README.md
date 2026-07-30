# AeroMesh: Open Autonomous AI Agent Engine & Declarative Swarm Ecosystem

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![DAM v3.0 Standard](https://img.shields.io/badge/Schema-DAM_v3.0-green.svg)](schemas/declarative-agent.schema.json)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](packages/aero)
[![GitHub Repository](https://img.shields.io/badge/GitHub-seismael%2Faeromesh-black.svg?logo=github)](https://github.com/seismael/aeromesh)
[![Contributing](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Tests](https://img.shields.io/badge/tests-47_passed-brightgreen.svg)](packages/aero/tests)

**AeroMesh** is an open-source, enterprise-grade autonomous AI agent ecosystem built on the **Declarative Agent Manifest (DAM v3.0)** standard. Powered by **Aero Engine (`amx`)**, it decouples agent capabilities from proprietary vendor lock-in, enabling deterministic pipelines, reusable mesh workflows, and OS-agnostic execution.

---

## ✨ Key Features

- **🏛️ Unified Master Orchestrator (`AeroMasterOrchestrator`)**: Auto-detects single agents, linear pipelines, and complex DAG workflows, dispatching to optimal engines with zero halts.
- **⚡ Non-Blocking Async Concurrency & Worker Pools**: Multi-thread worker pools dispatch independent DAG steps concurrently while dependent steps await prerequisite events asynchronously.
- **🎯 Deterministic Guaranteed Agent Pipeline (DGAP)**: Eliminates non-deterministic LLM flow gaps by enforcing contract-validated intermediate output hand-offs.
- **🔄 Declarative Mesh Workflows (DWM v1.0)**: Define reusable multi-agent DAG topologies (`workflow.json`) with native crontab scheduling (`0 8 * * 1-5`).
- **🛫 Interactive Pre-Flight Engine**: Auto-detects LLM provider keys, verifies agent feasibility, and negotiates credentials interactively before execution — zero mid-task failures.
- **🔑 Zero-Trust Explicit User Key Permission**: Discovered environment credentials require explicit human user approval before execution (`[1] Approve`, `[2] New Key`, `[3] Reject`).
- **🌐 OS-Agnostic AppData Home (`~/.aeromesh/`)**: Dynamic AppData path resolution across Windows (`%LOCALAPPDATA%\AeroMesh`), macOS (`~/Library/Application Support/AeroMesh`), Linux (`$XDG_DATA_HOME/aeromesh`), or `~/.aeromesh`.
- **📊 Real-Time OpenTelemetry Diagnostics (`--diagnostics`)**: Structured diagnostic event tracing with peak memory (RAM in MB) and latency tracking.

---

## 🏛️ Monorepo Repository Layout

```
aeromesh/
├── .agents/                    <-- Single Source of Governance Layer (AGENTS.md)
├── docs/                       <-- Authoritative Master Specifications (01_PRD to 13_ENV)
├── schemas/                    <-- JSON Schemas (DAM v3.0 & DWM v1.0)
├── packages/                   <-- Enterprise Monorepo Packages
│   └── aero/                   <-- Aero Standalone Agent Engine (`aero` / `amx`)
├── registry/                   <-- Git-as-a-Registry Agent Templates
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
# Run all 47 unit, integration, and stress tests
python -m pytest packages/aero/tests/ -v
```

---

## 🚀 Quickstart CLI Guide (`amx`)

### 1. Validate a Declarative Agent Manifest
```bash
amx validate registry/agents/postgres-performance-tuner.json
```

### 2. Run a Single Declarative Agent
```bash
amx run registry/agents/postgres-performance-tuner.json "Analyze slow query SELECT * FROM orders" --diagnostics
```

### 3. Run a Deterministic Guaranteed Pipeline (DGAP)
```bash
amx pipeline registry/agents/postgres-performance-tuner.json registry/agents/enterprise-security-auditor.json --intent "Optimize DB queries and audit repo secrets" --diagnostics
```

### 4. Run a Declarative Mesh Workflow (DWM v1.0)
```bash
amx workflow run registry/workflows/daily_enterprise_audit.json --diagnostics
```

### 5. Schedule a Recurring Crontab Workflow
```bash
amx workflow schedule registry/workflows/daily_enterprise_audit.json
```

### 6. Install or Share Agents
```bash
# Install to local user store (~/.aeromesh/agents/)
amx install custom_agent.json

# Share agent to public registry (Generates SHA-256 PR payload)
amx share custom_agent.json
```

---

## 🤝 Contributing

We welcome contributions of all kinds! Whether you want to add new declarative agents, build reusable mesh workflows, or enhance core engine drivers:
- Read our [**Contributing Guide (`CONTRIBUTING.md`)**](CONTRIBUTING.md) for full development setup and Pull Request guidelines.
- Submit bug reports or feature requests via GitHub Issues.

---

## 📚 Master Architecture Specifications

All technical specifications are organized in the [`docs/`](docs) directory:

- [`01_PRD_PRODUCT_REQUIREMENTS_DOCUMENT.md`](docs/01_PRD_PRODUCT_REQUIREMENTS_DOCUMENT.md) - Vision & Product Requirements
- [`02_SYSTEM_ARCHITECTURE.md`](docs/02_SYSTEM_ARCHITECTURE.md) - System Component Architecture, Master Orchestrator & Pre-Flight Engine
- [`03_DECLARATIVE_AGENT_SPECIFICATION.md`](docs/03_DECLARATIVE_AGENT_SPECIFICATION.md) - DAM v3.0 OpenAgent Specification
- [`04_USER_INTERFACE_AND_CLI_PRESENTATION.md`](docs/04_USER_INTERFACE_AND_CLI_PRESENTATION.md) - Rich Terminal UI & Interactive Prompts
- [`04_CLI_ENGINE_SPECIFICATION.md`](docs/04_CLI_ENGINE_SPECIFICATION.md) - CLI Engine Command Reference
- [`05_DISCOVERY_AND_MARKETPLACE_REGISTRY.md`](docs/05_DISCOVERY_AND_MARKETPLACE_REGISTRY.md) - Marketplace Registry & Local AppData Store
- [`06_SECURITY_VAULT_AND_SANDBOXING.md`](docs/06_SECURITY_VAULT_AND_SANDBOXING.md) - Zero-Trust Vault & Sandbox Firewall
- [`07_RUNTIME_MCP_AND_DYNAMIC_BUILDER.md`](docs/07_RUNTIME_MCP_AND_DYNAMIC_BUILDER.md) - Model Context Protocol & JIT Builder
- [`08_HORIZONTAL_ECOSYSTEM_PROJECTS_AND_TOOLS.md`](docs/08_HORIZONTAL_ECOSYSTEM_PROJECTS_AND_TOOLS.md) - Horizontal Ecosystem Projects & Tools
- [`09_ECOSYSTEM_INTEGRATION_AND_DEVELOPMENT_ROADMAP.md`](docs/09_ECOSYSTEM_INTEGRATION_AND_DEVELOPMENT_ROADMAP.md) - Strategic Roadmap & Milestones
- [`10_DECLARATIVE_MESH_WORKFLOWS_AND_SCHEDULING.md`](docs/10_DECLARATIVE_MESH_WORKFLOWS_AND_SCHEDULING.md) - Mesh Workflows & Crontab Scheduling
- [`13_WORKSPACE_AND_PACKAGE_ENVIRONMENT_STRUCTURE.md`](docs/13_WORKSPACE_AND_PACKAGE_ENVIRONMENT_STRUCTURE.md) - Monorepo Package Environment

---

## 📄 License

Distributed under the **Apache License 2.0**. See [`LICENSE`](LICENSE) for details.

