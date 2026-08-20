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
    funding: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class AgentCapabilities:
    domain: str
    tags: List[str]
    short_description: str
    evaluation_trigger: str
    sub_domain: Optional[str] = None
    input_contract: Optional[Dict[str, Any]] = None
    output_contract: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class CognitiveRuntimeProfile:
    persona: str
    success_criteria: str
    driver: str = "Driver.LangGraph"
    memory_policy: str = "CVM_LRU_PAGING"
    checkpoint_policy: str = "ON_STEP"


@dataclass(frozen=True)
class CapabilityProviderRequirement:
    type: str
    id: str
    kind: Optional[str] = "credential"
    transport: Optional[str] = None
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    allowed_domains: List[str] = field(default_factory=list)
    uri: Optional[str] = None
    required_tools: List[str] = field(default_factory=list)
    fallback_action: Optional[str] = None
    isolation: Optional[str] = None
    agent_id: Optional[str] = None
    delegation_purpose: Optional[str] = None


@dataclass(frozen=True)
class SwarmTopology:
    pattern: str = "hierarchical"
    consensus_threshold: Optional[float] = None
    routing_key: Optional[str] = None


@dataclass(frozen=True)
class ObservabilityProfile:
    trace_level: str = "info"
    cost_limit_usd: Optional[float] = None
    max_execution_steps: Optional[int] = None


@dataclass(frozen=True)
class AgentManifest:
    manifest_version: str
    identity: AgentIdentity
    capabilities: AgentCapabilities
    cognitive_runtime: CognitiveRuntimeProfile
    providers: List[CapabilityProviderRequirement]
    swarm_topology: Optional[SwarmTopology] = None
    observability: Optional[ObservabilityProfile] = None


@dataclass(frozen=True)
class WorkflowIdentity:
    id: str
    name: str
    version: str
    author: Optional[str] = None
    license: str = "MIT"
    description: Optional[str] = None


@dataclass(frozen=True)
class WorkflowStep:
    id: str
    agent_id: str
    intent: str
    depends_on: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class WorkflowManifest:
    workflow_version: str
    identity: WorkflowIdentity
    steps: List[WorkflowStep]
    output: Optional[str] = None
