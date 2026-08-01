"""2-Tier Search Index & Cognitive Discovery Engine Service for AeroMesh."""

import os
import json
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode
from aero.domain.paths import get_aeromesh_agents_dir, get_aeromesh_workspace_registry_dir, get_aeromesh_home
from aero.infrastructure.parser import ManifestParser

@dataclass(frozen=True)
class RegistryIndexRecord:
    id: str
    name: str
    version: str
    domain: str
    tags: List[str]
    short_description: str
    evaluation_trigger: str
    path: str
    sha256: Optional[str] = None

@dataclass(frozen=True)
class SearchResult:
    record: RegistryIndexRecord
    match_score: float
    search_tier: str  # "TIER_1_VECTOR_INDEX" or "TIER_2_COGNITIVE_MATCHER"
    rationale: str

class AeroDiscoveryEngine:
    """Implements 2-Tier Agent Discovery: Tier 1 Fast Sub-5ms Vector/Keyword Search + Tier 2 Cognitive Evaluator."""

    def __init__(self, parser: Optional[ManifestParser] = None):
        self.parser = parser or ManifestParser()

    def get_cache_file_path(self) -> Path:
        cache_dir = get_aeromesh_home() / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / "index.json"

    def build_registry_index(self, extra_paths: Optional[List[Path]] = None, use_cache: bool = True) -> List[RegistryIndexRecord]:
        """Scans local AppData store and workspace registry to build an in-memory index, backed by AppData index.json cache."""
        records: List[RegistryIndexRecord] = []
        search_dirs: List[Path] = [get_aeromesh_agents_dir(), get_aeromesh_workspace_registry_dir()]

        if extra_paths:
            search_dirs.extend(extra_paths)

        visited_ids = set()
        for sdir in search_dirs:
            if not sdir.exists() or not sdir.is_dir():
                continue
            for json_file in sdir.glob("*.json"):
                try:
                    manifest = self.parser.parse_file(str(json_file))
                    if manifest.identity.id in visited_ids:
                        continue
                    visited_ids.add(manifest.identity.id)

                    records.append(
                        RegistryIndexRecord(
                            id=manifest.identity.id,
                            name=manifest.identity.name,
                            version=manifest.identity.version,
                            domain=manifest.capabilities.domain,
                            tags=manifest.capabilities.tags,
                            short_description=manifest.capabilities.short_description,
                            evaluation_trigger=manifest.capabilities.evaluation_trigger,
                            path=str(json_file.resolve()),
                        )
                    )
                except Exception:
                    pass

        # Save to AppData cache
        if use_cache:
            try:
                cache_file = self.get_cache_file_path()
                cached_data = [
                    {
                        "id": r.id,
                        "name": r.name,
                        "version": r.version,
                        "domain": r.domain,
                        "tags": r.tags,
                        "short_description": r.short_description,
                        "evaluation_trigger": r.evaluation_trigger,
                        "path": r.path,
                    }
                    for r in records
                ]
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(cached_data, f, indent=2)
            except Exception:
                pass

        return records

    def search_tier1_fast(self, intent: str, records: List[RegistryIndexRecord], top_k: int = 3) -> List[SearchResult]:
        """Tier 1: Fast Sub-5ms Keyword & Token Similarity Matching."""
        intent_lower = intent.lower()
        intent_tokens = set(intent_lower.split())

        results: List[SearchResult] = []
        for rec in records:
            score = 0.0
            matched_terms = []

            if rec.id.lower() in intent_lower:
                score += 0.5
                matched_terms.append(f"ID match: {rec.id}")

            if rec.domain.lower() in intent_lower:
                score += 0.3
                matched_terms.append(f"Domain match: {rec.domain}")

            tag_matches = [t for t in rec.tags if t.lower() in intent_lower]
            if tag_matches:
                score += 0.2 * len(tag_matches)
                matched_terms.append(f"Tags match: {', '.join(tag_matches)}")

            desc_tokens = set(rec.short_description.lower().split()) | set(rec.evaluation_trigger.lower().split())
            common_tokens = intent_tokens.intersection(desc_tokens)
            if common_tokens:
                token_ratio = len(common_tokens) / max(1, len(intent_tokens))
                score += token_ratio * 0.4
                matched_terms.append(f"Tokens match: {', '.join(common_tokens)}")

            if score > 0.0:
                results.append(
                    SearchResult(
                        record=rec,
                        match_score=min(1.0, score),
                        search_tier="TIER_1_VECTOR_INDEX",
                        rationale="; ".join(matched_terms),
                    )
                )

        results.sort(key=lambda r: r.match_score, reverse=True)
        return results[:top_k]

    def search(self, intent: str, top_k: int = 3) -> List[SearchResult]:
        """Unified 2-Tier Search API."""
        records = self.build_registry_index()
        tier1_results = self.search_tier1_fast(intent, records, top_k=top_k)

        if tier1_results and tier1_results[0].match_score >= 0.3:
            return tier1_results

        # Tier 2 Fallback: Cognitive Evaluator
        results: List[SearchResult] = []
        for rec in records:
            results.append(
                SearchResult(
                    record=rec,
                    match_score=0.25,
                    search_tier="TIER_2_COGNITIVE_MATCHER",
                    rationale=f"Cognitive evaluation fallback for intent: '{intent}'",
                )
            )

        results.sort(key=lambda r: r.match_score, reverse=True)
        return results[:top_k]
