# AeroMesh CLI and runtime (`aero` / `amx`)

AeroMesh 1.0.0 validates, signs, approves and runs declarative agent releases through LangChain Deep Agents and LangGraph.

- Signed releases include recursive agent dependencies and exact tool-image references.
- Explicit signer trust and independent operator policies are checked at execution and resume.
- Production MCP tools use reviewed, preloaded, network-disabled Linux containers with scoped credentials and resource limits.
- Deterministic contracts, workflow dependency barriers, bounded execution and local records support reliable operation.
- Bundled JSON Schemas work from installed distributions. The Python SDK delegates to the same services.

## Install from a reviewed checkout

Run from the repository root in an activated virtual environment:

```bash
python -m pip install -c constraints/ci-python.txt build hatchling editables
python -m build --no-isolation --outdir dist packages/aero
python -m pip install -c constraints/ci-python.txt dist/aero-1.0.0-py3-none-any.whl
amx doctor
```

These commands use the local source distribution and wheel. They do not require a PyPI release. See the [repository README](https://github.com/seismael/aeromesh#readme) for the complete first approved-release walkthrough and optional SDK installation.

For development and local transport verification:

```bash
python -m pip install -c constraints/ci-python.txt -e 'packages/aero[dev]'
python -m pytest packages/aero/tests -q
python -m pytest packages/aero/tests_system -m 'not docker' -q
python examples/dependency-inventory/smoke.py
```

Agent reasoning requires a real configured model provider. Stored signing keys and tool credentials require secure OS keyring access. Host/remote tool authoring requires explicit development mode and has the caller's authority. Output validation establishes structure; domain-specific checks establish substantive correctness.

[Execution policy](https://github.com/seismael/aeromesh/blob/main/docs/RELEASES.md) · [Operations](https://github.com/seismael/aeromesh/blob/main/docs/OPERATIONS.md) · [Validation](https://github.com/seismael/aeromesh/blob/main/docs/VALIDATION.md)
