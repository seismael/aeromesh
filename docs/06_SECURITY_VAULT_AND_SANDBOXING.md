# Security: Attestation, Vault, and Sandbox (v0.1)

**Status:** v0.1 — matches the implemented code.

## 1. Attestation (Ed25519)

- `amx keygen` generates an Ed25519 keypair under `~/.aeromesh/keys/`.
- `amx sign <manifest>` writes a `<manifest>.sig` sidecar: `{algorithm, sha256, public_key, signature}` over the canonical (sorted-key) JSON.
- `amx verify <manifest>` cryptographically verifies the sidecar.
- `amx install` verifies the signature **and** that it matches `registry/trusted/<agent_id>.pub`; mismatches are refused (`--insecure` opts out).

This is honest, self-contained signing — **not** Sigstore (no transparency log / CA in v0.1).

## 2. Credential vault

Credentials are resolved in this order: override env → process env → **OS keyring** (encrypted, primary) → `~/.aeromesh/credentials.json` (plaintext fallback, only if the keyring is unavailable) → `~/.aeromesh/config.json` → desktop `tokens.txt`.

- **Interactive sessions**: discovered keys require explicit user approval before use.
- **Non-interactive sessions**: keys are used directly; a missing required credential raises `AMX_ERR_VAULT_KEY_MISSING`.

> **Honesty note:** new secrets are stored encrypted in the OS keyring; the plaintext `credentials.json` is written only as a loudly-warned fallback when no OS keyring is available.

## 3. Network sandbox

`NetworkSandboxFirewall` enforces a manifest's `allowed_domains`:

- Exact and `*.suffix` wildcard matching.
- A local egress proxy (`LocalEgressProxy`) injects `HTTP_PROXY`/`HTTPS_PROXY` into MCP stdio subprocesses so their outbound HTTP(S) is gated by the allowlist (CONNECT tunneling for HTTPS).
- Violations raise `AMX_ERR_DOMAIN_BLOCKED` (exit 21).

> **Honesty note:** this is HTTP(S) egress allowlisting, **not** full OS-level isolation — a malicious MCP server can bypass it via raw sockets or DNS. See `SECURITY.md`.

## 4. Static scan (`amx audit`)

`GuardianSecurityScanner` flags hardcoded secrets (`sk_live_`, `ghp_`, `AKIA`) and unrestricted `*` wildcards in `allowed_domains`, and reports a SHA-256 digest.
