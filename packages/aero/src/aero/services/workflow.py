"""Declarative Mesh Workflow (DWM v1.0) Execution & Scheduling Engine."""

import os
import json
import asyncio
import jsonschema
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.domain.paths import get_aeromesh_agents_dir, get_aeromesh_home
from aero.services.runner import AeroAgentRunnerService

SCHEMA_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "schemas", "declarative-workflow.schema.json")
)

class AeroWorkflowEngine:
    """Orchestrates Declarative Mesh Workflows (DWM v1.0), Concurrent Worker Pools, and Cron Schedules."""

    def __init__(self, runner_service: AeroAgentRunnerService = None, max_workers: int = 10):
        self.runner = runner_service or AeroAgentRunnerService()
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._schema = None

    def _load_schema(self) -> Dict[str, Any]:
        if self._schema is None:
            if not os.path.exists(SCHEMA_PATH):
                raise AeroMeshDomainError(
                    f"Workflow schema file missing: {SCHEMA_PATH}",
                    ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                    ExitCode.SCHEMA_VIOLATION,
                )
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                self._schema = json.load(f)
        return self._schema

    def validate_workflow_file(self, workflow_path: str) -> Dict[str, Any]:
        """Validates a DWM v1.0 workflow.json file against JSON Schema."""
        if not os.path.exists(workflow_path):
            raise AeroMeshDomainError(
                f"Workflow file not found: {workflow_path}",
                ErrorCode.AMX_ERR_DISCOVERY_NO_MATCH,
                ExitCode.DISCOVERY_NO_MATCH,
            )

        try:
            with open(workflow_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise AeroMeshDomainError(
                f"Invalid JSON in workflow file: {str(e)}",
                ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                ExitCode.SCHEMA_VIOLATION,
            )

        schema = self._load_schema()
        try:
            jsonschema.validate(instance=data, schema=schema)
        except jsonschema.ValidationError as ve:
            raise AeroMeshDomainError(
                f"Workflow Schema Validation Error: {ve.message}",
                ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                ExitCode.SCHEMA_VIOLATION,
            )

        return data

    def _resolve_manifest_path(self, step: Dict[str, Any]) -> str:
        manifest_path = step.get("manifest")
        if not manifest_path and step.get("agent_id"):
            agent_id = step["agent_id"]
            # Search local store
            local_path = get_aeromesh_agents_dir() / f"{agent_id}.json"
            if local_path.exists():
                return str(local_path)
            
            # Search workspace registry
            registry_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "registry", "agents", f"{agent_id}.json")
            )
            if os.path.exists(registry_path):
                return registry_path

            raise AeroMeshDomainError(
                f"Workflow step '{step['id']}' agent ID '{agent_id}' not found in local store or registry.",
                ErrorCode.AMX_ERR_DISCOVERY_NO_MATCH,
                ExitCode.DISCOVERY_NO_MATCH,
            )
        return manifest_path

    async def execute_workflow_async(
        self,
        workflow_path: str,
        non_interactive: bool = False,
        enable_diagnostics: bool = False,
    ) -> Dict[str, Any]:
        """Executes a DWM v1.0 workflow concurrently without blocking independent steps."""
        workflow = self.validate_workflow_file(workflow_path)
        steps = workflow["steps"]

        completed_events: Dict[str, asyncio.Event] = {step["id"]: asyncio.Event() for step in steps}
        step_outputs: Dict[str, str] = {}
        step_results: List[Dict[str, Any]] = []

        loop = asyncio.get_running_loop()

        def _run_manifest_task(m_path: str, intent_str: str):
            return self.runner.run_manifest_file(
                m_path,
                intent_str,
                non_interactive=non_interactive,
                enable_diagnostics=enable_diagnostics,
            )

        async def run_step_async(step: Dict[str, Any]):
            step_id = step["id"]
            depends_on = step.get("depends_on", [])

            # Wait asynchronously for specific dependency steps to complete
            for dep_id in depends_on:
                if dep_id in completed_events:
                    await completed_events[dep_id].wait()

            intent = step["intent"]
            for dep_id in depends_on:
                if dep_id in step_outputs:
                    intent += f"\nContext from {dep_id}: {step_outputs[dep_id]}"

            manifest_path = self._resolve_manifest_path(step)

            # Execute agent task in worker thread pool with keyword arguments
            step_res = await loop.run_in_executor(
                self.executor,
                _run_manifest_task,
                manifest_path,
                intent,
            )

            verified_output = step_res["execution_result"].get("verified_result", "")
            step_outputs[step_id] = verified_output

            step_results.append({
                "step_id": step_id,
                "manifest_path": manifest_path,
                "verified_output": verified_output,
                "diagnostics": step_res.get("diagnostics"),
            })

            # Signal that this step is complete to dependent steps
            completed_events[step_id].set()

        # Dispatch all steps concurrently into event loop
        tasks = [asyncio.create_task(run_step_async(step)) for step in steps]
        await asyncio.gather(*tasks)

        return {
            "workflow_id": workflow["identity"]["id"],
            "workflow_name": workflow["identity"]["name"],
            "schedule": workflow["identity"].get("schedule"),
            "status": "COMPLETED_SUCCESSFULLY",
            "steps_executed": len(step_results),
            "step_results": step_results,
        }

    def execute_workflow(
        self,
        workflow_path: str,
        non_interactive: bool = False,
        enable_diagnostics: bool = False,
    ) -> Dict[str, Any]:
        """Synchronous wrapper for execute_workflow_async."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    self.execute_workflow_async(workflow_path, non_interactive, enable_diagnostics)
                )
                return future.result()
        else:
            return loop.run_until_complete(
                self.execute_workflow_async(workflow_path, non_interactive, enable_diagnostics)
            )

    def schedule_workflow(self, workflow_path: str) -> Dict[str, Any]:
        """Registers a DWM v1.0 workflow as a scheduled background job."""
        workflow = self.validate_workflow_file(workflow_path)
        schedule = workflow["identity"].get("schedule")
        if not schedule:
            raise AeroMeshDomainError(
                f"Workflow '{workflow['identity']['id']}' does not contain a 'schedule' crontab field.",
                ErrorCode.AMX_ERR_SCHEMA_VIOLATION,
                ExitCode.SCHEMA_VIOLATION,
            )

        schedules_file = get_aeromesh_home() / "schedules.json"
        schedules = {}
        if schedules_file.exists():
            try:
                with open(schedules_file, "r", encoding="utf-8") as f:
                    schedules = json.load(f)
            except Exception:
                pass

        schedules[workflow["identity"]["id"]] = {
            "name": workflow["identity"]["name"],
            "schedule": schedule,
            "workflow_path": os.path.abspath(workflow_path),
        }

        schedules_file.parent.mkdir(parents=True, exist_ok=True)
        with open(schedules_file, "w", encoding="utf-8") as f:
            json.dump(schedules, f, indent=2)

        return {
            "workflow_id": workflow["identity"]["id"],
            "schedule": schedule,
            "schedules_file": str(schedules_file),
            "status": "SCHEDULED_SUCCESSFULLY",
        }
