"""AMX Main CLI Command Parser & Entrypoint for Aero Agent Engine."""

import sys
import os
import json
import hashlib
import argparse
from typing import List

from aero.domain.errors import AeroMeshDomainError
from aero.domain.paths import get_aeromesh_agents_dir, resolve_agent_manifest_path
from aero.services.runner import AeroAgentRunnerService
from aero.services.pipeline import DeterministicPipelineOrchestrator
from aero.services.workflow import AeroWorkflowEngine
from aero.presentation.ui import AeroTerminalUI

def main(args: List[str] = None) -> int:
    parser = argparse.ArgumentParser(prog="amx", description="Aero Autonomous Agent Engine (AMX CLI)")
    subparsers = parser.add_subparsers(dest="command", help="CLI Subcommands")

    # Command: amx run <manifest_file> "<intent>" [--diagnostics] [--non-interactive]
    run_parser = subparsers.add_parser("run", help="Run a single Declarative Agent Manifest")
    run_parser.add_argument("manifest", help="Path or Agent ID to DAM v3.0 agent.json file")
    run_parser.add_argument("intent", help="User intent string")
    run_parser.add_argument("--non-interactive", action="store_true", help="Fail if vault keys missing")
    run_parser.add_argument("--diagnostics", action="store_true", help="Emit real-time OTel diagnostic metrics")

    # Command: amx pipeline <manifest_1> <manifest_2> ... --intent "<intent>" [--diagnostics] [--non-interactive]
    pipe_parser = subparsers.add_parser("pipeline", help="Run a Deterministic Guaranteed Agent Pipeline (DGAP)")
    pipe_parser.add_argument("manifests", nargs="+", help="Ordered list of DAM v3.0 agent manifests")
    pipe_parser.add_argument("--intent", required=True, help="Initial high-level goal intent string")
    pipe_parser.add_argument("--non-interactive", action="store_true", help="Fail if vault keys missing")
    pipe_parser.add_argument("--diagnostics", action="store_true", help="Emit real-time OTel diagnostic metrics")

    # Command: amx workflow <subcommand> <workflow_file>
    wf_parser = subparsers.add_parser("workflow", help="Declarative Mesh Workflow (DWM v1.0) Subcommands")
    wf_subparsers = wf_parser.add_subparsers(dest="wf_command", help="Workflow Subcommands")
    
    wf_run_parser = wf_subparsers.add_parser("run", help="Run a DWM v1.0 workflow.json file")
    wf_run_parser.add_argument("workflow", help="Path to workflow.json file")
    wf_run_parser.add_argument("--non-interactive", action="store_true", help="Fail if vault keys missing")
    wf_run_parser.add_argument("--diagnostics", action="store_true", help="Emit real-time OTel diagnostic metrics")

    wf_sched_parser = wf_subparsers.add_parser("schedule", help="Schedule a DWM v1.0 workflow crontab job")
    wf_sched_parser.add_argument("workflow", help="Path to workflow.json file")

    # Command: amx validate <manifest_file>
    val_parser = subparsers.add_parser("validate", help="Validate a DAM v3.0 agent.json file")
    val_parser.add_argument("manifest", help="Path to DAM v3.0 agent.json file")

    # Command: amx install <manifest_file>
    inst_parser = subparsers.add_parser("install", help="Install an agent manifest into local store (~/.aeromesh/agents/)")
    inst_parser.add_argument("manifest", help="Path to DAM v3.0 agent.json file")

    # Command: amx share <manifest_file>
    share_parser = subparsers.add_parser("share", help="Share a local agent manifest by generating a registry pull request payload")
    share_parser.add_argument("manifest", help="Path to DAM v3.0 agent.json file")

    # Command: amx version
    subparsers.add_parser("version", help="Show Aero Agent Engine version")

    parsed = parser.parse_args(args)

    if parsed.command == "version":
        print("aero / amx version 1.0.0 (AeroMesh DAM v3.0 OpenAgent Standard)")
        return 0

    runner = AeroAgentRunnerService()

    if parsed.command == "workflow":
        wf_engine = AeroWorkflowEngine(runner_service=runner)
        if parsed.wf_command == "run":
            try:
                res = wf_engine.execute_workflow(
                    parsed.workflow,
                    non_interactive=parsed.non_interactive,
                    enable_diagnostics=parsed.diagnostics,
                )
                print(f"🔄 Executed Workflow '{res['workflow_name']}' ({res['steps_executed']} steps):")
                for s in res["step_results"]:
                    print(f"  Step '{s['step_id']}': {s['verified_output']}")
                return 0
            except AeroMeshDomainError as e:
                AeroTerminalUI.render_error(str(e))
                return e.exit_code.value
        elif parsed.wf_command == "schedule":
            try:
                res = wf_engine.schedule_workflow(parsed.workflow)
                print(f"⏰ Scheduled Workflow '{res['workflow_id']}' under crontab [{res['schedule']}]: {res['schedules_file']}")
                return 0
            except AeroMeshDomainError as e:
                AeroTerminalUI.render_error(str(e))
                return e.exit_code.value

    if parsed.command == "validate":
        try:
            manifest = runner.parser.parse_file(parsed.manifest)
            print(f"✅ Manifest '{manifest.identity.id}' is VALID under DAM v3.0 schema.")
            return 0
        except AeroMeshDomainError as e:
            AeroTerminalUI.render_error(str(e))
            return e.exit_code.value

    if parsed.command == "install":
        try:
            manifest = runner.parser.parse_file(parsed.manifest)
            agents_dir = get_aeromesh_agents_dir()
            agents_dir.mkdir(parents=True, exist_ok=True)
            target_path = agents_dir / f"{manifest.identity.id}.json"
            
            with open(parsed.manifest, "r", encoding="utf-8") as f_in:
                content = f_in.read()
            with open(target_path, "w", encoding="utf-8") as f_out:
                f_out.write(content)
                
            print(f"📦 Installed agent '{manifest.identity.id}' to local store: {target_path}")
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
                "pull_request_target": f"registry/agents/{manifest.identity.id}.json"
            }
            print(f"🚀 Registry Share Payload for '{manifest.identity.id}':")
            print(json.dumps(payload, indent=2))
            return 0
        except AeroMeshDomainError as e:
            AeroTerminalUI.render_error(str(e))
            return e.exit_code.value

    if parsed.command == "pipeline":
        try:
            orchestrator = DeterministicPipelineOrchestrator(runner_service=runner)
            res = orchestrator.execute_pipeline(
                parsed.manifests,
                parsed.intent,
                non_interactive=parsed.non_interactive,
                enable_diagnostics=parsed.diagnostics,
            )
            print(f"🔗 Executed Deterministic Guaranteed Pipeline ({res['steps_executed']} steps):")
            for step in res["pipeline_results"]:
                print(f"  Step {step['step']} [{step['agent_id']}]: {step['verified_output']}")
            return 0
        except AeroMeshDomainError as e:
            AeroTerminalUI.render_error(str(e))
            return e.exit_code.value

    if parsed.command == "run":
        try:
            resolved = resolve_agent_manifest_path(parsed.manifest)
            if not resolved:
                raise AeroMeshDomainError(
                    f"Agent file or manifest ID '{parsed.manifest}' not found in local store or registry.",
                    ErrorCode.AMX_ERR_DISCOVERY_NO_MATCH,
                    ExitCode.DISCOVERY_NO_MATCH,
                )
            target_manifest_path = str(resolved)

            res = runner.run_manifest_file(
                target_manifest_path,
                parsed.intent,
                non_interactive=parsed.non_interactive,
                enable_diagnostics=parsed.diagnostics,
            )
            AeroTerminalUI.render_agent_banner(res["manifest"])
            if res.get("diagnostics"):
                AeroTerminalUI.render_diagnostics(res["diagnostics"])
            verified_output = res["execution_result"].get("verified_result", "Completed successfully.")
            AeroTerminalUI.render_result(verified_output)
            return 0
        except AeroMeshDomainError as e:
            AeroTerminalUI.render_error(str(e))
            return e.exit_code.value

    parser.print_help()
    return 0

if __name__ == "__main__":
    sys.exit(main())
