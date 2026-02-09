"""SPARQL-based analysis tools exposed as MCP tools.

Wraps ``analysis_tools.gene_paths``, ``analysis_tools.gene_neighborhood``,
and ``analysis_tools.drug_disease`` from ``scripts/demos/``.
"""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from okn_wobd.mcp_server.server import redirect_prints


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
        try:
            with redirect_prints():
                from analysis_tools import GeneDiseasePathFinder

                finder = GeneDiseasePathFinder(verbose=False)
                connections = finder.find_all_connections(gene_symbol.upper())
        except Exception as e:
            return {"error": str(e), "gene": gene_symbol}

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

        try:
            with redirect_prints():
                from analysis_tools import GeneNeighborhoodQuery

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
            return {"error": f"Gene not found: {gene_symbol or ncbi_gene_id}"}
        except Exception as e:
            return {"error": str(e), "gene": gene_symbol or ncbi_gene_id}

        return neighborhood.to_dict()

    @mcp.tool()
    def drug_disease_opposing_expression(
        drug_direction: str = "down",
        disease_direction: str = "up",
        drug_fc_threshold: float = 2.0,
        disease_fc_threshold: float = 1.5,
        pvalue_threshold: float = 0.05,
        limit: int = 500,
        max_results: int = 50,
    ) -> dict:
        """Find genes with opposing expression between drug treatment and disease.

        Identifies potential therapeutic mechanisms by finding genes where a drug
        has the opposite effect compared to a disease.  Two main patterns:

        1. Drug DOWN + Disease UP: drug suppresses a pathologically elevated gene.
        2. Drug UP + Disease DOWN: drug activates a pathologically suppressed gene.

        Queries the Gene Expression Atlas (GXA) data in FRINK via SPARQL.

        Typical runtime: 15-45 seconds (two SPARQL queries + Python filtering).
        Increase ``limit`` for more comprehensive results at the cost of speed.

        Args:
            drug_direction: Direction of drug effect ("down" or "up").
            disease_direction: Direction of disease effect ("up" or "down").
            drug_fc_threshold: Absolute log2 fold-change threshold for drug effect.
            disease_fc_threshold: Absolute log2 fold-change threshold for disease.
            pvalue_threshold: Adjusted p-value significance threshold.
            limit: Max drug-gene pairs to query from SPARQL (default 500).
            max_results: Max results to return (default 50, sorted by disease FC).

        Returns:
            Dict with ``results`` (top hits), ``drug_label``, ``disease_label``,
            and ``summary`` statistics.
        """
        if drug_direction not in ("up", "down"):
            return {"error": "drug_direction must be 'up' or 'down'."}
        if disease_direction not in ("up", "down"):
            return {"error": "disease_direction must be 'up' or 'down'."}

        try:
            with redirect_prints():
                from analysis_tools import find_drug_disease_genes

                results, drug_label, disease_label = find_drug_disease_genes(
                    drug_direction=drug_direction,
                    disease_direction=disease_direction,
                    drug_fc_threshold=drug_fc_threshold,
                    disease_fc_threshold=disease_fc_threshold,
                    pvalue_threshold=pvalue_threshold,
                    limit=limit,
                )
        except Exception as e:
            return {"error": str(e)}

        # Summarise
        unique_genes = len({r["gene"] for r in results})
        unique_diseases = len({r["disease"] for r in results})
        unique_drugs = len({r.get("drug_name") or r.get("drug_test_group") for r in results})

        return {
            "drug_label": drug_label,
            "disease_label": disease_label,
            "total_combinations": len(results),
            "results": results[:max_results],
            "summary": {
                "unique_genes": unique_genes,
                "unique_diseases": unique_diseases,
                "unique_drugs": unique_drugs,
            },
        }
