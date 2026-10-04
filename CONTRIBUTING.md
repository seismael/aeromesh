# Contributing

AeroMesh is a focused configuration, approved-release and execution-policy layer on Deep Agents. Keep the runtime native; do not add speculative schema fields or security claims without implemented semantics and negative tests.

1. Read `.agents/AGENTS.md` and the architecture/security documentation.
2. Reproduce the user-visible defect with a failing regression first.
3. Make the bounded implementation change; preserve fail-closed defaults and explicit development opt-in.
4. Update documentation and migration notes when behavior changes.
5. Run `pytest packages/aero/tests -q`, real local MCP tests, and distribution checks. Container or provider checks must be explicitly reported as passed, failed or not exercised.

Use explicit test fixtures for model substitutes. Keep production code free of fake outputs. Test actual transport, scheduling, filesystem and crypto boundaries where those are the claim; avoid tests that only repeat a mapping implementation.

Do not commit credentials, signing private keys, local approvals, sessions, receipts or build products. Public examples are unsigned drafts. A signature does not prove a code review or independent safety evaluation.
