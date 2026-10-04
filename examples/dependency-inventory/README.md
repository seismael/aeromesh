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
