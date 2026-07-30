"""Aero Autonomous Agent Engine Domain Aggregates & Value Objects."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass(frozen=True)
class AgentIdentity:
    id: str
    name: str
    version: str
    author: Optional[str] = None
    license: str = "MIT"

@dataclass(frozen=True)
class AgentCapabilities:
    domain: str
    tags: List[str]
    short_description: str
    evaluation_trigger: str
    sub_domain: Optional[str] = None

@dataclass(frozen=True)
class CognitiveRuntimeProfile:
    persona: str
    success_criteria: str
    driver: str = "Driver.LangGraph"
    memory_policy: str = "CVM_LRU_PAGING"

@dataclass(frozen=True)
class CapabilityProviderRequirement:
    type: str
    id: str
    kind: Optional[str] = "credential"
    transport: Optional[str] = None
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    allowed_domains: List[str] = field(default_factory=list)

@dataclass(frozen=True)
class AgentManifest:
    manifest_version: str
    identity: AgentIdentity
    capabilities: AgentCapabilities
    cognitive_runtime: CognitiveRuntimeProfile
    providers: List[CapabilityProviderRequirement]
