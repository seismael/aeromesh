"""Goal Decomposition Engine, Upfront Requirement Checklist & JIT Agent Manifest Synthesizer."""

import os
import json
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from aero.domain.models import (
    AgentManifest,
    AgentIdentity,
    AgentCapabilities,
    CognitiveRuntimeProfile,
    CapabilityProviderRequirement,
)
from aero.domain.paths import get_aeromesh_workspace_registry_dir, get_aeromesh_agents_dir
from aero.infrastructure.parser import ManifestParser

@dataclass
class RequirementsChecklist:
    """Upfront structured requirement checklist for a user goal."""
    goal: str
    matched_agent_ids: List[str] = field(default_factory=list)
    matched_manifests: List[AgentManifest] = field(default_factory=list)
    required_credentials: List[CapabilityProviderRequirement] = field(default_factory=list)
    is_jit_synthesized: bool = False
    synthesized_manifest: Optional[AgentManifest] = None

@dataclass
class FallbackPlan:
    """Fallback execution plan when a user rejects a required credential."""
    is_degraded: bool
    active_agent_id: str
    description: str
    manifest: AgentManifest

class AeroGoalDecompositionEngine:
    """Decomposes raw natural language intents into agent swarms, requirement checklists, and JIT manifests."""

    def __init__(self, parser: Optional[ManifestParser] = None):
        self.parser = parser or ManifestParser()

    def _load_available_manifests(self) -> List[Tuple[str, AgentManifest]]:
        """Loads all available manifests from workspace registry and local user store."""
        manifests = []
        seen_ids = set()

        search_dirs = [get_aeromesh_agents_dir(), get_aeromesh_workspace_registry_dir()]
        for d in search_dirs:
            if d.exists() and d.is_dir():
                for fpath in d.glob("*.json"):
                    try:
                        manifest = self.parser.parse_file(str(fpath))
                        if manifest.identity.id not in seen_ids:
                            seen_ids.add(manifest.identity.id)
                            manifests.append((str(fpath), manifest))
                    except Exception:
                        pass

        return manifests

    def synthesize_jit_manifest(self, goal: str) -> AgentManifest:
        """Synthesizes a valid DAM v3.0 AgentManifest on-the-fly for unknown user goals."""
        slug = re.sub(r"[^a-z0-9]+", "-", goal.lower()).strip("-")[:30]
        agent_id = f"jit-{slug}"

        identity = AgentIdentity(
            id=agent_id,
            name=f"JIT Synthesized Agent ({agent_id})",
            version="1.0.0",
            author="AeroEngine JIT Synthesizer",
            license="MIT",
        )

        capabilities = AgentCapabilities(
            domain="Dynamic Multi-Domain",
            tags=["jit", "dynamic", "auto-generated"],
            short_description=f"Auto-generated JIT agent for intent: {goal}",
            evaluation_trigger=goal,
        )

        runtime = CognitiveRuntimeProfile(
            persona=f"You are a specialized autonomous agent created for: {goal}",
            success_criteria=f"Goal criteria met: {goal}",
            driver="Driver.LangGraph",
            memory_policy="CVM_LRU_PAGING",
        )

        # Standard baseline providers
        providers = [
            CapabilityProviderRequirement(
                type="credential",
                id="SYSTEM_API_KEY",
                kind="credential",
            )
        ]

        return AgentManifest(
            manifest_version="3.0",
            identity=identity,
            capabilities=capabilities,
            cognitive_runtime=runtime,
            providers=providers,
        )

    def decompose_goal(self, goal: str) -> RequirementsChecklist:
        """Decomposes natural language goal into matching agent manifests or JIT synthesis."""
        goal_lower = goal.lower()
        available = self._load_available_manifests()

        matched_ids = []
        matched_manifests = []
        all_reqs = []

        for fpath, manifest in available:
            m_id = manifest.identity.id.lower()
            m_domain = manifest.capabilities.domain.lower()
            m_trigger = manifest.capabilities.evaluation_trigger.lower()
            m_tags = [t.lower() for t in manifest.capabilities.tags]

            matched = False
            domain_handled = False
            if "postgres" in m_id or "postgres" in m_domain:
                domain_handled = True
                if any(k in goal_lower for k in ["postgres", "sql", "db", "query", "tuner"]):
                    matched = True
            elif "security" in m_id or "security" in m_domain:
                domain_handled = True
                if any(k in goal_lower for k in ["security", "audit", "secret", "github", "cve"]):
                    matched = True
            elif "devops" in m_id:
                domain_handled = True
                if any(k in goal_lower for k in ["devops", "aws", "kubernetes", "eks", "helm"]):
                    matched = True
            elif "fintech" in m_id or "payment" in m_id:
                domain_handled = True
                if any(k in goal_lower for k in ["stripe", "plaid", "fintech", "payout", "payment"]):
                    matched = True
            elif "rag" in m_id or "pinecone" in m_id:
                domain_handled = True
                if any(k in goal_lower for k in ["rag", "pinecone", "openai", "index", "vector"]):
                    matched = True

            if not domain_handled:
                if m_domain in goal_lower or m_trigger in goal_lower or any(t in goal_lower for t in m_tags):
                    matched = True

            if matched and manifest.identity.id not in matched_ids:
                matched_ids.append(manifest.identity.id)
                matched_manifests.append(manifest)
                all_reqs.extend(manifest.providers)

        if matched_manifests:
            return RequirementsChecklist(
                goal=goal,
                matched_agent_ids=matched_ids,
                matched_manifests=matched_manifests,
                required_credentials=all_reqs,
                is_jit_synthesized=False,
            )

        # Fallback: Synthesize JIT Agent Manifest
        jit_manifest = self.synthesize_jit_manifest(goal)
        return RequirementsChecklist(
            goal=goal,
            matched_agent_ids=[jit_manifest.identity.id],
            matched_manifests=[jit_manifest],
            required_credentials=jit_manifest.providers,
            is_jit_synthesized=True,
            synthesized_manifest=jit_manifest,
        )

    def negotiate_fallback(self, checklist: RequirementsChecklist, rejected_key_id: str) -> FallbackPlan:
        """Constructs a degraded offline fallback execution plan when user rejects a credential."""
        slug = f"degraded-fallback-{rejected_key_id.lower()}"
        
        identity = AgentIdentity(
            id=slug,
            name=f"Degraded Fallback Agent ({rejected_key_id} Rejected)",
            version="1.0.0",
            author="AeroEngine Fallback Negotiator",
            license="MIT",
        )

        capabilities = AgentCapabilities(
            domain="Offline Diagnostics",
            tags=["fallback", "degraded", "offline"],
            short_description=f"Degraded offline mode bypassing {rejected_key_id}",
            evaluation_trigger=checklist.goal,
        )

        runtime = CognitiveRuntimeProfile(
            persona=f"You are an offline diagnostic agent operating without key {rejected_key_id}",
            success_criteria="Performed offline log parsing and static rule checks.",
            driver="Driver.LangGraph",
        )

        fallback_manifest = AgentManifest(
            manifest_version="3.0",
            identity=identity,
            capabilities=capabilities,
            cognitive_runtime=runtime,
            providers=[],
        )

        return FallbackPlan(
            is_degraded=True,
            active_agent_id=slug,
            description=f"Degraded offline mode active (Bypassing rejected requirement '{rejected_key_id}')",
            manifest=fallback_manifest,
        )
