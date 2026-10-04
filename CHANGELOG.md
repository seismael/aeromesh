# Changelog

## 1.0.0

Initial AeroMesh release: approved, reproducible agent configuration and controlled tool execution on LangChain Deep Agents and LangGraph.

- Signed releases embed the complete agent dependency graph with recursive content pins and exact container image digests.
- Explicit local signer trust, fingerprint revocation and independent operator policies are checked against the artifacts used at execution and resume.
- Production MCP tools run in preloaded, network-disabled Linux containers with read-only filesystems, non-root identity, scoped credentials and resource limits.
- Versioned schemas accept implemented agent and workflow behavior, with deterministic input/output contracts and explicit task-assessment status.
- Native workflow dependency barriers, isolated execution identities and failure propagation provide predictable DAG scheduling.
- Immutable session snapshots, transactional metadata, concurrent-resume protection and controlled MCP process lifetimes support reliable operation.
- Model-call, output, execution and estimated-budget controls bound execution; local receipts record approved identities and observed outcomes.
- The CLI and Python SDK share the same execution services. Source distributions and wheels include runtime schemas.
- Reviewed example drafts, an actual local MCP tool, operational guidance and automated release gates support adoption.

Production tool support is scoped to offline containers. Live-model and domain-specific qualification are deployment gates; output shape validation does not establish task correctness.
