#!/usr/bin/env python3
"""
Reusable SPARQL client for querying FRINK and other SPARQL endpoints.

FRINK (https://frink.apps.renci.org/) hosts several knowledge graphs including:
- Wikidata: General knowledge graph
- Ubergraph: Integrated ontology graph (OBO ontologies)
- SPOKE: Biomedical knowledge graph

This client provides:
1. A generic query interface for any SPARQL endpoint
2. Pre-configured FRINK endpoints
3. Helper methods for common query patterns
4. Result formatting utilities

Usage:
    from sparql_client import SPARQLClient

    client = SPARQLClient()

    # Query Wikidata via FRINK
    results = client.query('''
        SELECT ?item ?label WHERE {
            ?item wdt:P31 wd:Q11173 .
            ?item rdfs:label ?label .
            FILTER(LANG(?label) = "en")
        } LIMIT 10
    ''', endpoint="wikidata")

    # Query a custom endpoint
    results = client.query(sparql, endpoint_url="https://example.org/sparql")
"""

import json
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass

try:
    from SPARQLWrapper import SPARQLWrapper, JSON, XML, CSV, TSV
    HAS_SPARQLWRAPPER = True
except ImportError:
    HAS_SPARQLWRAPPER = False
    print("Warning: SPARQLWrapper not installed. Install with: pip install sparqlwrapper")


# Common namespace prefixes for convenience
COMMON_PREFIXES = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX schema: <http://schema.org/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX obo: <http://purl.obolibrary.org/obo/>
PREFIX MONDO: <http://purl.obolibrary.org/obo/MONDO_>
PREFIX HP: <http://purl.obolibrary.org/obo/HP_>
PREFIX GO: <http://purl.obolibrary.org/obo/GO_>
PREFIX CHEBI: <http://purl.obolibrary.org/obo/CHEBI_>
PREFIX UBERON: <http://purl.obolibrary.org/obo/UBERON_>
PREFIX CL: <http://purl.obolibrary.org/obo/CL_>
PREFIX NCBITaxon: <http://purl.obolibrary.org/obo/NCBITaxon_>
"""


@dataclass
class QueryResult:
    """Container for SPARQL query results with helper methods."""

    raw: Dict[str, Any]
    bindings: List[Dict[str, Any]]
    variables: List[str]

    def __len__(self) -> int:
        return len(self.bindings)

    def __iter__(self):
        return iter(self.bindings)

    def __getitem__(self, index):
        return self.bindings[index]

    def to_simple_dicts(self) -> List[Dict[str, str]]:
        """Convert bindings to simple {var: value} dicts, extracting just the values."""
        return [
            {var: binding[var]["value"] if var in binding else None
             for var in self.variables}
            for binding in self.bindings
        ]

    def to_list(self, variable: str) -> List[str]:
        """Extract a single variable as a list of values."""
        return [
            b[variable]["value"]
            for b in self.bindings
            if variable in b
        ]

    def first(self) -> Optional[Dict[str, Any]]:
        """Return the first result or None."""
        return self.bindings[0] if self.bindings else None


class SPARQLClient:
    """
    Reusable SPARQL client for querying FRINK and other endpoints.

    FRINK Endpoints:
    - wikidata: Wikidata knowledge graph
    - ubergraph: Integrated OBO ontology graph
    - spoke: SPOKE biomedical knowledge graph

    Example:
        client = SPARQLClient()
        results = client.query("SELECT * WHERE { ?s ?p ?o } LIMIT 10", endpoint="wikidata")
    """

    # Pre-configured FRINK endpoints (hosted by RENCI)
    FRINK_ENDPOINTS = {
        "ubergraph": "https://frink.apps.renci.org/ubergraph/sparql",
        "spoke": "https://frink.apps.renci.org/spoke/sparql",
        "frink_wikidata": "https://frink.apps.renci.org/wikidata/sparql",  # Limited subset
    }

    # Public SPARQL endpoints
    PUBLIC_ENDPOINTS = {
        "wikidata": "https://query.wikidata.org/sparql",  # Official, full Wikidata
        "dbpedia": "https://dbpedia.org/sparql",
        "uniprot": "https://sparql.uniprot.org/sparql",
        "nextprot": "https://sparql.nextprot.org/sparql",
    }

    # Combined for easy lookup
    ALL_ENDPOINTS = {**FRINK_ENDPOINTS, **PUBLIC_ENDPOINTS}

    def __init__(self, default_endpoint: str = "wikidata", timeout: int = 60):
        """
        Initialize the SPARQL client.

        Args:
            default_endpoint: Default endpoint name or URL
            timeout: Query timeout in seconds
        """
        if not HAS_SPARQLWRAPPER:
            raise ImportError("SPARQLWrapper is required. Install with: pip install sparqlwrapper")

        self.default_endpoint = default_endpoint
        self.timeout = timeout

    def _get_endpoint_url(self, endpoint: Optional[str] = None, endpoint_url: Optional[str] = None) -> str:
        """Resolve endpoint name to URL."""
        if endpoint_url:
            return endpoint_url

        endpoint = endpoint or self.default_endpoint

        if endpoint in self.ALL_ENDPOINTS:
            return self.ALL_ENDPOINTS[endpoint]
        elif endpoint.startswith("http"):
            return endpoint
        else:
            raise ValueError(
                f"Unknown endpoint: {endpoint}. "
                f"Available endpoints: {list(self.ALL_ENDPOINTS.keys())}"
            )

    def query(
        self,
        sparql: str,
        endpoint: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        include_prefixes: bool = True,
        return_format: str = "json",
    ) -> QueryResult:
        """
        Execute a SPARQL SELECT query.

        Args:
            sparql: SPARQL query string
            endpoint: Named endpoint (e.g., "wikidata", "ubergraph", "spoke")
            endpoint_url: Direct endpoint URL (overrides endpoint name)
            include_prefixes: Whether to prepend common prefixes
            return_format: Response format ("json", "xml", "csv")

        Returns:
            QueryResult object with bindings and helper methods

        Example:
            results = client.query('''
                SELECT ?disease ?label WHERE {
                    ?disease rdfs:subClassOf* obo:MONDO_0005550 .
                    ?disease rdfs:label ?label .
                } LIMIT 10
            ''', endpoint="ubergraph")
        """
        url = self._get_endpoint_url(endpoint, endpoint_url)

        # Optionally prepend common prefixes
        if include_prefixes and not sparql.strip().upper().startswith("PREFIX"):
            sparql = COMMON_PREFIXES + "\n" + sparql

        wrapper = SPARQLWrapper(url)
        wrapper.setQuery(sparql)
        wrapper.setTimeout(self.timeout)

        format_map = {"json": JSON, "xml": XML, "csv": CSV, "tsv": TSV}
        wrapper.setReturnFormat(format_map.get(return_format, JSON))

        try:
            raw_result = wrapper.query().convert()
        except Exception as e:
            raise RuntimeError(f"SPARQL query failed: {e}\nEndpoint: {url}") from e

        # Parse results
        if return_format == "json":
            bindings = raw_result.get("results", {}).get("bindings", [])
            variables = raw_result.get("head", {}).get("vars", [])
        else:
            # For non-JSON formats, return raw
            bindings = []
            variables = []

        return QueryResult(raw=raw_result, bindings=bindings, variables=variables)

    def query_simple(
        self,
        sparql: str,
        endpoint: Optional[str] = None,
        endpoint_url: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        Execute a query and return simplified results as list of dicts.

        This is a convenience method that extracts just the values from bindings.

        Returns:
            List of dicts mapping variable names to string values
        """
        result = self.query(sparql, endpoint=endpoint, endpoint_url=endpoint_url)
        return result.to_simple_dicts()

    def ask(
        self,
        sparql: str,
        endpoint: Optional[str] = None,
        endpoint_url: Optional[str] = None,
    ) -> bool:
        """
        Execute a SPARQL ASK query.

        Returns:
            Boolean result of the ASK query
        """
        url = self._get_endpoint_url(endpoint, endpoint_url)

        if not sparql.strip().upper().startswith("PREFIX"):
            sparql = COMMON_PREFIXES + "\n" + sparql

        wrapper = SPARQLWrapper(url)
        wrapper.setQuery(sparql)
        wrapper.setReturnFormat(JSON)

        result = wrapper.query().convert()
        return result.get("boolean", False)

    # =========================================================================
    # Helper methods for common queries
    # =========================================================================

    def get_label(
        self,
        uri: str,
        endpoint: str = "ubergraph",
        lang: str = "en",
    ) -> Optional[str]:
        """
        Get the rdfs:label for a URI.

        Args:
            uri: Full URI or prefixed form (e.g., "MONDO:0005550")
            endpoint: Endpoint to query
            lang: Language filter (use None for any language)

        Returns:
            Label string or None if not found
        """
        # Handle CURIE format
        if ":" in uri and not uri.startswith("http"):
            prefix, local = uri.split(":", 1)
            uri = f"{prefix}:{local}"

        lang_filter = f'FILTER(LANG(?label) = "{lang}")' if lang else ""

        query = f"""
        SELECT ?label WHERE {{
            <{uri}> rdfs:label ?label .
            {lang_filter}
        }} LIMIT 1
        """

        # Try with prefixed form
        if not uri.startswith("http"):
            query = f"""
            SELECT ?label WHERE {{
                {uri} rdfs:label ?label .
                {lang_filter}
            }} LIMIT 1
            """

        result = self.query(query, endpoint=endpoint)
        return result.to_list("label")[0] if result else None

    def get_subclasses(
        self,
        class_uri: str,
        endpoint: str = "ubergraph",
        direct_only: bool = False,
        include_labels: bool = True,
        limit: int = 100,
    ) -> List[Dict[str, str]]:
        """
        Get subclasses of an ontology class.

        Args:
            class_uri: URI or CURIE of the parent class
            endpoint: Endpoint to query
            direct_only: If True, only return direct subclasses
            include_labels: If True, include rdfs:label
            limit: Maximum results

        Returns:
            List of dicts with 'uri' and optionally 'label'
        """
        subclass_path = "rdfs:subClassOf" if direct_only else "rdfs:subClassOf*"

        label_clause = "OPTIONAL { ?subclass rdfs:label ?label . }" if include_labels else ""
        select_vars = "?subclass ?label" if include_labels else "?subclass"

        # Handle CURIE vs full URI
        if class_uri.startswith("http"):
            class_ref = f"<{class_uri}>"
        else:
            class_ref = class_uri

        query = f"""
        SELECT DISTINCT {select_vars} WHERE {{
            ?subclass {subclass_path} {class_ref} .
            ?subclass a owl:Class .
            {label_clause}
        }} LIMIT {limit}
        """

        return self.query_simple(query, endpoint=endpoint)

    def get_genes_for_go_term(
        self,
        go_id: str,
        species: str = "Q15978631",  # Homo sapiens
        endpoint: str = "wikidata",
    ) -> List[Dict[str, str]]:
        """
        Get genes associated with a GO term (via Wikidata).

        Args:
            go_id: GO identifier (e.g., "GO:0006915" for apoptosis)
            species: Wikidata entity ID for species (default: human)
            endpoint: Endpoint to query

        Returns:
            List of dicts with 'symbol' and 'entrez' keys
        """
        query = f'''
        SELECT DISTINCT ?symbol ?entrez WHERE {{
            ?go_term wdt:P686 "{go_id}" .
            ?protein wdt:P682 ?go_term ;
                     wdt:P703 wd:{species} ;
                     wdt:P702 ?gene .
            ?gene wdt:P353 ?symbol ;
                  wdt:P351 ?entrez .
        }}
        '''
        return self.query_simple(query, endpoint=endpoint)

    def get_disease_genes(
        self,
        disease_id: str,
        endpoint: str = "wikidata",
    ) -> List[Dict[str, str]]:
        """
        Get genes associated with a disease (via Wikidata).

        Args:
            disease_id: Disease identifier (MONDO, DOID, etc.)
            endpoint: Endpoint to query

        Returns:
            List of dicts with gene information
        """
        query = f'''
        SELECT DISTINCT ?gene ?symbol ?entrez WHERE {{
            ?disease wdt:P5270|wdt:P699|wdt:P486 "{disease_id}" .
            ?gene wdt:P2293 ?disease ;
                  wdt:P353 ?symbol .
            OPTIONAL {{ ?gene wdt:P351 ?entrez . }}
        }}
        '''
        return self.query_simple(query, endpoint=endpoint)

    def search_by_label(
        self,
        search_term: str,
        endpoint: str = "ubergraph",
        limit: int = 20,
    ) -> List[Dict[str, str]]:
        """
        Search for entities by label (case-insensitive contains).

        Args:
            search_term: Text to search for in labels
            endpoint: Endpoint to query
            limit: Maximum results

        Returns:
            List of dicts with 'uri' and 'label'
        """
        query = f'''
        SELECT DISTINCT ?uri ?label WHERE {{
            ?uri rdfs:label ?label .
            FILTER(CONTAINS(LCASE(?label), LCASE("{search_term}")))
        }} LIMIT {limit}
        '''
        return self.query_simple(query, endpoint=endpoint)

    def get_gene_info(
        self,
        gene_symbol: str,
        species: str = "Q15978631",  # Homo sapiens
        endpoint: str = "wikidata",
    ) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive information about a gene from Wikidata.

        Args:
            gene_symbol: Gene symbol (e.g., "ACTA2")
            species: Wikidata entity ID for species (default: human)
            endpoint: Endpoint to query

        Returns:
            Dict with gene information including:
            - symbol: Gene symbol
            - entrez_id: NCBI Entrez Gene ID
            - ensembl_id: Ensembl gene ID
            - uniprot_ids: List of UniProt accessions
            - name: Full gene name
            - description: Gene description
            - go_terms: Associated GO term IDs
        """
        query = f'''
        SELECT DISTINCT ?gene ?symbol ?entrez ?ensembl ?uniprot ?name ?description ?go_id WHERE {{
            ?gene wdt:P353 "{gene_symbol}" ;
                  wdt:P703 wd:{species} .

            OPTIONAL {{ ?gene wdt:P353 ?symbol . }}
            OPTIONAL {{ ?gene wdt:P351 ?entrez . }}
            OPTIONAL {{ ?gene wdt:P594 ?ensembl . }}
            OPTIONAL {{ ?gene rdfs:label ?name . FILTER(LANG(?name) = "en") }}
            OPTIONAL {{ ?gene schema:description ?description . FILTER(LANG(?description) = "en") }}

            OPTIONAL {{
                ?gene wdt:P702 ?protein .
                ?protein wdt:P352 ?uniprot .
            }}

            OPTIONAL {{
                ?gene wdt:P702 ?protein2 .
                ?protein2 wdt:P682 ?go_term .
                ?go_term wdt:P686 ?go_id .
            }}
        }}
        '''

        results = self.query_simple(query, endpoint=endpoint)

        if not results:
            return None

        # Aggregate results (multiple rows for multiple UniProt/GO terms)
        gene_info = {
            "symbol": gene_symbol,
            "entrez_id": None,
            "ensembl_id": None,
            "uniprot_ids": [],
            "name": None,
            "description": None,
            "go_terms": [],
            "wikidata_id": None,
        }

        seen_uniprot = set()
        seen_go = set()

        for row in results:
            # Extract single-value fields from first row
            if gene_info["entrez_id"] is None and row.get("entrez"):
                gene_info["entrez_id"] = row["entrez"]
            if gene_info["ensembl_id"] is None and row.get("ensembl"):
                gene_info["ensembl_id"] = row["ensembl"]
            if gene_info["name"] is None and row.get("name"):
                gene_info["name"] = row["name"]
            if gene_info["description"] is None and row.get("description"):
                gene_info["description"] = row["description"]
            if gene_info["wikidata_id"] is None and row.get("gene"):
                # Extract Q-number from URI
                gene_uri = row["gene"]
                if "wikidata.org/entity/" in gene_uri:
                    gene_info["wikidata_id"] = gene_uri.split("/")[-1]

            # Collect multi-value fields
            if row.get("uniprot") and row["uniprot"] not in seen_uniprot:
                gene_info["uniprot_ids"].append(row["uniprot"])
                seen_uniprot.add(row["uniprot"])

            if row.get("go_id") and row["go_id"] not in seen_go:
                gene_info["go_terms"].append(row["go_id"])
                seen_go.add(row["go_id"])

        return gene_info


def demo():
    """Demonstrate the SPARQL client capabilities."""
    print("=" * 70)
    print("SPARQL Client Demo")
    print("=" * 70)

    client = SPARQLClient()

    # List available endpoints
    print("\nAvailable Endpoints:")
    print("\n  FRINK (RENCI-hosted):")
    for name, url in client.FRINK_ENDPOINTS.items():
        print(f"    - {name}: {url}")
    print("\n  Public:")
    for name, url in client.PUBLIC_ENDPOINTS.items():
        print(f"    - {name}: {url}")

    # Demo 1: Simple Wikidata query
    print("\n" + "-" * 70)
    print("1. Wikidata Query: Human genes associated with GO:0006915 (apoptosis)")
    print("-" * 70)

    try:
        genes = client.get_genes_for_go_term("GO:0006915")
        print(f"Found {len(genes)} genes")
        for gene in genes[:5]:
            print(f"  - {gene['symbol']} (Entrez: {gene['entrez']})")
        if len(genes) > 5:
            print(f"  ... and {len(genes) - 5} more")
    except Exception as e:
        print(f"Error: {e}")

    # Demo 2: Ubergraph ontology query
    print("\n" + "-" * 70)
    print("2. Ubergraph Query: Subclasses of infectious disease (MONDO:0005550)")
    print("-" * 70)

    try:
        subclasses = client.get_subclasses(
            "MONDO:0005550",
            endpoint="ubergraph",
            direct_only=True,
            limit=10
        )
        print(f"Found {len(subclasses)} direct subclasses")
        for item in subclasses[:5]:
            label = item.get('label', 'N/A')
            print(f"  - {label}")
    except Exception as e:
        print(f"Error: {e}")

    # Demo 3: Custom query
    print("\n" + "-" * 70)
    print("3. Custom Query: Count triples in SPOKE")
    print("-" * 70)

    try:
        result = client.query(
            "SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }",
            endpoint="spoke"
        )
        if result:
            count = result[0].get("count", {}).get("value", "N/A")
            print(f"SPOKE contains {count} triples")
    except Exception as e:
        print(f"Error: {e}")

    print("\n" + "=" * 70)
    print("Demo complete!")
    print("=" * 70)


if __name__ == "__main__":
    demo()
