# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for security vulnerabilities. Instead, report
them privately to the maintainers at `firas.ismael@gmail.com`. We aim to acknowledge
within 48 hours and provide a fix or mitigation plan within a reasonable timeframe.

## Security model (v0.1)

AeroMesh's security posture rests on four mechanisms:

1. **Ed25519 attestation** — manifests are signed; `amx install` verifies the
   signature and the trusted signer, and refuses revoked keys.
2. **Encrypted signing key** — the author's private key is encrypted at rest
   (Fernet key held in the OS keyring).
3. **Deny-by-default network allowlist** — an agent's `allowed_domains` restricts
   its MCP tool egress via a local proxy.
4. **Encrypted credentials** — provider/tool secrets are stored in the OS keyring.

### Known limitations (honest)

- The **sandbox is HTTP(S) egress allowlisting, not full OS-level process
  isolation.** A malicious MCP server can bypass it via raw sockets, DNS, or by
  reading local files. Do **not** run untrusted agents on a host containing
  secrets you are not willing to expose. Full isolation (container/gVisor) is a
  planned milestone.
- Attestation is **self-contained Ed25519** (no Sigstore transparency log yet);
  there is no public append-only audit log of who signed what.
- There is **no multi-tenant trust boundary** in the git registry — the registry
  is a shared git repo whose commit access controls trust.

### How to add later (deferred hardening)

- **Full OS-level sandbox.** Run MCP stdio subprocesses inside a container /
  gVisor / Firecracker microVM with a read-only rootfs, no default network, and
  only the egress-proxy socket exposed, wired into `DeepAgentsExecutionDriver`'s
  MCP spawn path. Linux-centric; on Windows it needs Docker/WSL2 — which is why
  it is deferred rather than shipped today.
- **Sigstore transparency log.** `amx sign` additionally produces a keyless
  Sigstore bundle (GitHub OIDC → Fulcio ephemeral cert, logged to the public
  Rekor instance); `amx verify` checks the bundle against Rekor. Keep the
  self-contained Ed25519 path as an offline fallback. Needs external services,
  so it is a later milestone.

See `docs/16_ROADMAP_AND_DEFERRED.md` for the full deferred-items list.

## Supported versions

Only the latest commit on `main` is supported for security fixes. The software is
`0.1.0`; the DAM standard is `v0.1`. The sandbox is HTTP(S) egress allowlisting,
not full OS isolation — treat third-party agents accordingly.
