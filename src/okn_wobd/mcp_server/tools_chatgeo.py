"""ChatGEO / ARCHS4-based tools exposed as MCP tools.

Wraps ``chatgeo.cli.run_analysis``, ``chatgeo.sample_finder.SampleFinder``,
and ``chatgeo.enrichment_analyzer.GProfilerBackend`` from ``scripts/demos/``.

Long-running analyses (e.g. DESeq2) are dispatched to a background thread
and polled via the ``get_analysis_result`` tool, keeping individual MCP
tool calls within the ~60-second client timeout.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from pathlib import Path
from typing import List, Optional

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
# Background job store
# ---------------------------------------------------------------------------

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()

# Methods that are fast enough to run synchronously (~20-40s)
_FAST_METHODS = {"mann-whitney", "mann_whitney_u", "welch-t", "welch_t"}


def _run_de_background(job_id: str, kwargs: dict) -> None:
    """Run differential expression in a background thread."""
    try:
        with redirect_prints():
            from chatgeo.cli import run_analysis

            result = run_analysis(**kwargs)
    except SystemExit as e:
        with _jobs_lock:
            _jobs[job_id] = {
                "status": "error",
                "result": {
                    "error": f"Analysis failed (exit code {e.code}). "
                    "Common causes: no matching samples found, ARCHS4 data issue."
                },
                "finished_at": time.time(),
            }
        return
    except Exception as e:
        with _jobs_lock:
            _jobs[job_id] = {
                "status": "error",
                "result": {"error": str(e)},
                "finished_at": time.time(),
            }
        return

    if result is None:
        result = {"error": "Analysis returned no results."}

    with _jobs_lock:
        _jobs[job_id] = {
            "status": "completed",
            "result": result,
            "finished_at": time.time(),
        }


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
        method: str = "mann-whitney",
        fdr_threshold: float = 0.01,
        log2fc_threshold: float = 2.0,
        max_test_samples: int = 100,
        max_control_samples: int = 100,
    ) -> dict:
        """Run differential expression analysis for a disease condition.

        Uses ARCHS4 bulk RNA-seq data to find test/control samples, then
        runs statistical testing and g:Profiler enrichment.

        The ``query`` is a natural-language string like
        "psoriasis in skin tissue". You can also provide explicit ``disease``
        and/or ``tissue`` overrides.

        **Requires** the ARCHS4_DATA_DIR environment variable to be set.

        **Method and runtime:**
        - ``mann-whitney`` (default): fast (~20-40s), runs synchronously,
          returns results directly.
        - ``welch-t``: fast (~20-40s), runs synchronously.
        - ``deseq2``: rigorous but slow (2-5 min). Runs in the **background**
          and returns a ``job_id`` immediately.  Call ``get_analysis_result``
          with the ``job_id`` to poll for results.

        Consider calling ``find_samples`` first to verify data availability.

        Args:
            query: Natural language query (e.g. "psoriasis in skin tissue").
            disease: Override parsed disease term.
            tissue: Override or specify tissue constraint.
            species: Species ("human", "mouse", or "both").
            method: DE method — "mann-whitney" (default, fast) or "deseq2"
                    (rigorous, runs in background) or "welch-t" (fast).
            fdr_threshold: FDR significance threshold (default 0.01).
            log2fc_threshold: Log2 fold-change threshold (default 2.0).
            max_test_samples: Max test samples (default 100).
            max_control_samples: Max control samples (default 100).

        Returns:
            For fast methods: dict with ``sample_discovery``, ``de_results``,
            ``enrichment``, and ``provenance``.
            For deseq2: dict with ``job_id`` and ``status`` ("running") —
            poll with ``get_analysis_result``.
        """
        err = _check_archs4()
        if err:
            return {"error": err}

        # Parse query
        try:
            with redirect_prints():
                from chatgeo.cli import parse_query
                parsed_disease, parsed_tissue = parse_query(query)
        except Exception as e:
            return {"error": f"Query parse failed: {e}"}

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

        run_kwargs = dict(
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

        # Fast methods: run synchronously
        if method in _FAST_METHODS or mapped_method in _FAST_METHODS:
            try:
                with redirect_prints():
                    from chatgeo.cli import run_analysis
                    result = run_analysis(**run_kwargs)
            except SystemExit as e:
                return {"error": f"Analysis failed (exit code {e.code}). "
                        "Common causes: no matching samples found, ARCHS4 data issue."}
            except Exception as e:
                return {"error": str(e)}

            if result is None:
                return {"error": "Analysis returned no results."}
            return result

        # Slow methods (deseq2): run in background
        job_id = str(uuid.uuid4())[:8]
        with _jobs_lock:
            _jobs[job_id] = {
                "status": "running",
                "result": None,
                "started_at": time.time(),
                "query": query,
                "method": method,
            }

        thread = threading.Thread(
            target=_run_de_background,
            args=(job_id, run_kwargs),
            daemon=True,
        )
        thread.start()

        return {
            "job_id": job_id,
            "status": "running",
            "message": (
                f"DESeq2 analysis started in background (job {job_id}). "
                f"This typically takes 2-5 minutes. "
                f"Call get_analysis_result(job_id='{job_id}') to check progress."
            ),
        }

    @mcp.tool()
    def get_analysis_result(job_id: str) -> dict:
        """Poll for the result of a background differential expression analysis.

        When ``differential_expression`` is called with ``method='deseq2'``,
        it returns a ``job_id`` and runs in the background. Use this tool
        to check whether the job has completed and retrieve its results.

        Typical DESeq2 runtime is 2-5 minutes. Poll every 30-60 seconds.

        Args:
            job_id: The job ID returned by ``differential_expression``.

        Returns:
            If still running: ``{"status": "running", "elapsed_seconds": ...}``
            If completed: ``{"status": "completed", "result": {...}}``
            If errored: ``{"status": "error", "result": {"error": ...}}``
        """
        with _jobs_lock:
            job = _jobs.get(job_id)

        if job is None:
            return {"error": f"No job found with id '{job_id}'."}

        if job["status"] == "running":
            elapsed = time.time() - job.get("started_at", time.time())
            return {
                "job_id": job_id,
                "status": "running",
                "elapsed_seconds": round(elapsed, 1),
                "message": "Analysis still running. Poll again in 30-60 seconds.",
            }

        # completed or error
        return {
            "job_id": job_id,
            "status": job["status"],
            "result": job["result"],
        }

    @mcp.tool()
    def find_samples(
        disease_term: str,
        tissue: Optional[str] = None,
        max_test_samples: int = 100,
        max_control_samples: int = 100,
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
            max_test_samples: Maximum test samples (default 100).
            max_control_samples: Maximum control samples (default 100).

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
