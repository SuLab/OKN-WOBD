"""SPARQL-based analysis tools exposed as MCP tools.

Wraps ``okn_wobd.analysis.gene_paths`` and ``okn_wobd.analysis.gene_neighborhood``.
"""

from __future__ import annotations

import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

from okn_wobd.mcp_server.server import redirect_prints

logger = logging.getLogger(__name__)


def register_tools(mcp: FastMCP) -> None:
    """Register all SPARQL-based analysis tools on *mcp*."""

    @mcp.tool()
    def gene_disease_paths(gene_symbol: str) -> dict:
        """Find connections between a gene and diseases across multiple knowledge graphs.

        Searches SPOKE-OKN, Wikidata, and Ubergraph for:
        - Direct gene-disease associations (markers, expression)
        - GO biological process pathways linking gene to disease
        - Genetic associations from Wikidata

        Typical runtime: 5-30 seconds (queries 3 remote SPARQL endpoints).

        Args:
            gene_symbol: Gene symbol (e.g. "SFRP2", "BRCA1", "TP53").

        Returns:
            Dict with ``gene``, ``total_connections``, ``connections`` list,
            and ``summary`` (counts by source and path type).
        """
        logger.info("gene_disease_paths called: gene=%s", gene_symbol)
        try:
            with redirect_prints():
                from okn_wobd.analysis import GeneDiseasePathFinder

                finder = GeneDiseasePathFinder(verbose=False)
                connections = finder.find_all_connections(gene_symbol.upper())
        except Exception as e:
            logger.error("gene_disease_paths failed for %s: %s", gene_symbol, e)
            return {"error": str(e), "gene": gene_symbol}

        logger.debug("gene_disease_paths result: %d connections for %s",
                      len(connections), gene_symbol)
        # Build summary
        by_source: dict[str, int] = {}
        by_path_type: dict[str, int] = {}
        for c in connections:
            by_source[c.source] = by_source.get(c.source, 0) + 1
            by_path_type[c.path_type] = by_path_type.get(c.path_type, 0) + 1

        return {
            "gene": gene_symbol.upper(),
            "total_connections": len(connections),
            "connections": [c.to_dict() for c in connections],
            "summary": {
                "by_source": by_source,
                "by_path_type": by_path_type,
            },
        }

    @mcp.tool()
    def gene_neighborhood(
        gene_symbol: Optional[str] = None,
        ncbi_gene_id: Optional[str] = None,
        limit: int = 10,
        timeout: int = 30,
    ) -> dict:
        """Query the immediate neighborhood of a gene across FRINK knowledge graphs.

        Returns related entities (diseases, proteins, pathways, compounds) from
        SPOKE-OKN, SPOKE-GeneLab, Wikidata, NDE, and BioBricks-AOPWiki.
        Queries run in parallel across graphs.

        Typical runtime: 5-20 seconds. Per-graph SPARQL timeout is controlled
        by the ``timeout`` parameter; graphs that exceed it are skipped with
        an error note.

        Provide either ``gene_symbol`` or ``ncbi_gene_id`` (at least one).

        Args:
            gene_symbol: Gene symbol (e.g. "CD19").
            ncbi_gene_id: NCBI Gene ID (e.g. "930").
            limit: Max entities per graph (default 10).
            timeout: Per-graph SPARQL timeout in seconds (default 30).

        Returns:
            Dict with gene info, per-graph entity lists, and total count.
        """
        if not gene_symbol and not ncbi_gene_id:
            return {"error": "Provide gene_symbol or ncbi_gene_id."}

        logger.info("gene_neighborhood called: gene=%s, ncbi_id=%s",
                     gene_symbol, ncbi_gene_id)
        try:
            with redirect_prints():
                from okn_wobd.analysis import GeneNeighborhoodQuery

                querier = GeneNeighborhoodQuery(timeout=timeout)
                neighborhood = querier.query_all(
                    symbol=gene_symbol.upper() if gene_symbol else None,
                    ncbi_id=ncbi_gene_id,
                    spoke_limit=limit,
                    wikidata_limit=limit,
                    nde_limit=limit,
                    biobricks_limit=limit,
                )
        except SystemExit:
            logger.error("gene_neighborhood: gene not found: %s",
                          gene_symbol or ncbi_gene_id)
            return {"error": f"Gene not found: {gene_symbol or ncbi_gene_id}"}
        except Exception as e:
            logger.error("gene_neighborhood failed for %s: %s",
                          gene_symbol or ncbi_gene_id, e)
            return {"error": str(e), "gene": gene_symbol or ncbi_gene_id}

        logger.debug("gene_neighborhood result: %s", gene_symbol or ncbi_gene_id)
        return neighborhood.to_dict()

