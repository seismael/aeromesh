"""Domain Error Taxonomy & Machine-Readable Exit Codes for AeroMesh CLI (AMX)."""

from enum import Enum, IntEnum

class ExitCode(IntEnum):
    SUCCESS = 0
    SCHEMA_VIOLATION = 10
    VAULT_KEY_MISSING = 20
    DOMAIN_BLOCKED = 21
    DISCOVERY_NO_MATCH = 30
    MCP_SPAWN_FAILED = 40
    MCP_TIMEOUT = 41
    JIT_BUILD_FAILED = 50

class ErrorCode(str, Enum):
    AMX_SUCCESS = "AMX_SUCCESS"
    AMX_ERR_SCHEMA_VIOLATION = "AMX_ERR_SCHEMA_VIOLATION"
    AMX_ERR_VAULT_KEY_MISSING = "AMX_ERR_VAULT_KEY_MISSING"
    AMX_ERR_DOMAIN_BLOCKED = "AMX_ERR_DOMAIN_BLOCKED"
    AMX_ERR_DISCOVERY_NO_MATCH = "AMX_ERR_DISCOVERY_NO_MATCH"
    AMX_ERR_MCP_SPAWN_FAILED = "AMX_ERR_MCP_SPAWN_FAILED"
    AMX_ERR_MCP_TIMEOUT = "AMX_ERR_MCP_TIMEOUT"
    AMX_ERR_JIT_BUILD_FAILED = "AMX_ERR_JIT_BUILD_FAILED"

class AeroMeshDomainError(Exception):
    """Base domain exception enforcing machine-readable error codes."""
    
    def __init__(self, message: str, error_code: ErrorCode, exit_code: ExitCode):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.exit_code = exit_code

    def __str__(self) -> str:
        return f"[{self.error_code.value}] (Exit {self.exit_code.value}): {self.message}"
