# V1 acceptance and release qualification

AeroMesh 1.0.0 is accepted against the execution contract below. Automated gates verify the runtime and its enforcement boundary; live-provider and deployment qualification establish suitability for a specific model, image and workload. Record evidence against the exact commit and installed artifacts. A skipped check is not a passed gate.

## Acceptance matrix

Paths in the evidence column are under `packages/aero/` unless otherwise stated.

| V1 requirement | Acceptance condition | Automated evidence |
|---|---|---|
| Artifact trust | Unsigned, untrusted, altered, revoked or identity-mismatched artifacts fail before execution | `tests/unit/test_trust_boundaries.py`, `test_registry_resolution.py`, `test_runner_integrity.py`; CLI trust integration tests |
| Complete release contents | Recursive digests and agent identities match; missing, cyclic, conflicting or extraneous dependencies fail | `tests/unit/test_releases.py` |
| Independent approval | Every requested tool, image and credential binding is granted by the active policy; policy and snapshot drift block execution | `tests/unit/test_releases.py`, `test_preflight_review.py` |
| Container boundary | Actual processes run without network or host mounts, with read-only rootfs, no image-declared volumes, non-root identity and scoped environment; production MCP calls succeed within that boundary | `tests_system/test_isolation_docker.py` with Docker prerequisites required |
| Credential confinement | Only declared and explicitly bound secrets reach tools; inaccessible secure storage fails without plaintext fallback | `tests/unit/test_credential_store.py`, `test_keystore.py`, `test_tool_execution.py`; authentication integration tests |
| Supported manifest semantics | Unsupported declarations fail; accepted versions and fields match their runtime behavior; schema references stay local | `tests/unit/test_schema_semantics.py`, `test_schema_binding.py`, `test_full_schema_dataclass_hydration.py` |
| Deterministic contracts | Invalid input/output fails structurally; execution completion never implies factual correctness | `tests/unit/test_runtime_contracts_and_limits.py` |
| Workflow scheduling | Unequal-depth joins wait for all dependencies, step context is explicit, identities are isolated and failures stop dependants | `tests/unit/test_workflow_reliability.py`, `test_workflow.py` |
| Persistence and resume | Immutable snapshots, current trust, mode and release authority are rechecked; concurrent resumes fail safely | `tests/unit/test_session_integrity.py`, `test_checkpoint_replay.py` |
| Resource bounds and cleanup | Model-call/output/execution limits apply; delegated limits are enforced; estimated-cost admission happens before calls; every finalizer runs and unconfirmed cleanup fails execution | `tests/unit/test_runtime_contracts_and_limits.py`, `test_runtime_mcp_lifecycle.py`, `test_tool_execution.py`, `test_runtime_boundary_regressions.py` |
| Real MCP interoperability | Actual stdio initialization, tool listing, calls and provenance work, including concurrent runtime calls | `tests_system/test_dependency_inventory_mcp.py`; container MCP system tests |
| Development HTTP utility | Redirects are returned without bypassing destination checks; request/response semantics, size bounds and malformed framing are checked | `tests/unit/test_egress_proxy.py` |
| CLI and SDK adoption | Missing paths do not synthesize implicitly; drafts persist; CLI/SDK use checked service paths and report domain errors | CLI integration tests; `tests/unit/test_sdk_python.py`, `test_preflight.py` |
| Installed distributions | Source-built wheels include schemas; SDK imports and CLI/parser behavior work outside the checkout without repository data | Repository `scripts/check_distribution.py`; CI `distribution` job |
| Runtime compatibility | Constrained dependencies resolve consistently and core plus local MCP tests pass on each supported Python version | CI `test` matrix: Python 3.11, 3.12 and 3.13; `pip check` |

These are required acceptance criteria, not a static claim that every future revision passes. The CI run attached to a source revision supplies its pass/fail evidence. [Publishing](PUBLISHING.md) uses distributions from that same run after the mandatory gates pass. Tests use explicit model fixtures for deterministic cases and real crypto, schemas, SQLite, native LangGraph scheduling, local transport and container execution for those boundaries.

## Run the automated gates

Install development dependencies in an isolated environment from the repository root:

```bash
python -m pip install -c constraints/ci-python.txt -e 'packages/aero[dev]' -e packages/sdk-python
python -m pip check
python -m pytest packages/aero/tests -q
python -m pytest packages/aero/tests_system -m 'not docker' -q
```

For container qualification, acquire the reviewed fixture image separately, set `AEROMESH_TEST_IMAGE` to its locally available digest-qualified reference, and require the prerequisite:

```bash
export AEROMESH_TEST_IMAGE='REVIEWED_IMAGE@sha256:EXACT_DIGEST'
export AEROMESH_REQUIRE_DOCKER_TESTS=1
python -m pytest packages/aero/tests_system -m docker -q
```

CI provisions a fixture image and requires these tests. Local execution without Docker can skip them, but that does not qualify the container boundary. Current container CI runs on Linux.

Build source distributions and wheels, then test only the installed wheels in a fresh environment:

```bash
python -m build --no-isolation --outdir dist packages/aero
python -m build --no-isolation --outdir dist packages/sdk-python
python -m venv .wheel-venv
.wheel-venv/bin/python -m pip install -c constraints/ci-python.txt dist/aero-1.0.0-py3-none-any.whl dist/aeromesh_sdk-1.0.0-py3-none-any.whl
.wheel-venv/bin/python -m pip check
.wheel-venv/bin/python scripts/check_distribution.py
```

`python -m build` builds the wheel from its source distribution. The distribution checker switches to a temporary directory outside the checkout and verifies packaged schemas, parsers, SDK import, entry points and secure-keyring failure behavior. On Windows, the virtual-environment interpreter is `.wheel-venv\Scripts\python.exe`.

## Live-model qualification

Live tests are explicitly dispatched from `main`, using the `live-model-tests` GitHub environment. Configure the `DEEPSEEK_API_KEY` environment secret and any required reviewer protection rules in repository settings. An environment name alone does not establish review protection. The live job fails if its provider credential is missing; ordinary pushes and pull requests do not make paid provider calls.

A connectivity or simple workflow test establishes only the exercised provider/model behavior. Record provider, model ID, date, representative inputs, output expectations, tool images, observed failures and cost. A model alias or hosted service can change independently of the signed release.

## Deployment acceptance

Before promoting a workload to production, record the following:

| Area | Required deployment evidence |
|---|---|
| Runtime identity | Exact source revision, wheel artifacts, dependency constraints, host/container-engine versions and approved tool-image digests |
| Authority | Independently verified signer key, signed release digest, reviewed operator policy, revocation and changed-policy rejection checks |
| Task quality | Representative real-model cases with domain-specific expected outcomes and failure handling |
| Tool compatibility | Actual reviewed Linux image declares no volumes and its entrypoint functions inside the required offline, read-only, non-root boundary |
| Operational behavior | Timeout/cancellation recovery, budget configuration, concurrency, checkpoint retention, backup and incident procedures |
| Adoption value | Measured setup and approval effort, repeat-run correctness, recovery time, support burden and actual cost |

No framework-level test certifies semantic truth, financial safety, regulatory compliance, provider billing accuracy or exactly-once external effects. Local receipts are operational records, not independently notarized evidence. Production networked MCP is outside the v1 supported boundary and is rejected.
