# Horizontal Ecosystem Projects & Developer Tools Specification

> **Status: aspirational roadmap — not implemented.** This document describes a 10-package ecosystem that does not exist. The shipped v0.1 is `packages/aero` (+ `packages/sdk-python` and a stub `packages/vscode-extension`). No Sigstore/Cosign, no `core-kernel`, no `studio-web`, no `desktop-app`, etc.

**Document Version:** 1.0.0 (Authoritative Final Release)  
**Package Directory:** `packages/`  
**Ecosystem Scope:** 10 Modular Horizontal Sub-Projects  

---

## 1. Executive Summary & Monorepo Package Layout

To maximize community adoption, developer productivity, and platform scalability, AeroMesh provides ten horizontal projects organized in an enterprise monorepo workspace:

```
c:\dev\projects\aeromesh\packages/
├── core-kernel/       <-- Core Abstractions, Interfaces & DAM v3.0 Models
├── cli-engine/        <-- AMX Standalone CLI (`amx`)
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

## 2. Detailed Project Specifications

### 2.1 Multi-Language Kernel SDKs (`packages/sdk-python`, `packages/sdk-typescript`, `packages/sdk-go`)
- **Python**: `pip install aeromesh-sdk`
- **TypeScript**: `npm install @aeromesh/sdk`
- **Go**: `go get github.com/aeromesh/sdk-go`
- **Function**: Allows third-party applications to embed the AeroMesh Cognitive Kernel directly into custom software without launching external processes.

### 2.2 AeroMesh Visual Studio (`packages/studio-web`)
- **Technology**: React 19, TypeScript, WebAssembly (WASM), Tailwind CSS.
- **Function**: Visual node graph builder for composing DAM v3.0 manifests, configuring MCP tool bindings, and testing prompt outputs in real time.

### 2.3 VS Code IDE Extension (`packages/vscode-extension`)
- **Technology**: TypeScript, VS Code Extension API.
- **Function**: Provides live JSON Schema validation for `agent.json` files, autocomplete for MCP tools, inline vault secret resolution warnings, and one-click `amx run` execution.

### 2.4 Agent Testing Harness (`packages/test-harness`)
- **Technology**: Python (`pytest`), Mock Drivers (`MockMcpDriver`, `MockVault`).
- **Function**: Provides automated unit and integration testing frameworks for benchmarking declarative agent manifests before publishing to registry.

### 2.5 AeroMesh Desktop Application (`packages/desktop-app`)
- **Technology**: Tauri, Rust, React, TypeScript.
- **Function**: Cross-platform desktop launcher providing local system tray management, active daemon monitoring, and local agent execution controls.

### 2.6 Web Hub & Marketplace (`packages/web-hub`)
- **Technology**: Next.js, React, Tailwind CSS, Algolia/Typesense.
- **Function**: Open web platform (`aeromesh.dev`) for searching, filtering, inspecting, and installing community-published declarative agent manifests.

### 2.7 Cloud Serverless Daemon (`packages/cloud-daemon`)
- **Technology**: Go / Python Docker Container.
- **Function**: Headless daemon for running scheduled cron workflows or reacting to incoming Webhook events in cloud environments.

### 2.8 Enterprise MCP Gateway (`packages/mcp-gateway`)
- **Technology**: Go, gRPC, OAuth2 / OIDC.
- **Function**: Enterprise reverse proxy enforcing rate limiting, central OAuth2 IAM mapping, and enterprise audit logging for remote SSE MCP servers.

### 2.9 Security Guardian & Attestation Scanner (`packages/guardian-scanner`)
- **Technology**: Python, Sigstore, Cosign.
- **Function**: Performs static security analysis on manifests, checks for prompt injection patterns, and verifies Sigstore digital signatures.

### 2.10 Telemetry & Evaluation Framework (`packages/telemetry-eval`)
- **Technology**: OpenTelemetry (OTel), Python.
- **Function**: Emits standard OTel traces for agent discovery, vault authentication, MCP tool calls, and LLM token cost metrics.
