# Roadmap & Deferred Items

> Honest status: what's shipped vs deferred, with *why* and *how to do it later*.
> This is the authoritative "remaining items" list.

## Shipped (v0.1.0)

- DAM v0.1 declarative standard + JSON schema + parser.
- Ed25519 sign/verify/revoke; encrypted signing key at rest; encrypted credentials (OS keyring).
- Deep Agents execution (real model via `init_chat_model`, real MCP tools, `RubricMiddleware`).
- Egress sandbox (deny-by-default `allowed_domains` + local HTTP(S) egress proxy).
- Persistent sessions (SQLite checkpointer + store; `amx history` / `amx run --replay`).
- Real BM25 search (`amx search`); git-as-registry index (`registry/index.json`, `amx index`).
- LLM-driven JIT synthesis (`amx run "<goal>"`).
- Live-model CI (opt-in via `DEEPSEEK_API_KEY` secret; `packages/aero/tests_live/`).

## Deferred

### 1. Full OS-level sandbox (container / gVisor / Firecracker)
- **Today:** `allowed_domains` gates HTTP(S) egress only; raw sockets, DNS, and
  local file reads are still possible for a malicious MCP server.
- **Why later:** a real isolation boundary is a heavy, Linux-centric dependency
  (Docker/WSL2 on Windows) and out of scope for a portable CLI v1.
- **How later:** run MCP stdio subprocesses in a container/gVisor/Firecracker
  microVM (read-only rootfs, no default network, only the egress-proxy socket),
  wired into `DeepAgentsExecutionDriver`'s MCP spawn path.
- **Refs:** `SECURITY.md`.

### 2. Sigstore / transparency-log attestation
- **Today:** self-contained Ed25519; no public append-only log of who signed what.
- **Why later:** needs external services (Fulcio OIDC CA + Rekor log) or a
  self-hosted log.
- **How later:** `amx sign` also emits a keyless Sigstore bundle (GitHub OIDC →
  Fulcio, logged to public Rekor); `amx verify` checks the bundle. Keep Ed25519
  as the offline fallback.
- **Refs:** `SECURITY.md`.

### 3. Hosted marketplace (web hub)
- **Today:** git-as-registry (`registry/index.json` + `registry/agents/` +
  `registry/trusted/`).
- **Why later:** hosting/search infra is overkill while the ecosystem is small.
- **How later:** serve `registry/index.json` from a static host (GitHub Pages /
  raw.githubusercontent.com) and add `amx search --remote` / `amx publish`
  against it; keep git as the source of truth.

### 4. Semantic / embedding search
- **Today:** real BM25 lexical search (no fakes).
- **Why later:** embeddings add a provider/network dependency; BM25 is enough for
  a small registry.
- **How later:** add a vector index (local sentence-transformers, or Gemini
  `text-embedding-004`) and LLM-rerank the BM25 top-N.

### 5. Multi-language SDKs + a real VS Code extension
- **Today:** thin Python SDK; VS Code extension is a `package.json` stub.
- **How later:** implement the extension (schema validation + one-click run);
  TS/Go SDKs that wrap the `amx` CLI (the runtime is Python).

### 6. Workflow engine (multi-agent orchestration as signed artifacts)
- **Status:** shipped in v0.1.0 — `amx workflow` (DWM v0.1) compiles a signed DAG
  of verified agents into a LangGraph `StateGraph` of Deep Agents; `install`
  enforces recursive trust. See `docs/10`.
