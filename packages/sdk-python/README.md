# AeroMesh Python SDK (`aeromesh-sdk`)

The AeroMesh 1.0.0 SDK executes agents, workflows and approved releases through the same checked services as the CLI. It requires the matching AeroMesh 1.x runtime API family.

From a reviewed repository checkout in an activated virtual environment:

```bash
python -m pip install -c constraints/ci-python.txt build hatchling editables
python -m build --no-isolation --outdir dist packages/aero
python -m build --no-isolation --outdir dist packages/sdk-python
python -m pip install -c constraints/ci-python.txt dist/aero-1.0.0-py3-none-any.whl dist/aeromesh_sdk-1.0.0-py3-none-any.whl
```

After approving a release through the CLI and configuring a supported model provider, pass the digest returned by `amx release approve`:

```python
from aeromesh import AeroKernel

kernel = AeroKernel()
result = kernel.run_release("approved-release-digest", "Inspect the approved inputs.")
```

`run_agent` and `run_workflow` accept signed manifest paths or installed IDs. Production tools and declared credentials require `run_release` with current operator approval. Unsigned authoring requires explicit `development=True`; development calls have the host application's authority.

Missing trust, credentials, dependencies or unsupported capabilities raise domain errors. The SDK does not substitute successful responses. Provider usage incurs the provider's normal charges. Output contracts validate structure; application-specific tests must establish task correctness.

Python callers can execute arbitrary host code, so the SDK is not an isolation boundary for hostile embedding applications. Production MCP isolation and release checks have the same scope as the CLI.

[First release walkthrough](https://github.com/seismael/aeromesh#readme) · [Release and policy contract](https://github.com/seismael/aeromesh/blob/main/docs/RELEASES.md) · [Validation](https://github.com/seismael/aeromesh/blob/main/docs/VALIDATION.md)
