# Security

Report suspected vulnerabilities privately to firas.ismael@gmail.com. Include the affected version, reproducible steps and the security boundary involved. Do not publish credentials or test against third-party deployments without authorization.

## V1 supported boundary

AeroMesh 1.x verifies exact manifest and release contents against explicitly approved local signer keys. Production tool and credential capabilities additionally require an independently approved release policy. Recursive dependencies are embedded and content-pinned; artifact identity mismatches, path escapes and unsupported capabilities fail before execution. A signature establishes content integrity and key possession. Operators remain responsible for reviewing publisher identity, agent instructions and tool code.

Trusted MCP tools run in reviewed, preloaded, digest-pinned Linux containers whose images declare no volumes, with network disabled, no host mounts, read-only root filesystems, non-root identity, dropped capabilities and resource limits. The host OS, Docker engine and approved runtime dependencies form part of the trusted deployment. A malicious image can still manipulate its allowed inputs and outputs. The model provider receives the task data and tool outputs sent to it, outside the tool container network namespace.

Per-tool credential bindings deliver only explicitly approved secrets. The parent environment is not copied wholesale into tools. Stored signing material and tool credentials use encryption backed by supported native OS keyrings: Windows Credential Locker, macOS Keychain, Secret Service/libsecret or KWallet. Arbitrary plugins and plaintext backends are rejected; missing or inaccessible secure storage causes failure. Explicit environment credentials are resolved without requiring secret storage. Signing encryption keys are scoped to the state directory and protected against concurrent initialization. Model-provider authentication is separate caller configuration and is not automatically granted to tools.

## Scope and limitations

- Development mode permits host commands and remote endpoints with the caller's authority. Its optional HTTP utility is not process containment.
- Production networked tools, remote MCP, arbitrary skills/plugins and unsupported policy declarations are rejected.
- Same-user/root compromise, kernel/container-runtime escapes and hostile Python callers are outside this boundary. Python SDK callers have their host process's authority.
- JSON Schema validates structure. The model's factual accuracy and task success require independent workload evaluation.
- Receipts are local records that the deployment administrator can modify. Native checkpoints can retain conversation data; ephemeral execution avoids durable conversation checkpoints.
- Revocation is checked at new execution and resume boundaries. It does not terminate running processes. Workflow effects have no transactional rollback or exactly-once guarantee.

Protect application code, trust roots, policy files, credentials and local state with the deployment's OS controls. Review [operations](docs/OPERATIONS.md) for key management, retention and recovery, and [validation](docs/VALIDATION.md) for exercised checks. Security fixes target the supported AeroMesh 1.x release line.
