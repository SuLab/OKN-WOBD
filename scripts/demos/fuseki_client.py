#!/usr/bin/env python3
"""
Reusable SPARQL client for querying local Apache Fuseki servers.

This client is designed for querying local Fuseki instances, particularly
the GXA (Gene Expression Atlas) / GeneLab data loaded into Fuseki.

Usage:
    from fuseki_client import FusekiClient

    client = FusekiClient(dataset="GXA-v2")

    # Check if server is available
    if client.is_available():
        # Query GO enrichments
        results = client.get_go_enrichments("GO:0006955")  # immune response
        for r in results:
            print(f"{r['studyTitle']}: p={r['pvalue']}")

    # Run custom SPARQL
    results = client.query('''
        SELECT ?study ?title WHERE {
            ?study biolink:name ?title .
        } LIMIT 10
    ''')
"""

import os
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Import QueryResult from sparql_client for consistency
from sparql_client import QueryResult


# Common prefixes for GXA/GeneLab data
GXA_PREFIXES = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX biolink: <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>
PREFIX obo: <http://purl.obolibrary.org/obo/>
"""


class FusekiClient:
    """
    SPARQL client for querying local Apache Fuseki servers.

    This client uses the W3C SPARQL Protocol with HTTP POST requests,
    which is the standard method for Fuseki servers.

    Example:
        client = FusekiClient(dataset="GXA-v2")
        results = client.query("SELECT * WHERE { ?s ?p ?o } LIMIT 10")
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 3030,
        dataset: str = "GXA-v2",
        timeout: int = 60,
        max_retries: int = 3,
    ):
        """
        Initialize the Fuseki client.

        Args:
            host: Fuseki server hostname (default: localhost)
            port: Fuseki server port (default: 3030)
            dataset: Fuseki dataset name (default: GXA-v2)
            timeout: Query timeout in seconds
            max_retries: Number of retry attempts for failed requests
        """
        self.host = host
        self.port = port
        self.dataset = dataset
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = None

        # Build endpoint URL
        base_url = f"http://{host}:{port}"
        self.endpoint_url = f"{base_url}/{dataset}/sparql"

    @property
    def session(self) -> requests.Session:
        """Lazy-initialize HTTP session with retry logic."""
        if self._session is None:
            self._session = requests.Session()

            # Configure retry strategy
            retries = Retry(
                total=self.max_retries,
                backoff_factor=0.5,
                status_forcelist=(500, 502, 503, 504),
                allowed_methods=("GET", "POST"),
            )
            adapter = HTTPAdapter(max_retries=retries)
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)

            # Set headers for SPARQL JSON results
            self._session.headers.update({
                "Accept": "application/sparql-results+json",
                "User-Agent": "OKN-WOBD/1.0 FusekiClient",
            })

        return self._session

    def is_available(self) -> bool:
        """
        Check if the Fuseki server is available.

        Returns:
            True if server responds, False otherwise
        """
        try:
            # Simple ASK query to test connectivity
            response = self.session.post(
                self.endpoint_url,
                data={"query": "ASK { ?s ?p ?o }"},
                timeout=5,
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def query(
        self,
        sparql: str,
        include_prefixes: bool = True,
    ) -> QueryResult:
        """
        Execute a SPARQL SELECT query.

        Args:
            sparql: SPARQL query string
            include_prefixes: Whether to prepend common GXA prefixes

        Returns:
            QueryResult object with bindings and helper methods

        Raises:
            RuntimeError: If the query fails

        Example:
            results = client.query('''
                SELECT ?study ?title WHERE {
                    ?study biolink:name ?title .
                } LIMIT 10
            ''')
        """
        # Optionally prepend common prefixes
        if include_prefixes and not sparql.strip().upper().startswith("PREFIX"):
            sparql = GXA_PREFIXES + "\n" + sparql

        try:
            response = self.session.post(
                self.endpoint_url,
                data={"query": sparql},
                timeout=self.timeout,
            )
            response.raise_for_status()
            raw_result = response.json()
        except requests.RequestException as e:
            raise RuntimeError(
                f"SPARQL query failed: {e}\nEndpoint: {self.endpoint_url}"
            ) from e
        except ValueError as e:
            raise RuntimeError(f"Failed to parse JSON response: {e}") from e

        # Parse results
        bindings = raw_result.get("results", {}).get("bindings", [])
        variables = raw_result.get("head", {}).get("vars", [])

        return QueryResult(raw=raw_result, bindings=bindings, variables=variables)

    def query_simple(self, sparql: str) -> List[Dict[str, str]]:
        """
        Execute a query and return simplified results as list of dicts.

        This is a convenience method that extracts just the values from bindings.

        Returns:
            List of dicts mapping variable names to string values
        """
        result = self.query(sparql)
        return result.to_simple_dicts()

    def ask(self, sparql: str) -> bool:
        """
        Execute a SPARQL ASK query.

        Returns:
            Boolean result of the ASK query
        """
        if not sparql.strip().upper().startswith("PREFIX"):
            sparql = GXA_PREFIXES + "\n" + sparql

        try:
            response = self.session.post(
                self.endpoint_url,
                data={"query": sparql},
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            return result.get("boolean", False)
        except requests.RequestException as e:
            raise RuntimeError(f"ASK query failed: {e}") from e

    # =========================================================================
    # Domain-specific helper methods for GXA/GeneLab data
    # =========================================================================

    def get_go_enrichments(
        self,
        go_id: str,
        limit: int = 100,
    ) -> List[Dict[str, str]]:
        """
        Get studies with GO term enrichments for a specific GO ID.

        Args:
            go_id: GO identifier (e.g., "GO:0006955" for immune response)
            limit: Maximum number of results

        Returns:
            List of dicts with study, studyTitle, assay, pvalue, goTermName
        """
        query = f'''
        SELECT ?study ?studyTitle ?assay ?pvalue ?goTermName
        WHERE {{
            # Find enrichment linked to a GO term
            ?enrichment biolink:participates_in ?goTerm ;
                        spokegenelab:adj_p_value ?pvalue .

            # Note: id/name are swapped in current data
            # biolink:name contains the GO ID, biolink:id contains the term name
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
        return self.query_simple(query)

    def list_studies(self, limit: int = 100) -> List[Dict[str, str]]:
        """
        List all studies in the dataset.

        Returns:
            List of dicts with study URI and title
        """
        query = f'''
        SELECT DISTINCT ?study ?title WHERE {{
            ?study a biolink:Study ;
                   biolink:name ?title .
        }}
        ORDER BY ?title
        LIMIT {limit}
        '''
        return self.query_simple(query)

    def get_study_assays(self, study_uri: str) -> List[Dict[str, str]]:
        """
        Get all assays for a specific study.

        Args:
            study_uri: Full URI of the study

        Returns:
            List of dicts with assay information
        """
        query = f'''
        SELECT ?assay ?assayType WHERE {{
            <{study_uri}> biolink:has_output ?assay .
            OPTIONAL {{ ?assay a ?assayType }}
        }}
        '''
        return self.query_simple(query)

    def count_triples(self) -> int:
        """
        Count the total number of triples in the dataset.

        Returns:
            Number of triples
        """
        result = self.query(
            "SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }",
            include_prefixes=False,
        )
        if result and result.bindings:
            count_str = result.bindings[0].get("count", {}).get("value", "0")
            return int(count_str)
        return 0


def demo():
    """Demonstrate the Fuseki client capabilities."""
    print("=" * 70)
    print("Fuseki SPARQL Client Demo")
    print("=" * 70)

    # Create client for local GXA-v2 dataset
    client = FusekiClient(dataset="GXA-v2")
    print(f"\nEndpoint: {client.endpoint_url}")

    # Check availability
    print("\n" + "-" * 70)
    print("1. Checking Fuseki availability...")
    print("-" * 70)

    if not client.is_available():
        print("ERROR: Fuseki server is not available at the configured endpoint.")
        print(f"Please ensure Fuseki is running at http://{client.host}:{client.port}")
        print("with dataset '{client.dataset}'")
        return

    print("Fuseki server is available!")

    # Count triples
    print("\n" + "-" * 70)
    print("2. Counting triples in dataset...")
    print("-" * 70)

    try:
        count = client.count_triples()
        print(f"Dataset contains {count:,} triples")
    except Exception as e:
        print(f"Error counting triples: {e}")

    # Query GO enrichments for immune response
    print("\n" + "-" * 70)
    print("3. GO Enrichment Query: GO:0006955 (immune response)")
    print("-" * 70)

    try:
        results = client.get_go_enrichments("GO:0006955")
        print(f"Found {len(results)} enrichment results")

        if results:
            print("\nTop results (by p-value):")
            for i, r in enumerate(results[:10], 1):
                study_title = r.get("studyTitle", "N/A")
                pvalue = r.get("pvalue", "N/A")
                go_name = r.get("goTermName", "N/A")
                # Truncate long titles
                if len(study_title) > 50:
                    study_title = study_title[:47] + "..."
                print(f"  {i}. {study_title}")
                print(f"     p-value: {pvalue}, GO term: {go_name}")
    except Exception as e:
        print(f"Error: {e}")

    # List studies
    print("\n" + "-" * 70)
    print("4. Listing studies in dataset...")
    print("-" * 70)

    try:
        studies = client.list_studies(limit=10)
        print(f"Found {len(studies)} studies (showing up to 10)")

        for study in studies[:10]:
            title = study.get("title", "N/A")
            if len(title) > 60:
                title = title[:57] + "..."
            print(f"  - {title}")
    except Exception as e:
        print(f"Error: {e}")

    # Custom query example
    print("\n" + "-" * 70)
    print("5. Custom SPARQL Query Example")
    print("-" * 70)

    custom_query = """
    SELECT ?goId (COUNT(?enrichment) as ?count)
    WHERE {
        ?enrichment biolink:participates_in ?goTerm .
        ?goTerm biolink:name ?goId .
    }
    GROUP BY ?goId
    ORDER BY DESC(?count)
    LIMIT 10
    """

    try:
        results = client.query_simple(custom_query)
        print("Top 10 GO terms by enrichment count:")
        for r in results:
            go_id = r.get("goId", "N/A")
            count = r.get("count", "0")
            print(f"  - {go_id}: {count} enrichments")
    except Exception as e:
        print(f"Error: {e}")

    print("\n" + "=" * 70)
    print("Demo complete!")
    print("=" * 70)


if __name__ == "__main__":
    demo()
