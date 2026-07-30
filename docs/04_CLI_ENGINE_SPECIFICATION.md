# Aero Agent Engine (`aero` / `amx`) Specification

**Document Version:** 1.0.0 (Authoritative Final Release)  
**Package Name:** `packages/aero`  
**Executable Command:** `amx`  
**Terminal UI Framework:** Python `rich` & `textual`  
**Default Driver:** LangGraph & LangChain Deep Agents Driver (`Driver.LangGraph`)  

---

## 1. Executive Summary: The Aero Standalone Agent Engine

`aero` is the standalone cognitive agent engine of the AeroMesh ecosystem.

To deliver a world-class developer experience, AeroMesh decouples **Terminal Presentation & Command Management (`packages/aero`)** from **Cognitive Graph Execution (`Driver.LangGraph`)**.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                         AERO STANDALONE AGENT ENGINE (`aero` / `amx`)                  │
│                         (packages/aero - Rich UI & API Interfaces)                     │
│                                                                                        │
│ • CLI Command Parsing (`amx run`, `amx search`, `amx validate`, `amx build`, `--replay`)│
│ • Rich Terminal Layout (Colored Panels, Status Spinners, Tables, Syntax Highlighting)  │
│ • Interactive Key Vault Credentials Prompting & Mutex Confirmations                     │
│ • Local Git-as-a-Registry Index Ingestion (`registry/index.json`)                      │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ (Passes Manifest + Credentials)
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│               LANGGRAPH & DEEP AGENTS EXECUTION ENGINE (`Driver.LangGraph`)            │
│                                                                                        │
│ • StateGraph Node Execution & Task Planning (`write_todos`)                            │
│ • Virtual File System (VFS) Payload Offloading (`/vfs/data.json`)                      │
│ • LangGraph State Snapshot Checkpointing (`SqliteSaver`)                               │
│ • MCP Tool Execution & Sub-Agent Swarm Delegation                                      │
└────────────────────────────────────────────────────────────────────────────────────────┘
```
