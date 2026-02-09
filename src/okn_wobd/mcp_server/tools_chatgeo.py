"""ChatGEO / ARCHS4-based tools exposed as MCP tools.

Wraps ``chatgeo.cli.run_analysis``, ``chatgeo.sample_finder.SampleFinder``,
and ``chatgeo.enrichment_analyzer.GProfilerBackend`` from ``scripts/demos/``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Literal, Optional

from mcp.server.fastmcp import FastMCP

from okn_wobd.mcp_server.server import redirect_prints


# ---------------------------------------------------------------------------
# ARCHS4 availability check
# ---------------------------------------------------------------------------

def _check_archs4() -> Optional[str]:
    """Return an error message if ARCHS4 data is unavailable, else None."""
    data_dir = os.environ.get("ARCHS4_DATA_DIR")
    if not data_dir:
        return (
            "ARCHS4_DATA_DIR environment variable is not set. "
            "Set it to the directory containing ARCHS4 HDF5 files."
        )
    if not Path(data_dir).is_dir():
        return f"ARCHS4_DATA_DIR ({data_dir}) does not exist or is not a directory."
    return None


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

def register_tools(mcp: FastMCP) -> None:
    """Register ChatGEO tools on *mcp*."""

    @mcp.tool()
    def differential_expression(
        query: str,
        disease: Optional[str] = None,
        tissue: Optional[str] = None,
        species: str = "human",
        method: str = "deseq2",
        fdr_threshold: float = 0.01,
        log2fc_threshold: float = 2.0,
        max_test_samples: int = 200,
        max_control_samples: int = 200,
    ) -> dict:
        """Run differential expression analysis for a disease condition.

        Uses ARCHS4 bulk RNA-seq data to find test/control samples, then
        runs DESeq2 (or other methods) and g:Profiler enrichment.

        The ``query`` is a natural-language string like
        "psoriasis in skin tissue". You can also provide explicit ``disease``
        and/or ``tissue`` overrides.

        **Requires** the ARCHS4_DATA_DIR environment variable to be set.

        **IMPORTANT — this is a long-running tool.** Typical runtime is
        60-120 seconds depending on sample counts. Consider calling
        ``find_samples`` first to verify data availability and sample counts
        before committing to the full analysis.

        Args:
            query: Natural language query (e.g. "psoriasis in skin tissue").
            disease: Override parsed disease term.
            tissue: Override or specify tissue constraint.
            species: Species ("human", "mouse", or "both").
            method: DE method ("deseq2", "mann-whitney", "welch-t").
            fdr_threshold: FDR significance threshold (default 0.01).
            log2fc_threshold: Log2 fold-change threshold (default 2.0).
            max_test_samples: Max test samples (default 200).
            max_control_samples: Max control samples (default 200).

        Returns:
            Dict with ``sample_discovery``, ``de_results`` (significant genes),
            ``enrichment`` (GO/KEGG/Reactome), and ``provenance``.
        """
        err = _check_archs4()
        if err:
            return {"error": err}

        try:
            with redirect_prints():
                from chatgeo.cli import parse_query, run_analysis

                parsed_disease, parsed_tissue = parse_query(query)
                if disease:
                    parsed_disease = disease
                if tissue:
                    parsed_tissue = tissue

                method_map = {
                    "deseq2": "deseq2",
                    "mann-whitney": "mann_whitney_u",
                    "welch-t": "welch_t",
                }
                mapped_method = method_map.get(method, method)

                result = run_analysis(
                    disease=parsed_disease,
                    tissue=parsed_tissue,
                    species=species,
                    method=mapped_method,
                    fdr_threshold=fdr_threshold,
                    log2fc_threshold=log2fc_threshold,
                    max_test_samples=max_test_samples,
                    max_control_samples=max_control_samples,
                    interpret=False,
                    verbose=False,
                )
        except SystemExit as e:
            # run_analysis calls sys.exit(1) on certain errors
            return {"error": f"Analysis failed (exit code {e.code}). "
                    "Common causes: no matching samples found, ARCHS4 data issue."}
        except Exception as e:
            return {"error": str(e)}

        if result is None:
            return {"error": "Analysis returned no results."}

        return result

    @mcp.tool()
    def find_samples(
        disease_term: str,
        tissue: Optional[str] = None,
        max_test_samples: int = 200,
        max_control_samples: int = 200,
    ) -> dict:
        """Find ARCHS4 test and control samples for a disease condition.

        Searches ARCHS4 metadata for samples matching the disease term and
        healthy controls. This is a fast operation (~5-10 seconds) and is
        recommended before calling ``differential_expression`` to verify
        data availability and sample counts.

        **Requires** the ARCHS4_DATA_DIR environment variable to be set.

        Args:
            disease_term: Disease or condition (e.g. "psoriasis").
            tissue: Optional tissue constraint (e.g. "skin").
            max_test_samples: Maximum test samples (default 200).
            max_control_samples: Maximum control samples (default 200).

        Returns:
            Dict with sample counts, GEO study accessions, and sample IDs.
        """
        err = _check_archs4()
        if err:
            return {"error": err}

        try:
            with redirect_prints():
                from chatgeo.query_builder import PatternQueryStrategy, QueryBuilder
                from chatgeo.sample_finder import SampleFinder

                data_dir = os.environ["ARCHS4_DATA_DIR"]
                query_builder = QueryBuilder(strategy=PatternQueryStrategy())
                finder = SampleFinder(data_dir=data_dir, query_builder=query_builder)

                pooled = finder.find_pooled_samples(
                    disease_term=disease_term,
                    tissue=tissue,
                    max_test_samples=max_test_samples,
                    max_control_samples=max_control_samples,
                )
        except Exception as e:
            return {"error": str(e)}

        # Extract study IDs from sample metadata
        test_studies = []
        control_studies = []
        if not pooled.test_samples.empty and "series_id" in pooled.test_samples.columns:
            test_studies = sorted(set(pooled.test_samples["series_id"].tolist()))
        if not pooled.control_samples.empty and "series_id" in pooled.control_samples.columns:
            control_studies = sorted(set(pooled.control_samples["series_id"].tolist()))

        return {
            "disease_term": disease_term,
            "tissue": tissue,
            "n_test_samples": pooled.n_test,
            "n_control_samples": pooled.n_control,
            "total_test_found": pooled.total_test_found,
            "total_control_found": pooled.total_control_found,
            "test_query": pooled.test_query,
            "control_query": pooled.control_query,
            "test_studies": test_studies,
            "control_studies": control_studies,
            "test_sample_ids": pooled.test_ids[:50],
            "control_sample_ids": pooled.control_ids[:50],
            "overlap_removed": pooled.overlap_removed,
        }

    @mcp.tool()
    def enrichment_analysis(
        gene_list: List[str],
        organism: str = "hsapiens",
        sources: Optional[List[str]] = None,
        threshold: float = 0.05,
    ) -> dict:
        """Run gene set enrichment analysis using g:Profiler.

        Performs over-representation analysis (ORA) for GO terms, KEGG pathways,
        and Reactome pathways. Does **not** require ARCHS4 data.

        Typical runtime: 2-5 seconds.

        Args:
            gene_list: List of gene symbols (e.g. ["TP53", "BRCA1", "MYC"]).
            organism: Organism identifier (default "hsapiens").
            sources: Data sources (default: GO:BP, GO:CC, GO:MF, KEGG, REAC).
            threshold: P-value significance threshold (default 0.05).

        Returns:
            Dict with enriched terms grouped by source, plus mapping stats.
        """
        if not gene_list:
            return {"error": "gene_list must not be empty."}

        if sources is None:
            sources = ["GO:BP", "GO:CC", "GO:MF", "KEGG", "REAC"]

        try:
            with redirect_prints():
                from chatgeo.enrichment_analyzer import GProfilerBackend

                backend = GProfilerBackend()
                terms, n_mapped = backend.analyze(
                    genes=gene_list,
                    organism=organism,
                    sources=sources,
                    threshold=threshold,
                    correction="g_SCS",
                )
        except ImportError as e:
            return {"error": f"Missing dependency: {e}. Install with: pip install gprofiler-official"}
        except Exception as e:
            return {"error": str(e)}

        # Group results by source
        by_source: dict[str, list] = {}
        for t in terms:
            entry = {
                "term_id": t.term_id,
                "term_name": t.term_name,
                "p_value": t.pvalue_adjusted,
                "intersection_size": t.intersection_size,
                "term_size": t.term_size,
                "precision": t.precision,
                "recall": t.recall,
                "genes": t.genes,
            }
            by_source.setdefault(t.source, []).append(entry)

        return {
            "input_genes": len(gene_list),
            "genes_mapped": n_mapped,
            "total_terms": len(terms),
            "by_source": by_source,
        }
