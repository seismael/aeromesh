# AeroMesh engineering rules

Applies to all engineers and agents working in this repository.

## Product boundary

AeroMesh is a versioned configuration and approved-release layer on LangChain Deep Agents. Native Deep Agents and LangGraph implement execution and graph scheduling. The current production tool boundary is a reviewed digest-pinned container with no network and no host mounts. Unsupported capabilities fail closed; development mode is explicit and untrusted.

## Required engineering behavior

- Use failing regressions first for behavior changes, then minimal implementation and verification.
- Keep production execution real; model/test substitutes belong only in tests and explicit fixtures. No import-time global test patches.
- Preserve dependency direction: presentation → services → infrastructure → domain. Do not rebuild the native agent runtime.
- Verify trust and active policy on the exact artifact used. Signing must not implicitly grant local trust or tool permissions.
- Never expose undeclared credentials or silently downgrade secure storage to plaintext.
- Implement each accepted schema field or reject it. Unsupported options must not be ignored.
- Do not equate a signature, static lint, nonempty model response, or schema-valid output with safe code or successful business outcomes.
- Keep schemas, README, operational guidance and the v1 acceptance matrix synchronized with behavior.
- Run `pytest packages/aero/tests -q` before claiming completion. Also exercise actual MCP transport, package installations and relevant container tests for changes to those boundaries.
- Record exact verification results and explicitly identify unavailable live/provider/container checks. Do not label skipped checks as passed.
- Cite concrete file paths. Keep communication concise and focused on behavior and evidence.

## Source layout

`packages/aero/src/aero`: domain models/paths/errors, infrastructure primitives, services for releases/policy/runtime/workflows/sessions, presentation CLI/UI. `schemas` is the canonical supported configuration format and is embedded in distributions. `packages/sdk-python` delegates to the same checked service paths. `registry` holds unsigned example drafts, never automatic trust roots. `tests_system` exercises real local transport and isolation outside model-substitute tests.
