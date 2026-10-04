# Architecture

The dependency direction is presentation → services → infrastructure → domain. Deep Agents implements the agent loop; LangGraph schedules workflows. AeroMesh translates a deliberately small configuration surface and enforces its boundary before invoking either framework.

## Artifact lifecycle

1. A draft describes one agent or a dependency DAG. Schema validation checks versions, IDs, actual supported options, local-only JSON Schema contracts and credential declarations.
2. `release build` reads all referenced agents, rejects missing/conflicting/cyclic dependencies, embeds their exact manifests, and pins references bottom-up. Tool images must already be digest-qualified; unsupported capabilities cannot enter a release.
3. An author signs the whole release with Ed25519. Signing never grants local trust.
4. An operator imports a verified publisher key into the user-owned trust store and approves the release against a separate policy. Per-provider image identity, allowed tools and exact credential mappings are approved together.
5. Run reloads the signed release, current key revocation and the active policy. It uses validated in-memory manifest snapshots. Changed canonical policy content requires reapproval even if the changes look permissive; formatting-only edits preserve its identity.
6. The runner compiles the exact approved definitions into native Deep Agents, passing only scoped tool credentials. The model's own provider authentication is separate from tool grants.
7. Deterministic contract checks surround execution. Receipts record identifiers and status; the semantic task assessment remains unverified.

## Execution modes

| Mode | Artifact authority | Tools |
|---|---|---|
| Approved release | Trusted release signature plus active operator approval | Exact digest-pinned, network-disabled containers and scoped credentials |
| Direct trusted manifest | Explicit trusted signer, pin checks for referenced agents | Tool-free only; privileged capabilities require a release |
| Development | Explicit caller opt-in, prominently warned | Local host commands or remote endpoints; not isolated or certified |

An SDK user can execute arbitrary Python and has the host application's authority. The SDK still delegates to the same checked runner/release interfaces; it is not an isolation mechanism for hostile Python callers.

## Workflow semantics

`depends_on` compiles into native all-predecessor barriers, including unequal-depth branches. Independent steps can run concurrently. Each workflow invocation and step has a fresh thread identity; no accidental continuation from a prior run occurs. Failed execution or failed output contracts stop dependent steps. There is no rollback of already completed external effects and no exactly-once delivery claim.

Each step receives a JSON envelope containing `task`, `workflow_input`, `dependency_outputs`, and `context_handling`. Only declared predecessor outputs are supplied. `{input}` refers to root input and `{step_id}` to a declared predecessor; substitution occurs once. The identifier `input` is reserved. Upstream output is evidence, not an authorization grant. A child input contract must describe this envelope, if supplied.

Subagents resolve real manifests and pinned identities recursively; the runtime compiles their tools and contracts. A name and persona alone are never treated as a resolved capability. Unsupported skill references and coordination patterns are rejected.

## Persistence and evidence

Checkpointed agent sessions record an immutable manifest digest and snapshot, mode, and original source. Resume rechecks trust/revocation and refuses content drift or mode changes. SQLite transactions protect session metadata; a process lock prevents concurrent resumes of the same session. Native checkpoint stores retain conversation data. `DISABLED` checkpointing or `EPHEMERAL_STREAM` avoids durable conversation persistence and makes resume unavailable.

Receipts identify actual runtime package versions, model, release and policy digests, status, contract outcome and available usage. Prompts, outputs and credentials are not copied into receipts. Receipts are local operational records, not signed third-party proof; host administrators can modify local storage.

Execution responses use `output` for the returned answer. Agent responses also expose `structured_output` when an output contract is declared. `output_valid` reports structural validation, `execution_success` reports successful execution, and `task_assessment` remains `unverified`. These fields do not assert factual correctness or fulfillment of business goals.

## Bounds

The driver caps model calls/output tokens, graph recursion and wall-clock duration. Delegated agents have task-scoped state; they do not create independently resumable conversation checkpoints. Delegated execution uses the tighter parent/child step limit. Monetary budgeting requires operator-supplied input/output prices and output limits; admission reserves a conservative estimate before a call. Provider billing/tokenization can differ, so this is not a financial hard cap. Call/output limits and provider-side billing limits remain the stronger spend controls. JIT authoring has bounded attempts and explicitly declared tool-free scope.
