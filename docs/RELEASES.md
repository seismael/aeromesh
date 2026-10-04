# Approved agent releases

AeroMesh releases make one specific promise: the runner uses the reviewed agent
manifests, their complete agent dependency graph, and exact MCP container image
digests, under a separately approved operator policy. Every run and resume
rechecks these inputs. This is an artifact and permission workflow, not a
certification that an agent will make correct decisions.

## Build, review, approve, run

Start with a schema-valid agent or workflow. A release can contain a single
agent with no tools, so Docker is not required for the simplest evaluation.

```sh
amx release build ./agent.json --output ./release.json
amx validate ./release.json
amx keygen --name release-author
amx sign ./release.json --key release-author
```

`keygen` prints the public-key location. On each execution installation, review
that public key through your existing trusted distribution channel and import
it explicitly. The artifact ID below is `release.json`'s `identity.id`, which
matches its entry agent or workflow ID:

```sh
amx trust <artifact-id> <reviewed-author-public-key-path>
```

Signing never automatically approves a key. A key shipped beside downloaded
content is not an independent reason to trust it.

Create an operator-owned `policy.json`. The smallest policy permits agents
without MCP tools or declared credentials:

```json
{
  "policy_version": "1",
  "allowed_credentials": [],
  "providers": {}
}
```

Review the release contents, including instructions, contracts, image entrypoint
arguments, and all embedded agents. Then approve the exact release:

```sh
amx release approve ./release.json --policy ./policy.json
amx release run ./release.json "Summarize the supplied information" --json
```

Approval prints `approved_release`, a canonical SHA-256 digest. The run command
also accepts that digest after approval, so it does not require the original
source files. Configure the desired model and provider credentials separately
before execution; `amx doctor` reports model configuration availability. Model
calls require the configured provider and are billed independently.

For a new version, create a new release file and review its permission and
content changes before signing and approving it:

```sh
amx release diff ./old.release.json ./new.release.json
```

The diff reports image, tool, credential, and environment-binding additions and
removals, changed agent digests, and entry changes. Inspect the manifest content
diff as well: changed instructions can alter behavior without adding permissions.
The machine-readable capability diff is an aid to review, not an automatic
approval decision.

Use `amx release run` for policy-managed deployments. Production MCP tools and
declared credentials require this independent release approval, including in
workflow agents and delegated subagents. Direct signed, tool-free manifests
remain usable without a release. Explicit development mode is a separate,
unrestricted authoring capability and should not be exposed as a production
admission path.

## Exact MCP grants

Production release v1 supports stdio MCP tools in **locally available,
digest-pinned Linux containers with no network and no host filesystem mounts**.
Remote SSE/HTTP servers, host commands, mutable image tags, network allowances,
skill paths, and unsupported provider types are rejected. The image entrypoint
is used; `args` supplies its arguments. An operator must provision the reviewed
image separately. Execution never pulls it automatically.

A manifest provider can request the following shape. The digest shown is an
illustrative placeholder, not an available image:

```json
{
  "type": "mcp",
  "id": "scanner",
  "transport": "stdio",
  "image": "registry.example/scanner@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "required_tools": ["scan_text"],
  "credential_bindings": {"SCANNER_TOKEN": "SCANNER_KEY"}
}
```

If a binding is present, the same agent must separately declare the credential:

```json
{"type": "credential", "id": "SCANNER_KEY"}
```

Credentials usually are unnecessary for an offline scanner; this example shows
how an explicitly needed binding is approved. Neither manifests nor policies
contain credential values. The independent operator policy must grant the
credential and bind this particular tool identity to its **exact image**:

```json
{
  "policy_version": "1",
  "allowed_credentials": ["SCANNER_KEY"],
  "providers": {
    "scanner": {
      "image": "registry.example/scanner@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "tools": ["scan_text"],
      "credential_bindings": {"SCANNER_TOKEN": "SCANNER_KEY"}
    }
  }
}
```

All omitted grants mean deny. Requested tool names must be explicit; wildcard
requests are rejected. A provider cannot substitute a different image while
retaining an approved credential binding. If separate agents require different
images, use distinct provider IDs or update the policy and reapprove the
affected releases. Reserved environment variables and language-loader injection
variables are rejected before approval.

Tool data is supplied through the MCP interface. Offline tools do not silently
gain access to a developer's checkout or services. Networked production
integrations need a separately designed and tested enforcement boundary before
they can be supported; a policy grant cannot enable that missing capability.

## What is locked

Release version `1` contains:

- The entry agent or workflow identity, kind, and canonical content digest.
- Each referenced agent's complete JSON manifest and canonical content digest.
- `agent_sha256` on every workflow and subagent reference.
- Exact image digests, enumerated tool names, instructions, arguments, contracts,
  and credential declarations as part of those signed manifests.

`release build` resolves an agent reference by ID, first beside the referring
source and then from the installed or workspace catalog. References cannot be
filesystem paths. It rejects missing dependencies, cycles, conflicting identities,
and source pins that do not match the input being read. It pins copies of
manifests bottom-up; original source files remain unchanged. Existing source
pins are checked against original source content before the copied dependency
references are locked.

The builder invokes no model, installs no code, and starts no tool. Sources are
drafts and do not require separate signatures: the final trusted release
signature approves the **entire embedded closure**. Do not interpret that as
independent endorsement of every original author's key.

Validation rejects altered digests, missing reference pins, omitted dependencies,
and unreachable extra agents. Content has a 2 MiB total limit, 256-agent maximum,
and bounded dependency depth. Canonical JSON uses the same serializer as
manifest signing; pretty-printing does not change content identity.

The model selection, Python environment, and model-provider service are not
embedded executable dependencies of this release format. Use the repository's
locked runtime deployment alongside it and retain model configuration with
operational records. A model alias may change at its provider. Identical
manifests do not promise identical model output.

## Approval lifecycle and evidence

Approval verifies the release signature against the operator's local trust store,
checks revocation, validates the closure, and compares every requested capability
with the separate policy. It materializes snapshots under
`AEROMESH_HOME/releases/<release-digest>/` and writes the approval record last.
Individual files are published through atomic replacement. A partially written
or altered installation cannot pass the subsequent integrity checks.

Every load, run, and resume rechecks:

1. The installed release's trusted signature and current signer revocation.
2. The release digest and every embedded manifest/reference digest.
3. The operator policy at the recorded absolute path and its approved content
   digest.
4. Whether the current grants authorize the release.
5. Materialized entry/agent snapshots against the signed content.

Runtime consumers use verified in-memory manifest data, not a second read of
mutable source files. Original drafts can be moved or deleted after approval.
Changing the active policy—even to add a grant—invalidates existing approvals
using that policy until `release approve` explicitly runs again. Formatting-only
changes preserve its canonical identity. Missing policies, revoked keys, and
modified snapshots fail closed. Reapproval repairs materialized copies from the
verified release and records the selected current policy.

Execution receipts identify the release, exact entry manifest, approved policy
digest, runtime package versions, session/run, and execution outcome; model usage
is included when available. Structural output
validation and execution completion are distinct from task correctness. Prompts,
outputs, and credential values are not written to receipts. Model checkpoint
storage is separate and may contain conversation/task data; operate the host
and retention controls accordingly.

The trust store, policy files, local approval records, and deployment account are
operator-controlled security state. This design does not defend against an
attacker who can rewrite that account's trust store or application code. Protect
those resources using OS permissions and the deployment's normal administration
controls. Container isolation depends on the security and correct operation of
the local container engine and host.

## Service API

The CLI delegates to `aero.services.releases`:

| Function | Result |
|---|---|
| `build_release(target_path)` | Unsigned deterministic release dictionary. |
| `validate_release(data)` | Validated dictionary or a domain error. |
| `diff_releases(old, new)` | Machine-readable content/capability changes. |
| `approve_release(path, policy_path)` | Approved canonical release digest. |
| `load_approved_release(path_or_digest)` | Freshly verified `ApprovedRelease` context. |

`ApprovedRelease.agent_data` and `entry_data` provide verified in-memory content;
`agent_paths` and `entry_path` identify installed snapshots. Runners refresh a
supplied context by digest rather than trusting a caller-constructed object.
