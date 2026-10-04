# Contributing

AeroMesh provides approved agent releases and enforceable execution policy on Deep Agents. Keep the runtime native and every public capability tied to implemented behavior and verification.

1. Read [.agents/AGENTS.md](.agents/AGENTS.md), [architecture](docs/ARCHITECTURE.md), [security](SECURITY.md) and the [v1 acceptance matrix](docs/VALIDATION.md).
2. Reproduce a behavior defect with a failing regression that exercises the affected boundary.
3. Make the focused implementation change. Preserve fail-closed production defaults and explicit development opt-in.
4. Keep schemas, CLI/SDK interfaces, examples and operational documentation consistent. Reject options whose semantics are unsupported.
5. Run the required acceptance gates and report each relevant container/provider check as passed, failed or not exercised.

## Development environment

From the repository root, in an activated Python 3.11–3.13 virtual environment:

```bash
python -m pip install -c constraints/ci-python.txt -e 'packages/aero[dev]' -e packages/sdk-python
python -m pip check
python -m pytest packages/aero/tests -q
python -m pytest packages/aero/tests_system -m 'not docker' -q
```

Follow [validation](docs/VALIDATION.md) for real Docker and clean-distribution gates. Use explicit per-test fixtures when substituting models. Production code must use real execution paths and must never return invented successful results. Tests of crypto, scheduling, transport and filesystem behavior should exercise those boundaries directly.

Do not commit credentials, private signing keys, local approvals, sessions, receipts or build products. Public examples are unsigned drafts. A signature, lint result or schema-valid output does not establish safe code or task correctness.
