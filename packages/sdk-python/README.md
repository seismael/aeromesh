# AeroMesh Embeddable Python SDK (`aeromesh-sdk`)

The SDK delegates agent and workflow execution to the same AeroMesh services as
the CLI. It does not provide a separate runtime or bypass release verification.
Version 0.2.x requires the matching AeroMesh 0.2.x API family.

From a repository checkout:

```bash
python -m pip install -c constraints/ci-python.txt -e packages/aero -e packages/sdk-python
```

After approving a release using the CLI, with a supported model provider
configured, pass the digest returned by `amx release approve`:

```python
from aeromesh import AeroKernel

kernel = AeroKernel()
result = kernel.run_release("approved-release-digest", "Inspect the approved inputs.")
```

`run_agent` and `run_workflow` also accept signed manifest paths or installed IDs.
Unsigned local work requires the explicit `development=True` option; that mode
does not establish release approval or host-process isolation.

The normal provider usage charges apply. Missing trust, credentials, dependencies,
or unsupported capabilities raise domain errors; the SDK does not silently
substitute a successful response. Output contract validation establishes
structure, and task-specific checks are still needed to establish correctness.

See the repository README for approval, release locking, supported capabilities,
isolation requirements, and the explicit local-development option. The SDK has
the same security boundaries and limitations as those services.
