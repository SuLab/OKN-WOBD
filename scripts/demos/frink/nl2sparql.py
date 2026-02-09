#!/usr/bin/env python3
"""
Natural Language to SPARQL Query System for FRINK Knowledge Graphs.

This script takes a natural language question, generates a SPARQL query using
an LLM, executes it against FRINK endpoints, and returns results in multiple formats.

Usage:
    # Basic usage
    from frink import FrinkNL2SPARQL

    nl2sparql = FrinkNL2SPARQL()
    result = nl2sparql.query("What are the subtypes of infectious disease?")

    # CLI usage
    python -m frink.nl2sparql "What are the subtypes of infectious disease?"

    # Specify output format
    python -m frink.nl2sparql "Find genes related to apoptosis" --format json
    python -m frink.nl2sparql "Find genes related to apoptosis" --format table
    python -m frink.nl2sparql "Find genes related to apoptosis" --format summary

    # Specify graphs to query
    python -m frink.nl2sparql "Find disease datasets" --graphs ubergraph nde

    # Show generated SPARQL without executing
    python -m frink.nl2sparql "Find all cancer types" --dry-run

Requirements:
    pip install anthropic  # or openai for OpenAI models
"""

import os
import sys
import json
import argparse
import textwrap
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

from frink.context import FrinkContext
from clients.sparql import SPARQLClient

# Try to import LLM clients
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    anthropic = None

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    openai = None


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class QueryResult:
    """Complete result of an NL-to-SPARQL query."""
    natural_language: str
    generated_sparql: str
    graphs_used: List[str]
    endpoint_url: str
    execution_time_ms: float
    row_count: int
    columns: List[str]
    rows: List[Dict[str, Any]]
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)


# =============================================================================
# LLM Query Generator
# =============================================================================

class SPARQLGenerator:
    """
    Generates SPARQL queries from natural language using an LLM.

    Supports both Anthropic Claude and OpenAI GPT models.
    The system prompt is built dynamically from the context file.
    """

    # Static parts of the system prompt (query patterns that don't change)
    QUERY_PATTERNS = """
WIKIDATA PATTERNS:
- Human genes: ?gene wdt:P31 wd:Q7187 ; wdt:P703 wd:Q15978631 .
- Gene symbol: ?gene wdt:P353 ?symbol .
- GO biological process: ?protein wdt:P682 ?go_term .
- Find GO term by ID: ?go_term wdt:P686 "GO:0006915" .
- Protein to gene: ?protein wdt:P702 ?gene .

UBERGRAPH PATTERNS:
- GO term hierarchy: ?term rdfs:subClassOf* obo:GO_0006915 .
- Disease hierarchy: ?disease rdfs:subClassOf* MONDO:0005550 .
- Labels: ?term rdfs:label ?label .

EXAMPLE 1 - Wikidata only (genes for apoptosis):
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX bd: <http://www.bigdata.com/rdf#>

SELECT DISTINCT ?gene ?geneLabel ?symbol WHERE {
  ?go_term wdt:P686 "GO:0006915" .
  ?protein wdt:P682 ?go_term ;
           wdt:P703 wd:Q15978631 ;
           wdt:P702 ?gene .
  ?gene wdt:P353 ?symbol .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
}
LIMIT 100

EXAMPLE 2 - FEDERATED (genes for apoptosis AND all subclasses):
This runs on ubergraph and federates to Wikidata via SERVICE clause.
IMPORTANT: Use https://query.wikidata.org/sparql for the SERVICE clause.
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX obo: <http://purl.obolibrary.org/obo/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wd: <http://www.wikidata.org/entity/>

SELECT DISTINCT ?go_label ?symbol WHERE {
  # Local ubergraph: get apoptosis and ALL subclasses
  ?go_term rdfs:subClassOf* obo:GO_0006915 .
  ?go_term rdfs:label ?go_label .

  # Convert OBO URI to GO ID string for joining
  BIND(REPLACE(STR(?go_term), "http://purl.obolibrary.org/obo/GO_", "GO:") AS ?go_id)

  # Remote Wikidata: find human genes for those GO terms
  SERVICE <https://query.wikidata.org/sparql> {
    ?go_wd wdt:P686 ?go_id .
    ?protein wdt:P682 ?go_wd ;
             wdt:P703 wd:Q15978631 ;
             wdt:P702 ?gene .
    ?gene wdt:P353 ?symbol .
  }
}
LIMIT 100

OUTPUT: Return ONLY valid SPARQL. No markdown, no explanations.
"""

    def __init__(
        self,
        context: FrinkContext,
        model: str = "claude-sonnet-4-20250514",
        provider: str = "anthropic",
    ):
        """
        Initialize the SPARQL generator.

        Args:
            context: FrinkContext with graph metadata and examples
            model: Model name to use
            provider: "anthropic" or "openai"
        """
        self.context = context
        self.model = model
        self.provider = provider
        self._system_prompt = None  # Built lazily

        if provider == "anthropic":
            if not HAS_ANTHROPIC:
                raise ImportError("anthropic package required: pip install anthropic")
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable required")
            self.client = anthropic.Anthropic(api_key=api_key)
        elif provider == "openai":
            if not HAS_OPENAI:
                raise ImportError("openai package required: pip install openai")
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable required")
            self.client = openai.OpenAI(api_key=api_key)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def _build_system_prompt(self) -> str:
        """Build the system prompt dynamically from context."""
        parts = []

        # Header
        parts.append("You are a SPARQL query generator for knowledge graph queries.")
        parts.append("Your task is to convert natural language questions into valid SPARQL queries.")
        parts.append("")

        # Critical rules
        parts.append("CRITICAL RULES:")
        parts.append("1. Generate ONLY the SPARQL query - no explanations, no markdown code blocks")
        parts.append("2. Always include necessary PREFIX declarations")
        parts.append("3. Use LIMIT to prevent excessive results (default: 100)")
        parts.append("4. Use rdfs:label to get human-readable names")
        parts.append("5. FOLLOW USER INSTRUCTIONS about which graphs/endpoints to use")
        parts.append("")

        # Available FRINK graphs - built from context
        # Show key graphs with more detail, others in compact list
        key_graphs = ["ubergraph", "wikidata", "spoke-okn", "nde", "biobricks-aopwiki"]
        other_graphs = [n for n in self.context.graph_names if n not in key_graphs]

        parts.append("KEY FRINK GRAPHS (with schema info):")
        for name in key_graphs:
            if name not in self.context.graph_names:
                continue
            meta = self.context.get_metadata(name)
            if meta:
                title = meta.get("title", name)
                domain = meta.get("domain", "general")
                use_cases = meta.get("typical_use_cases", [])
                use_case_str = ", ".join(use_cases[:3]) if use_cases else "general queries"
                parts.append(f"- {name}: {title} (domain: {domain})")
                parts.append(f"    Use cases: {use_case_str}")
                # Add schema info
                props = self.context.get_property_labels(name)
                if props:
                    parts.append(f"    Properties: {', '.join(props[:15])}")
                    if len(props) > 15:
                        parts.append(f"      ... and {len(props) - 15} more")
        parts.append("")

        parts.append("OTHER FRINK GRAPHS:")
        for name in other_graphs:
            meta = self.context.get_metadata(name)
            if meta:
                title = meta.get("title", name)
                domain = meta.get("domain", "general")
                parts.append(f"- {name}: {title} ({domain})")
        parts.append("")

        # External endpoints (Wikidata, UniProt, etc.)
        external_names = self.context.external_endpoint_names
        if external_names:
            parts.append("EXTERNAL SPARQL ENDPOINTS (non-FRINK):")
            for name in external_names:
                endpoint = self.context.get_external_endpoint(name)
                if endpoint:
                    title = endpoint.get("name", name)
                    url = endpoint.get("sparql_endpoint", "")
                    domain = endpoint.get("domain", "general")
                    use_cases = endpoint.get("typical_use_cases", [])
                    use_case_str = ", ".join(use_cases[:3]) if use_cases else "general queries"
                    parts.append(f"- {name}: {title} (domain: {domain}) - {use_case_str}")
                    parts.append(f"    Endpoint: {url}")
                    # Include query patterns
                    patterns = endpoint.get("query_patterns", [])
                    if patterns:
                        parts.append(f"    Patterns: {'; '.join(patterns[:3])}")
            parts.append("")

        # LLM hints from context
        instructions = self.context.get_usage_instructions()
        llm_hints = instructions.get("llm_prompt_hints", [])
        if llm_hints:
            parts.append("QUERY GENERATION HINTS:")
            for hint in llm_hints:
                parts.append(hint)
            parts.append("")

        # Choosing the right approach
        parts.append("CHOOSING THE RIGHT APPROACH:")
        parts.append("")
        parts.append("1. WIKIDATA-ONLY queries (simple gene lookups):")
        parts.append("   - Do NOT use SERVICE clauses for external endpoints")
        parts.append("   - Use SERVICE wikibase:label for labels only")
        parts.append("   - Example: \"find human genes related to apoptosis\"")
        parts.append("")
        parts.append("2. FEDERATED queries (combining ontology + Wikidata):")
        parts.append("   - Query FROM ubergraph, SERVICE out TO Wikidata")
        parts.append("   - Use this when user wants ontology hierarchy + Wikidata data")
        parts.append("   - Example: \"find genes for apoptosis AND its subclasses\"")
        parts.append("")

        # Add static query patterns
        parts.append(self.QUERY_PATTERNS)

        return "\n".join(parts)

    @property
    def system_prompt(self) -> str:
        """Get the system prompt, building it if needed."""
        if self._system_prompt is None:
            self._system_prompt = self._build_system_prompt()
        return self._system_prompt

    def _build_context_prompt(self, graphs: Optional[List[str]] = None) -> str:
        """Build context information for the LLM."""
        parts = []

        # Add available graphs
        parts.append("AVAILABLE KNOWLEDGE GRAPHS:")
        for name in (graphs or self.context.graph_names):
            graph = self.context.get_graph(name)
            if graph:
                meta = graph.get("metadata", {})
                parts.append(f"- {name}: {meta.get('title', name)}")
                parts.append(f"  Endpoint: {meta.get('sparql_endpoint', 'N/A')}")
                parts.append(f"  Domain: {meta.get('domain', 'general')}")
                if meta.get('typical_use_cases'):
                    parts.append(f"  Use cases: {', '.join(meta['typical_use_cases'][:3])}")

        # Add common prefixes
        parts.append("\nCOMMON PREFIXES:")
        for name, uri in list(self.context.common_prefixes.items())[:15]:
            parts.append(f"PREFIX {name}: <{uri}>")

        # Add example queries
        parts.append("\nEXAMPLE QUERIES:")
        for ex in self.context.get_example_queries()[:3]:
            parts.append(f"\nQuestion: {ex.natural_language}")
            parts.append(f"SPARQL:\n{ex.sparql[:500]}...")

        return "\n".join(parts)

    def generate(
        self,
        question: str,
        graphs: Optional[List[str]] = None,
    ) -> Tuple[str, List[str]]:
        """
        Generate SPARQL from natural language.

        Args:
            question: Natural language question
            graphs: Optional list of graphs to consider

        Returns:
            Tuple of (SPARQL query string, list of graphs to query)
        """
        context_prompt = self._build_context_prompt(graphs)

        user_prompt = f"""{context_prompt}

USER QUESTION: {question}

Generate a SPARQL query to answer this question. Return ONLY the SPARQL query."""

        if self.provider == "anthropic":
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=self.system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            sparql = response.content[0].text.strip()
        else:  # openai
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=2000,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            sparql = response.choices[0].message.content.strip()

        # Clean up response (remove markdown if present)
        if sparql.startswith("```"):
            lines = sparql.split("\n")
            sparql = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        # Determine which graphs are referenced
        graphs_used = self._detect_graphs(sparql, graphs)

        return sparql, graphs_used

    def _detect_graphs(self, sparql: str, hint_graphs: Optional[List[str]]) -> List[str]:
        """Detect which graphs a SPARQL query targets."""
        # Use hints if provided
        if hint_graphs:
            return hint_graphs

        sparql_lower = sparql.lower()

        # Check for federated query pattern: SERVICE to Wikidata means run on ubergraph
        if "service <https://query.wikidata.org" in sparql_lower:
            return ["ubergraph"]

        # Check for SERVICE to FRINK endpoints
        if "service <https://frink.apps.renci.org" in sparql_lower:
            # This is a federated query, determine primary endpoint
            if "ubergraph" in sparql_lower:
                return ["ubergraph"]
            return ["ubergraph"]  # default for FRINK federation

        # Ubergraph/ontology indicators - check before Wikidata
        # (queries with subClassOf* should go to ubergraph even if they mention GO terms)
        if "subclassof" in sparql_lower and "obo/" in sparql_lower:
            return ["ubergraph"]

        # Wikidata-only indicators
        wikidata_indicators = [
            "wdt:", "wd:", "wikibase:",
        ]
        if any(ind in sparql_lower for ind in wikidata_indicators):
            # But not if it's clearly an ontology query
            if "mondo" not in sparql_lower and "obo/" not in sparql_lower:
                return ["wikidata"]

        # Ontology queries
        if "mondo" in sparql_lower or "obo/" in sparql_lower:
            return ["ubergraph"]

        # Dataset discovery
        if "schema:dataset" in sparql_lower or "schema.org" in sparql_lower:
            return ["nde"]

        return ["ubergraph"]  # default


# =============================================================================
# Query Executor
# =============================================================================

class FrinkQueryExecutor:
    """
    Executes SPARQL queries against FRINK endpoints.

    For Wikidata queries, tries the official Wikidata endpoint first,
    falling back to FRINK's hosted subset if it fails.
    """

    # Primary endpoints (preferred) - official, full data
    PRIMARY_ENDPOINTS = {
        "wikidata": "https://query.wikidata.org/sparql",
    }

    # Fallback endpoints (FRINK-hosted subsets)
    FALLBACK_ENDPOINTS = {
        "wikidata": "https://frink.apps.renci.org/wikidata/sparql",
    }

    def __init__(self, context: FrinkContext):
        self.context = context

    def _execute_single(
        self,
        sparql: str,
        endpoint: str,
        timeout: int,
    ) -> Tuple[List[Dict[str, Any]], List[str], Optional[str]]:
        """
        Execute a query against a single endpoint.

        Returns:
            Tuple of (rows, columns, error_message)
        """
        client = SPARQLClient(default_endpoint=endpoint, timeout=timeout)

        try:
            result = client.query(sparql, include_prefixes=False)

            if not result.bindings:
                return [], result.variables, None

            # Convert bindings to simple dicts
            rows = []
            for binding in result.bindings:
                row = {}
                for var in result.variables:
                    if var in binding:
                        row[var] = binding[var].get("value", "")
                    else:
                        row[var] = ""
                rows.append(row)

            return rows, result.variables, None

        except Exception as e:
            return [], [], str(e)

    def execute(
        self,
        sparql: str,
        graphs: List[str],
        timeout: int = 60,
    ) -> Tuple[List[Dict[str, Any]], List[str], str, Optional[str]]:
        """
        Execute a SPARQL query.

        For graphs with primary endpoints (like Wikidata), tries the official
        endpoint first and falls back to FRINK if it fails.

        Args:
            sparql: SPARQL query string
            graphs: List of graph names to query
            timeout: Query timeout in seconds

        Returns:
            Tuple of (rows, columns, endpoint_url, error_message)
        """
        # Determine endpoint
        if len(graphs) == 1:
            graph_name = graphs[0]

            # Check if this graph has a primary endpoint to try first
            if graph_name in self.PRIMARY_ENDPOINTS:
                primary_endpoint = self.PRIMARY_ENDPOINTS[graph_name]
                fallback_endpoint = self.FALLBACK_ENDPOINTS.get(graph_name)

                # Try primary endpoint first
                rows, columns, error = self._execute_single(
                    sparql, primary_endpoint, timeout
                )

                if error is None:
                    return rows, columns, primary_endpoint, None

                # Primary failed - try fallback if available
                if fallback_endpoint:
                    fallback_rows, fallback_columns, fallback_error = self._execute_single(
                        sparql, fallback_endpoint, timeout
                    )

                    if fallback_error is None:
                        # Fallback succeeded - note which endpoint was used
                        return fallback_rows, fallback_columns, fallback_endpoint, None

                    # Both failed - return combined error info
                    combined_error = (
                        f"Primary endpoint ({primary_endpoint}) failed: {error}; "
                        f"Fallback ({fallback_endpoint}) also failed: {fallback_error}"
                    )
                    return [], [], primary_endpoint, combined_error

                # No fallback available
                return [], [], primary_endpoint, error

            # No primary endpoint - use FRINK endpoint directly
            endpoint = self.context.get_endpoint(graph_name)
        else:
            # For federated queries, use the federated endpoint
            endpoint = self.context.federated_endpoint

        if not endpoint:
            return [], [], "", f"No endpoint found for graphs: {graphs}"

        # Execute query against single endpoint
        rows, columns, error = self._execute_single(sparql, endpoint, timeout)
        return rows, columns, endpoint, error


# =============================================================================
# Result Formatters
# =============================================================================

class ResultFormatter:
    """Formats query results in various output formats."""

    @staticmethod
    def to_json(result: QueryResult, indent: int = 2) -> str:
        """Format as JSON."""
        return result.to_json(indent=indent)

    @staticmethod
    def to_table(result: QueryResult, max_width: int = 40) -> str:
        """Format as ASCII table."""
        if result.error:
            return f"ERROR: {result.error}"

        if not result.rows:
            return "No results found."

        # Calculate column widths
        cols = result.columns
        widths = {col: min(len(col), max_width) for col in cols}
        for row in result.rows[:100]:  # Sample first 100 rows
            for col in cols:
                val = str(row.get(col, ""))[:max_width]
                widths[col] = max(widths[col], len(val))

        # Build table
        lines = []

        # Header
        header = " | ".join(col.ljust(widths[col]) for col in cols)
        lines.append(header)
        lines.append("-+-".join("-" * widths[col] for col in cols))

        # Rows
        for row in result.rows:
            line = " | ".join(
                str(row.get(col, ""))[:max_width].ljust(widths[col])
                for col in cols
            )
            lines.append(line)

        # Footer
        lines.append(f"\n({result.row_count} rows, {result.execution_time_ms:.0f}ms)")

        return "\n".join(lines)

    @staticmethod
    def to_summary(result: QueryResult, context: FrinkContext) -> str:
        """Format as human-readable summary with references."""
        parts = []

        # Header
        parts.append("=" * 60)
        parts.append("QUERY RESULTS SUMMARY")
        parts.append("=" * 60)

        # Original question
        parts.append(f"\nQuestion: {result.natural_language}")

        # Query info
        parts.append(f"\nGraphs queried: {', '.join(result.graphs_used)}")
        parts.append(f"Endpoint used: {result.endpoint_url}")
        parts.append(f"Execution time: {result.execution_time_ms:.0f}ms")
        parts.append(f"Results found: {result.row_count}")

        if result.error:
            parts.append(f"\nERROR: {result.error}")
            parts.append("\nGenerated SPARQL:")
            parts.append(result.generated_sparql)
            return "\n".join(parts)

        if not result.rows:
            parts.append("\nNo results found for this query.")
            parts.append("\nGenerated SPARQL:")
            parts.append(result.generated_sparql)
            return "\n".join(parts)

        # Results summary
        parts.append("\n" + "-" * 60)
        parts.append("RESULTS")
        parts.append("-" * 60)

        # Show first N results with formatting
        for i, row in enumerate(result.rows[:10], 1):
            parts.append(f"\n{i}. ", )
            for col, val in row.items():
                # Shorten URIs for display
                if val.startswith("http"):
                    short_val = val.split("/")[-1]
                    if "#" in short_val:
                        short_val = short_val.split("#")[-1]
                    parts.append(f"   {col}: {short_val}")
                    parts.append(f"         ({val})")
                else:
                    parts.append(f"   {col}: {val}")

        if result.row_count > 10:
            parts.append(f"\n... and {result.row_count - 10} more results")

        # References
        parts.append("\n" + "-" * 60)
        parts.append("REFERENCES")
        parts.append("-" * 60)

        for graph in result.graphs_used:
            meta = context.get_metadata(graph)
            if meta:
                parts.append(f"\n{meta.get('title', graph)}:")
                parts.append(f"  SPARQL Endpoint: {meta.get('sparql_endpoint', 'N/A')}")
                parts.append(f"  Registry: {meta.get('registry_url', 'N/A')}")

        parts.append(f"\nFRINK Registry: {context.registry_url}")

        # Generated SPARQL
        parts.append("\n" + "-" * 60)
        parts.append("GENERATED SPARQL")
        parts.append("-" * 60)
        parts.append(result.generated_sparql)

        return "\n".join(parts)


# =============================================================================
# Main Interface
# =============================================================================

class FrinkNL2SPARQL:
    """
    Main interface for natural language to SPARQL queries.

    Usage:
        nl2sparql = FrinkNL2SPARQL()
        result = nl2sparql.query("What are the subtypes of infectious disease?")
        print(nl2sparql.format(result, "summary"))
    """

    def __init__(
        self,
        context_path: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        provider: str = "anthropic",
    ):
        """
        Initialize the NL-to-SPARQL system.

        Args:
            context_path: Path to context JSON file (default: frink_context.json)
            model: LLM model to use
            provider: LLM provider ("anthropic" or "openai")
        """
        if context_path:
            self.context = FrinkContext.load(context_path)
        else:
            self.context = FrinkContext.load_default()

        self.generator = SPARQLGenerator(self.context, model=model, provider=provider)
        self.executor = FrinkQueryExecutor(self.context)
        self.formatter = ResultFormatter()

    def query(
        self,
        question: str,
        graphs: Optional[List[str]] = None,
        timeout: int = 60,
    ) -> QueryResult:
        """
        Execute a natural language query.

        Args:
            question: Natural language question
            graphs: Optional list of graphs to query
            timeout: Query timeout in seconds

        Returns:
            QueryResult with all information
        """
        import time
        start_time = time.time()

        # Generate SPARQL
        sparql, graphs_used = self.generator.generate(question, graphs)

        # Execute query
        rows, columns, endpoint, error = self.executor.execute(
            sparql, graphs_used, timeout
        )

        execution_time = (time.time() - start_time) * 1000

        return QueryResult(
            natural_language=question,
            generated_sparql=sparql,
            graphs_used=graphs_used,
            endpoint_url=endpoint,
            execution_time_ms=execution_time,
            row_count=len(rows),
            columns=columns,
            rows=rows,
            error=error,
        )

    def format(self, result: QueryResult, format_type: str = "summary") -> str:
        """
        Format query results.

        Args:
            result: QueryResult to format
            format_type: "json", "table", or "summary"

        Returns:
            Formatted string
        """
        if format_type == "json":
            return self.formatter.to_json(result)
        elif format_type == "table":
            return self.formatter.to_table(result)
        else:
            return self.formatter.to_summary(result, self.context)

    def query_with_sparql(
        self,
        question: str,
        sparql: str,
        graphs: List[str],
        timeout: int = 60,
    ) -> QueryResult:
        """
        Execute a query with pre-generated SPARQL.

        Args:
            question: Original natural language question
            sparql: Pre-generated SPARQL query
            graphs: List of graphs to query
            timeout: Query timeout in seconds

        Returns:
            QueryResult with all information
        """
        import time
        start_time = time.time()

        # Execute query
        rows, columns, endpoint, error = self.executor.execute(
            sparql, graphs, timeout
        )

        execution_time = (time.time() - start_time) * 1000

        return QueryResult(
            natural_language=question,
            generated_sparql=sparql,
            graphs_used=graphs,
            endpoint_url=endpoint,
            execution_time_ms=execution_time,
            row_count=len(rows),
            columns=columns,
            rows=rows,
            error=error,
        )

    def generate_only(
        self,
        question: str,
        graphs: Optional[List[str]] = None,
    ) -> str:
        """
        Generate SPARQL without executing.

        Args:
            question: Natural language question
            graphs: Optional list of graphs

        Returns:
            Generated SPARQL query
        """
        sparql, _ = self.generator.generate(question, graphs)
        return sparql


# =============================================================================
# CLI
# =============================================================================

def main():
    # Load environment at CLI entry point
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    parser = argparse.ArgumentParser(
        description="Natural Language to SPARQL for FRINK Knowledge Graphs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Examples:
          %(prog)s "What are the subtypes of infectious disease?"
          %(prog)s "Find datasets about influenza" --format json
          %(prog)s "Find genes related to apoptosis" --graphs ubergraph wikidata
          %(prog)s "List all cancer types" --dry-run

        Environment Variables:
          ANTHROPIC_API_KEY  - Required for Claude models (default)
          OPENAI_API_KEY     - Required for OpenAI models

        Output Formats:
          json    - Machine-readable JSON with all metadata
          table   - ASCII table for quick viewing
          summary - Human-readable summary with references (default)
        """),
    )

    parser.add_argument(
        "question",
        help="Natural language question to answer",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["json", "table", "summary"],
        default="summary",
        help="Output format (default: summary)",
    )
    parser.add_argument(
        "--graphs", "-g",
        nargs="+",
        help="Specific graphs to query (default: auto-detect)",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Generate SPARQL without executing",
    )
    parser.add_argument(
        "--model", "-m",
        default="claude-sonnet-4-20250514",
        help="LLM model to use (default: claude-sonnet-4-20250514)",
    )
    parser.add_argument(
        "--provider", "-p",
        choices=["anthropic", "openai"],
        default="anthropic",
        help="LLM provider (default: anthropic)",
    )
    parser.add_argument(
        "--context",
        help="Path to context JSON file",
    )
    parser.add_argument(
        "--timeout", "-t",
        type=int,
        default=60,
        help="Query timeout in seconds (default: 60)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show verbose output",
    )

    args = parser.parse_args()

    # Initialize
    try:
        nl2sparql = FrinkNL2SPARQL(
            context_path=args.context,
            model=args.model,
            provider=args.provider,
        )
    except (ImportError, ValueError) as e:
        print(f"Error initializing: {e}", file=sys.stderr)
        print("\nMake sure you have set the appropriate API key:", file=sys.stderr)
        print("  export ANTHROPIC_API_KEY=your-key-here", file=sys.stderr)
        print("  # or", file=sys.stderr)
        print("  export OPENAI_API_KEY=your-key-here", file=sys.stderr)
        sys.exit(1)

    # Execute
    if args.dry_run:
        sparql = nl2sparql.generate_only(args.question, args.graphs)
        print("Generated SPARQL:")
        print("-" * 40)
        print(sparql)
    else:
        if args.verbose:
            print(f"Processing: {args.question}", file=sys.stderr)
            print(f"Graphs: {args.graphs or 'auto-detect'}", file=sys.stderr)

        # Generate SPARQL and show it before executing
        print("Generating SPARQL...", file=sys.stderr)
        sparql, graphs_used = nl2sparql.generator.generate(args.question, args.graphs)
        print(f"\nGenerated SPARQL (querying {', '.join(graphs_used)}):", file=sys.stderr)
        print("-" * 40, file=sys.stderr)
        print(sparql, file=sys.stderr)
        print("-" * 40, file=sys.stderr)
        print("Executing query...", file=sys.stderr)
        sys.stderr.flush()

        # Now execute with the pre-generated SPARQL
        result = nl2sparql.query_with_sparql(
            args.question,
            sparql,
            graphs_used,
            timeout=args.timeout,
        )

        output = nl2sparql.format(result, args.format)
        print(output)


if __name__ == "__main__":
    main()
