"""Validate installed distributions from a directory outside the source tree.

Run after installing both built wheels in a clean virtualenv. Requires no API
keys, network access, repository schemas, registry, or user configuration.
"""

import json
import os
import subprocess
import sys
import tempfile
from importlib import metadata, resources
from pathlib import Path


def main():
    import aero

    assert Path(aero.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()), (
        "Run this check using installed wheels in a clean virtualenv"
    )
    assert metadata.version("aero") == "1.0.0"
    assert metadata.version("aeromesh-sdk") == "1.0.0"
    schema_resource = (
        resources.files("aero") / "schemas" / "declarative-agent.schema.json"
    )
    assert schema_resource.is_file(), "The installed wheel is missing runtime schemas"
    with tempfile.TemporaryDirectory(prefix="aeromesh-wheel-check-") as directory:
        work = Path(directory)
        os.chdir(work)
        os.environ["AEROMESH_HOME"] = str(work / "state")
        os.environ.pop("PYTHONPATH", None)
        from aero.infrastructure.parser import ManifestParser, WorkflowParser
        from aero import __version__
        from aeromesh import AeroKernel, __version__ as sdk_version

        assert AeroKernel is not None
        assert __version__ == metadata.version("aero")
        assert sdk_version == __version__ == metadata.version("aeromesh-sdk")
        for distribution in ("aero", "aeromesh-sdk"):
            installed = metadata.distribution(distribution)
            licenses = installed.metadata.get_all("License-File")
            assert licenses and "LICENSE" in licenses, f"{distribution} lacks license metadata"
            files = installed.files or []
            license_paths = [p for p in files if str(p).endswith(".dist-info/licenses/LICENSE")]
            assert len(license_paths) == 1, f"{distribution} lacks its packaged license"
            assert "Apache License" in installed.locate_file(license_paths[0]).read_text()
        manifest = {
            "manifest_version": "1.0.0",
            "identity": {
                "id": "wheel-smoke",
                "name": "Wheel smoke",
                "version": "1.0.0",
            },
            "capabilities": {
                "domain": "Test",
                "tags": [],
                "short_description": "Distribution validation",
                "evaluation_trigger": "manual",
            },
            "cognitive_runtime": {
                "persona": "Return the requested data.",
                "success_criteria": "Output is checked externally.",
            },
            "requirements": {"providers": []},
        }
        target = work / "agent.json"
        target.write_text(json.dumps(manifest), encoding="utf-8")
        parsed = ManifestParser().parse_file(str(target))
        assert parsed.identity.id == "wheel-smoke"
        WorkflowParser().validate_dict(
            {
                "workflow_version": "1.0.0",
                "identity": {
                    "id": "wheel-flow",
                    "name": "Wheel flow",
                    "version": "1.0.0",
                },
                "steps": [
                    {"id": "inspect", "agent_id": "wheel-smoke", "intent": "inspect"}
                ],
                "output": "inspect",
            }
        )
        cli = Path(sys.executable).parent / ("amx.exe" if os.name == "nt" else "amx")
        for arguments in (["version"], ["validate", str(target)]):
            result = subprocess.run(
                [str(cli), *arguments], capture_output=True, text=True, timeout=30
            )
            if result.returncode:
                raise RuntimeError(
                    f"Installed entry point failed: {arguments}\n{result.stdout}\n{result.stderr}"
                )
        unavailable_keyring = subprocess.run(
            [str(cli), "keygen", "--name", "unavailable-keyring"],
            env={
                **os.environ,
                "PYTHON_KEYRING_BACKEND": "keyring.backends.fail.Keyring",
            },
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert unavailable_keyring.returncode == 20, unavailable_keyring.stderr
        assert "keyring" in unavailable_keyring.stderr.lower()
        assert "Traceback" not in unavailable_keyring.stderr
        assert not list((work / "state").rglob("*.key")), (
            "Failed keygen must not persist an unprotected key"
        )
        print(
            "Installed wheel schemas, SDK import, parsers, CLI, and missing-keyring failure: PASS"
        )


if __name__ == "__main__":
    main()
