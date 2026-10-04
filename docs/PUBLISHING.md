# Publishing AeroMesh 1.0.0

The first public release is `v1.0.0` on GitHub. It distributes the CLI/runtime and Python SDK as source distributions and wheels, with a SHA-256 manifest and the tested dependency constraint file. Publishing does not upload packages to PyPI.

## Release contents

| Asset | Purpose |
|---|---|
| `aero-1.0.0-py3-none-any.whl` | Installable CLI/runtime with bundled schemas |
| `aero-1.0.0.tar.gz` | Runtime source distribution |
| `aeromesh_sdk-1.0.0-py3-none-any.whl` | Installable Python SDK |
| `aeromesh_sdk-1.0.0.tar.gz` | SDK source distribution |
| `ci-python.txt` | Tested dependency constraints |
| `SHA256SUMS` | SHA-256 checksums for the release assets |

Use the wheel installation procedure in [operations](OPERATIONS.md). The [changelog](../CHANGELOG.md) describes only the initial 1.0.0 release. Schema contracts, package versions and CLI reporting must agree with v1 before publishing.

## Maintainer procedure

1. Complete the [v1 acceptance matrix](VALIDATION.md), reconcile documentation with the supported boundary and review the exact source changes. Do not count skipped provider or container checks as passed.
2. Confirm both package versions are `1.0.0`, the changelog has its initial `1.0.0` section, no credentials or local runtime state are tracked, and the working tree contains the intended release contents.
3. Push the reviewed release commit to `main` with the exact subject `release: v1.0.0`. This explicit subject opts into the publishing job in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).
4. Require the Python 3.11–3.13 matrix, clean source/wheel distribution checks and real Docker boundary job to pass for that commit. The publish job depends on all three gates.
5. Verify that the published `v1.0.0` tag targets the tested commit and that all expected assets are present. Retain the CI run URL and source revision as release evidence.

The publishing job downloads the `python-distributions` artifacts produced by the same workflow run. It does not rebuild packages after validation. [`scripts/publish_release.py`](../scripts/publish_release.py) checks expected artifact names, package metadata and checksums, creates a draft GitHub release at the tested commit, uploads the distributions and accompanying files, and publishes the completed release.

If any mandatory gate fails, fix the defect and validate the intended release commit before publishing. An incomplete draft is not a completed release. Confirm the draft state and artifacts before retrying a failed publication; never retarget an already published release to different code or silently replace published artifacts.

## Evidence scope

The release gates verify the supported v1 runtime, approval, transport, isolation and packaging contracts. They do not require or imply live-model task certification. Paid live-provider tests remain an explicit manual CI dispatch with configured credentials and repository environment protection. Record live-model and workload-specific qualification separately as described in [validation](VALIDATION.md).

Do not label a provider check as passed merely because a workflow or release published successfully. The release notes must preserve the documented offline-container boundary and the distinction between structural output validity and task correctness.
