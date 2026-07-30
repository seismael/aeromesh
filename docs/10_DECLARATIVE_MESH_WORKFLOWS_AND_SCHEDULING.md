# Declarative Mesh Workflows (DWM v1.0) & Scheduled Execution Specification

**Document Version:** 1.0.0 (Authoritative Final Release)  
**Specification:** AeroMesh Declarative Mesh Workflows (DWM v1.0)  
**Schema:** [`schemas/declarative-workflow.schema.json`](file:///c:/dev/projects/aeromesh/schemas/declarative-workflow.schema.json)  

---

## 1. Executive Summary: Pipelines vs. Declarative Mesh Workflows

AeroMesh distinguishes between single-line linear execution chains and reusable, scheduled mesh workflows:

- **Pipeline (`amx pipeline`)**: Ephemeral, linear sequential chain (`Agent A -> Agent B -> Agent C`) passed directly on the command line.
- **Declarative Mesh Workflow (`amx workflow`)**: Reusable DAG specification saved as a `workflow.json` manifest. Encapsulates step topology, dependency bindings, intent templates, and crontab scheduling (`0 8 * * 1-5`).

---

## 2. Declarative Workflow Manifest Schema (`workflow.json`)

```json
{
  "workflow_version": "1.0.0",
  "identity": {
    "id": "daily-executive-email-summary",
    "name": "Daily Executive Email Summary & Action Items",
    "description": "Fetches emails, analyzes database metrics, and audits repository security.",
    "schedule": "0 8 * * 1-5"
  },
  "steps": [
    {
      "id": "step-1-tune-queries",
      "agent_id": "postgres-performance-tuner",
      "intent": "Analyze slow SQL query SELECT * FROM users"
    },
    {
      "id": "step-2-audit-secrets",
      "agent_id": "enterprise-security-auditor",
      "intent": "Audit repository secrets",
      "depends_on": ["step-1-tune-queries"]
    }
  ]
}
```

---

## 3. CLI Subcommands

### 3.1 Execute Workflow (`amx workflow run`)
```bash
amx workflow run daily_summary_workflow.json --diagnostics --non-interactive
```

### 3.2 Schedule Recurring Workflow (`amx workflow schedule`)
Registers the workflow's `schedule` field into `~/.aeromesh/schedules.json` for recurring background execution:
```bash
amx workflow schedule daily_summary_workflow.json
```
