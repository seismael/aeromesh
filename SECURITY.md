# Security

Report suspected vulnerabilities privately to firas.ismael@gmail.com; do not publish credentials or exploit against third-party deployments.

## Supported boundary in 0.2

Trusted execution verifies exact manifest/release contents and explicit local signer approval. Production tool/credential capabilities additionally require an independently approved release policy. Recursive dependencies are embedded/pinned; arbitrary ID paths and unsupported features are rejected. Signing proves integrity and key possession, not code safety or author reputation.

Trusted MCP runs in reviewed, preloaded digest-pinned Linux containers with network disabled, no host mounts, read-only rootfs, nonroot identity, dropped capabilities and resource limits. Container images can still be malicious within their granted scope; the host OS, Docker daemon and approved runtime dependencies are trusted. The model provider receives the inputs/tool outputs passed to it and is outside the tool network namespace.

Per-tool credential bindings deliver only explicitly approved secrets. Runtime code does not copy the parent environment into each tool. Secure OS keyring failures never silently downgrade signing-key or tool-credential storage to plaintext. Model authentication is separate caller configuration and is not granted to tools automatically.

## Explicit exclusions

- Development mode is not a sandbox. Host commands and remote endpoints have the caller's authority. Its optional HTTP utility does not contain malicious processes.
- Networked production tools, production remote MCP, arbitrary skills/plugins and unsupported policy declarations are rejected.
- Same-user/root compromise, kernel/container-runtime escapes, hostile Python code embedded in the caller and arbitrary model behavior are outside this boundary.
- JSON Schema validates shape, not truth or completion. Task assessment remains unverified.
- Receipts are mutable local evidence, not independent notarization. Native checkpoints retain conversation data unless ephemeral behavior is selected.
- Revocation is checked at new execution/resume boundaries; it does not terminate already running processes. Workflow actions are not transactional or exactly-once.

See [operations](docs/OPERATIONS.md) for key management, retention and recovery and [validation](docs/VALIDATION.md) for exercised checks. Only the current supported 0.2 code line receives security fixes; legacy 0.1 behavior should not be used as a security boundary.
