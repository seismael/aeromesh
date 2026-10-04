# Validation evidence and release gates

This repository validates the implemented boundary, not the competence of every possible model, agent or tool. Regressions exercise real crypto, schemas, filesystem/SQLite state, native LangGraph scheduling and local network transport. Deterministic model substitutes are explicit per-test fixtures, not global import-time replacements.

## Required automated gates

1. `pytest packages/aero/tests -q`: trust/policy/closure tamper and revocation checks; CLI/SDK fail-closed behavior; scoped credential mappings; exact contracts; workflow barriers and failure propagation; immutable resume/state concurrency; budget admission and cleanup.
2. `pytest packages/aero/tests_system -m 'not docker' -q`: real local stdio MCP initialization, tool listing/calling and provenance. No paid model is required.
3. `pytest packages/aero/tests_system -m docker -q`: real Docker read-only/non-root/no-network/credential boundary. Set `AEROMESH_TEST_IMAGE` to a locally available digest and `AEROMESH_REQUIRE_DOCKER_TESTS=1` to make missing prerequisites fatal. CI does this; absent Docker is explicitly skipped locally, never reported as passed.
4. Build source distributions, build wheels from those distributions, install only wheels into a fresh environment, run `pip check` and `scripts/check_distribution.py` from outside the checkout.
5. Run unit/integration and non-Docker system tests on Python 3.11, 3.12 and 3.13 in CI. Distribution and Docker gates run on Python 3.12.

The suite includes adversarial cases from the audit: unsigned unknown IDs; tampered installed manifests; trust-store path escapes; changed policy and recursive dependencies; HTTP redirect behavior and request preservation; ambient secret rejection; invalid contracts; unequal-depth joins; accidental reuse of workflow threads; partial constructor failure; and incorrectly labelled task success.

## Separate live and deployment gates

Live tests are manually dispatched from `main`, using the `live-model-tests` environment. They require a configured provider secret and fail if the prerequisite is missing. Configure environment protection rules in repository settings; naming an environment does not itself establish approval rules. These jobs may incur provider charges and are never automatically exposed to pull-request code.

Local live-test skips mean **not exercised**, not success. Echo and simple workflow checks establish connectivity and basic execution only. Qualify production workflows against the intended model, actual reviewed images, domain-specific reference cases, and failure/cancellation behavior. No real provider key is shipped in this project.

## What is not certified

- Semantic/factual correctness, SQL optimization benefit, security finding completeness, financial safety or regulatory compliance.
- Equivalent behavior or deterministic outputs across models/providers.
- Cross-platform hostile-process resistance; current container CI is Linux.
- A trustworthy host/kernel/Docker daemon, or tamper-proof local receipts.
- Exact provider billing, rollback of external side effects, or exactly-once workflow execution.
- Networked production MCP isolation; this capability is rejected.

## Adoption measurement

Compare the same model/tools/tasks with a minimal native Deep Agents setup and a relevant packaged alternative. Measure first-correct-run setup time, repeat-run correctness, approval effort, rejection of privilege changes, recovery behavior and actual cost. Release content locking and passing tests are prerequisites, not evidence that another platform layer is needed.
