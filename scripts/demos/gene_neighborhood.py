#!/usr/bin/env python3
"""
Gene Neighborhood Query Tool

Queries the immediate neighborhood of a gene across multiple FRINK knowledge graphs,
returning related entities with their IRIs, types, and labels.

Usage:
    # By gene symbol
    python gene_neighborhood.py CD19
    python gene_neighborhood.py --symbol CD19

    # By NCBI Gene ID
    python gene_neighborhood.py --ncbi 930

    # With custom limits
    python gene_neighborhood.py CD19 --limit 20
    python gene_neighborhood.py CD19 --spoke-limit 15 --wikidata-limit 25

    # Output formats
    python gene_neighborhood.py CD19 --format json
    python gene_neighborhood.py CD19 --format table

    # Save to file
    python gene_neighborhood.py CD19 -o cd19_neighborhood.json

Requirements:
    pip install sparqlwrapper
"""

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory for imports
sys.path.insert(0, '.')

from sparql_client import SPARQLClient


@dataclass
class RelatedEntity:
    """A single related entity from the gene neighborhood."""
    iri: str
    label: str
    type_iri: str
    type_label: str
    predicate_iri: str
    predicate_label: str
    direction: str  # "outgoing" (gene -> entity) or "incoming" (entity -> gene)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GraphResult:
    """Results from a single knowledge graph."""
    graph_name: str
    endpoint: str
    entities: List[RelatedEntity]
    error: Optional[str] = None
    query_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_name": self.graph_name,
            "endpoint": self.endpoint,
            "entity_count": len(self.entities),
            "entities": [e.to_dict() for e in self.entities],
            "error": self.error,
            "query_time_ms": self.query_time_ms,
        }


@dataclass
class GeneNeighborhood:
    """Complete neighborhood results for a gene."""
    gene_symbol: str
    ncbi_gene_id: str
    gene_iri: str
    timestamp: str
    graphs: List[GraphResult]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gene_symbol": self.gene_symbol,
            "ncbi_gene_id": self.ncbi_gene_id,
            "gene_iri": self.gene_iri,
            "timestamp": self.timestamp,
            "total_entities": sum(len(g.entities) for g in self.graphs),
            "graphs": [g.to_dict() for g in self.graphs],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class GeneNeighborhoodQuery:
    """Query gene neighborhoods across multiple knowledge graphs."""

    # FRINK endpoints
    ENDPOINTS = {
        "spoke-okn": "https://frink.apps.renci.org/spoke-okn/sparql",
        "spoke-genelab": "https://frink.apps.renci.org/spoke-genelab/sparql",
        "nde": "https://frink.apps.renci.org/nde/sparql",
        "biobricks-aopwiki": "https://frink.apps.renci.org/biobricks-aopwiki/sparql",
    }

    # Official Wikidata endpoint (more complete than FRINK subset)
    WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"

    def __init__(self, timeout: int = 60):
        self.timeout = timeout

    def resolve_gene(self, symbol: Optional[str] = None, ncbi_id: Optional[str] = None) -> tuple[str, str, str]:
        """
        Resolve gene symbol or NCBI ID to canonical identifiers.

        Returns:
            Tuple of (symbol, ncbi_id, gene_iri)
        """
        if ncbi_id:
            gene_iri = f"http://www.ncbi.nlm.nih.gov/gene/{ncbi_id}"
            # Try to get symbol from Wikidata
            if not symbol:
                symbol = self._lookup_symbol_from_ncbi(ncbi_id) or f"Gene_{ncbi_id}"
            return symbol, ncbi_id, gene_iri

        if symbol:
            # Look up NCBI ID from Wikidata
            ncbi_id = self._lookup_ncbi_from_symbol(symbol)
            if ncbi_id:
                gene_iri = f"http://www.ncbi.nlm.nih.gov/gene/{ncbi_id}"
                return symbol, ncbi_id, gene_iri
            else:
                # Fall back to using symbol in IRI patterns
                return symbol, "", ""

        raise ValueError("Must provide either gene symbol or NCBI Gene ID")

    def _lookup_ncbi_from_symbol(self, symbol: str) -> Optional[str]:
        """Look up NCBI Gene ID from gene symbol via Wikidata."""
        client = SPARQLClient(default_endpoint=self.WIKIDATA_ENDPOINT, timeout=30)

        query = f"""
        SELECT ?entrez WHERE {{
          ?gene wdt:P353 "{symbol}" .
          ?gene wdt:P351 ?entrez .
          ?gene wdt:P703 wd:Q15978631 .  # Homo sapiens
        }}
        LIMIT 1
        """

        try:
            result = client.query(query, include_prefixes=False)
            if result.bindings:
                return result.bindings[0].get('entrez', {}).get('value', '')
        except Exception:
            pass
        return None

    def _lookup_symbol_from_ncbi(self, ncbi_id: str) -> Optional[str]:
        """Look up gene symbol from NCBI Gene ID via Wikidata."""
        client = SPARQLClient(default_endpoint=self.WIKIDATA_ENDPOINT, timeout=30)

        query = f"""
        SELECT ?symbol WHERE {{
          ?gene wdt:P351 "{ncbi_id}" .
          ?gene wdt:P353 ?symbol .
        }}
        LIMIT 1
        """

        try:
            result = client.query(query, include_prefixes=False)
            if result.bindings:
                return result.bindings[0].get('symbol', {}).get('value', '')
        except Exception:
            pass
        return None

    def query_spoke_okn(self, gene_iri: str, limit: int = 10) -> GraphResult:
        """Query SPOKE-OKN for gene neighborhood (disease associations, etc.)."""
        import time
        start = time.time()

        endpoint = self.ENDPOINTS["spoke-okn"]
        client = SPARQLClient(default_endpoint=endpoint, timeout=self.timeout)

        query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX biolink: <https://w3id.org/biolink/vocab/>

        SELECT DISTINCT ?entity ?entityLabel ?entityType ?entityTypeLabel ?predicate ?predicateLabel ?direction
        WHERE {{
          {{
            # Outgoing relations (gene -> entity)
            <{gene_iri}> ?predicate ?entity .
            BIND("outgoing" AS ?direction)
            OPTIONAL {{ ?entity rdfs:label ?entityLabel }}
            OPTIONAL {{
              ?entity a ?entityType .
              OPTIONAL {{ ?entityType rdfs:label ?entityTypeLabel }}
            }}
            OPTIONAL {{ ?predicate rdfs:label ?predicateLabel }}
            FILTER(?predicate != rdf:type && ?predicate != rdfs:label && ?predicate != rdfs:comment)
          }}
          UNION
          {{
            # Incoming relations (entity -> gene)
            ?entity ?predicate <{gene_iri}> .
            BIND("incoming" AS ?direction)
            OPTIONAL {{ ?entity rdfs:label ?entityLabel }}
            OPTIONAL {{
              ?entity a ?entityType .
              OPTIONAL {{ ?entityType rdfs:label ?entityTypeLabel }}
            }}
            OPTIONAL {{ ?predicate rdfs:label ?predicateLabel }}
            FILTER(?predicate != rdf:type && ?predicate != rdfs:label)
          }}
        }}
        LIMIT {limit * 2}
        """

        try:
            result = client.query(query, include_prefixes=False)
            entities = self._parse_neighborhood_results(result)
            return GraphResult(
                graph_name="spoke-okn",
                endpoint=endpoint,
                entities=entities[:limit],
                query_time_ms=(time.time() - start) * 1000
            )
        except Exception as e:
            return GraphResult(
                graph_name="spoke-okn",
                endpoint=endpoint,
                entities=[],
                error=str(e),
                query_time_ms=(time.time() - start) * 1000
            )

    def query_spoke_genelab(self, gene_iri: str, limit: int = 10) -> GraphResult:
        """Query SPOKE-GeneLab for gene neighborhood (orthologs, expression)."""
        import time
        start = time.time()

        endpoint = self.ENDPOINTS["spoke-genelab"]
        client = SPARQLClient(default_endpoint=endpoint, timeout=self.timeout)

        # More focused query for GeneLab - look for direct gene relations
        query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?entity ?entityLabel ?entityType ?entityTypeLabel ?predicate ?predicateLabel ?direction
        WHERE {{
          {{
            # Outgoing relations
            <{gene_iri}> ?predicate ?entity .
            BIND("outgoing" AS ?direction)
            FILTER(isIRI(?entity))
            OPTIONAL {{ ?entity rdfs:label ?entityLabel }}
            OPTIONAL {{
              ?entity a ?entityType .
              OPTIONAL {{ ?entityType rdfs:label ?entityTypeLabel }}
            }}
            BIND(REPLACE(STR(?predicate), "^.*/", "") AS ?predicateLabel)
          }}
          UNION
          {{
            # Incoming relations - orthologs
            ?entity ?predicate <{gene_iri}> .
            BIND("incoming" AS ?direction)
            FILTER(isIRI(?entity))
            FILTER(CONTAINS(STR(?predicate), "ORTHOLOG") || CONTAINS(STR(?predicate), "gene"))
            OPTIONAL {{ ?entity rdfs:label ?entityLabel }}
            OPTIONAL {{
              ?entity a ?entityType .
              OPTIONAL {{ ?entityType rdfs:label ?entityTypeLabel }}
            }}
            BIND(REPLACE(STR(?predicate), "^.*/", "") AS ?predicateLabel)
          }}
        }}
        LIMIT {limit * 2}
        """

        try:
            result = client.query(query, include_prefixes=False)
            entities = self._parse_neighborhood_results(result)
            return GraphResult(
                graph_name="spoke-genelab",
                endpoint=endpoint,
                entities=entities[:limit],
                query_time_ms=(time.time() - start) * 1000
            )
        except Exception as e:
            return GraphResult(
                graph_name="spoke-genelab",
                endpoint=endpoint,
                entities=[],
                error=str(e),
                query_time_ms=(time.time() - start) * 1000
            )

    def query_wikidata(self, gene_symbol: str, ncbi_id: str, limit: int = 10) -> GraphResult:
        """Query Wikidata for gene neighborhood (GO terms, diseases, etc.)."""
        import time
        start = time.time()

        endpoint = self.WIKIDATA_ENDPOINT
        client = SPARQLClient(default_endpoint=endpoint, timeout=self.timeout)

        # First find the gene and protein entities
        query = f"""
        SELECT DISTINCT ?entity ?entityLabel ?entityType ?entityTypeLabel ?property ?propertyLabel ?direction
        WHERE {{
          # Find the gene by symbol or NCBI ID
          {{
            ?gene wdt:P353 "{gene_symbol}" .
            ?gene wdt:P703 wd:Q15978631 .
          }}
          UNION
          {{
            ?gene wdt:P351 "{ncbi_id}" .
          }}

          # Get gene properties
          {{
            ?gene ?prop ?entity .
            ?property wikibase:directClaim ?prop .
            BIND("outgoing" AS ?direction)
            FILTER(isIRI(?entity) && ?entity != wd:Q15978631)
            OPTIONAL {{ ?entity wdt:P31 ?entityType }}
          }}
          UNION
          {{
            # Get protein and its GO terms
            ?gene wdt:P688 ?protein .
            ?protein ?prop ?entity .
            ?property wikibase:directClaim ?prop .
            BIND("outgoing" AS ?direction)
            FILTER(isIRI(?entity))
            OPTIONAL {{ ?entity wdt:P31 ?entityType }}
          }}

          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT {limit * 3}
        """

        try:
            result = client.query(query, include_prefixes=False)
            entities = self._parse_wikidata_results(result)
            return GraphResult(
                graph_name="wikidata",
                endpoint=endpoint,
                entities=entities[:limit],
                query_time_ms=(time.time() - start) * 1000
            )
        except Exception as e:
            return GraphResult(
                graph_name="wikidata",
                endpoint=endpoint,
                entities=[],
                error=str(e),
                query_time_ms=(time.time() - start) * 1000
            )

    def query_nde(self, gene_symbol: str, limit: int = 10) -> GraphResult:
        """Query NDE for datasets mentioning the gene."""
        import time
        start = time.time()

        endpoint = self.ENDPOINTS["nde"]
        client = SPARQLClient(default_endpoint=endpoint, timeout=self.timeout)

        # Search for datasets mentioning the gene symbol
        query = f"""
        PREFIX schema: <http://schema.org/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?entity ?entityLabel ?entityType ?predicate ?direction
        WHERE {{
          ?entity a schema:Dataset .
          BIND(schema:Dataset AS ?entityType)
          BIND("incoming" AS ?direction)
          BIND(schema:mentions AS ?predicate)

          {{
            ?entity schema:name ?name .
            FILTER(CONTAINS(LCASE(?name), LCASE("{gene_symbol}")))
            BIND(?name AS ?entityLabel)
          }}
          UNION
          {{
            ?entity schema:description ?desc .
            FILTER(CONTAINS(LCASE(?desc), LCASE("{gene_symbol}")))
            ?entity schema:name ?entityLabel .
          }}
          UNION
          {{
            ?entity schema:abstract ?abstract .
            FILTER(CONTAINS(LCASE(?abstract), LCASE("{gene_symbol}")))
            ?entity schema:name ?entityLabel .
          }}
        }}
        LIMIT {limit}
        """

        try:
            result = client.query(query, include_prefixes=False)
            entities = self._parse_nde_results(result)
            return GraphResult(
                graph_name="nde",
                endpoint=endpoint,
                entities=entities[:limit],
                query_time_ms=(time.time() - start) * 1000
            )
        except Exception as e:
            return GraphResult(
                graph_name="nde",
                endpoint=endpoint,
                entities=[],
                error=str(e),
                query_time_ms=(time.time() - start) * 1000
            )

    def query_biobricks(self, gene_symbol: str, ncbi_id: str, limit: int = 10) -> GraphResult:
        """Query BioBricks-AOPWiki for toxicology pathway information."""
        import time
        start = time.time()

        endpoint = self.ENDPOINTS["biobricks-aopwiki"]
        client = SPARQLClient(default_endpoint=endpoint, timeout=self.timeout)

        # Search for gene in AOPWiki
        query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?entity ?entityLabel ?entityType ?predicate ?direction
        WHERE {{
          ?entity ?predicate ?object .
          FILTER(
            CONTAINS(STR(?entity), "{gene_symbol}") ||
            CONTAINS(STR(?entity), "ncbigene/{ncbi_id}") ||
            CONTAINS(STR(?object), "{gene_symbol}") ||
            CONTAINS(STR(?object), "ncbigene/{ncbi_id}")
          )
          OPTIONAL {{ ?entity rdfs:label ?entityLabel }}
          OPTIONAL {{ ?entity a ?entityType }}
          BIND("related" AS ?direction)
        }}
        LIMIT {limit * 2}
        """

        try:
            result = client.query(query, include_prefixes=False)
            entities = self._parse_biobricks_results(result)
            return GraphResult(
                graph_name="biobricks-aopwiki",
                endpoint=endpoint,
                entities=entities[:limit],
                query_time_ms=(time.time() - start) * 1000
            )
        except Exception as e:
            return GraphResult(
                graph_name="biobricks-aopwiki",
                endpoint=endpoint,
                entities=[],
                error=str(e),
                query_time_ms=(time.time() - start) * 1000
            )

    def _parse_neighborhood_results(self, result) -> List[RelatedEntity]:
        """Parse SPARQL results into RelatedEntity objects."""
        entities = []
        seen = set()

        for binding in result.bindings:
            entity_iri = binding.get('entity', {}).get('value', '')
            if not entity_iri or entity_iri in seen:
                continue
            seen.add(entity_iri)

            entity_label = binding.get('entityLabel', {}).get('value', '')
            if not entity_label:
                entity_label = entity_iri.split('/')[-1].split('#')[-1]

            type_iri = binding.get('entityType', {}).get('value', '')
            type_label = binding.get('entityTypeLabel', {}).get('value', '')
            if not type_label and type_iri:
                type_label = type_iri.split('/')[-1].split('#')[-1]

            pred_iri = binding.get('predicate', {}).get('value', '')
            pred_label = binding.get('predicateLabel', {}).get('value', '')
            if not pred_label and pred_iri:
                pred_label = pred_iri.split('/')[-1].split('#')[-1]

            direction = binding.get('direction', {}).get('value', 'unknown')

            entities.append(RelatedEntity(
                iri=entity_iri,
                label=entity_label,
                type_iri=type_iri,
                type_label=type_label,
                predicate_iri=pred_iri,
                predicate_label=pred_label,
                direction=direction,
            ))

        return entities

    def _parse_wikidata_results(self, result) -> List[RelatedEntity]:
        """Parse Wikidata SPARQL results."""
        entities = []
        seen = set()

        for binding in result.bindings:
            entity_iri = binding.get('entity', {}).get('value', '')
            if not entity_iri or entity_iri in seen:
                continue

            # Skip Wikidata internal entities
            if 'statement/' in entity_iri or 'reference/' in entity_iri:
                continue

            seen.add(entity_iri)

            entity_label = binding.get('entityLabel', {}).get('value', '')
            if not entity_label or entity_label.startswith('Q') or entity_label.startswith('http'):
                entity_label = entity_iri.split('/')[-1]

            type_iri = binding.get('entityType', {}).get('value', '')
            type_label = binding.get('entityTypeLabel', {}).get('value', '')
            if not type_label and type_iri:
                type_label = type_iri.split('/')[-1]

            prop_iri = binding.get('property', {}).get('value', '')
            prop_label = binding.get('propertyLabel', {}).get('value', '')
            if not prop_label and prop_iri:
                prop_label = prop_iri.split('/')[-1]

            direction = binding.get('direction', {}).get('value', 'outgoing')

            entities.append(RelatedEntity(
                iri=entity_iri,
                label=entity_label,
                type_iri=type_iri,
                type_label=type_label,
                predicate_iri=prop_iri,
                predicate_label=prop_label,
                direction=direction,
            ))

        return entities

    def _parse_nde_results(self, result) -> List[RelatedEntity]:
        """Parse NDE SPARQL results."""
        entities = []
        seen = set()

        for binding in result.bindings:
            entity_iri = binding.get('entity', {}).get('value', '')
            if not entity_iri or entity_iri in seen:
                continue
            seen.add(entity_iri)

            entity_label = binding.get('entityLabel', {}).get('value', '')
            if not entity_label:
                entity_label = entity_iri.split('/')[-1]

            type_iri = binding.get('entityType', {}).get('value', '')
            pred_iri = binding.get('predicate', {}).get('value', '')
            direction = binding.get('direction', {}).get('value', 'related')

            entities.append(RelatedEntity(
                iri=entity_iri,
                label=entity_label[:100],  # Truncate long titles
                type_iri=type_iri,
                type_label="Dataset",
                predicate_iri=pred_iri,
                predicate_label="mentions",
                direction=direction,
            ))

        return entities

    def _parse_biobricks_results(self, result) -> List[RelatedEntity]:
        """Parse BioBricks SPARQL results."""
        entities = []
        seen = set()

        for binding in result.bindings:
            entity_iri = binding.get('entity', {}).get('value', '')
            if not entity_iri or entity_iri in seen:
                continue
            seen.add(entity_iri)

            entity_label = binding.get('entityLabel', {}).get('value', '')
            if not entity_label:
                entity_label = entity_iri.split('/')[-1]

            type_iri = binding.get('entityType', {}).get('value', '')
            type_label = type_iri.split('/')[-1] if type_iri else ''

            pred_iri = binding.get('predicate', {}).get('value', '')
            pred_label = pred_iri.split('/')[-1].split('#')[-1] if pred_iri else ''

            direction = binding.get('direction', {}).get('value', 'related')

            entities.append(RelatedEntity(
                iri=entity_iri,
                label=entity_label,
                type_iri=type_iri,
                type_label=type_label,
                predicate_iri=pred_iri,
                predicate_label=pred_label,
                direction=direction,
            ))

        return entities

    def query_all(
        self,
        symbol: Optional[str] = None,
        ncbi_id: Optional[str] = None,
        spoke_limit: int = 10,
        wikidata_limit: int = 10,
        nde_limit: int = 10,
        biobricks_limit: int = 10,
        parallel: bool = True,
    ) -> GeneNeighborhood:
        """
        Query all knowledge graphs for gene neighborhood.

        Args:
            symbol: Gene symbol (e.g., "CD19")
            ncbi_id: NCBI Gene ID (e.g., "930")
            spoke_limit: Max entities from each SPOKE graph
            wikidata_limit: Max entities from Wikidata
            nde_limit: Max entities from NDE
            biobricks_limit: Max entities from BioBricks
            parallel: Run queries in parallel

        Returns:
            GeneNeighborhood with results from all graphs
        """
        # Resolve gene identifiers
        gene_symbol, gene_ncbi_id, gene_iri = self.resolve_gene(symbol, ncbi_id)

        print(f"Querying neighborhood for: {gene_symbol} (NCBI: {gene_ncbi_id})", file=sys.stderr)
        print(f"Gene IRI: {gene_iri}", file=sys.stderr)

        graphs = []

        if parallel:
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {}

                if gene_iri:
                    futures[executor.submit(self.query_spoke_okn, gene_iri, spoke_limit)] = "spoke-okn"
                    futures[executor.submit(self.query_spoke_genelab, gene_iri, spoke_limit)] = "spoke-genelab"

                futures[executor.submit(self.query_wikidata, gene_symbol, gene_ncbi_id, wikidata_limit)] = "wikidata"
                futures[executor.submit(self.query_nde, gene_symbol, nde_limit)] = "nde"

                if gene_ncbi_id:
                    futures[executor.submit(self.query_biobricks, gene_symbol, gene_ncbi_id, biobricks_limit)] = "biobricks"

                for future in as_completed(futures):
                    graph_name = futures[future]
                    try:
                        result = future.result()
                        graphs.append(result)
                        status = f"{len(result.entities)} entities" if not result.error else f"ERROR: {result.error[:50]}"
                        print(f"  {graph_name}: {status}", file=sys.stderr)
                    except Exception as e:
                        print(f"  {graph_name}: ERROR - {e}", file=sys.stderr)
        else:
            # Sequential execution
            if gene_iri:
                graphs.append(self.query_spoke_okn(gene_iri, spoke_limit))
                graphs.append(self.query_spoke_genelab(gene_iri, spoke_limit))
            graphs.append(self.query_wikidata(gene_symbol, gene_ncbi_id, wikidata_limit))
            graphs.append(self.query_nde(gene_symbol, nde_limit))
            if gene_ncbi_id:
                graphs.append(self.query_biobricks(gene_symbol, gene_ncbi_id, biobricks_limit))

        return GeneNeighborhood(
            gene_symbol=gene_symbol,
            ncbi_gene_id=gene_ncbi_id,
            gene_iri=gene_iri,
            timestamp=datetime.now().isoformat(),
            graphs=sorted(graphs, key=lambda g: g.graph_name),
        )


def format_table(neighborhood: GeneNeighborhood) -> str:
    """Format neighborhood results as ASCII table."""
    lines = []

    lines.append("=" * 80)
    lines.append(f"GENE NEIGHBORHOOD: {neighborhood.gene_symbol}")
    lines.append(f"NCBI Gene ID: {neighborhood.ncbi_gene_id}")
    lines.append(f"Gene IRI: {neighborhood.gene_iri}")
    lines.append(f"Timestamp: {neighborhood.timestamp}")
    lines.append("=" * 80)

    total = sum(len(g.entities) for g in neighborhood.graphs)
    lines.append(f"\nTotal related entities: {total}")

    for graph in neighborhood.graphs:
        lines.append(f"\n{'-' * 60}")
        lines.append(f"GRAPH: {graph.graph_name.upper()}")
        lines.append(f"Endpoint: {graph.endpoint}")
        lines.append(f"Query time: {graph.query_time_ms:.0f}ms")
        lines.append(f"{'-' * 60}")

        if graph.error:
            lines.append(f"ERROR: {graph.error}")
            continue

        if not graph.entities:
            lines.append("No related entities found")
            continue

        for entity in graph.entities:
            direction_arrow = "->" if entity.direction == "outgoing" else "<-"
            type_str = f" [{entity.type_label}]" if entity.type_label else ""

            lines.append(f"\n  {direction_arrow} {entity.label}{type_str}")
            lines.append(f"     IRI: {entity.iri[:70]}")
            lines.append(f"     Predicate: {entity.predicate_label}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Query gene neighborhood across FRINK knowledge graphs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s CD19                        # Query by gene symbol
  %(prog)s --ncbi 930                  # Query by NCBI Gene ID
  %(prog)s CD19 --limit 20             # Set default limit for all graphs
  %(prog)s CD19 --spoke-limit 15       # Custom limit per graph
  %(prog)s CD19 --format json -o out.json
        """
    )

    parser.add_argument(
        "symbol",
        nargs="?",
        help="Gene symbol (e.g., CD19, TP53, BRCA1)",
    )
    parser.add_argument(
        "--symbol", "-s",
        dest="symbol_flag",
        help="Gene symbol (alternative to positional argument)",
    )
    parser.add_argument(
        "--ncbi", "-n",
        help="NCBI Gene ID (e.g., 930)",
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=10,
        help="Default limit for all graphs (default: 10)",
    )
    parser.add_argument(
        "--spoke-limit",
        type=int,
        help="Limit for SPOKE graphs (default: --limit value)",
    )
    parser.add_argument(
        "--wikidata-limit",
        type=int,
        help="Limit for Wikidata (default: --limit value)",
    )
    parser.add_argument(
        "--nde-limit",
        type=int,
        help="Limit for NDE (default: --limit value)",
    )
    parser.add_argument(
        "--biobricks-limit",
        type=int,
        help="Limit for BioBricks (default: --limit value)",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["json", "table"],
        default="table",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file (default: stdout)",
    )
    parser.add_argument(
        "--timeout", "-t",
        type=int,
        default=60,
        help="Query timeout in seconds (default: 60)",
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Run queries sequentially instead of in parallel",
    )

    args = parser.parse_args()

    # Get gene identifier
    symbol = args.symbol or args.symbol_flag
    ncbi_id = args.ncbi

    if not symbol and not ncbi_id:
        parser.error("Must provide gene symbol or --ncbi ID")

    # Set limits
    spoke_limit = args.spoke_limit or args.limit
    wikidata_limit = args.wikidata_limit or args.limit
    nde_limit = args.nde_limit or args.limit
    biobricks_limit = args.biobricks_limit or args.limit

    # Query
    querier = GeneNeighborhoodQuery(timeout=args.timeout)

    try:
        neighborhood = querier.query_all(
            symbol=symbol,
            ncbi_id=ncbi_id,
            spoke_limit=spoke_limit,
            wikidata_limit=wikidata_limit,
            nde_limit=nde_limit,
            biobricks_limit=biobricks_limit,
            parallel=not args.sequential,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Format output
    if args.format == "json":
        output = neighborhood.to_json()
    else:
        output = format_table(neighborhood)

    # Write output
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"\nOutput written to: {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
