# Declarative Mesh Workflows (DWM v0.1)

> **Status:** shipped. A workflow is a signed DAG of already-verified agents,
> compiled into a LangGraph `StateGraph` of Deep Agents. (The earlier hand-rolled
> workflow engine and `amx pipeline` were removed; this is the replacement.)

## 1. What a workflow is

A DWM manifest declares an ordered/parallel composition of existing agents:

```json
{
  "workflow_version": "0.1.0",
  "identity": { "id": "audit-then-tune", "name": "Audit → Tune", "version": "1.0.0" },
  "steps": [
    { "id": "audit", "agent_id": "enterprise-security-auditor", "intent": "Audit this repo for secrets" },
    { "id": "tune", "agent_id": "postgres-performance-tuner", "intent": "Tune the flagged query: {audit}", "depends_on": ["audit"] }
  ],
  "output": "tune"
}
```

- `steps[].agent_id` references a **verified DAM agent** (not inline code).
- `steps[].depends_on` defines DAG edges; steps with no shared dependency run **in parallel**.
- `steps[].intent` may use `{step_id}` placeholders to inject an upstream step's result.
- `output` names the step whose result is the workflow's final answer.

## 2. Trust model (recursive)

A workflow is runnable only when **all three** hold:

1. The **workflow's own Ed25519 signature** verifies against a trusted key.
2. **Every referenced agent** resolves to a signed, trusted, non-revoked manifest.
3. Revocation of the workflow's key **or** any referenced agent's key blocks future runs.

`amx workflow install` enforces 1 and 2 (unless `--insecure`). `sign`/`verify`/
`revoke` mirror the agent commands exactly — one author identity signs both agents
and workflows.

## 3. Execution

The DAG compiles into a LangGraph `StateGraph` (no hand-rolled engine):

- each step → a node that builds a Deep Agent from the referenced DAM manifest
  (reusing `manifest_to_deepagent_kwargs` + the persistent SQLite checkpointer)
  and runs its templated intent;
- `depends_on` → graph edges; independent steps fan out in one superstep;
- a per-step output accumulator (LangGraph reducer) carries results downstream.

## 4. CLI

```
amx workflow init <id>
amx workflow sign <wf.json>
amx workflow verify <wf.json>
amx workflow install <wf.json>
amx workflow run <wf.json> "<intent>"
amx workflow share <wf.json>
amx workflow revoke <id>
```

`amx workflow run "<natural-language goal>"` (no resolvable file) asks a live LLM
to **synthesize** a DWM manifest grounded on the available agent catalog, then
executes it — the workflow equivalent of `amx run "<goal>"`.

## 5. Sharing

`registry/workflows/<id>.json` + `.sig` sidecar, and `registry/trusted/<id>.pub`
— the same publish/verify/install flow as agents. `amx workflow share` emits the
same signed payload shape as `amx share`.
