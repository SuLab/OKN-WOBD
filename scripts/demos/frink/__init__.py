"""
FRINK knowledge graph integration.

Provides tools for:
- Registry metadata scraping
- Context file building and API access
- LLM-based natural language to SPARQL translation
"""
from frink.registry import FrinkRegistryClient, KnowledgeGraph, KnowledgeGraphMetadata, GraphSchema, GraphClass, GraphProperty
from frink.context import FrinkContext, ExampleQuery, build_context, graph_to_dict, COMMON_PREFIXES as CONTEXT_PREFIXES, EXAMPLE_QUERIES, EXTERNAL_ENDPOINTS
from frink.nl2sparql import SPARQLGenerator, FrinkQueryExecutor, FrinkNL2SPARQL, ResultFormatter
from frink.nl2sparql import QueryResult as NL2SPARQLResult
