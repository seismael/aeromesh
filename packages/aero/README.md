# Aero Standalone Agent Kernel (`aero` / `amx`)

`packages/aero` is the unified, standalone Python package for the AeroMesh kernel engine and command-line interface (`amx`).

## Key Capabilities
- **DAM v3.0 Parser & Validation**: Hydrates 100% of schema attributes.
- **Zero-Trust Security Vault**: 5-layer credential cascade with explicit human key approval.
- **Network Sandbox Proxy Firewall**: Enforces `allowed_domains` host allowlisting.
- **Dual Stdio & Remote SSE MCP Transport Drivers**: JSON-RPC 2.0 transport over subprocess stdio & HTTP SSE.
- **JIT Dynamic Builder**: Synthesizes DAM v3.0 manifests on the fly for arbitrary natural language prompts.
- **2-Tier Search Index**: Sub-5ms keyword discovery search backed by `~/.aeromesh/cache/index.json`.
- **DWM v1.0 Declarative Mesh Workflows**: Asynchronous DAG concurrency engine and crontab background daemon (`amx workflow daemon`).
- **DGAP Consensus Voting Swarms**: Multi-agent consensus voting agreement calculation (`amx pipeline`).
- **Sigstore Cryptographic Attestations**: SHA-256 digital signature bundle exporter (`amx export-bundle`).
- **Session Checkpoints & Time-Travel Replay**: Saved session checkpoint replay (`amx run --replay <id>`).

## Quickstart
```bash
pip install -e packages/aero
pytest packages/aero/tests
```
