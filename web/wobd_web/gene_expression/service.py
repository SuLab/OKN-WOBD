from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from wobd_web.sparql.client import SourceResult, execute_sparql
from wobd_web.sparql.endpoints import get_gene_expr_endpoint_for_mode


@runtime_checkable
class GeneExpressionService(Protocol):
    """Minimal interface for gene expression querying."""

    def query_sparql(self, sparql: str) -> SourceResult:  # pragma: no cover - protocol
        ...


@dataclass
class SparqlGeneExpressionService:
    """SPARQL-based implementation using a configured gene-expression endpoint."""

    mode: str = "sparql"

    def query_sparql(self, sparql: str) -> SourceResult:
        endpoint = get_gene_expr_endpoint_for_mode(self.mode)
        if endpoint is None:
            return SourceResult(
                rows=[],
                variables=[],
                row_count=0,
                elapsed_ms=0.0,
                endpoint_url="",
                status="error",
                error="Gene expression SPARQL endpoint not configured.",
            )
        return execute_sparql(endpoint.sparql_url, sparql)


@dataclass
class WebMCPGeneExpressionService:
    """
    Placeholder implementation for a Web-MCP-based gene expression adapter.

    For now this returns a not-enabled status until concrete Web-MCP integration
    details are available in configuration.
    """

    def query_sparql(self, sparql: str) -> SourceResult:
        return SourceResult(
            rows=[],
            variables=[],
            row_count=0,
            elapsed_ms=0.0,
            endpoint_url="",
            status="not_enabled",
            error="Web-MCP gene expression service is not configured.",
        )


@dataclass
class LocalGeneExpressionService:
    """
    Placeholder for a potential local/offline gene expression implementation.

    Currently this is a stub so that the router can expose a 'local' mode
    without requiring a concrete implementation.
    """

    def query_sparql(self, sparql: str) -> SourceResult:
        return SourceResult(
            rows=[],
            variables=[],
            row_count=0,
            elapsed_ms=0.0,
            endpoint_url="",
            status="not_implemented",
            error="Local gene expression service is not implemented.",
        )


def get_gene_expression_service(mode: str) -> GeneExpressionService:
    """
    Factory returning a GeneExpressionService for the requested mode.

    Modes:
    - "sparql": use configured SPARQL endpoint.
    - "web_mcp": placeholder Web-MCP adapter.
    - "local": placeholder local adapter.
    """

    if mode == "web_mcp":
        return WebMCPGeneExpressionService()
    if mode == "local":
        return LocalGeneExpressionService()
    return SparqlGeneExpressionService(mode="sparql")


__all__ = [
    "GeneExpressionService",
    "SparqlGeneExpressionService",
    "WebMCPGeneExpressionService",
    "LocalGeneExpressionService",
    "get_gene_expression_service",
]

