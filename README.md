# AeroMesh

**Review, approve, and run a specific agent release on LangChain Deep Agents.**

AeroMesh 0.2 packages agent and workflow manifests into a signed dependency closure, applies an independent operator policy, and records what ran. It uses Deep Agents for agent execution and LangGraph for workflow scheduling. It is a configuration and governance layer, not a new intelligence model or a cross-framework industry standard.

## What it guarantees within its supported boundary

- **Identity and integrity:** explicit local signer approval, Ed25519 verification and revocation checks at execution/resume. Repository keys never grant implicit trust.
- **Closed releases:** embedded agent manifests, recursive SHA-256 reference pins, digest-pinned MCP images, and capability changes visible through release diffs.
- **Independent permissions:** tools, image identity and credential bindings must match an operator policy. Changing the policy requires reapproval. Tool/credential execution requires an approved release.
- **Contained local tools:** trusted stdio MCP servers run in preloaded Linux containers with no network, no host mounts, read-only root filesystem, non-root identity, dropped capabilities and resource limits. Docker itself and the host OS remain trusted.
- **Correct execution contracts:** deterministic JSON Schema input/output checks, all-predecessor workflow barriers, per-run conversation identities, failed-step propagation and bounded execution.
- **Operational evidence:** local receipts bind the release, policy and runtime versions to execution status and usage. They do not include prompts, outputs or credentials, and are not a tamper-proof audit ledger.

**Output shape validation does not prove factual accuracy or business success.** Results explicitly mark task assessment as unverified. Native checkpoints can contain conversation data; use ephemeral mode when persistence is unwanted.

Networked production tool containers, remote production MCP endpoints, unsigned production artifacts, arbitrary host commands, standalone skill references and unsupported manifest policies fail closed. Host/remote tool experiments require an explicit `--development` mode, which is not a security boundary.

## Install

Python 3.11–3.13 is tested by CI. Use a virtual environment:

```bash
python -m venv .venv
# Activate .venv using the command for your shell.
python -m pip install -c constraints/ci-python.txt -e 'packages/aero[dev]' -e packages/sdk-python
amx doctor
```

For distribution, build the packages and install the generated wheels. Wheels include the schemas and work outside this checkout. See [operations](docs/OPERATIONS.md).

Signing requires a usable secure OS keyring. On headless machines, provision an appropriate keyring backend or sign on an authorized workstation and distribute the public key. AeroMesh does not silently store plaintext signing secrets or tool credentials.

## First local evaluation

Choose an actual model available to your account and set its provider credential. For example:

```bash
export AEROMESH_MODEL='openai:YOUR_MODEL_ID'
# Set OPENAI_API_KEY securely in your execution environment.
amx run registry/agents/structured-summary.json 'Summarize this supplied text...' --development
```

PowerShell uses `$env:AEROMESH_MODEL = 'openai:YOUR_MODEL_ID'`. A paid provider call occurs only when running the model. No provider credential is included in this repository.

The [catalog](registry/README.md) contains unsigned, tool-free drafts. They illustrate the interface; they are not independently certified agents.

## Approve and run a release

The following tool-free example exercises the complete release path. `keygen` prints the public-key path; substitute that path below.

```bash
amx release build registry/workflows/summary-review.json --output summary.release.json
amx validate summary.release.json
amx keygen --name team
amx sign summary.release.json --key team
amx trust summary-review /path/printed/by/keygen/team.pub
amx release approve summary.release.json --policy examples/tool-free-policy.json
amx preflight summary.release.json
amx release run summary.release.json 'Text to summarize and review' --json
amx history
```

Review the release and verify a publisher's key through an independent trusted channel before importing it. Signing proves key possession and integrity, not harmlessness. Approval requires a separate policy even if you signed the release yourself. Approving permissions once allows subsequent in-scope runs without per-tool human prompts; each run still verifies current trust and policy.

Use `amx release diff old.release.json new.release.json` before approving an update. Revoke a signing key with `amx revoke summary-review`; revocation applies to that key's fingerprint and blocks future verification, including other locally trusted identities using it. No running process is remotely terminated by revocation.

See [release and policy format](docs/RELEASES.md) for exact tool-image and credential grants. A Docker image must be acquired/reviewed separately and already exist locally by digest; agent execution never pulls tool code.

## Real tool integration example

[Dependency inventory](examples/dependency-inventory/README.md) runs an actual stdio MCP server and parses supplied dependency metadata without an LLM or external API. Its transport smoke test is:

```bash
python examples/dependency-inventory/smoke.py
```

The optional agent demo uses a real configured model in explicit development mode. Inventory is not a vulnerability scan or a claim that dependencies are safe.

## Interface essentials

| Task | Command |
|---|---|
| Author a draft | `amx init my-agent` |
| Validate supported semantics | `amx validate my-agent.agent.json` |
| Check local prerequisites | `amx doctor` / `amx preflight PATH` |
| Discover actual MCP tools | `amx preflight PATH --probe-tools` |
| Sign / independently approve signer | `amx sign PATH` / `amx trust ID PUBLIC_KEY` |
| Verify trust | `amx verify PATH` |
| Check integrity only | `amx verify PATH --signature-only` |
| Install a trusted tool-free agent | `amx install PATH_OR_ID` |
| Execute a trusted tool-free agent | `amx run PATH_OR_ID 'task'` |
| Execute approved capabilities | `amx release run PATH_OR_DIGEST 'task'` |
| Supply structured task input | Add `--input-json` with a JSON positional input |
| Explicitly synthesize a tool-free draft | `amx run 'goal' --synthesize --development` |
| Resume a checkpointed session | `amx run PATH --replay SESSION_ID 'follow-up'` |
| Inspect local sessions | `amx history` |
| Store a tool secret without putting it in shell arguments | `amx vault set CREDENTIAL_ID` |
| Lint a manifest | `amx lint PATH` (heuristics, not certification) |

A missing path never triggers automatic synthesis. New drafts are persisted for review; synthesis does not create missing tool capabilities or grant permissions. An ephemeral session cannot be resumed. Workflow repetitions are new runs and can repeat external effects; there is no implicit workflow resume or exactly-once side-effect guarantee.

## Validation and limits

```bash
python -m pytest packages/aero/tests -q
python -m pytest packages/aero/tests_system -m 'not docker' -q
python -m build --outdir dist packages/aero
python -m build --outdir dist packages/sdk-python
```

CI runs unit/integration regressions, real local MCP, clean wheel installations, and mandatory Docker isolation tests. Paid provider checks are explicit manual jobs and are separate from offline acceptance. See [validation](docs/VALIDATION.md) for the exact coverage and what remains deployment-specific.

AeroMesh does not promise better model reasoning, cross-provider behavioral equivalence, lower token usage, malicious-kernel resistance, or safe autonomous financial/administrative actions. Its value is reviewable configuration, approved permissions, reproducible software references and evidence of execution. Measure that value against native Deep Agents configuration before adopting another layer.

[Architecture](docs/ARCHITECTURE.md) · [Operations](docs/OPERATIONS.md) · [Migration](docs/MIGRATION.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md)

Apache-2.0.
