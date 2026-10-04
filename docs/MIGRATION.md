# Migration from 0.1

Version 0.2 deliberately rejects configurations whose earlier apparent behavior was not implemented. Back up local state before upgrading. Historical commits retain the removed examples and design proposals; those documents are not current specifications.

| Previous behavior | 0.2 behavior / action |
|---|---|
| Unknown unsigned agents install silently | Trusted install fails; sign and explicitly approve signer, or select development mode |
| Repository `registry/trusted` implicitly grants authority | Import verified keys into the local trust store with `amx trust` |
| Run assumes installation already verified | Execution/resume rechecks exact contents, signer and revocation |
| Signed MCP manifest alone can request credentials | Tools/credentials require an approved release and separate operator policy |
| Global security-provider allowlist | Per-tool requests; production containers have no network; host networking is development-only |
| Unversioned `npx` tools | Reviewed/preloaded digest-pinned container images for production |
| Generic subagent prompt from an ID | Real referenced manifest with content pin and contracts; cycles rejected |
| `CVM_LRU_PAGING`, `FULL_CONTEXT`, `ON_EVENT`, alternate drivers, consensus/pub-sub declarations | Unsupported fields fail. Use `NATIVE` / `EPHEMERAL_STREAM`, `ON_STEP` / `DISABLED`, native Deep Agents driver |
| Arbitrary skill/storage/plugin references | Unsupported until an implemented, verified packaging contract exists |
| Arbitrary format version | Only 0.2 and the implemented 0.1 subset accepted |
| Silent JIT on any missing filename | Explicit `--synthesize --development`; generated draft is persisted |
| Any nonempty answer is successful | Execution status and schema validity are explicit; task success remains unverified |
| JSON contract graded by model | Deterministic Draft 7 validation; external schema references forbidden |
| Monetary limit checked after spending | Pre-call estimated reservations plus hard call/output limits; explicit prices required |
| Shared workflow threads | Unique per-run threads, explicit root input and dependency context |
| Replay mutable manifest or missing JIT source | Immutable snapshot required; changed source/mode rejected; ephemeral sessions cannot resume |
| JSON sessions file | Transactional SQLite metadata; legacy entries without snapshots are not resumable |
| Plaintext fallback / Desktop token discovery | Disabled by default; secure credential storage required |
| `vault set KEY VALUE` exposes shell arguments | `vault set KEY` hidden prompt or `--stdin` |
| `audit`/`export-bundle` imply certification/signatures | Heuristic lint report only; use release build/sign/approve |
| Stale enterprise/demo catalog | Removed; current unsigned tool-free recipes and real dependency-inventory transport example |

Manifests use `credential_bindings: {"ENV_NAME": "DECLARED_CREDENTIAL_ID"}` on each MCP provider. Declaring a credential does not expose it to every tool. Shell/interpreter/proxy-control environment variable names are prohibited in bindings.

Workflow steps accept `agent_sha256` pins and IDs, never filesystem paths. Release building calculates pins automatically in copied manifests; it does not modify source drafts. `input` is reserved for the root task placeholder. Child input contracts in workflows describe the documented JSON envelope.
