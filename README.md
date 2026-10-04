# AeroMesh

**Approve a specific agent release. Enforce its tool permissions. Record what ran.**

AeroMesh 1.0.0 packages agents and workflows into signed releases with their complete agent dependency graph. Operators review the exact manifests, tool images and credential bindings, approve an independent policy, and run that release through LangChain Deep Agents and LangGraph.

Use AeroMesh when agent configuration must be reviewed, distributed and executed under explicit permissions. Its value is connecting artifact integrity, operator approval, execution controls and local evidence in one repeatable workflow.

## The v1 execution contract

| Capability | Enforced behavior |
|---|---|
| Artifact identity | Ed25519 signatures, explicitly trusted local signer keys, content verification and revocation checks at execution and resume |
| Complete agent releases | Embedded recursive agent dependencies, SHA-256 reference pins and exact MCP container image digests |
| Operator approval | Independent policy grants bind tool names, image identity and credential mappings; policy changes require reapproval |
| Tool containment | Preloaded Linux images without declared volumes; no network or host mounts, read-only root filesystem, non-root identity and resource limits |
| Input and output contracts | Deterministic JSON Schema validation; execution status and structural validity remain separate from task correctness |
| Workflow correctness | All-predecessor barriers, explicit dependency context, isolated run identities and failure propagation |
| Operational evidence | Local records of release, policy, runtime versions, status and available usage, excluding task text and credential values |

The host, Docker engine and runtime dependencies are part of the trusted deployment. Model-provider calls occur outside tool containers and receive the task data sent to the model. Output validation establishes structure; domain-specific evaluation establishes whether the result is correct. Native checkpoints may contain conversation data.

V1 accepts production tools only through approved releases and the container boundary above. Networked production tool containers, remote production MCP, arbitrary host commands, unsigned production artifacts and unsupported manifest capabilities are rejected. Explicit development mode supports local experimentation with the caller's authority.

## Install from source

Python 3.11–3.13 is covered by CI. Run these commands from a reviewed checkout:

```bash
git clone https://github.com/seismael/aeromesh.git
cd aeromesh
python -m venv .venv
# Activate .venv using the command for your shell.
python -m pip install -c constraints/ci-python.txt build hatchling editables
python -m build --no-isolation --outdir dist packages/aero
python -m build --no-isolation --outdir dist packages/sdk-python
python -m pip install -c constraints/ci-python.txt dist/aero-1.0.0-py3-none-any.whl dist/aeromesh_sdk-1.0.0-py3-none-any.whl
amx version
amx doctor
```

These commands build and install the local distributions and do not depend on packages being published to PyPI. Wheels include their runtime schemas. Use an isolated environment and retain the reviewed source revision, constraint file and wheels for deployment. See [installation and operations](docs/OPERATIONS.md).

Signing and stored tool credentials require a supported native OS keyring: Windows Credential Locker, macOS Keychain, Secret Service/libsecret or KWallet. On headless hosts, provision one for the execution account or sign on an authorized workstation. Arbitrary keyring plugins and plaintext backends are rejected; inaccessible secure storage fails clearly. Explicit environment credentials do not require stored secrets.

## First approved release

The included tool-free workflow summarizes and reviews supplied text. Configure a real model available to your account before executing it:

```bash
export AEROMESH_MODEL='openai:YOUR_MODEL_ID'
# Set OPENAI_API_KEY securely in this environment.
```

PowerShell uses `$env:AEROMESH_MODEL = 'openai:YOUR_MODEL_ID'`. Model execution incurs the selected provider's normal charges. Build, validation, signing and approval make no model calls.

Review the two referenced [agent drafts](registry/agents) and the [workflow](registry/workflows/summary-review.json), then create a release:

```bash
amx release build registry/workflows/summary-review.json --output summary.release.json
amx validate summary.release.json
amx keygen --name team
amx sign summary.release.json --key team
```

`keygen` prints the public-key path. Verify a publisher's key through an independent trusted channel, then substitute that path below. Even a locally signed release needs explicit signer trust and an independent operator policy:

```bash
amx trust summary-review /path/printed/by/keygen/team.pub
amx release approve summary.release.json --policy examples/tool-free-policy.json
amx preflight summary.release.json
amx release run summary.release.json 'Text to summarize and review' --json
amx history
```

Approval prints the release digest, which can also be passed to `amx release run`. Subsequent runs recheck current trust, dependency integrity and the active policy without routine per-tool approval prompts. Signing identifies a key and protects contents; review the instructions and tool code before approving them.

Compare candidate releases with `amx release diff current.release.json candidate.release.json`. Revoke a signer with `amx revoke summary-review`; the fingerprint is rejected at subsequent verification boundaries, including other locally trusted IDs using that key. Revocation does not terminate already running work.

See [releases and policy](docs/RELEASES.md) for the complete approval lifecycle and exact tool-image and credential grants. Production tool images must already be available locally by digest; execution never pulls tool code.

## Authoring and real tool evaluation

Create a draft with `amx init my-agent` and validate it with `amx validate my-agent.agent.json`. The [catalog](registry/README.md) contains unsigned tool-free examples. For explicit local authoring:

```bash
amx run registry/agents/structured-summary.json 'Summarize this supplied text' --development
```

[Dependency inventory](examples/dependency-inventory/README.md) implements an actual stdio MCP server that parses dependency metadata. Its offline smoke test verifies the real tool transport without a model account:

```bash
python examples/dependency-inventory/smoke.py
```

The example also includes a production container, a release/policy preparation command, and a complete sign–approve–run walkthrough. It accepts requirements text through MCP arguments, so new inputs need neither host mounts nor image rebuilds. CI builds the image and tests actual tool calls through a signed, independently approved release with networking disabled.

The optional local agent demo calls a configured model in development mode. Inventory describes dependencies; it does not assess vulnerabilities or dependency safety. Use the container walkthrough to exercise the supported production tool boundary.

## Interface essentials

| Task | Command |
|---|---|
| Check installation and configuration | `amx doctor` / `amx preflight PATH` |
| Start tools and check their exposed interface | `amx preflight PATH --probe-tools` |
| Verify a trusted signature | `amx verify PATH` |
| Check cryptographic integrity only | `amx verify PATH --signature-only` |
| Install a signed tool-free agent | `amx install PATH_OR_ID` |
| Run a signed tool-free agent | `amx run PATH_OR_ID 'task'` |
| Run an approved release | `amx release run PATH_OR_DIGEST 'task'` |
| Supply structured task input | Add `--input-json` with JSON positional input |
| Create a model-authored tool-free draft | `amx run 'goal' --synthesize --development` |
| Resume a checkpointed agent session | `amx run PATH 'follow-up' --replay SESSION_ID` |
| Store a tool secret using a hidden prompt | `amx vault set CREDENTIAL_ID` |
| Inspect manifest heuristics | `amx lint PATH` |

Synthesis persists drafts for review and requires explicit opt-in. Ephemeral agent sessions cannot be resumed. Each workflow invocation is a new run; already completed effects are not rolled back or guaranteed exactly once.

The [Python SDK](packages/sdk-python/README.md) uses the same checked execution services as the CLI.

## Release qualification

CI covers Python 3.11–3.13, trust and policy rejection cases, workflow scheduling, real local MCP, clean source/wheel installation and real Docker isolation. The [v1 acceptance matrix](docs/VALIDATION.md) maps each supported claim to its verification gate. Paid provider checks are explicit manual jobs, with deployment-specific model and task qualification recorded separately.

AeroMesh's operational records are local and mutable by the deployment administrator. Select appropriate retention, host protection and independent record export for your environment. Measure task quality and operating cost with your intended model, approved tools and representative workloads before production use.

[Architecture](docs/ARCHITECTURE.md) · [Release format](docs/RELEASES.md) · [Operations](docs/OPERATIONS.md) · [Validation](docs/VALIDATION.md) · [Publishing](docs/PUBLISHING.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md)

Apache-2.0.
