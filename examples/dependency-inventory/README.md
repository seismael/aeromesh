# Dependency inventory over real MCP

This bounded example reads a real requirements file, parses PEP 508 lines,
computes its SHA-256 digest, and reports direct dependencies and exact version
pins. The MCP server uses the official Python MCP SDK over stdio. It does not
download packages, query vulnerability databases, inspect installed software,
resolve transitive dependencies, or assert that dependencies are safe.

From the repository root, after the [AeroMesh v1 installation](../../README.md#install-from-source):

```bash
python examples/dependency-inventory/smoke.py
```

This offline command runs the actual tool through MCP and checks its observed
output: three dependencies, one without an exact version pin. It needs no model
or API key. This verifies the tool and transport, not autonomous model behavior.

To exercise the real Deep Agents runtime, configure a supported model provider
key using the main README, review `server.py`, then run:

```bash
python examples/dependency-inventory/demo.py --development
```

The live demo calls a provider and incurs its normal usage costs. It explicitly
uses development mode because it starts reviewed local Python code on the host.
Development mode provides no process isolation. A schema-valid response only
confirms output structure; it does not prove that a model called the tool or
copied every observed value correctly. Compare the result with `smoke.py`.

The tool accepts only paths under its configured input directory, rejects pip
directives and inputs larger than 1 MiB, and evaluates neither requirement URLs
nor environment markers. Its path checks are input validation, not an OS
security boundary; use read-only isolated input for untrusted data and tools.

## Run an independently approved production tool

The container mode accepts requirement **text through MCP arguments**, so it can
inventory different inputs without image rebuilds, host mounts or network
access. It uses the same deterministic parser as the file example. This is a
working example for the existing AeroMesh 1.0.0 runtime and needs no package
upgrade or format change.

Install AeroMesh and its dependencies, then review `server.py`, `Dockerfile`,
`prepare_release.py` and the root `constraints/ci-python.txt`. The image needs
Linux containers. Supply a reviewed digest of the official `python:3.12-slim`
image as `BASE_IMAGE`; the Dockerfile has no mutable default and rejects unpinned
references. These Bash commands run from the repository root:

```bash
export BASE_IMAGE='python:3.12-slim@sha256:REPLACE_WITH_REVIEWED_64_HEX_DIGEST'
export INVENTORY_IMAGE='YOUR_REGISTRY/YOUR_NAMESPACE/aeromesh-inventory'
docker pull "$BASE_IMAGE"
docker build --pull=false --build-arg BASE_IMAGE="$BASE_IMAGE" \
  -f examples/dependency-inventory/Dockerfile \
  -t "$INVENTORY_IMAGE:reviewed" .
```

The build installs `mcp==1.30.0` and `packaging==26.3` under the tested dependency
constraints. Base-image provisioning and package installation use the network
at build time. Review and retain the resulting image through your normal image
approval process. The following explicit commands publish **your image to your
registry**; authenticate to that registry first. AeroMesh and the preparation
helper never publish or pull an image automatically:

```bash
docker push "$INVENTORY_IMAGE:reviewed"
export PINNED_IMAGE="$(docker image inspect "$INVENTORY_IMAGE:reviewed" --format '{{index .RepoDigests 0}}')"
printf '%s\n' "$PINNED_IMAGE"
```

Check that the printed repository and digest identify the image you reviewed.
If the image has multiple repository digests, select the correct full
`repository@sha256:...` reference explicitly. On each execution host, separately
provision that exact image with `docker pull "$PINNED_IMAGE"` before running
AeroMesh. Runtime uses `--pull=never` and disables container networking.

Prepare a draft, unsigned release and separate policy in a **new** directory
whose parent already exists:

```bash
python examples/dependency-inventory/prepare_release.py \
  --image "$PINNED_IMAGE" --output-dir inventory-review
amx validate inventory-review/inventory.release.json
```

The helper invokes the normal release builder and policy validator. It refuses
existing output directories, removes its outputs if preparation fails, and
performs no signing, trust import, approval, tool execution, model calls or
Docker operations. Inspect all three generated files before proceeding:

| File | Review |
|---|---|
| `inventory.agent.json` | Instructions, input/output contracts, image digest and execution limits |
| `inventory.release.json` | Exact embedded agent and content digest |
| `inventory.policy.json` | Grant only `inventory_requirements_text` for this image, with no credentials |

The policy template is a review starting point. Operators must independently
approve its contents; the fact that a helper produced matching declarations
and grants provides no assurance about the tool's safety.

Sign the reviewed release using an existing authorized key, or create a new
signing identity backed by your configured native OS keyring:

```bash
amx keygen --name inventory-author
amx sign inventory-review/inventory.release.json --key inventory-author
```

Independently verify the public key printed by `keygen`, then replace the
placeholder path below. Trust is granted to the release's `dependency-inventory`
identity, and approval uses the separately reviewed operator policy:

```bash
export AEROMESH_MODEL='openai:YOUR_MODEL_ID'
amx trust dependency-inventory /PATH/PRINTED/BY/KEYGEN/inventory-author.pub
amx release approve inventory-review/inventory.release.json \
  --policy inventory-review/inventory.policy.json
amx preflight inventory-review/inventory.release.json --probe-tools
```

Choose a real model ID available to your account for `AEROMESH_MODEL` before
preflight. Preflight starts the real MCP tool inside the production container
boundary and checks its interface; it makes no model calls. The image has no volumes,
runs as a non-root user, and works with AeroMesh's read-only filesystem and
bounded temporary scratch space. All task input arrives through MCP arguments.

Configure a tool-capable model available to your account and its provider
credential as described in the main README, then execute:

```bash
amx release run inventory-review/inventory.release.json \
  '{"requirements_text":"jsonschema==4.26.0\nrich>=15,<16\npackaging==26.3\n"}' \
  --input-json --json
amx history
```

Model calls incur provider charges and send the supplied text and tool result
to that provider. Tool-container network isolation does not isolate the model
provider. Start with small inputs: the example caps model output at 4096 tokens;
large inventories can exceed that bound and need an explicitly reviewed change
to the agent limits or a different processing workflow.

The exposed MCP tool is `inventory_requirements_text(requirements_text: str)`;
its runtime name is `inventory__inventory_requirements_text`. Its JSON result
contains `path: "<provided>"`, the SHA-256 of the exact UTF-8 input bytes,
`dependency_count`, `unpinned_count`, `dependencies`, and `scope`. The sample
above must report three dependencies and one without an exact version pin.
UTF-8 input is bounded to 1 MiB; pip directives and continuations are rejected.
Hashes change if line endings or whitespace change.

Direct inventory computation is deterministic. The model-mediated result still
needs comparison with expected data: structural validation alone cannot prove
that the model called the tool or copied its result accurately. The example
does not install requirements, fetch URLs, resolve transitive dependencies or
judge vulnerabilities. The automated container gate exercises this same image,
an actually signed and approved release, and real MCP calls with varied input;
live-model task qualification remains a separate deployment check.
