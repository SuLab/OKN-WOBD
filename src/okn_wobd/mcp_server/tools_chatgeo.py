"""ChatGEO / ARCHS4-based tools exposed as MCP tools.

Wraps ``chatgeo.cli.run_analysis``, ``chatgeo.sample_finder.SampleFinder``,
and ``chatgeo.enrichment_analyzer.GProfilerBackend`` from ``scripts/demos/``.

All analyses are dispatched to a background thread and polled via the
``get_analysis_result`` tool, keeping individual MCP tool calls within
the ~60-second client timeout.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import List, Optional

from mcp.server.fastmcp import FastMCP

from okn_wobd.mcp_server.server import redirect_prints

logger = logging.getLogger(__name__)


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


def _run_de_background(job_id: str, kwargs: dict) -> None:
    """Run differential expression in a background thread."""
    logger.info("Background job %s started (disease=%s, method=%s)",
                job_id, kwargs.get("disease"), kwargs.get("method"))
    start = time.time()
    try:
        with redirect_prints():
            from chatgeo.cli import run_analysis

            result = run_analysis(**kwargs)
    except SystemExit as e:
        logger.error("Background job %s failed with SystemExit(%s)\n%s",
                      job_id, e.code, traceback.format_exc())
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
        logger.error("Background job %s failed: %s\n%s",
                      job_id, e, traceback.format_exc())
        with _jobs_lock:
            _jobs[job_id] = {
                "status": "error",
                "result": {"error": str(e)},
                "finished_at": time.time(),
            }
        return

    elapsed = time.time() - start
    if result is None:
        logger.warning("Background job %s returned None after %.1fs", job_id, elapsed)
        result = {"error": "Analysis returned no results."}
    else:
        n_genes = result.get("n_significant", "?")
        logger.info("Background job %s completed in %.1fs (%s significant genes)",
                     job_id, elapsed, n_genes)

    with _jobs_lock:
        _jobs[job_id] = {
            "status": "completed",
            "result": result,
            "finished_at": time.time(),
        }


def _build_study_breakdown(test_df, control_df) -> dict:
    """Build study-level breakdown from test/control DataFrames."""
    import pandas as pd

    test_by_study: dict[str, int] = {}
    control_by_study: dict[str, int] = {}
    platform_counts: dict[str, int] = {}

    for label, df, counts in [
        ("test", test_df, test_by_study),
        ("control", control_df, control_by_study),
    ]:
        if df is None or df.empty or "series_id" not in df.columns:
            continue
        for sid in df["series_id"].dropna():
            for part in str(sid).split(","):
                part = part.strip()
                if part.startswith("GSE"):
                    counts[part] = counts.get(part, 0) + 1

    # Platform distribution
    for df in [test_df, control_df]:
        if df is not None and not df.empty and "platform_id" in df.columns:
            for plat in df["platform_id"].dropna():
                plat = str(plat)
                platform_counts[plat] = platform_counts.get(plat, 0) + 1

    all_studies = set(test_by_study) | set(control_by_study)
    studies_with_test = len(test_by_study)
    studies_with_control = len(control_by_study)
    studies_with_both = len(set(test_by_study) & set(control_by_study))

    # Top studies by total samples
    top_studies = []
    for sid in all_studies:
        n_test = test_by_study.get(sid, 0)
        n_control = control_by_study.get(sid, 0)
        top_studies.append({
            "study_id": sid,
            "n_test": n_test,
            "n_control": n_control,
        })
    top_studies.sort(key=lambda s: s["n_test"] + s["n_control"], reverse=True)

    return {
        "studies_with_test": studies_with_test,
        "studies_with_control": studies_with_control,
        "studies_with_both": studies_with_both,
        "top_studies": top_studies[:20],
        "platform_distribution": platform_counts,
        "recommendation": "study-matched" if studies_with_both >= 3 else "pooled",
    }


def _run_get_sample_metadata_background(
    job_id: str,
    disease_term: str,
    tissue: Optional[str],
    max_samples: int,
    use_ontology: bool,
) -> None:
    """Run sample metadata lookup in a background thread."""
    logger.info("Background get_sample_metadata job %s started", job_id)
    start = time.time()
    try:
        with redirect_prints():
            from chatgeo.query_builder import PatternQueryStrategy, QueryBuilder
            from chatgeo.sample_finder import SampleFinder

            data_dir = os.environ["ARCHS4_DATA_DIR"]
            query_builder = QueryBuilder(strategy=PatternQueryStrategy())
            finder = SampleFinder(data_dir=data_dir, query_builder=query_builder)

            # Find samples (no size limit — we just want counts)
            pooled = None
            if use_ontology:
                try:
                    pooled = finder.find_pooled_samples_ontology(
                        disease_term=disease_term,
                        tissue=tissue,
                        max_test_samples=max_samples,
                        max_control_samples=max_samples,
                        keyword_fallback=True,
                    )
                except Exception:
                    pooled = None
                if pooled is not None and pooled.n_test == 0:
                    pooled = None

            if pooled is None:
                pooled = finder.find_pooled_samples(
                    disease_term=disease_term,
                    tissue=tissue,
                    max_test_samples=max_samples,
                    max_control_samples=max_samples,
                )

            study_breakdown = _build_study_breakdown(
                pooled.test_samples, pooled.control_samples
            )

            result = {
                "disease_term": disease_term,
                "tissue": tissue,
                "n_test_samples": pooled.n_test,
                "n_control_samples": pooled.n_control,
                "total_test_found": pooled.total_test_found,
                "total_control_found": pooled.total_control_found,
                "study_breakdown": study_breakdown,
                "recommendation": study_breakdown["recommendation"],
                "recommendation_reason": (
                    f"{study_breakdown['studies_with_both']} studies have both test+control; "
                    f"{'study-matched meta-analysis recommended' if study_breakdown['studies_with_both'] >= 3 else 'pooled mode recommended (fewer than 3 matched studies)'}"
                ),
            }

    except SystemExit as e:
        with _jobs_lock:
            _jobs[job_id] = {
                "status": "error",
                "result": {"error": f"Sample metadata lookup failed (exit code {e.code})."},
                "finished_at": time.time(),
            }
        return
    except Exception as e:
        logger.error("get_sample_metadata job %s failed: %s", job_id, e)
        with _jobs_lock:
            _jobs[job_id] = {
                "status": "error",
                "result": {"error": str(e)},
                "finished_at": time.time(),
            }
        return

    elapsed = time.time() - start
    logger.info("get_sample_metadata job %s completed in %.1fs", job_id, elapsed)

    with _jobs_lock:
        _jobs[job_id] = {
            "status": "completed",
            "result": result,
            "finished_at": time.time(),
        }


def _run_find_samples_background(
    job_id: str,
    disease_term: str,
    tissue: Optional[str],
    max_test_samples: int,
    max_control_samples: int,
    use_ontology: bool,
) -> None:
    """Run sample search in a background thread."""
    logger.info("Background find_samples job %s started (disease=%s, ontology=%s)",
                job_id, disease_term, use_ontology)
    start = time.time()
    try:
        with redirect_prints():
            from chatgeo.query_builder import PatternQueryStrategy, QueryBuilder
            from chatgeo.sample_finder import SampleFinder

            data_dir = os.environ["ARCHS4_DATA_DIR"]
            query_builder = QueryBuilder(strategy=PatternQueryStrategy())
            finder = SampleFinder(data_dir=data_dir, query_builder=query_builder)

            pooled = None
            if use_ontology:
                try:
                    pooled = finder.find_pooled_samples_ontology(
                        disease_term=disease_term,
                        tissue=tissue,
                        max_test_samples=max_test_samples,
                        max_control_samples=max_control_samples,
                        keyword_fallback=True,
                    )
                except Exception as e:
                    logger.warning("Ontology search failed: %s — falling back to keyword", e)
                    pooled = None

                if pooled is not None and pooled.n_test == 0:
                    pooled = None

            if pooled is None:
                pooled = finder.find_pooled_samples(
                    disease_term=disease_term,
                    tissue=tissue,
                    max_test_samples=max_test_samples,
                    max_control_samples=max_control_samples,
                )
    except SystemExit as e:
        logger.error("find_samples job %s SystemExit(%s)\n%s",
                      job_id, e.code, traceback.format_exc())
        with _jobs_lock:
            _jobs[job_id] = {
                "status": "error",
                "result": {
                    "error": f"Sample search failed (exit code {e.code}). "
                    "Common causes: no matching samples found, ARCHS4 data issue."
                },
                "finished_at": time.time(),
            }
        return
    except Exception as e:
        logger.error("find_samples job %s failed: %s\n%s",
                      job_id, e, traceback.format_exc())
        with _jobs_lock:
            _jobs[job_id] = {
                "status": "error",
                "result": {"error": str(e)},
                "finished_at": time.time(),
            }
        return

    elapsed = time.time() - start

    # Build result dict
    test_studies = []
    control_studies = []
    if not pooled.test_samples.empty and "series_id" in pooled.test_samples.columns:
        test_studies = sorted(set(pooled.test_samples["series_id"].tolist()))
    if not pooled.control_samples.empty and "series_id" in pooled.control_samples.columns:
        control_studies = sorted(set(pooled.control_samples["series_id"].tolist()))

    # Build study breakdown
    study_breakdown = _build_study_breakdown(
        pooled.test_samples, pooled.control_samples
    )

    result = {
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
        "study_breakdown": study_breakdown,
    }

    ont_stats = (pooled.filtering_stats or {}).get("ontology_discovery")
    if ont_stats:
        result["ontology_discovery"] = ont_stats

    logger.info("find_samples job %s completed in %.1fs (%d test, %d control)",
                 job_id, elapsed, pooled.n_test, pooled.n_control)

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
        mode: str = "auto",
        meta_method: str = "stouffer",
        min_studies: int = 3,
    ) -> dict:
        """Run differential expression analysis for a disease condition.

        Uses ARCHS4 bulk RNA-seq data to find test/control samples, then
        runs statistical testing and g:Profiler enrichment.

        The ``query`` is a natural-language string like
        "psoriasis in skin tissue". You can also provide explicit ``disease``
        and/or ``tissue`` overrides.

        **Requires** the ARCHS4_DATA_DIR environment variable to be set.

        **All methods run in the background** and return a ``job_id``
        immediately. Call ``get_analysis_result`` with the ``job_id`` to
        poll for results.

        Analysis modes:
        - ``auto`` (default): Tries study-matched meta-analysis first
          (per-study DE + Stouffer/Fisher combination). Falls back to
          study-prioritized pooling, then basic pooling.
        - ``study-matched``: Per-study DE + meta-analysis only.
        - ``pooled``: Cross-study pooling (original behavior).

        Consider calling ``get_sample_metadata`` first to check study
        availability and choose the best mode.

        Args:
            query: Natural language query (e.g. "psoriasis in skin tissue").
            disease: Override parsed disease term.
            tissue: Override or specify tissue constraint.
            species: Species ("human", "mouse", or "both").
            method: DE method — "mann-whitney" (default), "welch-t", or
                    "deseq2" (rigorous but slower).
            fdr_threshold: FDR significance threshold (default 0.01).
            log2fc_threshold: Log2 fold-change threshold (default 2.0).
            max_test_samples: Max test samples (default 100).
            max_control_samples: Max control samples (default 100).
            mode: Analysis mode — "auto" (default), "pooled", "study-matched".
            meta_method: Meta-analysis method — "stouffer" (default) or "fisher".
            min_studies: Minimum matched studies for study-matched mode (default 3).

        Returns:
            dict with ``job_id`` and ``status`` ("running") — poll with
            ``get_analysis_result``.
        """
        logger.info("differential_expression called: query=%r, method=%s", query, method)
        err = _check_archs4()
        if err:
            return {"error": err}

        # Parse query
        try:
            with redirect_prints():
                from chatgeo.cli import parse_query
                parsed_disease, parsed_tissue = parse_query(query)
        except Exception as e:
            logger.error("Query parse failed: %s", e)
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
            mode=mode,
            meta_method=meta_method,
            min_studies=min_studies,
        )

        # Dispatch all methods to background thread to avoid MCP timeouts
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
        logger.info("Dispatched background job %s (disease=%s, tissue=%s, method=%s)",
                     job_id, parsed_disease, parsed_tissue, method)

        return {
            "job_id": job_id,
            "status": "running",
            "message": (
                f"Analysis started in background (job {job_id}, method={method}). "
                f"Call get_analysis_result(job_id='{job_id}') to check progress."
            ),
        }

    @mcp.tool()
    def get_analysis_result(job_id: str) -> dict:
        """Poll for the result of a background job.

        Both ``differential_expression`` and ``find_samples`` run in the
        background and return a ``job_id``. Use this tool to check whether
        the job has completed and retrieve its results.

        Poll every 30-60 seconds. Typical runtime:
        - ``find_samples``: 30-120s (longer with ontology search)
        - ``differential_expression``: 30-60s (mann-whitney/welch-t),
          2-5 min (deseq2)

        Args:
            job_id: The job ID returned by ``differential_expression``
                or ``find_samples``.

        Returns:
            If still running: ``{"status": "running", "elapsed_seconds": ...}``
            If completed: ``{"status": "completed", "result": {...}}``
            If errored: ``{"status": "error", "result": {"error": ...}}``
        """
        logger.debug("get_analysis_result polled for job %s", job_id)
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
        use_ontology: bool = True,
    ) -> dict:
        """Find ARCHS4 test and control samples for a disease condition.

        Searches ARCHS4 metadata for samples matching the disease term and
        healthy controls. When ``use_ontology`` is True (default), also
        discovers studies via MONDO ontology annotations in NDE, dramatically
        improving recall for well-annotated diseases.

        **Runs in the background** and returns a ``job_id`` immediately.
        Call ``get_analysis_result`` with the ``job_id`` to poll for results.
        Typical runtime: 30-120 seconds depending on disease and ontology mode.

        **Requires** the ARCHS4_DATA_DIR environment variable to be set.

        Args:
            disease_term: Disease or condition (e.g. "psoriasis").
            tissue: Optional tissue constraint (e.g. "skin").
            max_test_samples: Maximum test samples (default 100).
            max_control_samples: Maximum control samples (default 100).
            use_ontology: Use ontology-enhanced search (default True).
                Set to False for keyword-only search.

        Returns:
            Dict with ``job_id`` and ``status`` ("running") — poll with
            ``get_analysis_result``.
        """
        logger.info("find_samples called: disease_term=%r, tissue=%r, use_ontology=%s",
                     disease_term, tissue, use_ontology)
        err = _check_archs4()
        if err:
            return {"error": err}

        job_id = str(uuid.uuid4())[:8]
        with _jobs_lock:
            _jobs[job_id] = {
                "status": "running",
                "result": None,
                "started_at": time.time(),
                "query": f"find_samples: {disease_term}",
                "method": "ontology" if use_ontology else "keyword",
            }

        thread = threading.Thread(
            target=_run_find_samples_background,
            args=(job_id, disease_term, tissue,
                  max_test_samples, max_control_samples, use_ontology),
            daemon=True,
        )
        thread.start()
        logger.info("Dispatched find_samples job %s (disease=%s, tissue=%s, ontology=%s)",
                     job_id, disease_term, tissue, use_ontology)

        return {
            "job_id": job_id,
            "status": "running",
            "message": (
                f"Sample search started in background (job {job_id}). "
                f"Call get_analysis_result(job_id='{job_id}') to check progress."
            ),
        }

    @mcp.tool()
    def get_sample_metadata(
        disease_term: str,
        tissue: Optional[str] = None,
        max_samples: int = 500,
        use_ontology: bool = True,
    ) -> dict:
        """Get study-level sample metadata for planning DE analysis.

        Returns per-study sample counts, platform distribution, and a
        recommendation for which analysis mode to use. Use this **before**
        calling ``differential_expression`` to understand what data is
        available and choose the best mode.

        **Runs in the background** — poll with ``get_analysis_result``.

        **Requires** ARCHS4_DATA_DIR.

        Args:
            disease_term: Disease or condition (e.g. "psoriasis").
            tissue: Optional tissue constraint (e.g. "skin").
            max_samples: Maximum samples to consider (default 500).
            use_ontology: Use ontology-enhanced search (default True).

        Returns:
            Dict with ``job_id`` — poll with ``get_analysis_result``.
            Final result includes:
            - n_test_samples, n_control_samples
            - study_breakdown: per-study counts, platform distribution
            - recommendation: "study-matched" or "pooled"
            - recommendation_reason: explanation
        """
        logger.info("get_sample_metadata called: disease_term=%r, tissue=%r", disease_term, tissue)
        err = _check_archs4()
        if err:
            return {"error": err}

        job_id = str(uuid.uuid4())[:8]
        with _jobs_lock:
            _jobs[job_id] = {
                "status": "running",
                "result": None,
                "started_at": time.time(),
                "query": f"get_sample_metadata: {disease_term}",
                "method": "metadata",
            }

        thread = threading.Thread(
            target=_run_get_sample_metadata_background,
            args=(job_id, disease_term, tissue, max_samples, use_ontology),
            daemon=True,
        )
        thread.start()

        return {
            "job_id": job_id,
            "status": "running",
            "message": (
                f"Sample metadata lookup started (job {job_id}). "
                f"Call get_analysis_result(job_id='{job_id}') to check progress."
            ),
        }

    @mcp.tool()
    def resolve_disease_ontology(
        disease_name: str,
        expand: bool = True,
        max_terms: int = 50,
    ) -> dict:
        """Resolve a disease name to MONDO IDs and expand via ontology hierarchy.

        Useful for exploring what MONDO terms will be queried before running
        differential expression. Shows the resolved MONDO IDs, their labels,
        and the expanded set of subtypes.

        Does **not** require ARCHS4 data.

        Args:
            disease_name: Disease name (e.g. "atherosclerosis", "psoriasis").
            expand: Whether to expand via ontology hierarchy (default True).
            max_terms: Maximum terms in expansion (default 50).

        Returns:
            Dict with resolved MONDO IDs, labels, confidence, and expansion.
        """
        logger.info("resolve_disease_ontology called: disease_name=%r", disease_name)
        try:
            with redirect_prints():
                from clients.ontology import DiseaseOntologyClient

                client = DiseaseOntologyClient()
                resolution = client.resolve_disease(disease_name)

                result = {
                    "disease_name": disease_name,
                    "mondo_ids": resolution.mondo_ids,
                    "labels": resolution.labels,
                    "confidence": resolution.confidence,
                }

                if expand and resolution.top_id:
                    expansion = client.expand_mondo_id(
                        resolution.top_id, max_terms=max_terms
                    )
                    result["expansion"] = {
                        "root_id": expansion.root_id,
                        "n_terms": len(expansion.expanded_ids),
                        "expanded_ids": expansion.expanded_ids,
                        "labels": expansion.labels,
                    }

        except Exception as e:
            logger.error("resolve_disease_ontology failed: %s", e)
            return {"error": str(e)}

        return result

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
        logger.info("enrichment_analysis called: %d genes, organism=%s", len(gene_list), organism)
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
            logger.error("enrichment_analysis missing dependency: %s", e)
            return {"error": f"Missing dependency: {e}. Install with: pip install gprofiler-official"}
        except Exception as e:
            logger.error("enrichment_analysis failed: %s", e)
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

        logger.info("enrichment_analysis result: %d terms, %d/%d genes mapped",
                     len(terms), n_mapped, len(gene_list))
        return {
            "input_genes": len(gene_list),
            "genes_mapped": n_mapped,
            "total_terms": len(terms),
            "by_source": by_source,
        }
