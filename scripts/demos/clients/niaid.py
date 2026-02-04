#!/usr/bin/env python3
"""
Client for the NIAID Data Ecosystem Discovery Portal API.

The NIAID Data Ecosystem (https://data.niaid.nih.gov/) provides a unified
search API across multiple biomedical data repositories including:
- ImmPort: Immunology data
- Vivli: Clinical trial data
- RADx Data Hub: COVID-19 rapid diagnostics
- VDJServer: Adaptive immune receptor repertoire data
- Zenodo, Figshare, and many more

API Endpoint: https://api.data.niaid.nih.gov/v1/query

Query Syntax (Lucene-based):
----------------------------
1. Simple keyword search:
   q=vaccine
   q="COVID-19 vaccine"

2. Field-specific queries:
   q=healthCondition.name:"influenza"
   q=species.name:"Homo sapiens"
   q=infectiousAgent.name:"Influenza A virus"
   q=includedInDataCatalog.name:"ImmPort"

3. Ontology identifier queries:
   q=species.identifier:"9606"            # NCBI Taxonomy ID
   q=healthCondition.identifier:"0005550" # MONDO ID (without prefix)

4. Boolean combinations:
   q=vaccine AND healthCondition.name:"malaria"
   q=(influenza OR COVID-19) AND vaccine

Ontology Annotations in Records:
--------------------------------
- healthCondition: MONDO ontology (e.g., MONDO:0005550)
- species: NCBI Taxonomy (e.g., 9606 for Homo sapiens)
- infectiousAgent: NCBI Taxonomy (e.g., 2697049 for SARS-CoV-2)

Usage:
    from clients import NIAIDClient

    client = NIAIDClient()

    # Simple search
    result = client.search("vaccine")

    # Search by disease
    result = client.search_by_disease("malaria", keywords="vaccine")

    # Search by species
    result = client.search_by_species("9606")  # Human

    # Get all results with pagination
    datasets = client.fetch_all("vaccine", max_results=500)
"""

import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Iterator

import requests
from clients.http_utils import create_session


# Common ontology identifiers for reference
COMMON_SPECIES = {
    "human": "9606",
    "mouse": "10090",
    "rat": "10116",
    "chicken": "9031",
    "pig": "9823",
    "macaque": "9544",
    "zebrafish": "7955",
    "fruit_fly": "7227",
    "c_elegans": "6239",
}

COMMON_DISEASES = {
    # MONDO IDs (without MONDO: prefix)
    "infectious_disease": "0005550",
    "influenza": "0005812",
    "malaria": "0005136",
    "tuberculosis": "0018076",
    "hiv": "0005109",
    "covid19": "0100096",
    "dengue": "0005502",
    "hepatitis": "0005231",
    "asthma": "0004979",
    "diabetes": "0005015",
    "cancer": "0004992",
}

COMMON_CATALOGS = [
    "ImmPort",
    "Vivli",
    "VDJServer",
    "RADx Data Hub",
    "Zenodo",
    "Figshare",
    "NCBI GEO",
    "Omics Discovery Index (OmicsDI)",
    "Dryad Digital Repository",
    "Data Discovery Engine",
]


@dataclass
class SearchResult:
    """Container for NIAID API search results."""

    total: int
    hits: List[Dict[str, Any]]
    facets: Dict[str, Any]
    query: str
    raw: Dict[str, Any] = field(repr=False)

    def __len__(self) -> int:
        return len(self.hits)

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        return iter(self.hits)

    def __getitem__(self, index) -> Dict[str, Any]:
        return self.hits[index]

    def get_facet_values(self, facet_name: str) -> List[Dict[str, Any]]:
        """Get values for a specific facet."""
        facet = self.facets.get(facet_name, {})
        return facet.get("terms", [])


class NIAIDClient:
    """
    Client for querying the NIAID Data Ecosystem Discovery Portal.

    Example:
        client = NIAIDClient()

        # Simple keyword search
        result = client.search("vaccine", size=10)
        print(f"Found {result.total} datasets")

        # Search with disease filter
        result = client.search_by_disease("influenza", keywords="vaccine")

        # Iterate through results
        for dataset in result:
            print(dataset["name"])
    """

    BASE_URL = "https://api.data.niaid.nih.gov/v1/query"
    METADATA_URL = "https://api.data.niaid.nih.gov/v1/metadata"

    def __init__(self, timeout: int = 30, max_retries: int = 5):
        """
        Initialize the NIAID client.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = None

    @property
    def session(self) -> requests.Session:
        """Get or create the requests session."""
        if self._session is None:
            self._session = create_session(
                max_retries=self.max_retries,
                backoff_factor=1.0,
                allowed_methods=("GET",),
                user_agent="OKN-WOBD/1.0 (+https://github.com/SuLab/OKN-WOBD)",
            )
        return self._session

    # Default facet fields to request
    DEFAULT_FACETS = [
        "includedInDataCatalog.name",
        "healthCondition.name",
        "species.name",
        "infectiousAgent.name",
        "@type",
    ]

    def search(
        self,
        query: str,
        size: int = 10,
        offset: int = 0,
        extra_filter: Optional[str] = None,
        facet_size: int = 10,
        facets: Optional[List[str]] = None,
    ) -> SearchResult:
        """
        Search the NIAID Data Ecosystem.

        Args:
            query: Search query using Lucene syntax
            size: Number of results to return (max 1000)
            offset: Starting offset for pagination
            extra_filter: Additional filter expression
            facet_size: Number of facet values to return per facet
            facets: List of facet fields to include (default: common fields)

        Returns:
            SearchResult object with hits and metadata
        """
        params = {
            "q": query,
            "size": min(size, 1000),
            "facet_size": facet_size,
        }

        # Include facets
        facet_fields = facets if facets is not None else self.DEFAULT_FACETS
        if facet_fields:
            params["facets"] = ",".join(facet_fields)

        if offset > 0:
            params["from"] = offset

        if extra_filter:
            params["extra_filter"] = extra_filter

        response = self.session.get(
            self.BASE_URL,
            params=params,
            timeout=self.timeout
        )
        response.raise_for_status()
        data = response.json()

        return SearchResult(
            total=data.get("total", 0),
            hits=data.get("hits", []),
            facets=data.get("facets", {}),
            query=query,
            raw=data,
        )

    def search_by_disease(
        self,
        disease_name: str,
        keywords: Optional[str] = None,
        size: int = 10,
    ) -> SearchResult:
        """
        Search datasets by disease/health condition name.

        Args:
            disease_name: Disease name (e.g., "influenza", "malaria")
            keywords: Optional additional keywords to combine
            size: Number of results

        Returns:
            SearchResult object
        """
        query = f'healthCondition.name:"{disease_name}"'
        if keywords:
            query = f"{keywords} AND {query}"
        return self.search(query=query, size=size)

    def search_by_disease_id(
        self,
        mondo_id: str,
        keywords: Optional[str] = None,
        size: int = 10,
    ) -> SearchResult:
        """
        Search datasets by MONDO disease identifier.

        Args:
            mondo_id: MONDO ID without prefix (e.g., "0005812" for influenza)
            keywords: Optional additional keywords
            size: Number of results

        Returns:
            SearchResult object
        """
        query = f'healthCondition.identifier:"{mondo_id}"'
        if keywords:
            query = f"{keywords} AND {query}"
        return self.search(query=query, size=size)

    def search_by_species(
        self,
        species_id: str,
        keywords: Optional[str] = None,
        size: int = 10,
    ) -> SearchResult:
        """
        Search datasets by NCBI Taxonomy species ID.

        Args:
            species_id: NCBI Taxonomy ID (e.g., "9606" for human)
            keywords: Optional additional keywords
            size: Number of results

        Returns:
            SearchResult object
        """
        query = f'species.identifier:"{species_id}"'
        if keywords:
            query = f"{keywords} AND {query}"
        return self.search(query=query, size=size)

    def search_by_species_name(
        self,
        species_name: str,
        keywords: Optional[str] = None,
        size: int = 10,
    ) -> SearchResult:
        """
        Search datasets by species name.

        Args:
            species_name: Species name (e.g., "Homo sapiens", "Mus musculus")
            keywords: Optional additional keywords
            size: Number of results

        Returns:
            SearchResult object
        """
        query = f'species.name:"{species_name}"'
        if keywords:
            query = f"{keywords} AND {query}"
        return self.search(query=query, size=size)

    def search_by_pathogen(
        self,
        pathogen_name: str,
        keywords: Optional[str] = None,
        size: int = 10,
    ) -> SearchResult:
        """
        Search datasets by infectious agent/pathogen name.

        Args:
            pathogen_name: Pathogen name (e.g., "Influenza A virus")
            keywords: Optional additional keywords
            size: Number of results

        Returns:
            SearchResult object
        """
        query = f'infectiousAgent.name:"{pathogen_name}"'
        if keywords:
            query = f"{keywords} AND {query}"
        return self.search(query=query, size=size)

    def search_by_catalog(
        self,
        catalog_name: str,
        query: str = "*",
        size: int = 10,
    ) -> SearchResult:
        """
        Search datasets within a specific data catalog/repository.

        Args:
            catalog_name: Repository name (e.g., "ImmPort", "Vivli")
            query: Search query within the catalog
            size: Number of results

        Returns:
            SearchResult object
        """
        extra_filter = f'(includedInDataCatalog.name:("{catalog_name}")) AND (@type:("Dataset"))'
        return self.search(query=query, size=size, extra_filter=extra_filter)

    def fetch_all(
        self,
        query: str,
        max_results: int = 1000,
        page_size: int = 100,
        extra_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch all results for a query with automatic pagination.

        Args:
            query: Search query
            max_results: Maximum total results to fetch
            page_size: Results per API call
            extra_filter: Optional additional filter

        Returns:
            List of all dataset records
        """
        all_hits = []
        offset = 0

        while offset < max_results:
            result = self.search(
                query=query,
                size=min(page_size, max_results - offset),
                offset=offset,
                extra_filter=extra_filter,
            )

            if not result.hits:
                break

            all_hits.extend(result.hits)
            offset += len(result.hits)

            if offset >= result.total:
                break

        return all_hits

    def get_metadata(self) -> Dict[str, Any]:
        """
        Get API metadata including available data sources.

        Returns:
            Metadata dictionary with source information
        """
        response = self.session.get(self.METADATA_URL, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def extract_ontology_annotations(hit: Dict[str, Any]) -> Dict[str, List[Dict]]:
        """
        Extract ontology annotations from a dataset record.

        Args:
            hit: A single dataset record

        Returns:
            Dictionary with lists of annotations for each field
        """
        annotations = {
            "healthCondition": [],
            "species": [],
            "infectiousAgent": [],
        }

        for field_name in annotations.keys():
            items = hit.get(field_name, [])
            if not isinstance(items, list):
                items = [items] if items else []

            for item in items:
                if isinstance(item, dict):
                    annotations[field_name].append({
                        "name": item.get("name", ""),
                        "identifier": item.get("identifier", ""),
                        "ontology": item.get("inDefinedTermSet", ""),
                        "url": item.get("url", ""),
                    })

        return annotations

    @staticmethod
    def format_dataset(hit: Dict[str, Any], include_ontology: bool = False) -> str:
        """
        Format a dataset record for display.

        Args:
            hit: Dataset record
            include_ontology: Include ontology annotation details

        Returns:
            Formatted string representation
        """
        lines = []

        # Title
        lines.append(f"Title: {hit.get('name', 'Untitled')}")

        # Identifier
        identifier = hit.get("identifier") or hit.get("_id", "N/A")
        lines.append(f"ID: {identifier}")

        # Data catalog
        catalogs = hit.get("includedInDataCatalog", [])
        if catalogs:
            if isinstance(catalogs, list):
                names = [c.get("name", "Unknown") for c in catalogs if isinstance(c, dict)]
            else:
                names = [catalogs.get("name", "Unknown")]
            lines.append(f"Source: {', '.join(names)}")

        # Description
        description = hit.get("description", "")
        if description:
            if len(description) > 300:
                description = description[:297] + "..."
            lines.append(f"Description: {description}")

        # Keywords
        keywords = hit.get("keywords", [])
        if keywords:
            kw_list = keywords if isinstance(keywords, list) else [keywords]
            lines.append(f"Keywords: {', '.join(kw_list[:10])}")

        # Health conditions
        conditions = hit.get("healthCondition", [])
        if conditions:
            if isinstance(conditions, list):
                names = [c.get("name", str(c)) if isinstance(c, dict) else str(c)
                        for c in conditions[:5]]
            else:
                names = [conditions.get("name", str(conditions))
                        if isinstance(conditions, dict) else str(conditions)]
            lines.append(f"Health Conditions: {', '.join(names)}")

        # Species
        species = hit.get("species", [])
        if species:
            if isinstance(species, list):
                names = [s.get("name", str(s)) if isinstance(s, dict) else str(s)
                        for s in species[:5]]
            else:
                names = [species.get("name", str(species))
                        if isinstance(species, dict) else str(species)]
            lines.append(f"Species: {', '.join(names)}")

        # Infectious agents
        agents = hit.get("infectiousAgent", [])
        if agents:
            if isinstance(agents, list):
                names = [a.get("name", str(a)) if isinstance(a, dict) else str(a)
                        for a in agents[:5]]
            else:
                names = [agents.get("name", str(agents))
                        if isinstance(agents, dict) else str(agents)]
            lines.append(f"Infectious Agents: {', '.join(names)}")

        # URL
        url = hit.get("url", "")
        if url:
            lines.append(f"URL: {url}")

        # Ontology details
        if include_ontology:
            annotations = NIAIDClient.extract_ontology_annotations(hit)
            lines.append("\nOntology Annotations:")
            for field_name, items in annotations.items():
                if items:
                    lines.append(f"  {field_name}:")
                    for item in items[:3]:
                        if item.get("identifier"):
                            lines.append(
                                f"    - {item['name']} ({item['ontology']}:{item['identifier']})"
                            )

        return "\n".join(lines)

    def save_results(
        self,
        query: str,
        output_file: str,
        max_results: int = 100,
    ) -> int:
        """
        Search and save results to a JSON file.

        Args:
            query: Search query
            output_file: Path to output JSON file
            max_results: Maximum results to fetch

        Returns:
            Number of results saved
        """
        hits = self.fetch_all(query, max_results=max_results)

        output = {
            "query": query,
            "total_saved": len(hits),
            "hits": hits,
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)

        return len(hits)
