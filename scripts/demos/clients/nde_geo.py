"""NDE-to-GEO study discovery.

Queries the NIAID Data Ecosystem (NDE) for GEO datasets annotated with
MONDO disease IDs and extracts GSE accessions, optionally filtering by
ARCHS4 availability.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from clients.niaid import NIAIDClient

logger = logging.getLogger(__name__)

_GSE_PATTERN = re.compile(r"(GSE\d+)")


@dataclass
class GEOStudyMatch:
    """A GEO study discovered via NDE ontology annotations."""

    gse_id: str
    title: str
    health_conditions: List[str]
    mondo_ids: List[str]
    in_archs4: Optional[bool] = None  # None = not checked


@dataclass
class NDEGeoDiscoveryResult:
    """Result of NDE-based GEO study discovery."""

    mondo_ids_queried: List[str]
    total_nde_records: int
    studies: List[GEOStudyMatch]

    @property
    def n_studies(self) -> int:
        return len(self.studies)

    @property
    def gse_ids(self) -> List[str]:
        return [s.gse_id for s in self.studies]

    @property
    def archs4_available(self) -> List[str]:
        """GSE IDs confirmed available in ARCHS4."""
        return [s.gse_id for s in self.studies if s.in_archs4 is True]


@dataclass
class NDEGeoDiscovery:
    """Discover GEO studies annotated with MONDO IDs via NDE.

    Example:
        discovery = NDEGeoDiscovery()
        result = discovery.discover_studies(["0005311"])
        print(f"Found {result.n_studies} studies")
    """

    nde_client: NIAIDClient = field(default_factory=NIAIDClient)
    _archs4_client: object = field(default=None, repr=False)

    @property
    def archs4_client(self):
        """Lazy ARCHS4 client — only initialized if filtering is requested."""
        if self._archs4_client is None:
            try:
                from clients.archs4 import ARCHS4Client

                self._archs4_client = ARCHS4Client()
            except Exception as e:
                logger.warning("ARCHS4Client unavailable: %s", e)
                self._archs4_client = False  # sentinel: tried but failed
        return self._archs4_client if self._archs4_client is not False else None

    def discover_studies(
        self,
        mondo_ids: List[str],
        max_records: int = 1000,
        species_filter: str = "Homo sapiens",
        filter_archs4: bool = True,
        batch_size: int = 10,
    ) -> NDEGeoDiscoveryResult:
        """Discover GEO datasets annotated with the given MONDO IDs.

        Uses batched OR queries to minimize NDE API calls.  For example,
        20 MONDO IDs are sent as 2 queries of 10 each instead of 20
        individual queries.

        Args:
            mondo_ids: List of numeric MONDO IDs (e.g. ["0005311", "0004993"])
            max_records: Max total NDE records to fetch
            species_filter: Species name filter (empty to skip)
            filter_archs4: If True, check each GSE against ARCHS4 availability
            batch_size: Max MONDO IDs per NDE OR-query (default 10)

        Returns:
            NDEGeoDiscoveryResult with matched studies
        """
        all_hits: List[Dict] = []
        seen_gse: Set[str] = set()
        studies: List[GEOStudyMatch] = []

        # Batch MONDO IDs into OR queries
        for i in range(0, len(mondo_ids), batch_size):
            batch = mondo_ids[i : i + batch_size]
            id_clause = " OR ".join(f'"{mid}"' for mid in batch)
            query = f"healthCondition.identifier:({id_clause})"
            if species_filter:
                query += f' AND species.name:"{species_filter}"'

            logger.info("NDE batch query: %d IDs (batch %d/%d)",
                        len(batch), i // batch_size + 1,
                        (len(mondo_ids) + batch_size - 1) // batch_size)
            try:
                hits = self.nde_client.fetch_all(
                    query=query,
                    max_results=max_records,
                    page_size=100,
                )
            except Exception as e:
                logger.warning("NDE batch query failed: %s", e)
                continue

            all_hits.extend(hits)

        # Extract GSE IDs from all hits
        for hit in all_hits:
            gse_ids = self._extract_gse_ids(hit)
            title = (hit.get("name", "") or "")[:80]
            health_conditions = self._extract_health_conditions(hit)
            hit_mondo_ids = self._extract_mondo_ids(hit)

            for gse_id in gse_ids:
                if gse_id in seen_gse:
                    continue
                seen_gse.add(gse_id)
                studies.append(
                    GEOStudyMatch(
                        gse_id=gse_id,
                        title=title,
                        health_conditions=health_conditions,
                        mondo_ids=hit_mondo_ids,
                    )
                )

        # Filter by ARCHS4 availability (batch via get_series_sample_ids)
        if filter_archs4 and studies:
            studies = self._filter_archs4_available(studies)

        return NDEGeoDiscoveryResult(
            mondo_ids_queried=mondo_ids,
            total_nde_records=len(all_hits),
            studies=studies,
        )

    def _filter_archs4_available(
        self, studies: List[GEOStudyMatch]
    ) -> List[GEOStudyMatch]:
        """Filter studies to only those present in ARCHS4."""
        client = self.archs4_client
        if client is None:
            return studies

        for study in studies:
            try:
                study.in_archs4 = client.has_series(study.gse_id)
            except Exception:
                study.in_archs4 = None
        before = len(studies)
        studies = [s for s in studies if s.in_archs4 is True]
        logger.info("ARCHS4 filter: %d/%d studies available", len(studies), before)
        return studies

    @staticmethod
    def _extract_gse_ids(hit: Dict) -> List[str]:
        """Extract GSE accessions from an NDE hit record.

        Searches identifier, url, sameAs, and distribution fields.
        Pattern adapted from questions/cross_layer_datasets.py.
        """
        gse_ids = []
        seen = set()
        for field_val in [
            hit.get("identifier", ""),
            hit.get("url", ""),
            str(hit.get("sameAs", [])),
            str(hit.get("distribution", [])),
        ]:
            if isinstance(field_val, str):
                for m in _GSE_PATTERN.findall(field_val):
                    if m not in seen:
                        gse_ids.append(m)
                        seen.add(m)
        return gse_ids

    @staticmethod
    def _extract_health_conditions(hit: Dict) -> List[str]:
        """Extract health condition names from an NDE record."""
        conditions = hit.get("healthCondition", [])
        if isinstance(conditions, dict):
            conditions = [conditions]
        names = []
        for cond in conditions:
            if isinstance(cond, dict):
                name = cond.get("name", "")
                if name:
                    names.append(name)
        return names

    @staticmethod
    def _extract_mondo_ids(hit: Dict) -> List[str]:
        """Extract MONDO IDs from an NDE record's healthCondition annotations."""
        conditions = hit.get("healthCondition", [])
        if isinstance(conditions, dict):
            conditions = [conditions]
        mondo_ids = []
        pattern = re.compile(r"MONDO:?(\d{7})")
        for cond in conditions:
            if isinstance(cond, dict):
                identifier = cond.get("identifier", "")
                for m in pattern.finditer(str(identifier)):
                    mondo_ids.append(m.group(1))
        return mondo_ids
