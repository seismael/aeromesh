"""AeroMesh CLI: explicit trust, immutable releases, and bounded execution."""

from __future__ import annotations

import argparse
import dataclasses
import getpass
import json
import os
import sys
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path

from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.domain import paths
from aero.infrastructure.parser import ManifestParser, WorkflowParser, strict_json
from aero.services import trust

VERSION = "0.2.0"


def _error(
    message, code=ErrorCode.AMX_ERR_SCHEMA_VIOLATION, status=ExitCode.SCHEMA_VIOLATION
):
    return AeroMeshDomainError(message, code, status)


def _json(value):
    def default(obj):
        if dataclasses.is_dataclass(obj):
            return dataclasses.asdict(obj)
        if isinstance(obj, Path):
            return str(obj)
        raise TypeError(type(obj).__name__)

    print(json.dumps(value, indent=2, default=default, allow_nan=False))


def _development(args):
    enabled = getattr(args, "development", False)
    if enabled:
        print(
            "DEVELOPMENT MODE: unsigned artifacts and local tool processes are permitted; host isolation is not provided.",
            file=sys.stderr,
        )
    return enabled


def _resolve(target, workflow=False):
    resolved = (
        paths.resolve_workflow_manifest_path
        if workflow
        else paths.resolve_agent_manifest_path
    )(target)
    if resolved is None:
        raise _error(
            f"Artifact not found: {target}. Synthesis requires --synthesize --development."
        )
    if not Path(target).is_file():
        expected_id = target.removesuffix(".json")
        if _read(resolved).get("identity", {}).get("id") != expected_id:
            raise _error("Catalog reference resolved to a different artifact identity")
    return resolved


def _read(path):
    from aero.infrastructure.parser import _read_manifest

    return strict_json(_read_manifest(str(path)))


def _write_new(path, data):
    # O_EXCL preserves existing user work; no implicit --force behavior.
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write("\n")


def _template(artifact_id):
    paths.validate_artifact_id(artifact_id)
    return {
        "manifest_version": "0.2.0",
        "identity": {
            "id": artifact_id,
            "name": artifact_id.replace("-", " ").title(),
            "version": "1.0.0",
        },
        "capabilities": {
            "domain": "General",
            "tags": [],
            "short_description": "Describe the agent's bounded task.",
            "evaluation_trigger": "Manual",
        },
        "cognitive_runtime": {
            "persona": "Answer the user's request using the provided information. State limitations and do not claim actions you did not perform.",
            "success_criteria": "Provide an answer grounded in the supplied information.",
            "memory_policy": "NATIVE",
            "checkpoint_policy": "ON_STEP",
        },
        "requirements": {"providers": []},
        "observability": {
            "max_execution_steps": 40,
            "max_model_calls": 20,
            "max_output_tokens": 4096,
        },
    }


def _run_arguments(parser, target="target"):
    parser.add_argument(target)
    parser.add_argument("intent", nargs="?", default=None)
    parser.add_argument("--development", action="store_true")
    parser.add_argument(
        "--synthesize",
        action="store_true",
        help="Explicitly author a new tool-free draft (requires development mode)",
    )
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument(
        "--input-json",
        action="store_true",
        help="Parse intent as structured JSON input",
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit execution data as JSON"
    )
    parser.add_argument(
        "--diagnostics", action="store_true", help="Include actual execution metadata"
    )


def _arguments():
    parser = argparse.ArgumentParser(
        prog="amx", description="Approved agent releases on Deep Agents"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version")
    p = sub.add_parser("init")
    p.add_argument("agent_id")
    p.add_argument("--output")
    p = sub.add_parser("validate")
    p.add_argument("manifest")
    p = sub.add_parser("keygen")
    p.add_argument("--name", default="default")
    p = sub.add_parser(
        "trust",
        help="Explicitly approve an artifact signing key in this user's trust store",
    )
    p.add_argument("artifact_id")
    p.add_argument("public_key")
    p = sub.add_parser("sign")
    p.add_argument("manifest")
    p.add_argument("--key", default="default")
    p = sub.add_parser("verify")
    p.add_argument("manifest")
    p.add_argument("--signature-only", action="store_true")
    p = sub.add_parser("revoke")
    p.add_argument("artifact_id")
    p = sub.add_parser("install")
    p.add_argument("manifest")
    p.add_argument("--development", action="store_true")
    p = sub.add_parser("share")
    p.add_argument("manifest")
    p = sub.add_parser("run")
    _run_arguments(p)
    p.add_argument("--replay")
    sub.add_parser("history")
    sub.add_parser(
        "doctor",
        help="Report installed versions and isolation availability without making model calls",
    )
    p = sub.add_parser(
        "preflight",
        help="Validate local configuration, trust, and execution requirements",
    )
    p.add_argument("target")
    p.add_argument("--development", action="store_true")
    p.add_argument(
        "--probe-tools",
        action="store_true",
        help="Connect to declared MCP tools (may start an approved container)",
    )
    p = sub.add_parser("search")
    p.add_argument("intent")
    sub.add_parser("index")
    for name in ("audit", "lint", "export-bundle"):
        p = sub.add_parser(
            name, help="Static manifest lint; not a security certification"
        )
        p.add_argument("manifest")
    p = sub.add_parser("vault")
    vs = p.add_subparsers(dest="vault_command", required=True)
    v = vs.add_parser("set")
    v.add_argument("key")
    v.add_argument(
        "--stdin",
        action="store_true",
        help="Read secret from stdin instead of an interactive hidden prompt",
    )
    v = vs.add_parser("check")
    v.add_argument("manifest")
    p = sub.add_parser("workflow")
    ws = p.add_subparsers(dest="workflow_command", required=True)
    v = ws.add_parser("init")
    v.add_argument("workflow_id")
    for name in ("sign", "verify", "install", "share"):
        v = ws.add_parser(name)
        v.add_argument("workflow")
        if name == "sign":
            v.add_argument("--key", default="default")
        if name == "verify":
            v.add_argument("--signature-only", action="store_true")
        if name == "install":
            v.add_argument("--development", action="store_true")
    v = ws.add_parser("revoke")
    v.add_argument("artifact_id")
    v = ws.add_parser("run")
    _run_arguments(v, "workflow")
    p = sub.add_parser("release")
    rs = p.add_subparsers(dest="release_command", required=True)
    v = rs.add_parser("build")
    v.add_argument("target")
    v.add_argument("--output", required=True)
    v = rs.add_parser("diff")
    v.add_argument("old")
    v.add_argument("new")
    v = rs.add_parser("approve")
    v.add_argument("release")
    v.add_argument("--policy", required=True)
    v = rs.add_parser("run")
    _run_arguments(v, "release")
    return parser


def _verify(path, signature_only=False):
    if signature_only:
        ok, reason = trust.verify_manifest_file(str(path))
    else:
        data = trust.require_trusted_manifest(str(path))
        ok, reason = True, f"trusted signature valid for {data['identity']['id']}"
    _json(
        {
            "verified": ok,
            "scope": "signature_only" if signature_only else "trusted_signer",
            "reason": reason,
        }
    )
    return 0 if ok else 22


def _install(target, *, development=False, workflow=False):
    source = _resolve(target, workflow)
    data = _read(source) if development else trust.require_trusted_manifest(str(source))
    parser = WorkflowParser() if workflow else ManifestParser()
    manifest = parser.validate_dict(data)
    if workflow and not development:
        from aero.services.workflow_runner import WorkflowExecutionDriver

        # Resolve and verify the complete referenced set without model calls.
        WorkflowExecutionDriver(
            manifest, manifest_path=str(source), non_interactive=True
        ).preflight()
    target_dir = (
        paths.get_aeromesh_workflows_dir()
        if workflow
        else paths.get_aeromesh_agents_dir()
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / f"{manifest.identity.id}.json"
    if source.resolve() != dest.resolve():
        trust.atomic_write(dest, json.dumps(data, sort_keys=True, indent=2).encode())
        trust.install_attestation(str(source), str(dest))
    print(
        f"Installed {'workflow' if workflow else 'agent'} '{manifest.identity.id}' to {dest}"
    )
    return 0


def _intent(args):
    value = args.intent if args.intent is not None else "Perform the configured task."
    if args.input_json:
        try:
            return json.loads(
                value,
                parse_constant=lambda v: (_ for _ in ()).throw(
                    ValueError("Non-finite number")
                ),
            )
        except ValueError as exc:
            raise _error(f"Invalid --input-json: {exc}") from exc
    return value


def _show_run(result, args):
    if args.json:
        _json(result)
    else:
        execution = result.get("execution_result", result.get("result", result))
        if isinstance(execution, dict) and "execution_result" in execution:
            execution = execution["execution_result"]
        output = (
            execution.get("verified_result", execution)
            if isinstance(execution, dict)
            else execution
        )
        print("Result:")
        print(output if isinstance(output, str) else json.dumps(output, indent=2))
        print(
            "Task completion is not independently certified; inspect the result and domain evidence."
        )
        session = result.get("session_id") or result.get("execution_id")
        if session:
            print(f"Execution: {session}")
        if args.diagnostics:
            _json(
                result.get("diagnostics")
                or {
                    k: v
                    for k, v in execution.items()
                    if k not in {"verified_result", "output"}
                }
            )
    return 0


def _dispatch(args):
    command = args.command
    if command == "version":
        print(f"aero / amx {VERSION} (DAM/DWM 0.2; supported 0.1 subset)")
        return 0
    if command == "init":
        output = args.output or f"{args.agent_id}.agent.json"
        _write_new(output, _template(args.agent_id))
        print(f"Created {output}")
        return 0
    if command == "validate":
        data = _read(args.manifest)
        if "release_version" in data:
            from aero.services.releases import validate_release

            validate_release(data)
        else:
            (
                WorkflowParser() if "workflow_version" in data else ManifestParser()
            ).validate_dict(data)
        print(f"VALID: {data['identity']['id']}")
        return 0
    if command == "keygen":
        private, public = trust.generate_and_store_keypair(args.name)
        _json({"private_key": str(private), "public_key": str(public)})
        return 0
    if command == "trust":
        _json({"trusted_key": str(trust.trust_key(args.artifact_id, args.public_key))})
        return 0
    if command == "sign":
        _json(trust.sign_manifest_file(args.manifest, args.key))
        return 0
    if command == "verify":
        return _verify(args.manifest, args.signature_only)
    if command == "revoke":
        ok = trust.revoke_key(args.artifact_id)
        _json({"revoked": ok, "artifact_id": args.artifact_id})
        return 0 if ok else 22
    if command == "install":
        return _install(args.manifest, development=_development(args))
    if command == "share":
        data = trust.require_trusted_manifest(args.manifest)
        _json(
            {
                "identity": data["identity"],
                "attestation": trust.load_attestation(args.manifest),
                "instructions": "Publish the manifest and signature together. Recipients must independently approve its signing key.",
            }
        )
        return 0
    if command == "run":
        from aero.services.runner import AeroAgentRunnerService
        from aero.services.orchestrator import AeroMasterOrchestrator

        development = _development(args)
        if args.replay:
            if args.synthesize:
                raise _error("--replay cannot be combined with --synthesize")
            result = AeroAgentRunnerService().run_manifest_file(
                args.target,
                _intent(args),
                non_interactive=args.non_interactive,
                enable_diagnostics=args.diagnostics,
                replay_session_id=args.replay,
                development=development,
            )
        else:
            result = AeroMasterOrchestrator().dispatch(
                args.target,
                args.intent if args.synthesize else _intent(args),
                non_interactive=args.non_interactive,
                enable_diagnostics=args.diagnostics,
                development=development,
                synthesize=args.synthesize,
            )
            result = result.get("result", result)
        return _show_run(result, args)
    if command == "history":
        from aero.services.session import SessionRegistry

        _json(SessionRegistry().list())
        return 0
    if command == "doctor":
        import shutil

        dependencies = {}
        for name in (
            "aero",
            "deepagents",
            "langchain",
            "langgraph",
            "langchain-mcp-adapters",
        ):
            try:
                dependencies[name] = version(name)
            except PackageNotFoundError:
                dependencies[name] = None
        _json(
            {
                "version": VERSION,
                "dependencies": dependencies,
                "docker_available": bool(shutil.which("docker")),
                "model_configured": bool(os.environ.get("AEROMESH_MODEL")),
                "trusted_directory": str(paths.get_aeromesh_trusted_dir()),
                "networked_production_tools_supported": False,
            }
        )
        return 0
    if command == "preflight":
        from aero.services.preflight import preflight

        _json(
            preflight(
                args.target,
                development=_development(args),
                probe_tools=args.probe_tools,
            )
        )
        return 0
    if command in {"search", "index"}:
        from aero.services.discovery import AeroDiscoveryEngine

        discovery = AeroDiscoveryEngine()
        if command == "search":
            _json(discovery.search(args.intent))
        else:
            _json({"agents": discovery.build_workspace_index()})
        return 0
    if command in {"audit", "lint", "export-bundle"}:
        from aero.infrastructure.guardian import GuardianSecurityScanner

        scanner = GuardianSecurityScanner()
        raw = Path(args.manifest).read_text(encoding="utf-8")
        result = (
            scanner.scan_manifest_content(raw)
            if command != "export-bundle"
            else scanner.export_bundle(raw)
        )
        _json(result)
        return 1 if result.get("issues") else 0
    if command == "vault":
        from aero.infrastructure.vault import ZeroTrustVaultResolver

        vault = ZeroTrustVaultResolver()
        if args.vault_command == "set":
            value = (
                sys.stdin.readline().rstrip("\r\n")
                if args.stdin
                else getpass.getpass(f"Secret for {args.key}: ")
            )
            if not value:
                raise _error("Secret cannot be empty")
            vault.store.set(args.key, value)
            print(f"Stored credential {args.key}")
            return 0
        manifest = ManifestParser().parse_file(str(_resolve(args.manifest)))
        resolved = vault.resolve_requirements(manifest.providers, non_interactive=True)
        _json({"required_credentials_present": sorted(resolved)})
        return 0
    if command == "workflow":
        return _workflow(args)
    if command == "release":
        return _release(args)
    raise _error("Unsupported command")


def _workflow(args):
    command = args.workflow_command
    if command == "init":
        paths.validate_artifact_id(args.workflow_id)
        data = {
            "workflow_version": "0.2.0",
            "identity": {
                "id": args.workflow_id,
                "name": args.workflow_id,
                "version": "1.0.0",
            },
            "steps": [
                {
                    "id": "answer",
                    "agent_id": "structured-summary",
                    "intent": "Summarize the supplied input.",
                    "depends_on": [],
                }
            ],
            "output": "answer",
        }
        _write_new(f"{args.workflow_id}.workflow.json", data)
        print(f"Created {args.workflow_id}.workflow.json")
        return 0
    if command in {"sign", "verify", "share", "revoke"}:
        args.command = command
        if command != "revoke":
            args.manifest = args.workflow
        return _dispatch(args)
    if command == "install":
        return _install(args.workflow, development=_development(args), workflow=True)
    if command == "run":
        from aero.services.workflow_runner import WorkflowExecutionDriver
        from aero.services.workflow_synthesizer import WorkflowSynthesizer

        development = _development(args)
        if args.synthesize:
            if not development:
                raise _error(
                    "Synthesis runs require --development; review and sign a release for trusted use"
                )
            workflow = WorkflowSynthesizer().synthesize(args.workflow)
            path = None
        else:
            path = _resolve(args.workflow, True)
            data = (
                _read(path)
                if development
                else trust.require_trusted_manifest(str(path))
            )
            workflow = WorkflowParser().validate_dict(data)
        driver = WorkflowExecutionDriver(
            workflow,
            non_interactive=args.non_interactive,
            development=development,
            manifest_path=str(path) if path else None,
        )
        return _show_run(driver.execute(_intent(args)), args)
    raise _error("Unsupported workflow command")


def _release(args):
    from aero.services.releases import (
        build_release,
        diff_releases,
        approve_release,
        load_approved_release,
    )

    command = args.release_command
    if command == "build":
        _write_new(args.output, build_release(args.target))
        print(f"Created unsigned release draft {args.output}")
        return 0
    if command == "diff":
        _json(diff_releases(_read(args.old), _read(args.new)))
        return 0
    if command == "approve":
        _json({"approved_release": approve_release(args.release, args.policy)})
        return 0
    if command == "run":
        if args.development or args.synthesize:
            raise _error(
                "Approved release execution does not accept development or synthesis flags"
            )
        approved = load_approved_release(args.release)
        if approved.data["entry"]["kind"] == "workflow":
            from aero.services.workflow_runner import WorkflowExecutionDriver

            manifest = WorkflowParser().validate_dict(approved.entry_data)
            driver = WorkflowExecutionDriver(
                manifest,
                manifest_path=str(approved.entry_path),
                non_interactive=True,
                approved_release=approved,
            )
            result = driver.execute(_intent(args))
        else:
            from aero.services.runner import AeroAgentRunnerService

            result = AeroAgentRunnerService().run_manifest_file(
                str(approved.entry_path),
                _intent(args),
                non_interactive=True,
                enable_diagnostics=args.diagnostics,
                approved_release=approved,
            )
        return _show_run(result, args)
    raise _error("Unsupported release command")


def main(args=None):
    try:
        return _dispatch(_arguments().parse_args(args))
    except AeroMeshDomainError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return int(exc.exit_code)
    except (OSError, ValueError, KeyError) as exc:
        print(f"Error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 10
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130
    except Exception as exc:
        # Provider/backend exceptions can include credentials or request bodies.
        # Return a useful category without leaking arbitrary exception payloads.
        print(
            f"Operation failed ({type(exc).__name__}). Check model, keyring, and tool configuration with amx doctor/preflight.",
            file=sys.stderr,
        )
        return 51


if __name__ == "__main__":
    raise SystemExit(main())
