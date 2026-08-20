# Workspace Package Environment & Layered Component Architecture Specification

> **Status: aspirational — not the shipped layout.** The actual v0.1 layout is in `README.md`; there is no `core-kernel`, `guardian-scanner`, or 10-package monorepo.

**Document Version:** 1.0.0 (Authoritative Final Release)  
**Architectural Pattern:** Enterprise Monorepo & Clean Layered Architecture (`packages/<package_name>/src/`)  
**Target Core Engine:** AeroMesh Cognitive Kernel (AMCK)  

---

## 1. Clean Repository Root Directory Layout

To maintain an un-cluttered, enterprise-grade repository structure, the root of the AeroMesh workspace contains exclusively five top-level directories:

```
c:\dev\projects\aeromesh\
├── .agents/                    <-- Single Source of Truth Governance Layer
├── docs/                       <-- Authoritative Master Specifications (01_PRD to 13_ENV)
├── schemas/                    <-- JSON Schemas (DAM v3.0 OpenAgent Standard)
├── packages/                   <-- Enterprise Monorepo Packages (Clean Layered src/)
└── registry/                   <-- Git-as-a-Registry Agent Templates
```

*Note: No ad-hoc `bin/` directories or root scripts are permitted. Executables are installed via standard `pyproject.toml` console scripts (`amx = aero.presentation.cli:main`).*

---

## 2. User Home AppData Directory Specification (`~/.aeromesh/`)

All user runtime state, credentials, local registry caches, Virtual File System (VFS) context payloads, and OpenTelemetry diagnostic logs MUST be saved in the standard User Home AppData directory (`~/.aeromesh/` or `%USERPROFILE%\.aeromesh`):

```
~/.aeromesh/                           <-- (C:\Users\<user>\.aeromesh on Windows)
├── config.json                        <-- User configuration & provider defaults
├── credentials.json                   <-- Encrypted Keyring fallback store
├── cache/                             <-- Schema & Vector index cache
├── vfs/                               <-- Virtual File System context payload offloads
├── logs/                              <-- OTel diagnostic traces & execution logs
└── registry/                          <-- Local offline synced agent manifests
```

---

## 3. Monorepo Package Topology (`packages/`)

```
packages/
├── core-kernel/       <-- Core Abstractions, Interfaces & DAM v3.0 Models
├── aero/              <-- Aero Standalone Agent Engine (`aero` / `amx`)
├── discovery-index/   <-- 2-Tier Vector & Cognitive Discovery Search Engine
├── mcp-driver/        <-- Stdio & SSE MCP Transport Daemons & LangGraph Driver
├── security-vault/    <-- Zero-Trust Vault Cascade & Sandbox Firewall
├── jit-builder/       <-- JIT Manifest Synthesizer
├── sdk-python/        <-- Embeddable Python Kernel SDK
├── sdk-typescript/    <-- Embeddable Node.js/TS Kernel SDK
├── sdk-go/            <-- Embeddable Go Kernel SDK
├── studio-web/        <-- AeroMesh Visual Studio (React/Wasm Drag-and-Drop)
├── vscode-extension/  <-- VS Code IDE Plugin (IntelliSense & Debugger)
├── test-harness/      <-- Agent & MCP Testing Framework
├── desktop-app/       <-- Tauri/Rust Desktop Application Launcher
├── mcp-gateway/       <-- Enterprise Go Proxy Gateway with OAuth2 IAM
├── guardian-scanner/  <-- Static Security Analysis & Sigstore Attestor
└── telemetry-eval/    <-- OpenTelemetry Tracing & Cost Tracker
```

---

## 4. Clean Layered Package Internal Architecture (`src/`)

Every package within `packages/` is internally organized into four strict Onion Architecture layers:

```
packages/<package_name>/
├── pyproject.toml / package.json
├── tests/
│   ├── unit/                   <-- TDD Unit Tests (Fast, Isolated)
│   └── integration/            <-- End-to-End Integration Tests
└── src/
    └── <module_name>/
        ├── domain/             <-- Entities, Dataclasses, Value Objects, Errors (ZERO DEPS)
        ├── services/           <-- Use Cases, Business Services, Orchestration Logic
        ├── presentation/       <-- CLI Commands, Rich UI Terminal Layouts, Web Views
        └── infrastructure/     <-- Vault Keyrings, Subprocess Drivers, Repositories
```
