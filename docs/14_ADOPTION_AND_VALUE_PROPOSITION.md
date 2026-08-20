# AeroMesh — Adoption & Value Proposition

**Status:** v0.1 · built on LangChain Deep Agents · Apache-2.0

---

## One line

**AeroMesh is the declarative standard + trust boundary for AI agents — "npm for agents, with security" — on top of Deep Agents.**

## The problem

The AI-agent stack has three layers that are being solved independently, and one layer that is not:

| Layer | Solved by |
|---|---|
| Agent **runtime** (planning, subagents, skills, memory, HITL) | Deep Agents / LangGraph |
| Tool **protocol** | MCP |
| Agent-to-agent **interop** | A2A / ANP / ACP |

**What's missing:** a standard way to **declare**, **distribute**, **verify**, and **safely execute** an agent — so you can share an agent the way you share a package, with the same confidence (`pip install` / `npm install` level of trust).

## What AeroMesh is

A **declarative agent manifest (DAM v0.1)** that compiles into `create_deep_agent()`, plus the trust/sandbox layer Deep Agents does not provide:

1. **DAM v0.1** — a JSON manifest (identity, capabilities, persona, `mcp`/`sub_agent`/`skill`/`credential` providers, `allowed_domains`).
2. **LLM-driven synthesis** — a live model authors a schema-valid manifest from a natural-language goal.
3. **Ed25519 trust** — `keygen`/`sign`/`verify`; `install` refuses unsigned/untrusted agents.
4. **Sandbox** — deny-by-default `allowed_domains` + an egress proxy on MCP tool subprocesses.
5. **Real execution** — real LLM (`init_chat_model`), real MCP tools (`langchain-mcp-adapters`), output verification (`RubricMiddleware`).

## Benefits

- **Provider-agnostic manifest** — a DAM declares *intent*, not a specific model provider; Deep Agents resolves the provider (DeepSeek / Anthropic / OpenAI / Gemini) at runtime.
- **No code** — agents are JSON; an LLM can author them.
- **Trust** — prove who signed an agent and that it wasn't tampered with.
- **Safety** — a third-party agent's network egress is allowlisted.
- **Governance** — a signed registry = an auditable approval boundary.

## Use cases

- **Enterprise agent governance** — a signed registry of approved agents; engineers install + run verified, sandboxed agents.
- **Vendor-neutral packaging** — one manifest, any provider Deep Agents supports, with no manifest changes.
- **On-demand authoring** — "build me an agent that reviews code for vulnerabilities" → a runnable manifest.
- **Safe third-party agents** — download an agent and run it with confidence + restricted egress.

## Target adopters

- **Platform/DevEx teams** building internal agent registries and governance.
- **Security teams** that need auditable, signed, sandboxed agent distribution.
- **Agent builders** who want a provider-agnostic, declarative packaging format.
- **Enterprises** standardizing on "agents as signed artifacts" (like images/packages).

## Differentiation — why not just MCP or Deep Agents?

| | MCP | Deep Agents | AeroMesh |
|---|---|---|---|
| Tool protocol | ✅ | — | consumes MCP |
| Agent runtime | — | ✅ | delegates to it |
| **Declarative agent format** | ❌ | ❌ (code/config, not a standard) | ✅ **DAM v0.1** |
| **Signed distribution + verification** | ❌ | ❌ | ✅ **Ed25519** |
| **Sandboxed execution of third-party agents** | ❌ | ❌ | ✅ **deny-by-default + egress proxy** |
| **LLM-authored agents** | ❌ | ❌ | ✅ **JIT synthesis** |

**AeroMesh is not a competitor to MCP or Deep Agents — it's the missing layer on top of both.**

## Why now

Declarative agent manifests and "trusted agent marketplaces" are an active, forming standard (e.g. the W3C `agent.json` + trust-scoring proposal). AeroMesh is a working reference for that layer, with the security/trust angle that the framework and protocol layers don't cover.

## Honest limitations (v0.1)

- Registry is **git-based** (no hosted registry service yet).
- Attestation is **self-contained Ed25519** (no Sigstore transparency log yet).
- Sandbox gates **HTTP(S) egress** (not arbitrary raw sockets).

## How to adopt

```bash
pip install -e packages/aero
amx init my-agent && amx keygen && amx sign my-agent.json
amx run "build me an agent that …"     # LLM authors + runs it
```

See `README.md` for the full quickstart and `docs/` for the DAM spec, architecture, and security model.
