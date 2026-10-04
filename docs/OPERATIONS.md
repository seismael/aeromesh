# Operations

## Installation and reproducibility

Use Python 3.11–3.13. `constraints/ci-python.txt` records the tested dependency set, while package metadata bounds compatible API families. Build and install both packages as needed; the SDK depends on the CLI/runtime package. A release locks manifests and tool-image digests, not the Python environment or model output. Use the constraint file, retained wheel artifacts and your own deployment image to reproduce the runtime environment.

```bash
python -m pip install -c constraints/ci-python.txt build hatchling editables
python -m build --no-isolation --outdir dist packages/aero
python -m build --no-isolation --outdir dist packages/sdk-python
python -m venv /path/to/clean-environment
/path/to/clean-environment/bin/python -m pip install -c constraints/ci-python.txt dist/*.whl
/path/to/clean-environment/bin/python scripts/check_distribution.py
```

`amx doctor` makes no model calls. `amx preflight` checks local configuration and credentials without printing their values. It rechecks trust/closure and optionally discovers tools with `--probe-tools`; it does not prove that a remote model account is usable or that a business task will succeed.

## Model configuration and limits

Set `AEROMESH_MODEL=provider:model` explicitly, plus the selected provider's authentication. When omitted, exactly one supported provider credential is required; ambiguous environments fail. Select an available model ID rather than relying on historical examples. Models must support the tool interface required by Deep Agents.

Use `max_model_calls`, `max_output_tokens`, and `max_execution_steps` in `observability`. A `cost_limit_usd` additionally requires `input_price_per_million` and `output_price_per_million`, maintained by the operator. Budget estimates are conservative admission controls, not billing guarantees. The execution timeout defaults to a bounded driver limit and can be selected with `AEROMESH_EXECUTION_TIMEOUT_SECONDS` up to 3600 seconds. Cancellation cannot undo requests that an external service already accepted.

## Keys, approvals and recovery

Signing keys are encrypted with a key stored in the OS keyring. Back up the signing material and its recoverable keyring context under your organization's procedures. AeroMesh refuses to replace an inaccessible encryption key or overwrite an existing signing identity. A missing secure keyring is an error, not permission to write plaintext secrets.

Trust roots live in the current user's `AEROMESH_HOME/trusted`; Git catalog keys do not authorize anything automatically. Verify the public key before `amx trust`. Rotation uses a new signing identity and explicit operator administration; different key material cannot silently replace an approved ID. Revocation blocks future verification for that fingerprint, including aliases. It does not forcibly terminate work already running.

On policy edits, inspect `release diff` and reapprove. Do not edit installed release snapshots. If the local cache is damaged, rebuild/reinstall from the retained signed release and repeat explicit approval. Preserve receipts externally if your audit requirements exceed a local mutable record.

## Docker execution

Trusted tools require a local Linux-container Docker engine and a reviewed image available by digest. Runtime uses `--pull=never`; acquire images separately. Containers have no network, no host mounts, read-only rootfs, nonroot UID, no added capabilities, resource bounds and temporary scratch space. Pass task data through MCP arguments. Image entrypoints must work within these constraints. Windows requires a compatible Linux-container engine; CI currently exercises the container boundary on Linux.

Networked container egress and production remote MCP are unsupported and rejected. `--development` permits host or remote tools with the caller's authority. The development proxy is only a bounded HTTP utility, not a containment boundary: redirects are returned to the client, credentials/body/status are preserved, and malformed requests are rejected. Its current limits are 16 MiB bodies, 60-second request/tunnel lifetime, 10-second idle timeout and 32 workers.

A process crash can leave containers requiring operator cleanup. Inspect only managed containers (`docker ps -a --filter label=aeromesh.managed=true`) and remove the specific stopped/orphaned containers after confirming no run is active. Normal completion, errors and cancellation invoke session cleanup. Never run Docker container cleanup against unrelated workloads.

## Data retention

Metadata/receipts exclude task text and secrets, but native checkpoints can contain prompts, tool results and model outputs. Select ephemeral mode for sensitive transient work; metadata about a run still exists. Protect `AEROMESH_HOME` with OS permissions and appropriate disk encryption/backup policy. Tool credentials are resolved only from explicit sources/bindings. Legacy plaintext credential reads require deliberate API opt-in and are not the CLI default.

## Deployment qualification

Before adopting a workflow: run real-provider checks with the intended model; exercise the reviewed tool image inside the enforced container; validate your domain-specific success criteria; test revocation, changed dependencies, permissions and budgets; establish retention and incident procedures. Benchmark setup effort, task correctness, support burden and cost against native configuration. A green framework test suite cannot certify an arbitrary new agent or tool image.
