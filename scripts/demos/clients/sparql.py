#!/usr/bin/env python3
"""
Unified SPARQL client for querying FRINK, Wikidata, local Fuseki, and other endpoints.

Supports both remote endpoints (FRINK, Wikidata, UniProt) and local endpoints
(Apache Fuseki) through a single SPARQLClient class with named endpoint registration.

Usage:
    from clients import SPARQLClient

    client = SPARQLClient()

    # Query Wikidata via FRINK
    results = client.query('''
        SELECT ?item ?label WHERE {
            ?item wdt:P31 wd:Q11173 .
            ?item rdfs:label ?label .
            FILTER(LANG(?label) = "en")
        } LIMIT 10
    ''', endpoint="wikidata")

    # Add and query a local Fuseki endpoint
    client.add_endpoint("gxa", "http://localhost:3030/GXA-v2/sparql")
    results = client.query("SELECT * WHERE { ?s ?p ?o } LIMIT 5", endpoint="gxa")

    # Check endpoint availability
    if client.is_available("gxa"):
        results = GXAQueries.get_go_enrichments(client, "GO:0006955")
"""

import json
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass

import requests
from clients.http_utils import create_session

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

# Common prefixes for GXA/GeneLab data (used by GXAQueries)
GXA_PREFIXES = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX biolink: <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>
PREFIX obo: <http://purl.obolibrary.org/obo/>
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
    Unified SPARQL client for querying FRINK, Wikidata, Fuseki, and other endpoints.

    Supports named endpoints that can be pre-configured or added at runtime.
    Uses SPARQLWrapper for remote endpoints and raw HTTP POST for local Fuseki.

    Example:
        client = SPARQLClient()
        results = client.query("SELECT * WHERE { ?s ?p ?o } LIMIT 10", endpoint="wikidata")

        # Add custom endpoint
        client.add_endpoint("gxa", "http://localhost:3030/GXA-v2/sparql")
    """

    # Pre-configured FRINK endpoints (hosted by RENCI)
    FRINK_ENDPOINTS = {
        "ubergraph": "https://frink.apps.renci.org/ubergraph/sparql",
        "spoke": "https://frink.apps.renci.org/spoke/sparql",
        "frink_wikidata": "https://frink.apps.renci.org/wikidata/sparql",
    }

    # Public SPARQL endpoints
    PUBLIC_ENDPOINTS = {
        "wikidata": "https://query.wikidata.org/sparql",
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
        self._custom_endpoints: Dict[str, str] = {}
        self._http_session: Optional[requests.Session] = None

    def add_endpoint(self, name: str, url: str, prefixes: Optional[str] = None) -> None:
        """
        Register a custom SPARQL endpoint.

        Args:
            name: Short name for the endpoint
            url: SPARQL endpoint URL
            prefixes: Optional default PREFIX block for this endpoint
        """
        self._custom_endpoints[name] = url

    def _get_endpoint_url(self, endpoint: Optional[str] = None, endpoint_url: Optional[str] = None) -> str:
        """Resolve endpoint name to URL."""
        if endpoint_url:
            return endpoint_url

        endpoint = endpoint or self.default_endpoint

        # Check custom endpoints first
        if endpoint in self._custom_endpoints:
            return self._custom_endpoints[endpoint]

        if endpoint in self.ALL_ENDPOINTS:
            return self.ALL_ENDPOINTS[endpoint]
        elif endpoint.startswith("http"):
            return endpoint
        else:
            all_names = list(self.ALL_ENDPOINTS.keys()) + list(self._custom_endpoints.keys())
            raise ValueError(
                f"Unknown endpoint: {endpoint}. "
                f"Available endpoints: {all_names}"
            )

    @property
    def _session(self) -> requests.Session:
        """Lazy-initialize HTTP session for direct HTTP queries."""
        if self._http_session is None:
            self._http_session = create_session(
                user_agent="OKN-WOBD/1.0 SPARQLClient",
                allowed_methods=("GET", "POST"),
            )
            self._http_session.headers.update({
                "Accept": "application/sparql-results+json",
            })
        return self._http_session

    def is_available(self, endpoint: Optional[str] = None) -> bool:
        """
        Check if a SPARQL endpoint is available.

        Args:
            endpoint: Endpoint name or URL to check (default: default_endpoint)

        Returns:
            True if endpoint responds, False otherwise
        """
        url = self._get_endpoint_url(endpoint)
        try:
            response = self._session.post(
                url,
                data={"query": "ASK { ?s ?p ?o }"},
                timeout=5,
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

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
        """Get the rdfs:label for a URI."""
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
        """Get subclasses of an ontology class."""
        subclass_path = "rdfs:subClassOf" if direct_only else "rdfs:subClassOf*"
        label_clause = "OPTIONAL { ?subclass rdfs:label ?label . }" if include_labels else ""
        select_vars = "?subclass ?label" if include_labels else "?subclass"

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
        species: str = "Q15978631",
        endpoint: str = "wikidata",
    ) -> List[Dict[str, str]]:
        """Get genes associated with a GO term (via Wikidata)."""
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
        """Get genes associated with a disease (via Wikidata)."""
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
        """Search for entities by label (case-insensitive contains)."""
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
        species: str = "Q15978631",
        endpoint: str = "wikidata",
    ) -> Optional[Dict[str, Any]]:
        """Get comprehensive information about a gene from Wikidata."""
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
            if gene_info["entrez_id"] is None and row.get("entrez"):
                gene_info["entrez_id"] = row["entrez"]
            if gene_info["ensembl_id"] is None and row.get("ensembl"):
                gene_info["ensembl_id"] = row["ensembl"]
            if gene_info["name"] is None and row.get("name"):
                gene_info["name"] = row["name"]
            if gene_info["description"] is None and row.get("description"):
                gene_info["description"] = row["description"]
            if gene_info["wikidata_id"] is None and row.get("gene"):
                gene_uri = row["gene"]
                if "wikidata.org/entity/" in gene_uri:
                    gene_info["wikidata_id"] = gene_uri.split("/")[-1]
            if row.get("uniprot") and row["uniprot"] not in seen_uniprot:
                gene_info["uniprot_ids"].append(row["uniprot"])
                seen_uniprot.add(row["uniprot"])
            if row.get("go_id") and row["go_id"] not in seen_go:
                gene_info["go_terms"].append(row["go_id"])
                seen_go.add(row["go_id"])

        return gene_info


class GXAQueries:
    """
    Domain-specific helper queries for GXA/GeneLab data in local Fuseki.

    These functions accept a SPARQLClient instance configured with a GXA endpoint.
    Register the endpoint first: client.add_endpoint("gxa", "http://localhost:3030/GXA-v2/sparql")

    Usage:
        client = SPARQLClient()
        client.add_endpoint("gxa", "http://localhost:3030/GXA-v2/sparql")
        studies = GXAQueries.list_studies(client)
    """

    @staticmethod
    def _query_with_gxa_prefixes(client: SPARQLClient, sparql: str, endpoint: str = "gxa") -> QueryResult:
        """Execute a query with GXA prefixes prepended."""
        if not sparql.strip().upper().startswith("PREFIX"):
            sparql = GXA_PREFIXES + "\n" + sparql
        return client.query(sparql, endpoint=endpoint, include_prefixes=False)

    @staticmethod
    def get_go_enrichments(
        client: SPARQLClient,
        go_id: str,
        endpoint: str = "gxa",
        limit: int = 100,
    ) -> List[Dict[str, str]]:
        """Get studies with GO term enrichments for a specific GO ID."""
        query = f'''
        SELECT ?study ?studyTitle ?assay ?pvalue ?goTermName
        WHERE {{
            ?enrichment biolink:participates_in ?goTerm ;
                        spokegenelab:adj_p_value ?pvalue .
            ?goTerm biolink:name ?goId .
            FILTER(?goId = "{go_id}")
            OPTIONAL {{ ?goTerm biolink:id ?goTermName }}
            ?assay biolink:has_output ?enrichment .
            ?study biolink:has_output ?assay ;
                   biolink:name ?studyTitle .
        }}
        ORDER BY ?pvalue
        LIMIT {limit}
        '''
        result = GXAQueries._query_with_gxa_prefixes(client, query, endpoint)
        return result.to_simple_dicts()

    @staticmethod
    def list_studies(
        client: SPARQLClient,
        endpoint: str = "gxa",
        limit: int = 100,
    ) -> List[Dict[str, str]]:
        """List all studies in the dataset."""
        query = f'''
        SELECT DISTINCT ?study ?title WHERE {{
            ?study a biolink:Study ;
                   biolink:name ?title .
        }}
        ORDER BY ?title
        LIMIT {limit}
        '''
        result = GXAQueries._query_with_gxa_prefixes(client, query, endpoint)
        return result.to_simple_dicts()

    @staticmethod
    def get_study_assays(
        client: SPARQLClient,
        study_uri: str,
        endpoint: str = "gxa",
    ) -> List[Dict[str, str]]:
        """Get all assays for a specific study."""
        query = f'''
        SELECT ?assay ?assayType WHERE {{
            <{study_uri}> biolink:has_output ?assay .
            OPTIONAL {{ ?assay a ?assayType }}
        }}
        '''
        result = GXAQueries._query_with_gxa_prefixes(client, query, endpoint)
        return result.to_simple_dicts()

    @staticmethod
    def count_triples(
        client: SPARQLClient,
        endpoint: str = "gxa",
    ) -> int:
        """Count the total number of triples in the dataset."""
        result = client.query(
            "SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }",
            endpoint=endpoint,
            include_prefixes=False,
        )
        if result and result.bindings:
            count_str = result.bindings[0].get("count", {}).get("value", "0")
            return int(count_str)
        return 0
