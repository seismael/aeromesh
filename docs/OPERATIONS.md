# Operations

## Installation and reproducibility

Python 3.11–3.13 is covered by CI. Install reviewed source-built wheels or the wheels attached to the published GitHub release. Installation does not require a PyPI publication. `constraints/ci-python.txt` records tested dependency versions, while package metadata bounds compatible API families.

For a published GitHub release, download both wheels, `ci-python.txt` and `SHA256SUMS` from that release. Verify the artifact hashes against `SHA256SUMS` using your platform's SHA-256 utility. Use a trusted source for the release and checksum file: checksums detect content changes but do not independently establish publisher authenticity. In a fresh activated virtual environment, from the download directory:

```bash
python -m pip install -c ci-python.txt aero-1.0.0-py3-none-any.whl aeromesh_sdk-1.0.0-py3-none-any.whl
python -m pip check
amx version
amx doctor
```

To build from a reviewed repository checkout:

```bash
python -m pip install -c constraints/ci-python.txt build hatchling editables
python -m build --no-isolation --outdir dist packages/aero
python -m build --no-isolation --outdir dist packages/sdk-python
python -m venv .wheel-venv
.wheel-venv/bin/python -m pip install -c constraints/ci-python.txt dist/aero-1.0.0-py3-none-any.whl dist/aeromesh_sdk-1.0.0-py3-none-any.whl
.wheel-venv/bin/python -m pip check
.wheel-venv/bin/python scripts/check_distribution.py
```

On Windows, use `.wheel-venv\Scripts\python.exe`. The checker runs installed-package checks outside the checkout. The SDK depends on the runtime package; installing both wheels together resolves that dependency locally.

A signed agent release locks manifests and tool-image digests. Runtime reproducibility additionally requires the reviewed source revision, installed wheels, dependency constraints, platform and deployment image. Model output can vary independently. Retain these artifacts with your deployment records; see [publishing](PUBLISHING.md) for the release process.

`amx doctor` makes no model calls. `amx preflight` checks local configuration and credentials without printing their values. It rechecks trust/closure and optionally discovers tools with `--probe-tools`; it does not prove that a remote model account is usable or that a business task will succeed.

## Model configuration and limits

Set `AEROMESH_MODEL=provider:model` explicitly, plus the selected provider's authentication. When omitted, exactly one supported provider credential is required; ambiguous environments fail. Select a model ID available to the deployment account. Models must support the tool interface required by Deep Agents.

Use `max_model_calls`, `max_output_tokens`, and `max_execution_steps` in `observability`. A `cost_limit_usd` additionally requires `input_price_per_million` and `output_price_per_million`, maintained by the operator. Budget estimates are conservative admission controls, not billing guarantees. The execution timeout defaults to a bounded driver limit and can be selected with `AEROMESH_EXECUTION_TIMEOUT_SECONDS` up to 3600 seconds. Cancellation cannot undo requests that an external service already accepted.

## Keys, approvals and recovery

Signing keys are encrypted with an independent encryption key stored in a supported native OS keyring. The non-secret `keys/store-id` identifies its keyring entry and travels with the encrypted keys when the state directory moves. Back up `keys/store-id`, the encrypted signing material and its recoverable keyring context together under your organization's procedures. Restoring files alone cannot restore a missing keyring secret. Supported backends are Windows Credential Locker, macOS Keychain, Secret Service/libsecret and KWallet; arbitrary plugins and plaintext backends are rejected. AeroMesh refuses to replace an inaccessible encryption key, recreate a missing store identity beside existing encrypted keys, or overwrite an existing signing identity. A missing secure keyring is an error, not permission to write plaintext secrets.

Trust roots live in the current user's `AEROMESH_HOME/trusted`; Git catalog keys do not authorize anything automatically. Verify the public key before `amx trust`. Rotation uses a new signing identity and explicit operator administration; different key material cannot silently replace an approved ID. Revocation blocks future verification for that fingerprint, including aliases. It does not forcibly terminate work already running.

On policy edits, inspect `release diff` and reapprove. Do not edit installed release snapshots. If the local cache is damaged, rebuild/reinstall from the retained signed release and repeat explicit approval. Preserve receipts externally if your audit requirements exceed a local mutable record.

## Docker execution

Trusted tools require a local Linux-container Docker engine and a reviewed Linux image available by digest. Images declaring Docker volumes are rejected so they cannot add writable storage outside the bounded temporary directory. Runtime uses `--pull=never`; acquire images separately. Containers have no network, no host mounts, read-only rootfs, nonroot UID, no added capabilities, resource bounds and temporary scratch space. Pass task data through MCP arguments. Image entrypoints must work within these constraints. Windows requires a compatible Linux-container engine; CI currently exercises the container boundary on Linux.

Networked container egress and production remote MCP are unsupported and rejected. `--development` permits host or remote tools with the caller's authority. The development proxy is only a bounded HTTP utility, not a containment boundary: redirects are returned to the client, credentials/body/status are preserved, and malformed requests are rejected. Its current limits are 16 MiB bodies, 60-second request/tunnel lifetime, 10-second idle timeout and 32 workers.

A process crash can leave containers requiring operator cleanup. Inspect only managed containers (`docker ps -a --filter label=aeromesh.managed=true`) and remove the specific stopped/orphaned containers after confirming no run is active. Normal completion, errors and cancellation invoke every registered cleanup callback. Unconfirmed cleanup fails the run and its receipt; an initiating execution error also reports a cleanup warning when needed. Never run Docker container cleanup against unrelated workloads.

## Data retention

Metadata/receipts exclude task text and secrets, but native checkpoints can contain prompts, tool results and model outputs. Select ephemeral mode for sensitive transient work; metadata about a run still exists. Protect `AEROMESH_HOME` with OS permissions and appropriate disk encryption/backup policy. Tool credentials are resolved only from explicit sources and bindings. Stored credentials require supported native OS-keyring-backed encryption. Explicit environment credentials do not require keyring storage. Protect any environment-based secret injection through the deployment service or shell.

## Deployment qualification

Before adopting a workflow: run real-provider checks with the intended model; exercise the reviewed tool image inside the enforced container; validate your domain-specific success criteria; test revocation, changed dependencies, permissions and budgets; establish retention and incident procedures. Benchmark setup effort, task correctness, support burden and cost against native configuration. A green framework test suite cannot certify an arbitrary new agent or tool image.

## Troubleshooting

| Symptom | Operator action |
|---|---|
| Signing or credential storage reports a keyring error | Provision a secure OS keyring for the execution account, or sign on an authorized workstation; do not substitute plaintext storage |
| Release is not trusted | Independently verify its publisher key, import it for the release identity and verify the signed artifact |
| Policy or snapshot integrity check fails | Review the intended signed release and current policy, then explicitly approve again; do not edit installed snapshots |
| Container image is unavailable | Acquire and review the image separately, confirm the exact digest exists in the selected local Docker engine and retry preflight |
| A tool requires network or a host file mount | Redesign it for the supported offline MCP argument interface, or evaluate it explicitly in development mode outside production admission |
| Model configuration is ambiguous | Set `AEROMESH_MODEL=provider:model` and the appropriate provider credential explicitly |
| Session cannot resume | Check the session mode, source integrity and current trust; ephemeral sessions are intentionally non-resumable |
| Output contract validation fails | Inspect the task/model output in the authorized execution context; revise the task or draft contract, then review and approve the resulting release |

Preflight without `--probe-tools` checks configuration without invoking a model. `--probe-tools` starts the configured tool processes to discover their interfaces; use it only after reviewing the image or development command.
