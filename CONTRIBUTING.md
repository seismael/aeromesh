# Contributing to AeroMesh

Thank you for your interest in contributing to **AeroMesh**! We welcome and deeply appreciate contributions from developers, researchers, AI engineers, and open-source enthusiasts around the world.

AeroMesh is an open-source, enterprise-grade autonomous AI agent ecosystem and declarative mesh workflow engine built on the **Declarative Agent Manifest (DAM v3.0)** standard.

---

## 📜 Table of Contents

- [Code of Conduct](#-code-of-conduct)
- [Ways to Contribute](#-ways-to-contribute)
  - [1. Submitting New Declarative Agents](#1-submitting-new-declarative-agents)
  - [2. Submitting Declarative Mesh Workflows](#2-submitting-declarative-mesh-workflows)
  - [3. Core Engine & Package Enhancements](#3-core-engine--package-enhancements)
  - [4. Reporting Bugs & Security Issues](#4-reporting-bugs--security-issues)
- [Local Development Setup](#-local-development-setup)
- [Pull Request Process](#-pull-request-process)
- [Coding Standards & Conventions](#-coding-standards--conventions)

---

## 🤝 Code of Conduct

We are committed to providing a welcoming, inclusive, and respectful community for everyone. Please maintain professional communication, constructiveness, and mutual respect in all issues, pull requests, and discussions.

---

## 💡 Ways to Contribute

### 1. Submitting New Declarative Agents
You can contribute new pre-configured agent manifests to the [`registry/agents/`](registry/agents) directory!
- Ensure your manifest validates against [`schemas/declarative-agent.schema.json`](schemas/declarative-agent.schema.json):
  ```bash
  amx validate registry/agents/your-agent.json
  ```
- Test your agent with a sample intent:
  ```bash
  amx run registry/agents/your-agent.json "Sample intent description"
  ```

### 2. Submitting Declarative Mesh Workflows
You can contribute reusable multi-agent DAG topologies to the [`registry/workflows/`](registry/workflows) directory!
- Ensure your workflow manifest validates against [`schemas/declarative-workflow.schema.json`](schemas/declarative-workflow.schema.json).
- Verify step node dependencies and non-blocking execution:
  ```bash
  amx workflow run registry/workflows/your-workflow.json
  ```

### 3. Core Engine & Package Enhancements
Want to improve the engine performance, add new MCP drivers, or build monorepo packages under `packages/`?
- Follow the **Clean Layered Architecture** (`domain/`, `services/`, `presentation/`, `infrastructure/`).
- Follow **Test-Driven Development (TDD)** by adding unit and integration tests under `tests/`.

### 4. Reporting Bugs & Security Issues
Found a bug or security issue? Please open a GitHub Issue with:
- Clear steps to reproduce
- Expected vs actual behavior
- Relevant diagnostic output (`--diagnostics`)
- System OS environment details

---

## 🛠️ Local Development Setup

1. **Fork and Clone the Repository**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/aeromesh.git
   cd aeromesh
   ```

2. **Set Up Python Virtual Environment**:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. **Install Package in Editable Mode**:
   ```bash
   pip install -e packages/aero
   pip install pytest pytest-asyncio
   ```

4. **Run Automated Test Suite**:
   ```bash
   python -m pytest packages/aero/tests/
   ```

---

## 🚀 Pull Request Process

1. **Create a Feature Branch**:
   ```bash
   git checkout -b feat/your-feature-name
   ```

2. **Verify Tests**:
   Ensure all 39+ unit and integration tests pass before submitting:
   ```bash
   python -m pytest packages/aero/tests/
   ```

3. **Commit your Changes**:
   Follow Conventional Commits formatting:
   - `feat(core): add new capability`
   - `fix(vault): fix key resolution edge case`
   - `docs(readme): improve quickstart instructions`

4. **Push & Open Pull Request**:
   Push your branch and open a Pull Request against the `main` branch of [`seismael/aeromesh`](https://github.com/seismael/aeromesh).

---

## 📐 Coding Standards & Conventions

- **SOLID & GoF Patterns**: Strictly adhere to Object-Oriented Design (OOD) and Domain-Driven Design (DDD).
- **Type Annotations**: Use Python type hints on all public interfaces and methods.
- **Error Handling**: Use domain error hierarchy (`AeroMeshDomainError`) with machine-readable codes (`AMX_ERR_*`).
- **OS-Agnostic Paths**: Always resolve user home paths dynamically using `get_aeromesh_home()`.

Thank you for building the future of open autonomous agent swarms with us! 🚀
