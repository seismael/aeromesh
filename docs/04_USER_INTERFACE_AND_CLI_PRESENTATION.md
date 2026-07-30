# User Interface & CLI Presentation Specification

**Document Version:** 1.0.0 (Authoritative Final Release)  
**Package Path:** [`packages/aero/src/aero/presentation/`](file:///c:/dev/projects/aeromesh/packages/aero/src/aero/presentation)  
**Rich Layout Engine:** `AMXTerminalUI`  

---

## 1. Executive Summary

The Aero Agent Engine presentation layer (`AMXTerminalUI`) provides human-centric, informative terminal rendering for CLI users:

- **Interactive Vault Resolution (`AMXTerminalUI.prompt_missing_credential`)**: When running in interactive human sessions (`non_interactive=False`), if a required secret credential is missing from environment, config, or keyring, `amx` displays a Rich panel highlighting the missing requirement, prompts the user securely, and automatically saves the acquired secret to `~/.aeromesh/credentials.json`.
- **Real-Time OTel Diagnostic Telemetry (`--diagnostics`)**: Renders structured diagnostic trace tables and performance SLA summary panels (Latency in ms, Peak RAM in MB).
- **Execution Output Panels**: Renders syntax-highlighted SQL, JSON, and step verification results.

---

## 2. Interactive Vault Resolution UI Layout

```
┌──────────────────────── 🔑 Interactive Vault Resolution ────────────────────────┐
│ Missing Required Credential: STRIPE_SECRET_KEY (Kind: bearer_token)            │
│ Please enter the value to continue execution and save securely to              │
│ ~/.aeromesh/credentials.json.                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
Enter secret for 'STRIPE_SECRET_KEY': [hidden input]
✅ Credential 'STRIPE_SECRET_KEY' acquired and saved to vault.
```
