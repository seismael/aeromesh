"""Aero Autonomous Agent Engine Domain Aggregates & Value Objects."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass(frozen=True)
class AgentIdentity:
    id: str
    name: str
    version: str
    author: Optional[str] = None
    license: Optional[str] = None
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
    memory_policy: str = "NATIVE"
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
    agent_id: Optional[str] = None
    delegation_purpose: Optional[str] = None
    image: Optional[str] = None
    credential_bindings: Dict[str, str] = field(default_factory=dict)
    agent_sha256: Optional[str] = None


@dataclass(frozen=True)
class SwarmTopology:
    pattern: str = "hierarchical"


@dataclass(frozen=True)
class ObservabilityProfile:
    cost_limit_usd: Optional[float] = None
    max_execution_steps: Optional[int] = None
    max_model_calls: Optional[int] = None
    max_output_tokens: Optional[int] = None
    input_price_per_million: Optional[float] = None
    output_price_per_million: Optional[float] = None


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
    license: Optional[str] = None
    description: Optional[str] = None


@dataclass(frozen=True)
class WorkflowStep:
    id: str
    agent_id: str
    intent: str
    depends_on: List[str] = field(default_factory=list)
    agent_sha256: Optional[str] = None


@dataclass(frozen=True)
class WorkflowManifest:
    workflow_version: str
    identity: WorkflowIdentity
    steps: List[WorkflowStep]
    output: Optional[str] = None
