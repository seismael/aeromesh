# AGENTS.md: AeroMesh Repository Enforcement & Governance Layer

**Status:** Authoritative Repository Governance Standard  
**Applies To:** All AI Coding Agents, Subagents, and Software Engineers working on AeroMesh  

---

## 1. MANDATORY LOGICAL DEEP-THINKING & CONTINUOUS ALIGNMENT PROTOCOL

Before taking action on ANY user request (whether implementation, design, or debugging), every agent MUST execute the **4-Dimension Logical Alignment Audit**:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                   LOGICAL DEEP-THINKING & CONTINUOUS ALIGNMENT AUDIT                   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Dim A: GOVERNANCE EVOLUTION   │ Does this request require updating or enhancing        │
│                               │ AGENTS.md itself with new standards or rules?          │
├───────────────────────────────┼────────────────────────────────────────────────────────┤
│ Dim B: ARCHITECTURE ALIGNMENT │ Is there any conflict, drift, or synchronization gap    │
│                               │ between code, docs/ (01_PRD-13_WORKSPACE), & schemas?  │
├───────────────────────────────┼────────────────────────────────────────────────────────┤
│ Dim C: DESIGN EVALUATION      │ Is the proposed design optimal, or is a major systemic │
│                               │ improvement/enhancement required before proceeding?    │
├───────────────────────────────┼────────────────────────────────────────────────────────┤
│ Dim D: ENFORCEMENT & TDD      │ Which specific SOLID, OOD, DDD, TDD, and GoF patterns  │
│                               │ MUST be applied and empirically verified for this step?│
└───────────────────────────────┴────────────────────────────────────────────────────────┘
```

### 1.1 Dynamic Self-Updating Mandate
`AGENTS.md` is a living governance contract. Whenever a task or request discovers a superior engineering pattern, architectural rule, or workflow constraint, the agent **MUST update `.agents/AGENTS.md` immediately**.

### 1.2 Mandatory Documentation Synchronization Rule
No code modification or architectural enhancement is complete without synchronizing the corresponding design specifications in `docs/` and `schemas/declarative-agent.schema.json` in the same execution turn.

---

## 2. REPOSITORY TOPOLOGY & USER HOME APPDATA STANDARDS

### 2.1 Clean Repository Root Directory Layout
The repository root MUST adhere strictly to the following 5 top-level directories. No ad-hoc root scripts or `bin/` directories are permitted.

```
c:\dev\projects\aeromesh\
├── .agents/                    <-- Single Source of Truth Governance Layer
├── docs/                       <-- Authoritative Master Specifications (01_PRD to 13_ENV)
├── schemas/                    <-- JSON Schemas (DAM v3.0 OpenAgent Standard)
├── packages/                   <-- Enterprise Monorepo Packages (Clean Layered src/)
└── registry/                   <-- Git-as-a-Registry Agent Templates
```

### 2.2 User Home AppData Directory Standard (`~/.aeromesh/`)
All user runtime state, credentials, local registry caches, Virtual File System (VFS) context payloads, and OpenTelemetry diagnostic logs MUST be saved in the standard User Home AppData directory (`~/.aeromesh/` or `%USERPROFILE%\.aeromesh`):

```
~/.aeromesh/
├── config.json                 <-- User configuration & provider defaults
├── credentials.json            <-- Vault Keyring encrypted credentials fallback
├── cache/                      <-- Vector search index & DAM schema cache
├── vfs/                        <-- Virtual File System context payload offloads
├── logs/                       <-- OpenTelemetry diagnostic traces & logs
└── registry/                   <-- Local offline synced agent manifests
```

### 2.3 OS-Agnostic AppData Resolution Algorithm
All code interacting with user state MUST resolve AppData paths dynamically using `get_aeromesh_home()`, adhering to the following cross-platform priority:
1. `AEROMESH_HOME` environment variable (if explicitly set)
2. **Windows**: `%LOCALAPPDATA%\AeroMesh` (or `%APPDATA%\AeroMesh`)
3. **macOS**: `~/Library/Application Support/AeroMesh`
4. **Linux / POSIX**: `$XDG_DATA_HOME/aeromesh` (or `~/.local/share/aeromesh`)
5. **Fallback**: `~/.aeromesh`

---

## 3. ZERO-TRUST EXPLICIT USER KEY PERMISSION PROTOCOL

- **No Silent Environment Consumption**: Discovered credentials in `os.environ` or config files MUST NOT be silently consumed in interactive human sessions (`non_interactive=False`).
- **Explicit Human Approval UI**: `AMXTerminalUI.prompt_credential_approval()` MUST present discovered keys to the user for explicit approval, replacement, or rejection before execution.
- **Provider Preference Selection**: Users can select default model provider preferences (e.g. DeepSeek vs Anthropic vs OpenAI), which are persisted to `~/.aeromesh/config.json`.

---

## 4. UNCOMPROMISING SOFTWARE ENGINEERING MANDATES

### 4.1 SOLID Principles Enforcement
- **Single Responsibility (SRP)**: Each class/module has ONE reason to change. Parsers parse; Vaults authenticate; Drivers execute.
- **Open/Closed (OCP)**: Systems extend via pluggable adapters (`providers`, `CDI` drivers) without mutating core kernel code.
- **Liskov Substitution (LSP)**: All interface implementations (`ISecureVault`, `IMcpDriver`, `ICognitiveDriver`) MUST be 100% interchangeable in tests.
- **Interface Segregation (ISP)**: Expose small, role-specific interfaces (`IManifestIndexRecord` vs `AgentManifestAggregate`).
- **Dependency Inversion (DIP)**: Kernel depends strictly on abstractions (`ICognitiveDriver`, `ISecureVault`), never vendor APIs.

### 4.2 Object-Oriented & Domain-Driven Design (OOD / DDD)
- **Domain Boundaries**: Maintain strict separation across Bounded Contexts (Discovery, Manifest, Security, Runtime, Telemetry).
- **Aggregates & Entities**: Domain models (`AgentManifest`, `SecurityContext`) MUST be type-safe, immutable dataclasses.
- **Value Objects**: Encapsulate domain rules within immutable value objects.

### 4.3 Test-Driven Development (TDD)
- **TDD Workflow**: ALWAYS write failing unit tests in `tests/` BEFORE implementing feature logic.
- **Mocking**: Use mock drivers (`MockMcpDriver`, `EnvironmentCredentialVault`) to verify state transitions deterministically.

### 4.4 Gang of Four (GoF) Design Patterns
- **Strategy Pattern**: `IDiscoveryEngine` (Vector vs BM25 vs Cognitive Matcher).
- **Factory Pattern**: `ManifestFactory` for type-safe hydration from raw JSON text.
- **Adapter Pattern**: `IMcpDriver` adapting stdio/sse JSON-RPC streams to unified tool calls.
- **Observer / State Machine Pattern**: `C-Bus` event stream (`CBusStream`).
- **Proxy / Decorator Pattern**: `NetworkSandboxFirewall` wrapping tool calls to enforce domain allowlisting (`allowed_domains`).

---

## 5. MONOREPO PACKAGE TOPOLOGY & CLEAN LAYERED ARCHITECTURE

All implementation code MUST be placed within the corresponding isolated package under `packages/` following the **Clean Layered Architecture (`src/`)**:

```
packages/<package_name>/
├── pyproject.toml / package.json
├── tests/
│   ├── unit/                   <-- TDD Unit Tests
│   └── integration/            <-- End-to-End Integration Tests
└── src/
    └── <module_name>/
        ├── domain/             <-- Entities, Dataclasses, Value Objects, AMX_ERR_* (ZERO DEPS)
        ├── services/           <-- Use Cases, Business Services, Orchestrators
        ├── presentation/       <-- CLI Commands, Rich UI Layouts, HTTP Controllers
        └── infrastructure/     <-- Vault Keyrings, MCP Stdio Drivers, Repositories
```

---

## 6. DETERMINISTIC GUARANTEED AGENT PIPELINE ENGINE (DGAP)

- **Zero Non-Deterministic Flow Gaps**: Goal execution NEVER relies on generic, unvalidated, or non-deterministic agent flows.
- **Contract-Validated Pipelines**: Master Orchestrators (`amx pipeline`) MUST decompose high-level goals into pipelines of contract-validated declarative agents (`AgentManifest`).
- **Sequential Output Verification**: Every intermediate agent output MUST pass explicit validation before being fed into the next agent in the mesh.
- **Zero Floating Fallbacks**: If any agent output fails verification or missing credentials occur, execution terminates deterministically with machine-readable error codes (`AMX_ERR_*`).

---

## 7. DECLARATIVE MESH WORKFLOWS (DWM v1.0) & SCHEDULING

- **Reusable Workflow Manifests (`workflow.json`)**: Reusable DAG topologies encapsulating step dependencies, intent templates, and crontab schedules (`schedule`).
- **Workflow Engine (`amx workflow run`)**: Validates workflow manifests against [`schemas/declarative-workflow.schema.json`](file:///c:/dev/projects/aeromesh/schemas/declarative-workflow.schema.json) and executes step nodes with dependency resolution.
- **Crontab Scheduling (`amx workflow schedule`)**: Registers recurring workflow manifests into `~/.aeromesh/schedules.json` for automated daily, weekly, or hourly execution.

---

## 8. NON-BLOCKING ASYNCHRONOUS DAG CONCURRENCY & WORKER POOLS

- **Zero Blocking Queues**: Long-running agents (e.g., 30s LLM or heavy data processing) MUST NOT block unrelated independent steps in the workflow or other incoming requests.
- **Async Concurrency Engine (`AeroWorkflowEngine.execute_workflow_async`)**: Uses `asyncio` event loops and `ThreadPoolExecutor` worker pools to dispatch independent steps concurrently while async-awaiting specific `depends_on` prerequisite events.

---

## 9. TOKEN-EFFICIENT & HIGH-SIGNAL COMMUNICATION

- **Be Extremely Brief**: Use fragments, concise bullet points, and omit conversational fluff.
- **Clickable File Links**: ALWAYS create clickable markdown links using `file:///` scheme (e.g., [`13_WORKSPACE_AND_PACKAGE_ENVIRONMENT_STRUCTURE.md`](file:///c:/dev/projects/aeromesh/docs/13_WORKSPACE_AND_PACKAGE_ENVIRONMENT_STRUCTURE.md)).
- **Empirical Verification**: Never claim a task is complete without running build/test verification commands.
