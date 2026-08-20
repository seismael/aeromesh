"""AMX Main CLI Command Parser & Entrypoint for Aero Agent Engine."""

import sys
import json
import hashlib
import argparse
from typing import List

from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.domain.paths import (
    get_aeromesh_agents_dir,
    get_aeromesh_home,
    resolve_agent_manifest_path,
)
from aero.services.runner import AeroAgentRunnerService
from aero.services.discovery import AeroDiscoveryEngine
from aero.services import trust
from aero.infrastructure import keystore
from aero.infrastructure.guardian import GuardianSecurityScanner
from aero.presentation.ui import AeroTerminalUI


def main(args: List[str] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="amx", description="Aero Autonomous Agent Engine (AMX CLI)"
    )
    subparsers = parser.add_subparsers(dest="command", help="CLI Subcommands")

    # Command: amx search "<intent>"
    search_parser = subparsers.add_parser(
        "search", help="Search the 2-Tier Agent Registry Index"
    )
    search_parser.add_argument(
        "intent", help="Natural language intent or keyword search query"
    )

    # Command: amx audit <manifest_file>
    audit_parser = subparsers.add_parser(
        "audit",
        help="Run static security scan and SHA-256 attestation audit on a manifest",
    )
    audit_parser.add_argument("manifest", help="Path to DAM v0.1 agent.json file")

    # Command: amx export-bundle <manifest_file>
    export_parser = subparsers.add_parser(
        "export-bundle",
        help="Export an Ed25519-signed attestation bundle for a manifest",
    )
    export_parser.add_argument("manifest", help="Path to DAM v0.1 agent.json file")

    # Command: amx run <manifest_file> "<intent>" [--diagnostics] [--non-interactive] [--replay <session_id>]
    run_parser = subparsers.add_parser(
        "run", help="Run a manifest, agent ID, or a natural-language goal"
    )
    run_parser.add_argument(
        "manifest", help="Path / agent ID, or a natural-language goal (JIT synthesis)"
    )
    run_parser.add_argument(
        "intent", nargs="?", default=None, help="User intent string"
    )
    run_parser.add_argument(
        "--non-interactive", action="store_true", help="Fail if vault keys missing"
    )
    run_parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="Emit real-time OTel diagnostic metrics",
    )
    run_parser.add_argument(
        "--replay", help="Replay a previously checkpointed session ID"
    )

    # Command: amx init <agent_id>
    init_parser = subparsers.add_parser(
        "init", help="Scaffold a new DAM v0.1 boilerplate agent.json manifest"
    )
    init_parser.add_argument("agent_id", help="ID/Name of the new agent manifest")

    # Command: amx history
    subparsers.add_parser(
        "history", help="List past session checkpoints for time-travel replay"
    )

    # Command: amx vault <subcommand>
    vault_parser = subparsers.add_parser(
        "vault", help="Inspect and audit security vault credentials"
    )
    vault_subparsers = vault_parser.add_subparsers(
        dest="vault_command", help="Vault Subcommands"
    )
    v_check = vault_subparsers.add_parser(
        "check", help="Check credential status for an agent manifest"
    )
    v_check.add_argument("manifest", help="Path to DAM v0.1 agent.json file")

    v_set = vault_subparsers.add_parser(
        "set", help="Store a secret in the encrypted OS keyring"
    )
    v_set.add_argument("key", help="Credential key name (e.g. DB_CONNECT_STRING)")
    v_set.add_argument("value", help="Secret value to store")

    # Command: amx validate <manifest_file>
    val_parser = subparsers.add_parser(
        "validate", help="Validate a DAM v0.1 agent.json file"
    )
    val_parser.add_argument("manifest", help="Path to DAM v0.1 agent.json file")

    # Command: amx install <manifest_file>
    inst_parser = subparsers.add_parser(
        "install",
        help="Install an agent manifest into local store (~/.aeromesh/agents/)",
    )
    inst_parser.add_argument("manifest", help="Path to DAM v0.1 agent.json file")
    inst_parser.add_argument(
        "--insecure",
        action="store_true",
        help="Skip Ed25519 trust verification for marketplace agents",
    )

    # Command: amx share <manifest_file>
    share_parser = subparsers.add_parser(
        "share",
        help="Share a local agent manifest by generating a signed registry payload",
    )
    share_parser.add_argument("manifest", help="Path to DAM v0.1 agent.json file")

    # Command: amx keygen [--name <key>]
    keygen_parser = subparsers.add_parser(
        "keygen", help="Generate an Ed25519 signing keypair for agent attestation"
    )
    keygen_parser.add_argument("--name", default=None, help="Key name (default: 'default')")

    # Command: amx sign <manifest_file> [--key <key>]
    sign_parser = subparsers.add_parser(
        "sign", help="Sign an agent manifest with an Ed25519 key (writes .sig sidecar)"
    )
    sign_parser.add_argument("manifest", help="Path to DAM v0.1 agent.json file")
    sign_parser.add_argument("--key", default=None, help="Key name (default: 'default')")

    # Command: amx verify <manifest_file>
    verify_parser = subparsers.add_parser(
        "verify", help="Verify an agent manifest's Ed25519 signature"
    )
    verify_parser.add_argument("manifest", help="Path to DAM v0.1 agent.json file")

    # Command: amx version
    subparsers.add_parser("version", help="Show Aero Agent Engine version")

    parsed = parser.parse_args(args)

    if parsed.command == "version":
        print("aero / amx version 0.1.0 (AeroMesh DAM v0.1)")
        return 0

    if parsed.command == "keygen":
        name = getattr(parsed, "name", None) or keystore.DEFAULT_KEY_NAME
        priv_path, pub_path = trust.generate_and_store_keypair(name)
        print(f"🔑 Generated Ed25519 keypair '{name}':")
        print(f"  Private: {priv_path}")
        print(f"  Public:  {pub_path}")
        return 0

    if parsed.command == "sign":
        try:
            key_name = getattr(parsed, "key", None) or keystore.DEFAULT_KEY_NAME
            attestation = trust.sign_manifest_file(parsed.manifest, key_name)
            print(f"✍️  Signed '{parsed.manifest}' (Ed25519):")
            print(f"  SHA-256: {attestation['sha256']}")
            print(f"  Sidecar: {parsed.manifest}.sig")
            return 0
        except Exception as e:
            AeroTerminalUI.render_error(str(e))
            return 10

    if parsed.command == "verify":
        try:
            ok, reason = trust.verify_manifest_file(parsed.manifest)
            if ok:
                print(f"✅ Manifest '{parsed.manifest}' signature valid ({reason}).")
                return 0
            print(f"❌ Manifest '{parsed.manifest}' NOT verified: {reason}.")
            return 1
        except Exception as e:
            AeroTerminalUI.render_error(str(e))
            return 10

    if parsed.command == "search":
        discovery = AeroDiscoveryEngine()
        results = discovery.search(parsed.intent)
        AeroTerminalUI.render_search_results(results)
        return 0

    if parsed.command == "audit":
        try:
            with open(parsed.manifest, "r", encoding="utf-8") as f:
                content = f.read()
            scanner = GuardianSecurityScanner()
            audit_res = scanner.scan_manifest_content(content)
            AeroTerminalUI.render_security_audit(audit_res)
            return 0 if audit_res.get("is_secure") else 1
        except Exception as e:
            AeroTerminalUI.render_error(str(e))
            return 10

    if parsed.command == "export-bundle":
        try:
            with open(parsed.manifest, "r", encoding="utf-8") as f:
                content = f.read()
            scanner = GuardianSecurityScanner()
            bundle = scanner.export_bundle(content)
            print(f"📦 Exported Attestation Bundle for '{bundle['agent_id']}':")
            print(f"  Attestation: {bundle['attestation']}")
            print(f"  Status: {'SECURE ✅' if bundle['is_secure'] else 'WARNING ⚠️'}")
            return 0
        except Exception as e:
            AeroTerminalUI.render_error(str(e))
            return 10

    runner = AeroAgentRunnerService()

    if parsed.command == "init":
        file_name = f"{parsed.agent_id}.agent.json"
        template = {
            "manifest_version": "3.0.0",
            "identity": {
                "id": parsed.agent_id,
                "name": parsed.agent_id.replace("-", " ").title(),
                "version": "1.0.0",
            },
            "capabilities": {
                "domain": "Custom",
                "tags": ["custom"],
                "short_description": "Scaffolded agent",
                "evaluation_trigger": "Manual",
            },
            "cognitive_runtime": {"persona": "Assistant", "success_criteria": "Done"},
            "requirements": {"providers": []},
        }
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(template, f, indent=2)
        print(f"✨ Scaffolded boilerplate agent manifest: {file_name}")
        return 0

    if parsed.command == "history":
        chk_dir = get_aeromesh_home() / "checkpoints"
        if chk_dir.exists():
            files = list(chk_dir.glob("*.json"))
            print(f"📜 Session History Checkpoints ({len(files)}):")
            for f in files:
                print(f"  • {f.stem}")
        else:
            print(
                "📜 No session checkpoints found in %LOCALAPPDATA%\\AeroMesh\\checkpoints\\"
            )
        return 0

    if parsed.command == "vault":
        if parsed.vault_command == "check":
            try:
                manifest = runner.parser.parse_file(parsed.manifest)
                runner.vault.resolve_requirements(
                    manifest.providers, non_interactive=True
                )
                print(
                    f"🔐 Security Vault Status for '{manifest.identity.id}': ALL REQUIRED CREDENTIALS SATISFIED ✅"
                )
                return 0
            except AeroMeshDomainError as e:
                AeroTerminalUI.render_error(str(e))
                return e.exit_code.value
        elif parsed.vault_command == "set":
            try:
                runner.vault.store.set(parsed.key, parsed.value)
                print(f"🔐 Stored '{parsed.key}' in the encrypted OS keyring.")
                return 0
            except Exception as e:
                AeroTerminalUI.render_error(str(e))
                return 10

    if parsed.command == "validate":
        try:
            manifest = runner.parser.parse_file(parsed.manifest)
            print(
                f"✅ Manifest '{manifest.identity.id}' is VALID under DAM v0.1 schema."
            )
            return 0
        except AeroMeshDomainError as e:
            AeroTerminalUI.render_error(str(e))
            return e.exit_code.value

    if parsed.command == "install":
        try:
            manifest = runner.parser.parse_file(parsed.manifest)

            # Trust gate: if a trusted public key exists for this agent in the
            # git-registry trust store, the manifest MUST be signed by it.
            if not parsed.insecure:
                if trust.trusted_public_key(manifest.identity.id) is not None:
                    ok, reason = trust.verify_manifest_trusted_file(
                        parsed.manifest, manifest.identity.id
                    )
                    if not ok:
                        raise AeroMeshDomainError(
                            f"Refusing to install untrusted agent '{manifest.identity.id}': {reason}. Use --insecure to override.",
                            ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                            ExitCode.SCHEMA_VIOLATION,
                        )

            agents_dir = get_aeromesh_agents_dir()
            agents_dir.mkdir(parents=True, exist_ok=True)
            target_path = agents_dir / f"{manifest.identity.id}.json"

            with open(parsed.manifest, "r", encoding="utf-8") as f_in:
                content = f_in.read()
            with open(target_path, "w", encoding="utf-8") as f_out:
                f_out.write(content)

            print(
                f"📦 Installed agent '{manifest.identity.id}' to local store: {target_path}"
            )
            return 0
        except AeroMeshDomainError as e:
            AeroTerminalUI.render_error(str(e))
            return e.exit_code.value

    if parsed.command == "share":
        try:
            manifest = runner.parser.parse_file(parsed.manifest)
            with open(parsed.manifest, "rb") as f:
                sha256_hash = hashlib.sha256(f.read()).hexdigest()

            payload = {
                "id": manifest.identity.id,
                "version": manifest.identity.version,
                "title": manifest.identity.name,
                "domain": manifest.capabilities.domain,
                "tags": manifest.capabilities.tags,
                "short_description": manifest.capabilities.short_description,
                "evaluation_trigger": manifest.capabilities.evaluation_trigger,
                "sha256": sha256_hash,
                "pull_request_target": f"registry/agents/{manifest.identity.id}.json",
            }

            # Attach an Ed25519 attestation if a signing key exists.
            try:
                payload["attestation"] = trust.sign_manifest_file(parsed.manifest)
            except Exception:
                payload["attestation"] = None

            print(f"🚀 Registry Share Payload for '{manifest.identity.id}':")
            print(json.dumps(payload, indent=2))
            return 0
        except AeroMeshDomainError as e:
            AeroTerminalUI.render_error(str(e))
            return e.exit_code.value

    if parsed.command == "run":
        try:
            if parsed.replay:
                # Checkpoint replay: requires a resolvable manifest path.
                resolved = resolve_agent_manifest_path(parsed.manifest)
                if not resolved:
                    raise AeroMeshDomainError(
                        f"Agent file or manifest ID '{parsed.manifest}' not found.",
                        ErrorCode.AMX_ERR_DISCOVERY_NO_MATCH,
                        ExitCode.DISCOVERY_NO_MATCH,
                    )
                res = runner.run_manifest_file(
                    str(resolved),
                    parsed.intent or "Replay",
                    non_interactive=parsed.non_interactive,
                    enable_diagnostics=parsed.diagnostics,
                    replay_session_id=parsed.replay,
                )
                if res.get("is_replayed"):
                    print(
                        f"🔄 [REPLAY] Session '{res.get('session_id')}' (Agent: {res.get('agent_id')})"
                    )
                AeroTerminalUI.render_result(
                    res.get("execution_result", {}).get("verified_result", "Replayed.")
                )
                return 0

            # Resolvable manifest / agent id → direct execution (no provider preflight).
            resolved = resolve_agent_manifest_path(parsed.manifest)
            if resolved:
                res = runner.run_manifest_file(
                    str(resolved),
                    parsed.intent or parsed.manifest,
                    non_interactive=parsed.non_interactive,
                    enable_diagnostics=parsed.diagnostics,
                )
                if "manifest" in res:
                    AeroTerminalUI.render_agent_banner(res["manifest"])
                if res.get("diagnostics"):
                    AeroTerminalUI.render_diagnostics(res["diagnostics"])
                exec_res = res.get("execution_result", {})
                verified = (
                    exec_res.get("verified_result", "Completed successfully.")
                    if isinstance(exec_res, dict)
                    else str(exec_res)
                )
                AeroTerminalUI.render_result(verified)
                return 0

            # Not a resolvable manifest → treat as a natural-language goal (JIT synthesis).
            from aero.services.orchestrator import AeroMasterOrchestrator

            orchestrator = AeroMasterOrchestrator()
            res = orchestrator.dispatch(
                parsed.manifest,
                intent=parsed.intent,
                non_interactive=parsed.non_interactive,
                enable_diagnostics=parsed.diagnostics,
            )

            result = res.get("result", {})
            if "manifest" in result:
                AeroTerminalUI.render_agent_banner(result["manifest"])
            exec_res = result.get("execution_result", {})
            verified = (
                exec_res.get("verified_result", "Completed successfully.")
                if isinstance(exec_res, dict)
                else str(exec_res)
            )
            AeroTerminalUI.render_result(verified)
            return 0
        except AeroMeshDomainError as e:
            AeroTerminalUI.render_error(str(e))
            return e.exit_code.value

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
