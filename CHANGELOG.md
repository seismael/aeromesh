# Changelog

## 0.2.0

Focused release-governance and correctness update following the repository audit.

- Fail-closed local signer trust, exact runtime/resume revalidation, confined references, revocation and atomic state writes.
- Signed embedded dependency releases; recursive pins; operator policy bound to exact tool image, tool names and credentials; update diffs and execution receipts.
- Privileged production execution requires approved releases. Digest-pinned network-disabled containers replace the prior proxy-only security claim. Development mode is explicit.
- Scoped credentials, no desktop-token harvesting or automatic plaintext fallback, overwrite-resistant signing keys.
- HTTP utility preserves request/response semantics, returns redirects, rejects ambiguous framing and bounds resources.
- Deterministic input/output contracts, honest task status, supported-policy validation, model/call/output bounds and pre-call estimated budget admission.
- Correct workflow barriers, root/dependency context, unique run IDs, failure propagation, transactional sessions, immutable resume snapshots and concurrent-resume protection.
- Real referenced subagent compilation and tool-server provenance; unsupported phantom capabilities rejected.
- Explicit persisted tool-free synthesis, no accidental generation on missing paths.
- Packaged schemas, constrained dependencies, SDK parity, clean-wheel CI, real MCP and mandatory container checks, isolated manual live tests.
- Retired stale integration catalog and speculative specifications. Current examples and documentation describe only supported behavior.

## 0.1.0 (historical)

Initial declarative manifests, signing primitives and Deep Agents integration. Its installation, runtime verification, proxy, workflow and packaging limitations are addressed or explicitly rejected by 0.2; do not rely on the former security claims.
