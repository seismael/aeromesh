"""Search index & discovery engine for AeroMesh (real BM25 keyword search)."""

import hashlib
import math
import re
from collections import Counter
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from aero.domain.paths import (
    get_aeromesh_agents_dir,
    get_aeromesh_workspace_registry_dir,
)
from aero.infrastructure.parser import ManifestParser

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    """Lowercase alphanumeric tokenizer (stable, dependency-free)."""
    return _TOKEN_RE.findall(text.lower())


class _BM25:
    """Compact Okapi BM25 scorer (pure Python, no external deps)."""

    def __init__(self, documents: List[List[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents = documents
        self.n = len(documents)
        self.doc_len = [len(d) for d in documents]
        self.avgdl = sum(self.doc_len) / self.n if self.n else 0.0
        self.df: Dict[str, int] = {}
        self.freqs: List[Counter] = []
        for doc in documents:
            tf = Counter(doc)
            self.freqs.append(tf)
            for term in tf:
                self.df[term] = self.df.get(term, 0) + 1

    def _idf(self, term: str) -> float:
        df = self.df.get(term, 0)
        return math.log((self.n - df + 0.5) / (df + 0.5) + 1.0)

    def score(self, query_terms: List[str], index: int) -> float:
        tf = self.freqs[index]
        dl = self.doc_len[index]
        total = 0.0
        for term in query_terms:
            if term not in tf:
                continue
            f = tf[term]
            denom = f + self.k1 * (1.0 - self.b + self.b * (dl / self.avgdl))
            total += self._idf(term) * (f * (self.k1 + 1.0)) / denom
        return total


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
    method: str
    rationale: str


class AeroDiscoveryEngine:
    """Local BM25 lexical retrieval; scores are rankings, not confidence."""

    def __init__(self, parser: Optional[ManifestParser] = None):
        self.parser = parser or ManifestParser()

    def build_registry_index(
        self, extra_paths: Optional[List[Path]] = None
    ) -> List[RegistryIndexRecord]:
        """Read local and workspace manifest metadata without persistent cache state."""
        records: List[RegistryIndexRecord] = []
        search_dirs: List[Path] = [
            get_aeromesh_agents_dir(),
            get_aeromesh_workspace_registry_dir(),
        ]

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

        return records

    def build_workspace_index(self) -> List[Dict[str, Any]]:
        """Build the shared registry catalog from workspace ``registry/agents/``.

        The CLI emits this data as JSON. It never grants trust or permissions.
        """
        registry_dir = get_aeromesh_workspace_registry_dir()
        entries: List[Dict[str, Any]] = []
        for json_file in sorted(registry_dir.glob("*.json")):
            try:
                manifest = self.parser.parse_file(str(json_file))
            except Exception:
                continue
            entries.append(
                {
                    "id": manifest.identity.id,
                    "version": manifest.identity.version,
                    "name": manifest.identity.name,
                    "domain": manifest.capabilities.domain,
                    "tags": manifest.capabilities.tags,
                    "short_description": manifest.capabilities.short_description,
                    "evaluation_trigger": manifest.capabilities.evaluation_trigger,
                    "sha256": hashlib.sha256(json_file.read_bytes()).hexdigest(),
                    "path": f"registry/agents/{json_file.name}",
                }
            )
        return entries

    @staticmethod
    def _record_document(record: RegistryIndexRecord) -> List[str]:
        text = " ".join(
            [
                record.id,
                record.name,
                record.domain,
                " ".join(record.tags),
                record.short_description,
                record.evaluation_trigger,
            ]
        )
        return _tokenize(text)

    def rank(
        self, intent: str, records: List[RegistryIndexRecord], top_k: int = 3
    ) -> List[SearchResult]:
        """Rank records by real BM25 lexical score over their metadata.

        Scores describe lexical relevance, not agent quality or correctness.
        """
        if not records:
            return []
        documents = [self._record_document(r) for r in records]
        bm25 = _BM25(documents)
        query_terms = _tokenize(intent)

        scored = []
        for index, record in enumerate(records):
            score = bm25.score(query_terms, index)
            if score > 0.0:
                scored.append((score, record))
        if not scored:
            return []

        scored.sort(key=lambda pair: pair[0], reverse=True)
        results: List[SearchResult] = []
        for score, record in scored[:top_k]:
            results.append(
                SearchResult(
                    record=record,
                    match_score=round(score, 4),
                    method="bm25",
                    rationale=f"BM25 lexical match score {score:.3f}",
                )
            )
        return results

    def search(self, intent: str, top_k: int = 3) -> List[SearchResult]:
        """BM25 keyword search over local agent metadata."""
        records = self.build_registry_index()
        return self.rank(intent, records, top_k=top_k)
