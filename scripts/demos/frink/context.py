#!/usr/bin/env python3
"""
FRINK context API and builder.

This module provides:
- FrinkContext: API for loading and querying context data (graph metadata, schemas,
  prefixes, example queries) from a JSON context file.
- build_context / main: Builder functions that scrape the FRINK registry,
  assemble metadata, and write a structured JSON context file optimized for
  LLM-based SPARQL query generation.

Usage (API):
    from frink.context import FrinkContext

    ctx = FrinkContext.load("frink_context.json")
    endpoint = ctx.get_endpoint("ubergraph")
    biomedical = ctx.find_graphs_by_domain("biomedical")

Usage (Builder):
    python -m frink.context
    python -m frink.context --output custom_context.json
    python -m frink.context --skip-schemas
"""

# =========================================================================
# Context API (from frink_context_api)
# =========================================================================

import json
from typing import Dict, List, Any, Optional, Set
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ExampleQuery:
    """An example SPARQL query from the context."""
    name: str
    natural_language: str
    sparql: str
    notes: str = ""
    graph: Optional[str] = None
    graphs: Optional[List[str]] = None

    @property
    def is_federated(self) -> bool:
        return self.graphs is not None and len(self.graphs) > 1


class FrinkContext:
    """
    API for accessing FRINK NL-to-SPARQL context data.

    Provides methods for:
    - Loading and accessing graph metadata and schemas
    - Finding graphs by domain or capability
    - Building SPARQL prefixes and SERVICE clauses
    - Retrieving example queries

    Example:
        ctx = FrinkContext.load("frink_context.json")

        # Get ubergraph endpoint
        endpoint = ctx.get_endpoint("ubergraph")

        # Find biomedical graphs
        graphs = ctx.find_graphs_by_domain("biomedical")

        # Build prefixes for a federated query
        prefix_str = ctx.get_prefix_declarations(["ubergraph", "nde"])
    """

    def __init__(self, context_data: Dict[str, Any]):
        """
        Initialize with context data.

        Args:
            context_data: Loaded context dictionary
        """
        self._data = context_data
        self._graphs = context_data.get("knowledge_graphs", {})
        self._external = context_data.get("external_endpoints", {})
        self._common_prefixes = context_data.get("common_prefixes", {})
        self._examples = context_data.get("example_queries", {})
        self._patterns = context_data.get("federated_query_patterns", {})
        self._instructions = context_data.get("usage_instructions", {})

    @classmethod
    def load(cls, path: str | Path) -> "FrinkContext":
        """
        Load context from a JSON file.

        Args:
            path: Path to the context JSON file

        Returns:
            FrinkContext instance

        Raises:
            FileNotFoundError: If context file doesn't exist
            json.JSONDecodeError: If file is not valid JSON
        """
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(data)

    @classmethod
    def load_default(cls) -> "FrinkContext":
        """
        Load context from the default location (same directory as this file).

        Returns:
            FrinkContext instance
        """
        default_path = Path(__file__).parent / "frink_context.json"
        return cls.load(default_path)

    # =========================================================================
    # Basic Accessors
    # =========================================================================

    @property
    def version(self) -> str:
        """Context file version."""
        return self._data.get("version", "unknown")

    @property
    def generated_at(self) -> str:
        """When the context was generated."""
        return self._data.get("generated_at", "unknown")

    @property
    def registry_url(self) -> str:
        """URL of the FRINK registry."""
        return self._data.get("registry_url", "https://frink.renci.org/registry/")

    @property
    def federated_endpoint(self) -> str:
        """URL of the federated query endpoint."""
        return self._data.get("federated_endpoint", "https://frink.apps.renci.org/?query=")

    @property
    def graph_names(self) -> List[str]:
        """List of all graph shortnames."""
        return list(self._graphs.keys())

    @property
    def common_prefixes(self) -> Dict[str, str]:
        """Common prefixes shared across graphs."""
        return self._common_prefixes.copy()

    @property
    def external_endpoint_names(self) -> List[str]:
        """List of external endpoint names (wikidata, uniprot, etc.)."""
        return list(self._external.keys())

    # =========================================================================
    # External Endpoints (non-FRINK)
    # =========================================================================

    def get_external_endpoint(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get external endpoint data by name.

        Args:
            name: Endpoint name (e.g., "wikidata", "uniprot")

        Returns:
            Endpoint data dict or None if not found
        """
        return self._external.get(name)

    def get_external_sparql_url(self, name: str) -> Optional[str]:
        """
        Get SPARQL endpoint URL for an external endpoint.

        Args:
            name: Endpoint name

        Returns:
            SPARQL endpoint URL or None
        """
        endpoint = self._external.get(name)
        if endpoint:
            return endpoint.get("sparql_endpoint")
        return None

    def get_external_prefixes(self, name: str) -> Dict[str, str]:
        """
        Get prefixes for an external endpoint.

        Args:
            name: Endpoint name

        Returns:
            Dict of prefix name -> URI
        """
        endpoint = self._external.get(name)
        if endpoint:
            return endpoint.get("prefixes", {})
        return {}

    def get_external_query_patterns(self, name: str) -> List[str]:
        """
        Get query patterns for an external endpoint.

        Args:
            name: Endpoint name

        Returns:
            List of pattern strings
        """
        endpoint = self._external.get(name)
        if endpoint:
            return endpoint.get("query_patterns", [])
        return []

    # =========================================================================
    # Graph Access
    # =========================================================================

    def get_graph(self, shortname: str) -> Optional[Dict[str, Any]]:
        """
        Get complete data for a graph by shortname.

        Args:
            shortname: Graph shortname (e.g., "ubergraph")

        Returns:
            Graph data dict or None if not found
        """
        return self._graphs.get(shortname)

    def get_endpoint(self, shortname: str) -> Optional[str]:
        """
        Get SPARQL endpoint URL for a graph.

        Args:
            shortname: Graph shortname

        Returns:
            SPARQL endpoint URL or None if not found
        """
        graph = self._graphs.get(shortname)
        if graph:
            return graph.get("metadata", {}).get("sparql_endpoint")
        return None

    def get_metadata(self, shortname: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a graph.

        Args:
            shortname: Graph shortname

        Returns:
            Metadata dict or None
        """
        graph = self._graphs.get(shortname)
        if graph:
            return graph.get("metadata")
        return None

    def get_schema(self, shortname: str) -> Optional[Dict[str, Any]]:
        """
        Get schema (classes and properties) for a graph.

        Args:
            shortname: Graph shortname

        Returns:
            Schema dict with 'classes' and 'properties' keys, or None
        """
        graph = self._graphs.get(shortname)
        if graph:
            return graph.get("schema")
        return None

    def get_classes(self, shortname: str) -> List[Dict[str, Any]]:
        """
        Get list of classes for a graph.

        Args:
            shortname: Graph shortname

        Returns:
            List of class dicts with uri, label, count
        """
        schema = self.get_schema(shortname)
        if schema:
            return schema.get("classes", [])
        return []

    def get_properties(self, shortname: str) -> List[Dict[str, Any]]:
        """
        Get list of properties for a graph.

        Args:
            shortname: Graph shortname

        Returns:
            List of property dicts with uri, label, usage_count
        """
        schema = self.get_schema(shortname)
        if schema:
            return schema.get("properties", [])
        return []

    def get_property_labels(self, shortname: str) -> List[str]:
        """
        Get list of property labels for a graph.

        Args:
            shortname: Graph shortname

        Returns:
            List of property label strings
        """
        return [p.get("label", "") for p in self.get_properties(shortname)]

    def get_schema_summary(self, shortname: str, max_properties: int = 20) -> str:
        """
        Get a brief text summary of a graph's schema.

        Args:
            shortname: Graph shortname
            max_properties: Maximum number of properties to include

        Returns:
            Text summary of schema
        """
        props = self.get_properties(shortname)
        prefixes = self.get_graph_prefixes(shortname)

        parts = []
        if props:
            prop_labels = [p.get("label", "") for p in props[:max_properties]]
            parts.append(f"Properties: {', '.join(prop_labels)}")
            if len(props) > max_properties:
                parts.append(f"  ... and {len(props) - max_properties} more")
        if prefixes:
            prefix_list = [f"{k}:" for k in list(prefixes.keys())[:10]]
            parts.append(f"Prefixes: {', '.join(prefix_list)}")

        return "\n".join(parts) if parts else "No schema data available"

    def get_graph_prefixes(self, shortname: str) -> Dict[str, str]:
        """
        Get graph-specific prefixes.

        Args:
            shortname: Graph shortname

        Returns:
            Dict of prefix name -> URI
        """
        graph = self._graphs.get(shortname)
        if graph:
            return graph.get("prefixes", {})
        return {}

    # =========================================================================
    # Graph Discovery
    # =========================================================================

    def find_graphs_by_domain(self, domain: str) -> List[str]:
        """
        Find graphs belonging to a domain.

        Args:
            domain: Domain name (e.g., "biomedical", "ontology", "geospatial")

        Returns:
            List of graph shortnames matching the domain
        """
        matches = []
        domain_lower = domain.lower()
        for shortname, graph in self._graphs.items():
            graph_domain = graph.get("metadata", {}).get("domain", "").lower()
            if domain_lower in graph_domain or graph_domain in domain_lower:
                matches.append(shortname)
        return matches

    def find_graphs_with_class(self, class_pattern: str) -> List[str]:
        """
        Find graphs containing a class matching a pattern.

        Args:
            class_pattern: Substring to match in class URI or label

        Returns:
            List of graph shortnames
        """
        pattern_lower = class_pattern.lower()
        matches = []
        for shortname, graph in self._graphs.items():
            classes = graph.get("schema", {}).get("classes", [])
            for cls in classes:
                if pattern_lower in cls.get("uri", "").lower() or \
                   pattern_lower in cls.get("label", "").lower():
                    matches.append(shortname)
                    break
        return matches

    def find_graphs_with_property(self, property_pattern: str) -> List[str]:
        """
        Find graphs containing a property matching a pattern.

        Args:
            property_pattern: Substring to match in property URI or label

        Returns:
            List of graph shortnames
        """
        pattern_lower = property_pattern.lower()
        matches = []
        for shortname, graph in self._graphs.items():
            properties = graph.get("schema", {}).get("properties", [])
            for prop in properties:
                if pattern_lower in prop.get("uri", "").lower() or \
                   pattern_lower in prop.get("label", "").lower():
                    matches.append(shortname)
                    break
        return matches

    def get_domains(self) -> List[str]:
        """
        Get list of all unique domains.

        Returns:
            Sorted list of domain names
        """
        domains = set()
        for graph in self._graphs.values():
            domain = graph.get("metadata", {}).get("domain")
            if domain:
                domains.add(domain)
        return sorted(domains)

    # =========================================================================
    # Prefix Handling
    # =========================================================================

    def get_prefixes_for_graphs(self, shortnames: List[str]) -> Dict[str, str]:
        """
        Get merged prefixes for multiple graphs.

        Combines common prefixes with graph-specific prefixes.

        Args:
            shortnames: List of graph shortnames

        Returns:
            Dict of prefix name -> URI
        """
        prefixes = self._common_prefixes.copy()
        for shortname in shortnames:
            graph_prefixes = self.get_graph_prefixes(shortname)
            prefixes.update(graph_prefixes)
        return prefixes

    def get_prefix_declarations(self, shortnames: Optional[List[str]] = None) -> str:
        """
        Generate SPARQL PREFIX declarations.

        Args:
            shortnames: List of graphs to include prefixes for (None = common only)

        Returns:
            SPARQL PREFIX block as string
        """
        if shortnames:
            prefixes = self.get_prefixes_for_graphs(shortnames)
        else:
            prefixes = self._common_prefixes

        lines = [f"PREFIX {name}: <{uri}>" for name, uri in sorted(prefixes.items())]
        return "\n".join(lines)

    # =========================================================================
    # Query Building Helpers
    # =========================================================================

    def build_service_clause(self, shortname: str, subquery: str, indent: int = 2) -> str:
        """
        Build a SPARQL SERVICE clause for a graph.

        Args:
            shortname: Graph shortname
            subquery: SPARQL pattern to wrap in SERVICE
            indent: Number of spaces to indent the subquery

        Returns:
            SERVICE clause string
        """
        endpoint = self.get_endpoint(shortname)
        if not endpoint:
            raise ValueError(f"Unknown graph: {shortname}")

        # Indent subquery lines
        indent_str = " " * indent
        indented = "\n".join(indent_str + line for line in subquery.strip().split("\n"))

        return f"SERVICE <{endpoint}> {{\n{indented}\n}}"

    def build_federated_query(
        self,
        graph_queries: Dict[str, str],
        select_vars: str = "*",
        limit: Optional[int] = None,
    ) -> str:
        """
        Build a complete federated SPARQL query.

        Args:
            graph_queries: Dict mapping shortname -> SPARQL WHERE pattern
            select_vars: Variables to SELECT (default: *)
            limit: Optional LIMIT clause

        Returns:
            Complete SPARQL query string
        """
        # Collect all prefixes
        prefixes = self.get_prefix_declarations(list(graph_queries.keys()))

        # Build SERVICE clauses
        services = []
        for shortname, pattern in graph_queries.items():
            services.append(self.build_service_clause(shortname, pattern))

        # Assemble query
        where_body = "\n\n  ".join(services)

        query = f"""{prefixes}

SELECT {select_vars}
WHERE {{
  {where_body}
}}"""

        if limit:
            query += f"\nLIMIT {limit}"

        return query

    # =========================================================================
    # Example Queries
    # =========================================================================

    def get_example_queries(
        self,
        graph: Optional[str] = None,
        federated: Optional[bool] = None,
    ) -> List[ExampleQuery]:
        """
        Get example queries, optionally filtered.

        Args:
            graph: Filter to examples for a specific graph
            federated: If True, only federated; if False, only single-graph

        Returns:
            List of ExampleQuery objects
        """
        results = []

        # Single-graph examples
        if federated is not True:
            for ex in self._examples.get("single_graph", []):
                if graph and ex.get("graph") != graph:
                    continue
                results.append(ExampleQuery(
                    name=ex.get("name", ""),
                    natural_language=ex.get("natural_language", ""),
                    sparql=ex.get("sparql", ""),
                    notes=ex.get("notes", ""),
                    graph=ex.get("graph"),
                ))

        # Federated examples
        if federated is not False:
            for ex in self._examples.get("federated", []):
                if graph and graph not in ex.get("graphs", []):
                    continue
                results.append(ExampleQuery(
                    name=ex.get("name", ""),
                    natural_language=ex.get("natural_language", ""),
                    sparql=ex.get("sparql", ""),
                    notes=ex.get("notes", ""),
                    graphs=ex.get("graphs"),
                ))

        return results

    def get_example_by_name(self, name: str) -> Optional[ExampleQuery]:
        """
        Get a specific example query by name.

        Args:
            name: Example name

        Returns:
            ExampleQuery or None
        """
        for ex in self.get_example_queries():
            if ex.name == name:
                return ex
        return None

    # =========================================================================
    # Federated Query Patterns
    # =========================================================================

    def get_compatible_graph_groups(self) -> Dict[str, Any]:
        """
        Get groups of graphs that work well together for federated queries.

        Returns:
            Dict of group name -> group info (graphs, description, join_strategy)
        """
        return self._patterns.get("compatible_graph_groups", {})

    def get_join_strategies(self) -> List[Dict[str, str]]:
        """
        Get strategies for joining data across graphs.

        Returns:
            List of join strategy dicts with name, description, example
        """
        return self._patterns.get("join_strategies", [])

    # =========================================================================
    # Usage Instructions
    # =========================================================================

    def get_llm_hints(self) -> List[str]:
        """
        Get hints for LLM-based query generation.

        Returns:
            List of hint strings
        """
        return self._instructions.get("llm_prompt_hints", [])

    def get_usage_instructions(self) -> Dict[str, str]:
        """
        Get all usage instructions.

        Returns:
            Dict with instruction categories
        """
        return self._instructions.copy()

    # =========================================================================
    # Summary and Export
    # =========================================================================

    def summary(self) -> str:
        """
        Generate a text summary of the context.

        Returns:
            Multi-line summary string
        """
        lines = [
            f"FRINK Context Summary",
            f"=" * 40,
            f"Version: {self.version}",
            f"Generated: {self.generated_at}",
            f"",
            f"Knowledge Graphs: {len(self._graphs)}",
        ]

        # Count by domain
        domain_counts: Dict[str, int] = {}
        for graph in self._graphs.values():
            domain = graph.get("metadata", {}).get("domain", "unknown")
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

        lines.append("  By domain:")
        for domain, count in sorted(domain_counts.items()):
            lines.append(f"    - {domain}: {count}")

        # Schema stats
        total_classes = sum(
            len(g.get("schema", {}).get("classes", []))
            for g in self._graphs.values()
        )
        total_props = sum(
            len(g.get("schema", {}).get("properties", []))
            for g in self._graphs.values()
        )

        lines.extend([
            f"",
            f"Schema Coverage:",
            f"  Total classes: {total_classes}",
            f"  Total properties: {total_props}",
            f"",
            f"Example Queries:",
            f"  Single-graph: {len(self._examples.get('single_graph', []))}",
            f"  Federated: {len(self._examples.get('federated', []))}",
            f"",
            f"Common Prefixes: {len(self._common_prefixes)}",
        ])

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """
        Export full context as dictionary.

        Returns:
            Complete context data
        """
        return self._data.copy()


# =========================================================================
# Context Builder (from frink_context_builder)
# =========================================================================

import argparse
from datetime import datetime, timezone
from dataclasses import asdict

from frink.registry import (
    FrinkRegistryClient,
    KnowledgeGraph,
    GraphSchema,
    GraphClass,
    GraphProperty,
)


# =============================================================================
# Common Prefixes (shared across FRINK graphs)
# =============================================================================

COMMON_PREFIXES = {
    # W3C Standards
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "skos": "http://www.w3.org/2004/02/skos/core#",

    # Common Vocabularies
    "dcterms": "http://purl.org/dc/terms/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "schema": "http://schema.org/",

    # Wikidata
    "wdt": "http://www.wikidata.org/prop/direct/",
    "wd": "http://www.wikidata.org/entity/",
    "wikibase": "http://wikiba.se/ontology#",

    # OBO Ontologies (via Ubergraph)
    "obo": "http://purl.obolibrary.org/obo/",
    "MONDO": "http://purl.obolibrary.org/obo/MONDO_",
    "HP": "http://purl.obolibrary.org/obo/HP_",
    "GO": "http://purl.obolibrary.org/obo/GO_",
    "CHEBI": "http://purl.obolibrary.org/obo/CHEBI_",
    "UBERON": "http://purl.obolibrary.org/obo/UBERON_",
    "CL": "http://purl.obolibrary.org/obo/CL_",
    "NCBITaxon": "http://purl.obolibrary.org/obo/NCBITaxon_",
    "DOID": "http://purl.obolibrary.org/obo/DOID_",
    "PR": "http://purl.obolibrary.org/obo/PR_",

    # Biomedical
    "mesh": "http://id.nlm.nih.gov/mesh/",
    "umls": "http://linkedlifedata.com/resource/umls/id/",
    "uniprot": "http://purl.uniprot.org/core/",

    # SPOKE / Neo4j
    "neo4j": "neo4j://graph.schema#",

    # AOP-Wiki
    "aop": "http://identifiers.org/aop/",
    "aop-ont": "http://aopkb.org/aop_ontology#",
}


# =============================================================================
# Example SPARQL Queries
# =============================================================================

EXAMPLE_QUERIES = {
    "single_graph": [
        {
            "name": "ubergraph_disease_hierarchy",
            "graph": "ubergraph",
            "natural_language": "Find all subtypes of infectious disease (MONDO:0005550)",
            "sparql": """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX MONDO: <http://purl.obolibrary.org/obo/MONDO_>

SELECT DISTINCT ?disease ?label
WHERE {
  ?disease rdfs:subClassOf* MONDO:0005550 .
  ?disease rdfs:label ?label .
}
LIMIT 100""",
            "notes": "Uses transitive subClassOf (*) for hierarchy traversal in Ubergraph"
        },
        {
            "name": "ubergraph_go_terms",
            "graph": "ubergraph",
            "natural_language": "Find GO biological process terms related to apoptosis",
            "sparql": """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX GO: <http://purl.obolibrary.org/obo/GO_>

SELECT ?term ?label
WHERE {
  ?term rdfs:subClassOf* GO:0006915 .
  ?term rdfs:label ?label .
}
LIMIT 50""",
            "notes": "GO:0006915 is 'apoptotic process'. Returns child terms."
        },
        {
            "name": "ubergraph_phenotype_disease",
            "graph": "ubergraph",
            "natural_language": "Find diseases associated with fever phenotype",
            "sparql": """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX HP: <http://purl.obolibrary.org/obo/HP_>
PREFIX obo: <http://purl.obolibrary.org/obo/>

SELECT DISTINCT ?disease ?diseaseLabel
WHERE {
  ?disease obo:RO_0002200 HP:0001945 .
  ?disease rdfs:label ?diseaseLabel .
}
LIMIT 50""",
            "notes": "HP:0001945 is 'Fever'. RO_0002200 is 'has phenotype'."
        },
        {
            "name": "wikidata_human_genes",
            "graph": "wikidata",
            "natural_language": "Find human genes associated with apoptosis GO term",
            "sparql": """PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wd: <http://www.wikidata.org/entity/>

SELECT ?gene ?symbol ?entrez
WHERE {
  ?go_term wdt:P686 "GO:0006915" .
  ?protein wdt:P682 ?go_term ;
           wdt:P703 wd:Q15978631 ;
           wdt:P702 ?gene .
  ?gene wdt:P353 ?symbol ;
        wdt:P351 ?entrez .
}
LIMIT 50""",
            "notes": "P686=GO ID, P682=biological process, P703=found in taxon, P702=encoded by, Q15978631=Homo sapiens"
        },
        {
            "name": "spoke_disease_prevalence",
            "graph": "spoke-okn",
            "natural_language": "Find disease prevalence data by location",
            "sparql": """PREFIX neo4j: <neo4j://graph.schema#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?disease ?diseaseLabel ?location
WHERE {
  ?disease a neo4j:Neo4jDisease .
  ?disease rdfs:label ?diseaseLabel .
  ?disease neo4j:PREVALENCE_DpL ?connection .
}
LIMIT 100""",
            "notes": "SPOKE uses Neo4j-derived schema. PREVALENCE_DpL = Disease prevalence in Location."
        },
        {
            "name": "aopwiki_pathways",
            "graph": "biobricks-aopwiki",
            "natural_language": "Find adverse outcome pathways and their key events",
            "sparql": """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?pathway ?pathwayLabel ?keyEvent ?eventLabel
WHERE {
  ?pathway rdf:type ?pathwayType .
  FILTER(CONTAINS(STR(?pathwayType), "AdverseOutcomePathway"))
  ?pathway rdfs:label ?pathwayLabel .
  ?pathway ?hasEvent ?keyEvent .
  FILTER(CONTAINS(STR(?hasEvent), "has_key_event"))
  OPTIONAL { ?keyEvent rdfs:label ?eventLabel . }
}
LIMIT 100""",
            "notes": "Queries AOP-Wiki for adverse outcome pathways and associated key events"
        },
        {
            "name": "nde_datasets_by_disease",
            "graph": "nde",
            "natural_language": "Find datasets about influenza",
            "sparql": """PREFIX schema: <http://schema.org/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?dataset ?name ?description
WHERE {
  ?dataset a schema:Dataset .
  ?dataset schema:name ?name .
  OPTIONAL { ?dataset schema:description ?description . }
  FILTER(CONTAINS(LCASE(?name), "influenza") || CONTAINS(LCASE(?description), "influenza"))
}
LIMIT 50""",
            "notes": "NDE (NIAID Data Ecosystem) uses Schema.org vocabulary for datasets"
        },
    ],
    "federated": [
        {
            "name": "ontology_to_datasets",
            "graphs": ["ubergraph", "nde"],
            "natural_language": "Find NDE datasets about subtypes of infectious disease using ontology",
            "sparql": """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX MONDO: <http://purl.obolibrary.org/obo/MONDO_>
PREFIX schema: <http://schema.org/>

SELECT ?disease ?diseaseLabel ?dataset ?datasetName
WHERE {
  # Get disease subclasses from Ubergraph
  SERVICE <https://frink.apps.renci.org/ubergraph/sparql> {
    ?disease rdfs:subClassOf* MONDO:0005550 .
    ?disease rdfs:label ?diseaseLabel .
  }

  # Find datasets referencing these diseases in NDE
  SERVICE <https://frink.apps.renci.org/nde/sparql> {
    ?dataset schema:healthCondition ?disease .
    ?dataset schema:name ?datasetName .
  }
}
LIMIT 50""",
            "notes": "Federated query joining Ubergraph ontology with NDE dataset metadata via disease IRI"
        },
        {
            "name": "cross_ontology_mapping",
            "graphs": ["ubergraph", "wikidata"],
            "natural_language": "Find Wikidata items for MONDO diseases",
            "sparql": """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX MONDO: <http://purl.obolibrary.org/obo/MONDO_>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?mondoDisease ?mondoLabel ?wikidataItem
WHERE {
  # Get MONDO diseases from Ubergraph
  SERVICE <https://frink.apps.renci.org/ubergraph/sparql> {
    ?mondoDisease rdfs:subClassOf* MONDO:0005550 .
    ?mondoDisease rdfs:label ?mondoLabel .
    FILTER(LANG(?mondoLabel) = "en" || LANG(?mondoLabel) = "")
  }

  # Find matching Wikidata items by exact mapping
  SERVICE <https://frink.apps.renci.org/wikidata/sparql> {
    ?wikidataItem wdt:P5270 ?mondoId .
    BIND(IRI(CONCAT("http://purl.obolibrary.org/obo/MONDO_", ?mondoId)) AS ?mondoDisease)
  }
}
LIMIT 50""",
            "notes": "P5270 is MONDO ID property in Wikidata. Links ontology terms to Wikidata entities."
        },
        {
            "name": "biomedical_enrichment",
            "graphs": ["spoke-okn", "ubergraph"],
            "natural_language": "Enrich SPOKE diseases with ontology labels and hierarchy",
            "sparql": """PREFIX neo4j: <neo4j://graph.schema#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX MONDO: <http://purl.obolibrary.org/obo/MONDO_>

SELECT ?spokeDisease ?mondoLabel ?parentDisease ?parentLabel
WHERE {
  # Get diseases from SPOKE
  SERVICE <https://frink.apps.renci.org/spoke-okn/sparql> {
    ?spokeDisease a neo4j:Neo4jDisease .
  }

  # Enrich with Ubergraph ontology data
  SERVICE <https://frink.apps.renci.org/ubergraph/sparql> {
    ?spokeDisease rdfs:label ?mondoLabel .
    OPTIONAL {
      ?spokeDisease rdfs:subClassOf ?parentDisease .
      ?parentDisease rdfs:label ?parentLabel .
    }
  }
}
LIMIT 50""",
            "notes": "Uses SPOKE disease entities and enriches with Ubergraph ontology hierarchy"
        },
    ],
}


# =============================================================================
# Federated Query Patterns
# =============================================================================

FEDERATED_PATTERNS = {
    "service_clause_template": "SERVICE <{{endpoint_url}}> {\n  {{subquery}}\n}",

    "endpoint_url": "https://frink.apps.renci.org/?query=",

    "compatible_graph_groups": {
        "ontology_and_data": {
            "description": "Use ontology graphs for term resolution, then join with data graphs",
            "ontology_graphs": ["ubergraph", "biobricks-mesh"],
            "data_graphs": ["nde", "spoke-okn", "semopenalex"],
            "join_strategy": "IRI identity - same ontology term URI appears in both graphs"
        },
        "biomedical_ecosystem": {
            "description": "Cross-query biomedical knowledge graphs for comprehensive data",
            "graphs": ["spoke-okn", "nde", "biobricks-aopwiki", "biobricks-tox21", "kg-microbe"],
            "join_strategy": "Shared ontology IRIs (MONDO, CHEBI, NCBITaxon)"
        },
        "wikidata_enrichment": {
            "description": "Use Wikidata to enrich other graphs with identifiers and metadata",
            "graphs": ["wikidata", "ubergraph", "spoke-okn"],
            "join_strategy": "External ID properties in Wikidata (P5270=MONDO, P351=Entrez, etc.)"
        },
        "geospatial_environmental": {
            "description": "Geospatial and environmental data integration",
            "graphs": ["geoconnex", "sawgraph", "ufokn", "kg-ichange"],
            "join_strategy": "Geographic identifiers and spatial relationships"
        },
    },

    "join_strategies": [
        {
            "name": "iri_identity",
            "description": "Join on identical IRIs across graphs (e.g., same MONDO disease URI)",
            "example": "?disease in Ubergraph = ?disease in NDE (both use MONDO URIs)",
            "sparql_pattern": "# Same variable used in both SERVICE blocks"
        },
        {
            "name": "label_matching",
            "description": "Join on rdfs:label or schema:name text matching (less precise)",
            "example": "FILTER(?labelA = ?labelB) or FILTER(CONTAINS(LCASE(?labelA), LCASE(?labelB)))",
            "sparql_pattern": "FILTER(?label1 = ?label2)"
        },
        {
            "name": "external_id_mapping",
            "description": "Use Wikidata external ID properties to link identifiers",
            "example": "Wikidata P5270 (MONDO ID) links to MONDO URIs in Ubergraph",
            "sparql_pattern": "?wdItem wdt:P5270 ?mondoId . BIND(IRI(CONCAT(prefix, ?mondoId)) AS ?mondoUri)"
        },
    ],
}


# =============================================================================
# External SPARQL Endpoints (outside FRINK)
# =============================================================================

EXTERNAL_ENDPOINTS = {
    "wikidata": {
        "name": "Wikidata Query Service",
        "sparql_endpoint": "https://query.wikidata.org/sparql",
        "description": "Official Wikidata SPARQL endpoint with full database access",
        "domain": "general knowledge",
        "typical_use_cases": [
            "gene and protein lookups",
            "disease-gene associations",
            "identifier cross-references",
            "taxonomic information",
        ],
        "prefixes": {
            "wdt": "http://www.wikidata.org/prop/direct/",
            "wd": "http://www.wikidata.org/entity/",
            "wikibase": "http://wikiba.se/ontology#",
            "bd": "http://www.bigdata.com/rdf#",
        },
        "query_patterns": [
            "Human genes: ?gene wdt:P31 wd:Q7187 ; wdt:P703 wd:Q15978631 .",
            "Gene symbol: ?gene wdt:P353 ?symbol .",
            "GO process: ?protein wdt:P682 ?go_term .",
            "GO term by ID: ?go_term wdt:P686 'GO:0006915' .",
            "Labels: SERVICE wikibase:label { bd:serviceParam wikibase:language 'en' . }",
        ],
        "notes": "Use SERVICE wikibase:label for labels. Supports federation FROM other endpoints.",
    },
    "uniprot": {
        "name": "UniProt SPARQL",
        "sparql_endpoint": "https://sparql.uniprot.org/sparql",
        "description": "UniProt protein database with sequences, annotations, and cross-references",
        "domain": "proteomics",
        "typical_use_cases": [
            "protein sequence lookups",
            "protein function annotations",
            "cross-references to other databases",
            "taxonomy and organism information",
        ],
        "prefixes": {
            "up": "http://purl.uniprot.org/core/",
            "taxon": "http://purl.uniprot.org/taxonomy/",
            "uniprotkb": "http://purl.uniprot.org/uniprot/",
            "ec": "http://purl.uniprot.org/enzyme/",
        },
        "query_patterns": [
            "Human proteins: ?protein up:organism taxon:9606 .",
            "Protein by gene: ?protein up:encodedBy/up:locusName 'BRCA1' .",
            "GO annotations: ?protein up:classifiedWith ?go_term .",
            "Function: ?protein up:annotation ?annot . ?annot a up:Function_Annotation .",
        ],
        "notes": "Rich protein annotations. Good for sequence and function queries.",
    },
    "nextprot": {
        "name": "neXtProt SPARQL",
        "sparql_endpoint": "https://sparql.nextprot.org/sparql",
        "description": "Human protein knowledge base with curated annotations",
        "domain": "human proteomics",
        "typical_use_cases": [
            "human protein annotations",
            "expression data",
            "disease associations",
            "protein-protein interactions",
        ],
        "prefixes": {
            "nextprot": "http://nextprot.org/rdf#",
            "cv": "http://nextprot.org/rdf/terminology/",
        },
        "query_patterns": [
            "Human entries: ?entry a :Entry .",
            "Expression: ?entry :isoform/:expression ?expr .",
            "Disease: ?entry :isoform/:medical/:in ?disease .",
        ],
        "notes": "Human-focused. High-quality curated data.",
    },
    "dbpedia": {
        "name": "DBpedia SPARQL",
        "sparql_endpoint": "https://dbpedia.org/sparql",
        "description": "Structured data extracted from Wikipedia",
        "domain": "general knowledge",
        "typical_use_cases": [
            "entity lookups",
            "general knowledge queries",
            "cross-references to other datasets",
        ],
        "prefixes": {
            "dbo": "http://dbpedia.org/ontology/",
            "dbr": "http://dbpedia.org/resource/",
            "dbp": "http://dbpedia.org/property/",
        },
        "query_patterns": [
            "Resources: ?x a dbo:Disease .",
            "Labels: ?x rdfs:label ?label . FILTER(LANG(?label) = 'en')",
        ],
        "notes": "Good for general entity information. May be less current than Wikidata.",
    },
}


# =============================================================================
# Usage Instructions
# =============================================================================

USAGE_INSTRUCTIONS = {
    "single_graph_query": (
        "For single-graph queries, use the sparql_endpoint URL directly. "
        "Include relevant prefixes from common_prefixes and the graph's specific prefixes. "
        "Check the graph's schema.classes and schema.properties to ensure valid predicates."
    ),
    "federated_query": (
        "For federated queries across multiple graphs, use SERVICE clauses. "
        "The federated_endpoint (https://frink.apps.renci.org/?query=) can execute "
        "queries containing SERVICE clauses to multiple graph endpoints. "
        "Identify join points using shared IRIs or identifier mappings."
    ),
    "llm_prompt_hints": [
        "1. Identify the domain: biomedical, ontology, geospatial, scholarly, etc.",
        "2. Select appropriate graph(s) based on domain and data type needed",
        "3. For ontology term lookups (disease, gene, phenotype, anatomy), start with ubergraph",
        "4. For dataset/study discovery, use nde (NIAID Data Ecosystem)",
        "5. For biomedical relationships (disease-compound, gene-disease), use spoke-okn",
        "6. For identifier enrichment and cross-references, use wikidata",
        "7. Include appropriate prefixes for the IRIs you're querying",
        "8. Use rdfs:label for human-readable names",
        "9. For hierarchy traversal, use rdfs:subClassOf* (transitive closure)",
        "10. Check example_queries for similar patterns to adapt",
    ],
}


# =============================================================================
# Context Builder Functions
# =============================================================================

def graph_to_dict(graph: KnowledgeGraph) -> Dict[str, Any]:
    """Convert KnowledgeGraph to JSON-serializable dict."""
    d = {
        "metadata": {
            "shortname": graph.metadata.shortname,
            "title": graph.metadata.title,
            "description": graph.metadata.description,
            "sparql_endpoint": graph.metadata.sparql_endpoint,
            "stats_url": graph.metadata.stats_url,
            "registry_url": graph.metadata.registry_url,
            "domain": graph.metadata.domain,
            "typical_use_cases": graph.metadata.typical_use_cases,
        },
    }

    if graph.schema:
        d["prefixes"] = graph.schema.prefixes
        d["schema"] = {
            "classes": [
                {"uri": c.uri, "label": c.label, "count": c.count, "description": c.description}
                for c in graph.schema.classes
            ],
            "properties": [
                {
                    "uri": p.uri,
                    "label": p.label,
                    "usage_count": p.usage_count,
                    "domain": p.domain,
                    "range": p.range,
                }
                for p in graph.schema.properties
            ],
        }
    else:
        d["prefixes"] = {}
        d["schema"] = {"classes": [], "properties": []}

    return d


def build_context(graphs: List[KnowledgeGraph]) -> Dict[str, Any]:
    """
    Build the complete context file structure.

    Args:
        graphs: List of KnowledgeGraph objects from registry

    Returns:
        Complete context dictionary ready for JSON serialization
    """
    context = {
        "version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "registry_url": "https://frink.renci.org/registry/",
        "federated_endpoint": "https://frink.apps.renci.org/?query=",

        "common_prefixes": COMMON_PREFIXES,

        "knowledge_graphs": {
            g.shortname: graph_to_dict(g) for g in graphs
        },

        "external_endpoints": EXTERNAL_ENDPOINTS,

        "example_queries": EXAMPLE_QUERIES,

        "federated_query_patterns": FEDERATED_PATTERNS,

        "usage_instructions": USAGE_INSTRUCTIONS,
    }

    return context


def main():
    """Main entry point for context builder."""
    parser = argparse.ArgumentParser(
        description="Build FRINK NL-to-SPARQL context file from registry",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python frink_context_builder.py
  python frink_context_builder.py --output my_context.json
  python frink_context_builder.py --skip-schemas  # Faster, metadata only
  python frink_context_builder.py --graphs ubergraph spoke-okn nde
        """,
    )
    parser.add_argument(
        "--output", "-o",
        default="frink_context.json",
        help="Output JSON file path (default: frink_context.json)"
    )
    parser.add_argument(
        "--skip-schemas",
        action="store_true",
        help="Skip fetching schema stats (faster, metadata only)"
    )
    parser.add_argument(
        "--graphs",
        nargs="+",
        help="Only include specific graphs (by shortname)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed progress"
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation (default: 2, use 0 for compact)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("FRINK Context Builder")
    print("=" * 60)

    client = FrinkRegistryClient()

    # Fetch graphs
    print("\nFetching registry and schemas...")
    all_graphs = client.fetch_all_graphs(
        fetch_schemas=not args.skip_schemas,
        verbose=args.verbose
    )

    # Filter if specific graphs requested
    if args.graphs:
        requested = set(args.graphs)
        graphs = [g for g in all_graphs if g.shortname in requested]
        missing = requested - {g.shortname for g in graphs}
        if missing:
            print(f"\nWarning: Graphs not found: {', '.join(missing)}")
    else:
        graphs = all_graphs

    print(f"\nBuilding context with {len(graphs)} graphs...")
    context = build_context(graphs)

    # Save to file
    output_path = Path(args.output)
    indent = args.indent if args.indent > 0 else None
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(context, f, indent=indent, ensure_ascii=False)

    # Summary
    print(f"\nContext file saved to: {output_path}")
    print(f"  - {len(context['knowledge_graphs'])} knowledge graphs")
    print(f"  - {len(context['common_prefixes'])} common prefixes")
    print(f"  - {len(context['example_queries']['single_graph'])} single-graph examples")
    print(f"  - {len(context['example_queries']['federated'])} federated examples")

    # Stats on schemas
    total_classes = sum(
        len(g.get("schema", {}).get("classes", []))
        for g in context["knowledge_graphs"].values()
    )
    total_properties = sum(
        len(g.get("schema", {}).get("properties", []))
        for g in context["knowledge_graphs"].values()
    )
    print(f"  - {total_classes} total classes across all graphs")
    print(f"  - {total_properties} total properties across all graphs")

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
