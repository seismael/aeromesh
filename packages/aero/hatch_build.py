"""Bundle shared schemas both from the monorepo and from an unpacked sdist."""

from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        if self.target_name != "wheel":
            return
        package_root = Path(self.root)
        candidates = (package_root / "schemas", package_root.parents[1] / "schemas")
        schema_dir = next((path for path in candidates if path.is_dir()), None)
        if schema_dir is None:
            raise RuntimeError(
                "AeroMesh runtime schemas are missing from the build source"
            )
        build_data["force_include"][str(schema_dir)] = "aero/schemas"
