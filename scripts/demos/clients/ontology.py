"""Disease ontology resolution and expansion via Ubergraph.

Resolves disease names to MONDO IDs and expands them through the
ontology hierarchy (subclass traversal) for comprehensive sample
discovery.

Uses the existing SPARQLClient with the 'ubergraph' endpoint.
"""

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from clients.sparql import SPARQLClient

logger = logging.getLogger(__name__)

# MONDO namespace in Ubergraph
MONDO_URI_PREFIX = "http://purl.obolibrary.org/obo/MONDO_"


@dataclass
class MondoResolution:
    """Result of resolving a disease name to MONDO IDs."""

    query: str
    mondo_ids: List[str]  # numeric IDs like "0005311"
    labels: Dict[str, str]  # mondo_id -> label
    confidence: str  # "exact", "partial", "none"

    @property
    def top_id(self) -> Optional[str]:
        """Return the best-matching MONDO ID, or None."""
        return self.mondo_ids[0] if self.mondo_ids else None

    @property
    def top_uri(self) -> Optional[str]:
        """Return the best-matching MONDO URI, or None."""
        if self.top_id:
            return f"{MONDO_URI_PREFIX}{self.top_id}"
        return None


@dataclass
class OntologyExpansion:
    """Result of expanding a MONDO ID through the ontology hierarchy."""

    root_id: str
    expanded_ids: List[str]  # includes root_id
    labels: Dict[str, str]  # mondo_id -> label


@dataclass
class DiseaseOntologyClient:
    """Resolve disease names to MONDO IDs and expand via ontology hierarchy.

    Uses Ubergraph SPARQL for resolution and subclass traversal.

    Example:
        client = DiseaseOntologyClient()
        resolution = client.resolve_disease("atherosclerosis")
        expansion = client.expand_mondo_id(resolution.top_id)
    """

    sparql: SPARQLClient = field(default_factory=SPARQLClient)
    _cache: Dict[str, Tuple[float, object]] = field(
        default_factory=dict, repr=False
    )
    cache_ttl: float = 3600.0  # 1 hour

    def _cache_get(self, key: str) -> Optional[object]:
        """Get a value from the TTL cache."""
        if key in self._cache:
            ts, val = self._cache[key]
            if time.time() - ts < self.cache_ttl:
                return val
            del self._cache[key]
        return None

    def _cache_set(self, key: str, val: object) -> None:
        self._cache[key] = (time.time(), val)

    def resolve_disease(
        self, disease_name: str, max_results: int = 5
    ) -> MondoResolution:
        """Resolve a disease name to MONDO IDs via Ubergraph label search.

        Searches Ubergraph for entities with matching labels in the MONDO
        namespace. Results are ranked: exact match > starts-with > contains.

        Falls back to NDE health condition search if Ubergraph fails.

        Args:
            disease_name: Human-readable disease name (e.g. "atherosclerosis")
            max_results: Maximum MONDO IDs to return

        Returns:
            MondoResolution with ranked MONDO IDs and labels
        """
        cache_key = f"resolve:{disease_name.lower()}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            result = self._resolve_via_ubergraph(disease_name, max_results)
        except Exception as e:
            logger.warning("Ubergraph resolution failed: %s — trying NDE fallback", e)
            result = self._resolve_via_nde(disease_name, max_results)

        self._cache_set(cache_key, result)
        return result

    def _resolve_via_ubergraph(
        self, disease_name: str, max_results: int
    ) -> MondoResolution:
        """Search Ubergraph labels filtered to MONDO namespace."""
        escaped = disease_name.replace('"', '\\"')
        query = f'''
        SELECT DISTINCT ?uri ?label WHERE {{
            ?uri rdfs:label ?label .
            FILTER(STRSTARTS(STR(?uri), "{MONDO_URI_PREFIX}"))
            FILTER(CONTAINS(LCASE(?label), LCASE("{escaped}")))
        }} LIMIT {max_results * 3}
        '''
        results = self.sparql.query_simple(query, endpoint="ubergraph")

        if not results:
            return MondoResolution(
                query=disease_name, mondo_ids=[], labels={}, confidence="none"
            )

        # Extract MONDO IDs and rank
        candidates: List[Tuple[str, str, int]] = []
        for r in results:
            uri = r.get("uri", "")
            label = r.get("label", "")
            if not uri.startswith(MONDO_URI_PREFIX):
                continue
            mondo_id = uri[len(MONDO_URI_PREFIX):]
            rank = self._rank_match(disease_name.lower(), label.lower())
            candidates.append((mondo_id, label, rank))

        # Sort by rank (lower is better), then by label length (prefer concise)
        candidates.sort(key=lambda x: (x[2], len(x[1])))

        mondo_ids = []
        labels = {}
        seen = set()
        for mondo_id, label, _ in candidates[:max_results]:
            if mondo_id not in seen:
                mondo_ids.append(mondo_id)
                labels[mondo_id] = label
                seen.add(mondo_id)

        confidence = "none"
        if candidates:
            best_rank = candidates[0][2]
            if best_rank == 0:
                confidence = "exact"
            else:
                confidence = "partial"

        return MondoResolution(
            query=disease_name,
            mondo_ids=mondo_ids,
            labels=labels,
            confidence=confidence,
        )

    def _resolve_via_nde(
        self, disease_name: str, max_results: int
    ) -> MondoResolution:
        """Fallback: search NDE by disease name, extract MONDO IDs from annotations."""
        try:
            from clients.niaid import NIAIDClient
        except ImportError:
            return MondoResolution(
                query=disease_name, mondo_ids=[], labels={}, confidence="none"
            )

        nde = NIAIDClient()
        result = nde.search_by_disease(disease_name, size=20)

        mondo_pattern = re.compile(r"MONDO:?(\d{7})")
        mondo_ids = []
        labels: Dict[str, str] = {}
        seen = set()

        for hit in result.hits:
            annotations = NIAIDClient.extract_ontology_annotations(hit)
            for cond in annotations.get("healthCondition", []):
                identifier = cond.get("identifier", "")
                name = cond.get("name", "")
                for m in mondo_pattern.finditer(identifier):
                    mid = m.group(1)
                    if mid not in seen:
                        mondo_ids.append(mid)
                        labels[mid] = name
                        seen.add(mid)
                    if len(mondo_ids) >= max_results:
                        break

        confidence = "partial" if mondo_ids else "none"
        return MondoResolution(
            query=disease_name,
            mondo_ids=mondo_ids,
            labels=labels,
            confidence=confidence,
        )

    @staticmethod
    def _rank_match(query: str, label: str) -> int:
        """Rank a label match: 0=exact, 1=starts-with, 2=contains."""
        if query == label:
            return 0
        if label.startswith(query):
            return 1
        return 2

    def expand_mondo_id(
        self,
        mondo_id: str,
        max_depth: int = 2,
        max_terms: int = 50,
    ) -> OntologyExpansion:
        """Expand a MONDO ID to include its subtypes via Ubergraph.

        Uses rdfs:subClassOf* for full transitive closure.

        Args:
            mondo_id: Numeric MONDO ID (e.g. "0005311")
            max_depth: Not currently used (subClassOf* gets full closure)
            max_terms: Maximum terms to return

        Returns:
            OntologyExpansion with the root and all descendant MONDO IDs
        """
        cache_key = f"expand:{mondo_id}:{max_terms}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        uri = f"{MONDO_URI_PREFIX}{mondo_id}"
        subclasses = self.sparql.get_subclasses(
            uri, endpoint="ubergraph", limit=max_terms
        )

        expanded_ids = []
        labels: Dict[str, str] = {}
        seen = set()

        for sc in subclasses:
            sc_uri = sc.get("subclass", "")
            sc_label = sc.get("label", "")
            if sc_uri.startswith(MONDO_URI_PREFIX):
                sc_id = sc_uri[len(MONDO_URI_PREFIX):]
                if sc_id not in seen:
                    expanded_ids.append(sc_id)
                    if sc_label:
                        labels[sc_id] = sc_label
                    seen.add(sc_id)

        # Ensure root is included
        if mondo_id not in seen:
            expanded_ids.insert(0, mondo_id)

        result = OntologyExpansion(
            root_id=mondo_id, expanded_ids=expanded_ids, labels=labels
        )
        self._cache_set(cache_key, result)
        return result
