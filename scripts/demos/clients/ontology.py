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
        """Search Ubergraph labels and synonyms filtered to MONDO namespace.

        Uses a two-phase strategy:
        1. Exact text matches on labels and synonyms (fast, precise)
        2. CONTAINS matches for broader recall

        Results are ranked by match quality:
            0 = exact label match
            1 = exact synonym match
            2 = label starts with query
            3 = synonym starts with query
            4 = label contains query
            5 = broad/related/narrow synonym contains query
        """
        escaped = disease_name.replace('"', '\\"')
        obo = "http://www.geneontology.org/formats/oboInOwl#"

        # Phase 1: Exact text matches on label and all synonym types.
        # This is fast and ensures we never miss an exact match due to
        # LIMIT truncation from many partial matches.
        # NOTE: Blazegraph (Ubergraph's backend) has issues with BIND
        # inside UNION branches combined with LCASE filters. We use
        # separate simple queries instead.
        exact_label_q = f'''
        SELECT DISTINCT ?uri ?label WHERE {{
            ?uri rdfs:label ?label .
            FILTER(STRSTARTS(STR(?uri), "{MONDO_URI_PREFIX}"))
            FILTER(LCASE(?label) = LCASE("{escaped}"))
        }} LIMIT {max_results}
        '''
        exact_syn_q = f'''
        SELECT DISTINCT ?uri ?label ?match ?matchType WHERE {{
            ?uri rdfs:label ?label .
            FILTER(STRSTARTS(STR(?uri), "{MONDO_URI_PREFIX}"))
            {{
                ?uri <{obo}hasExactSynonym> ?match .
                BIND("exact_synonym" AS ?matchType)
                FILTER(LCASE(?match) = LCASE("{escaped}"))
            }} UNION {{
                ?uri <{obo}hasBroadSynonym> ?match .
                BIND("broad_synonym" AS ?matchType)
                FILTER(LCASE(?match) = LCASE("{escaped}"))
            }} UNION {{
                ?uri <{obo}hasRelatedSynonym> ?match .
                BIND("related_synonym" AS ?matchType)
                FILTER(LCASE(?match) = LCASE("{escaped}"))
            }} UNION {{
                ?uri <{obo}hasNarrowSynonym> ?match .
                BIND("narrow_synonym" AS ?matchType)
                FILTER(LCASE(?match) = LCASE("{escaped}"))
            }}
        }} LIMIT {max_results * 5}
        '''

        # Collect exact label matches with synthetic matchType
        results = []
        for r in self.sparql.query_simple(exact_label_q, endpoint="ubergraph"):
            r["match"] = r["label"]
            r["matchType"] = "label"
            results.append(r)

        results.extend(
            self.sparql.query_simple(exact_syn_q, endpoint="ubergraph")
        )

        # Phase 2: CONTAINS matches for broader recall.
        contains_query = f'''
        SELECT DISTINCT ?uri ?label ?match ?matchType WHERE {{
            ?uri rdfs:label ?label .
            FILTER(STRSTARTS(STR(?uri), "{MONDO_URI_PREFIX}"))
            {{
                ?uri <{obo}hasExactSynonym> ?match .
                BIND("exact_synonym" AS ?matchType)
                FILTER(CONTAINS(LCASE(?match), LCASE("{escaped}")))
            }} UNION {{
                ?uri <{obo}hasBroadSynonym> ?match .
                BIND("broad_synonym" AS ?matchType)
                FILTER(CONTAINS(LCASE(?match), LCASE("{escaped}")))
            }} UNION {{
                ?uri <{obo}hasRelatedSynonym> ?match .
                BIND("related_synonym" AS ?matchType)
                FILTER(CONTAINS(LCASE(?match), LCASE("{escaped}")))
            }} UNION {{
                ?uri <{obo}hasNarrowSynonym> ?match .
                BIND("narrow_synonym" AS ?matchType)
                FILTER(CONTAINS(LCASE(?match), LCASE("{escaped}")))
            }}
        }} LIMIT {max_results * 10}
        '''
        results.extend(
            self.sparql.query_simple(contains_query, endpoint="ubergraph")
        )

        if not results:
            return MondoResolution(
                query=disease_name, mondo_ids=[], labels={}, confidence="none"
            )

        # Extract MONDO IDs and track the best rank per entity.
        # SPARQL DISTINCT can collapse label and synonym rows when the
        # text is identical, so we also check the preferred label directly.
        best_rank: Dict[str, int] = {}  # mondo_id -> best rank seen
        label_for: Dict[str, str] = {}  # mondo_id -> preferred label
        query_lower = disease_name.lower()

        for r in results:
            uri = r.get("uri", "")
            label = r.get("label", "")  # always the preferred label
            match_text = r.get("match", "")
            match_type = r.get("matchType", "label")
            if not uri.startswith(MONDO_URI_PREFIX):
                continue
            mondo_id = uri[len(MONDO_URI_PREFIX):]
            label_for[mondo_id] = label

            rank = self._rank_synonym_match(
                query_lower, match_text.lower(), match_type
            )
            if mondo_id not in best_rank or rank < best_rank[mondo_id]:
                best_rank[mondo_id] = rank

        # Ensure label-based ranking is considered even if the label
        # UNION branch was deduplicated away by SPARQL DISTINCT.
        for mondo_id, label in label_for.items():
            label_rank = self._rank_synonym_match(
                query_lower, label.lower(), "label"
            )
            if label_rank < best_rank.get(mondo_id, 999):
                best_rank[mondo_id] = label_rank

        # Build sorted candidate list
        candidates: List[Tuple[str, str, int]] = [
            (mid, label_for[mid], best_rank[mid])
            for mid in best_rank
        ]
        # Sort by rank (lower is better), then by label length (prefer concise)
        candidates.sort(key=lambda x: (x[2], len(x[1])))

        mondo_ids = []
        labels = {}
        seen = set()
        for mondo_id, label, _ in candidates:
            if mondo_id not in seen:
                mondo_ids.append(mondo_id)
                labels[mondo_id] = label
                seen.add(mondo_id)
            if len(mondo_ids) >= max_results:
                break

        confidence = "none"
        if candidates:
            best_rank = candidates[0][2]
            if best_rank <= 1:
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

    @staticmethod
    def _rank_synonym_match(query: str, match_text: str, match_type: str) -> int:
        """Rank a match considering both match quality and source.

        Returns:
            0 = exact label match
            1 = exact synonym match
            2 = label starts with query
            3 = synonym starts with query
            4 = label contains query
            5 = broad/related/narrow synonym contains query
        """
        is_exact_text = query == match_text
        is_starts = match_text.startswith(query)

        if match_type == "label":
            if is_exact_text:
                return 0
            if is_starts:
                return 2
            return 4
        elif match_type == "exact_synonym":
            if is_exact_text:
                return 1
            if is_starts:
                return 3
            return 4  # exact synonym containing query ≈ label containing
        else:
            # broad, related, narrow synonyms
            if is_exact_text:
                return 1
            if is_starts:
                return 3
            return 5

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

        expanded_ids, labels = self._parse_subclass_results(subclasses)

        # Ensure root is included
        if mondo_id not in set(expanded_ids):
            expanded_ids.insert(0, mondo_id)

        result = OntologyExpansion(
            root_id=mondo_id, expanded_ids=expanded_ids, labels=labels
        )
        self._cache_set(cache_key, result)
        return result

    def expand_mondo_ids_batch(
        self,
        mondo_ids: List[str],
        max_terms: int = 50,
    ) -> Dict[str, OntologyExpansion]:
        """Expand multiple MONDO IDs in a single SPARQL query using VALUES.

        Much faster than calling expand_mondo_id() in a loop — sends one
        query to Ubergraph instead of N.

        Args:
            mondo_ids: List of numeric MONDO IDs
            max_terms: Maximum total subclass results

        Returns:
            Dict mapping each mondo_id to its OntologyExpansion
        """
        if not mondo_ids:
            return {}

        # Check cache first — only query uncached IDs
        results: Dict[str, OntologyExpansion] = {}
        uncached = []
        for mid in mondo_ids:
            cache_key = f"expand:{mid}:{max_terms}"
            cached = self._cache_get(cache_key)
            if cached is not None:
                results[mid] = cached
            else:
                uncached.append(mid)

        if not uncached:
            return results

        # Build VALUES clause for batch query
        values_entries = " ".join(
            f"<{MONDO_URI_PREFIX}{mid}>" for mid in uncached
        )
        query = f"""
        SELECT DISTINCT ?parent ?subclass ?label WHERE {{
            VALUES ?parent {{ {values_entries} }}
            ?subclass rdfs:subClassOf* ?parent .
            ?subclass a owl:Class .
            OPTIONAL {{ ?subclass rdfs:label ?label . }}
            FILTER(STRSTARTS(STR(?subclass), "{MONDO_URI_PREFIX}"))
        }} LIMIT {max_terms * len(uncached)}
        """

        try:
            rows = self.sparql.query_simple(query, endpoint="ubergraph")
        except Exception as e:
            logger.warning("Batch expansion SPARQL failed: %s — falling back to sequential", e)
            for mid in uncached:
                results[mid] = self.expand_mondo_id(mid, max_terms=max_terms)
            return results

        # Group results by parent
        by_parent: Dict[str, List[Dict[str, str]]] = {mid: [] for mid in uncached}
        for row in rows:
            parent_uri = row.get("parent", "")
            if parent_uri.startswith(MONDO_URI_PREFIX):
                parent_id = parent_uri[len(MONDO_URI_PREFIX):]
                if parent_id in by_parent:
                    by_parent[parent_id].append(row)

        # Build OntologyExpansion for each parent
        for mid in uncached:
            expanded_ids, labels = self._parse_subclass_results(
                by_parent[mid], uri_key="subclass"
            )
            if mid not in set(expanded_ids):
                expanded_ids.insert(0, mid)

            expansion = OntologyExpansion(
                root_id=mid, expanded_ids=expanded_ids, labels=labels
            )
            results[mid] = expansion
            self._cache_set(f"expand:{mid}:{max_terms}", expansion)

        return results

    @staticmethod
    def _parse_subclass_results(
        rows: List[Dict[str, str]], uri_key: str = "subclass"
    ) -> Tuple[List[str], Dict[str, str]]:
        """Parse SPARQL subclass results into ID list and label dict."""
        expanded_ids: List[str] = []
        labels: Dict[str, str] = {}
        seen: set = set()

        for sc in rows:
            sc_uri = sc.get(uri_key, "")
            sc_label = sc.get("label", "")
            if sc_uri.startswith(MONDO_URI_PREFIX):
                sc_id = sc_uri[len(MONDO_URI_PREFIX):]
                if sc_id not in seen:
                    expanded_ids.append(sc_id)
                    if sc_label:
                        labels[sc_id] = sc_label
                    seen.add(sc_id)

        return expanded_ids, labels
