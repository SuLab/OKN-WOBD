"""
FRINK knowledge graph integration.

Provides tools for:
- Registry metadata scraping
- Context file building and API access
- LLM-based natural language to SPARQL translation
"""
from .registry import FrinkRegistryClient, KnowledgeGraph, KnowledgeGraphMetadata, GraphSchema, GraphClass, GraphProperty
from .context import FrinkContext, ExampleQuery, build_context, graph_to_dict, COMMON_PREFIXES as CONTEXT_PREFIXES, EXAMPLE_QUERIES, EXTERNAL_ENDPOINTS
from .nl2sparql import SPARQLGenerator, FrinkQueryExecutor, FrinkNL2SPARQL, ResultFormatter
from .nl2sparql import QueryResult as NL2SPARQLResult
