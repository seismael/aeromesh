# User Experience & End-to-End Workflows

**Status:** v1.0.0

This document walks through **how AeroMesh is actually used** — the three core
experiences, what happens under the hood at each step, and why the design is
optimal.

---

## The mental model

AeroMesh is **"npm for AI agents, with security."** Just as `npm`/`pip` let you
`install` a library someone else wrote and trust it, AeroMesh lets you
`install` an **agent** — a signed JSON file — and `run` it with confidence.

The runtime is **Deep Agents** (LangChain's agent engine). AeroMesh only adds
the **packaging, trust, and safety** layer that Deep Agents does not provide.
There are exactly three things a user does:

---

## Experience 1 — The Author ("ship an agent")

```bash
amx init my-code-reviewer          # 1. scaffold a manifest
# 2. edit my-code-reviewer.agent.json (persona, tools, allowed_domains)
amx keygen                         # 3. create your signing identity (encrypted)
amx sign my-code-reviewer.json     # 4. sign it
amx share my-code-reviewer.json    # 5. produce a signed PR payload
```

**What you're actually doing:** you author a **JSON manifest**, not code. It
declares:

- `identity` — who the agent is (id, name, version, author, license).
- `capabilities` — what it does (domain, tags, description, trigger).
- `cognitive_runtime` — how it thinks (`persona`, `success_criteria`, driver).
- `requirements.providers` — what it needs (`mcp` tools, `credential`s,
  `sub_agent`s, `skill`s, `security`/`allowed_domains`).
- `observability` — optional budget (`cost_limit_usd`, `max_execution_steps`).

You then **cryptographically sign it** (Ed25519) so consumers can verify it is
really yours and untampered. Your private key is **encrypted at rest** (Fernet,
key held in the OS keyring).

**Why this is optimal:** you wrote zero Python, didn't vendor a framework, and
your agent is a **portable, reviewable, diffable, versionable artifact** — the
same thing a package manager expects. A reviewer reads the whole agent in one
screen of JSON.

---

## Experience 2 — The Consumer ("run someone else's agent safely")

```bash
amx install postgres-performance-tuner      # verifies signature + trusted signer
amx run postgres-performance-tuner "Optimize my slow join query"
```

**End-to-end, under the hood:**

1. **`install` verifies** the manifest's Ed25519 signature *and* that the signer
   matches `registry/trusted/<agent>.pub`, and that the key isn't revoked.
   Failure → refusal, before any code runs.
2. **`run` parses + validates** the manifest against the DAM schema
   (`AMX_ERR_SCHEMA_VIOLATION` on failure).
3. **`run` resolves credentials** (env → OS keyring → config).
4. **`run` compiles the manifest into `create_deep_agent()`** — inheriting
   Deep Agents' planning, subagents, skills, filesystem, and HITL.
5. **`run` wires the real model** (`init_chat_model`) and **the real MCP
   tools** (`langchain-mcp-adapters`). A declared MCP tool is a hard
   requirement: if its server can't be reached, `amx run` fails loudly
   (`AMX_ERR_MCP_SPAWN_FAILED`).
6. **`run` enforces the sandbox** — the agent's MCP tools' HTTP(S) egress is
   routed through an allowlist proxy; `allowed_domains` is deny-by-default.
7. **Deep Agents executes** — the model reasons and calls tools; an
   `output_contract` (JSON Schema) is enforced via `RubricMiddleware`.

**Why this is optimal:** you got a **safe, signed, sandboxed, vendor-neutral**
agent without writing any glue. The trust gate runs *before* execution, so a
tampered or revoked agent never starts.

---

## Experience 3 — Zero-code ("I need an agent I don't want to write")

```bash
amx run "build me an agent that reviews code for security vulnerabilities"
```

**What happens:** the **JIT synthesizer** asks a live LLM to *author* a DAM
manifest for the goal, schema-validates it (retrying on error), then runs it.
Live example output:

```json
{ "id": "security-code-reviewer", "domain": "software-security",
  "tags": ["code-review", "vulnerability-detection", "security-audit"],
  "persona": "expert security engineer with deep knowledge of common vulnerabilities…" }
```

**Why this is optimal:** the LLM is both *author* and *runtime* — from a
sentence to a running, signable agent in seconds, with no manifest editing.

---

## Why this experience is optimal — the design rationale

| Design choice | Why it's the right one |
|---|---|
| **JSON manifest, not code** | Portable, diffable, reviewable, LLM-authorable, vendor-neutral. |
| **Compile to Deep Agents** | Inherit planning/subagents/skills/HITL/memory for free — no re-implemented engine. |
| **Sign + verify + revoke** | The missing "trust" layer — provenance + revocation that MCP/Deep Agents don't provide. |
| **LLM authoring (JIT)** | Removes the last barrier: no format knowledge needed to create an agent. |
| **Deny-by-default sandbox** | A downloaded agent can't exfiltrate over HTTP unless its manifest explicitly allows a domain. |
| **Provider-agnostic manifest** | The DAM never hardcodes a model; the actual multi-provider runtime (DeepSeek / Claude / GPT / Gemini) is inherited from Deep Agents' `init_chat_model`. |
| **Hard tool requirement** | A declared MCP tool is guaranteed available, or the run fails loudly — no silent degradation. |

---

## Honest rough edges

1. **Natural-language runs can be slow** if the goal is ambiguous (the agent may
   legitimately do filesystem/subagent work). A focused synthesized persona and
   a default step cap keep this bounded.
2. **An MCP tool is a hard requirement** — its server must be reachable, or the
   run fails clearly.
3. **The sandbox is HTTP(S) egress allowlisting, not full OS isolation** — a
   determined malicious MCP server can bypass it via raw sockets. Real isolation
   (container/gVisor) is the top remaining milestone (see `SECURITY.md`).
4. **Distribution is git-based** — no hosted registry yet; discovery is the
   `registry/` directory, not a searchable marketplace.

---

## One-line summary

> **You declare an agent as signed JSON, or let the LLM write it for you; you
> `install` it with cryptographic verification; and you `run` it as a full Deep
> Agent — real model, real tools, sandboxed — with the model provider resolved by Deep Agents.**
