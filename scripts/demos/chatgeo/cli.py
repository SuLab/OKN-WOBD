"""
Command-line interface for ChatGEO differential expression analysis.

Provides a natural language interface for querying gene expression
differences between biological conditions.

Usage:
    python -m chatgeo.cli "psoriasis in skin tissue" --output results.json
    python -m chatgeo.cli "lung fibrosis" --tissue lung --species human
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Tuple

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env from demos directory
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass


def parse_query(query: str) -> Tuple[str, Optional[str]]:
    """
    Parse a natural language query into disease and tissue components.

    Examples:
        "psoriasis in skin tissue" -> ("psoriasis", "skin")
        "lung fibrosis" -> ("lung fibrosis", None)
        "breast cancer in mammary tissue" -> ("breast cancer", "mammary")

    Args:
        query: Natural language query string

    Returns:
        Tuple of (disease, tissue) where tissue may be None
    """
    query = query.strip().lower()

    # Pattern: "disease in tissue [tissue]"
    in_pattern = r"^(.+?)\s+in\s+(.+?)(?:\s+tissue)?$"
    match = re.match(in_pattern, query, re.IGNORECASE)

    if match:
        disease = match.group(1).strip()
        tissue = match.group(2).strip()
        # Remove trailing "tissue" if present
        tissue = re.sub(r"\s+tissue$", "", tissue)
        return disease, tissue

    # Pattern: "tissue disease" (e.g., "lung fibrosis")
    # Common tissue prefixes
    tissue_prefixes = [
        "lung", "liver", "kidney", "brain", "heart", "skin",
        "blood", "bone", "muscle", "intestine", "colon", "breast",
        "prostate", "ovarian", "pancreatic", "gastric", "hepatic",
        "renal", "cardiac", "pulmonary", "dermal", "neural",
    ]

    for tissue in tissue_prefixes:
        if query.startswith(tissue + " "):
            disease = query
            return disease, tissue

    # No tissue detected
    return query, None


def run_analysis(
    disease: str,
    tissue: Optional[str] = None,
    species: Literal["human", "mouse", "both"] = "human",
    method: str = "mann_whitney_u",
    fdr_threshold: float = 0.01,
    log2fc_threshold: float = 2.0,
    max_test_samples: int = 500,
    max_control_samples: int = 500,
    gene_filter_biotypes: Optional[str] = "protein_coding",
    include_mt_genes: bool = False,
    exclude_ribosomal: bool = False,
    min_library_size: int = 1_000_000,
    output_path: Optional[str] = None,
    output_format: Literal["summary", "json", "tsv"] = "summary",
    interpret: bool = True,
    verbose: bool = False,
    rdf: bool = False,
    rdf_format: str = "turtle",
    rdf_base_uri: str = "https://okn.wobd.org/",
    mode: Literal["auto", "pooled", "study-matched"] = "auto",
    meta_method: str = "stouffer",
    min_studies: int = 3,
    platform_filter: str = "none",
) -> Optional[Dict[str, Any]]:
    """
    Run differential expression analysis.

    Args:
        disease: Disease or condition to search
        tissue: Optional tissue constraint
        species: Species to analyze
        method: DE method (deseq2, mann-whitney, welch-t)
        fdr_threshold: FDR significance threshold
        log2fc_threshold: Log2 fold change threshold
        max_test_samples: Maximum test samples
        max_control_samples: Maximum control samples
        gene_filter_biotypes: Comma-separated biotypes to keep
        include_mt_genes: Keep MT- genes
        exclude_ribosomal: Remove RPS/RPL genes
        min_library_size: Min total counts per sample
        output_path: Output directory or file path
        output_format: Output format
        verbose: Print verbose output
        mode: Analysis mode — "auto" (tiered fallback), "pooled", "study-matched"
        meta_method: Meta-analysis method — "stouffer" or "fisher"
        min_studies: Minimum matched studies for study-matched mode
        platform_filter: Platform filtering — "none" or "majority"
    """
    # Import here to defer ARCHS4 initialization
    from clients.archs4 import ARCHS4Client

    from .de_analysis import DEConfig, DifferentialExpressionAnalyzer, GeneFilterConfig
    from .de_result import DEProvenance
    from .query_builder import (
        PatternQueryStrategy,
        QueryBuilder,
        build_query_spec,
        build_query_spec_fallback,
    )
    from .report_generator import ReportGenerator
    from .sample_finder import SampleFinder

    # Check for ARCHS4 data directory
    data_dir = os.environ.get("ARCHS4_DATA_DIR")
    if not data_dir:
        print("Error: ARCHS4_DATA_DIR environment variable not set")
        print("Set it to the directory containing ARCHS4 HDF5 files:")
        print("  export ARCHS4_DATA_DIR=/path/to/archs4/data")
        sys.exit(1)

    if verbose:
        print(f"Using ARCHS4 data from: {data_dir}")
        print(f"Disease: {disease}")
        print(f"Tissue: {tissue or 'any'}")
        print(f"Species: {species}")
        print(f"Method: {method}")
        if gene_filter_biotypes:
            print(f"Gene filter: {gene_filter_biotypes}")
        print()

    # Initialize components
    client = ARCHS4Client(organism="human", data_dir=data_dir)
    query_builder = QueryBuilder(strategy=PatternQueryStrategy())
    finder = SampleFinder(data_dir=data_dir, query_builder=query_builder)

    # Configure gene filtering
    if gene_filter_biotypes:
        biotype_set = frozenset(b.strip() for b in gene_filter_biotypes.split(","))
    else:
        biotype_set = None  # no biotype filtering

    gene_filter = GeneFilterConfig(
        biotypes=biotype_set,
        exclude_mt_genes=not include_mt_genes,
        exclude_ribosomal=exclude_ribosomal,
    )

    # Configure DE analysis
    config = DEConfig(
        method=method,
        fdr_threshold=fdr_threshold,
        log2fc_threshold=log2fc_threshold,
        min_library_size=min_library_size,
        gene_filter=gene_filter,
    )

    # Load biotype annotations for gene filtering
    gene_biotypes = client.get_gene_biotypes() if gene_filter.biotypes is not None else None

    analyzer = DifferentialExpressionAnalyzer(config=config, gene_biotypes=gene_biotypes)
    reporter = ReportGenerator()

    # Build structured query spec for tissue-aware filtering
    query_spec = None
    if tissue:
        try:
            query_spec = build_query_spec(disease, tissue)
            if verbose:
                print(f"Query strategy: LLM")
                print(f"  Disease terms: {query_spec.disease_terms}")
                print(f"  Tissue include: {query_spec.tissue_include}")
                print(f"  Tissue exclude: {query_spec.tissue_exclude}")
                print(f"  Reasoning: {query_spec.reasoning}")
                print()
        except Exception as e:
            if verbose:
                print(f"LLM query builder failed ({e}), using pattern fallback")
            query_spec = build_query_spec_fallback(disease, tissue)

    # =========================================================================
    # Mode-aware sample discovery + analysis
    # =========================================================================
    use_ontology = os.environ.get("CHATGEO_ONTOLOGY_SEARCH", "1") != "0"
    actual_mode = mode
    fallback_reason = None

    # --- Study-matched meta-analysis path ---
    meta_result = None
    if mode in ("auto", "study-matched"):
        if verbose:
            print(f"Attempting study-matched meta-analysis (min_studies={min_studies})...")

        study_matched = _find_study_matched(
            finder, disease, tissue, query_spec, use_ontology, verbose,
        )

        if study_matched is not None and study_matched.n_studies >= min_studies:
            actual_mode = "study-matched"
            if verbose:
                print(f"  Found {study_matched.n_studies} matched studies")
                for sp in study_matched.study_pairs[:5]:
                    print(f"    {sp.study_id}: {sp.n_test} test, {sp.n_control} control")
                if study_matched.n_studies > 5:
                    print(f"    ... and {study_matched.n_studies - 5} more")
                print()

            from .meta_analysis import MetaAnalyzer

            meta_analyzer = MetaAnalyzer(de_config=config, gene_biotypes=gene_biotypes)

            # Build provenance
            all_test_ids = [sid for sp in study_matched.study_pairs for sid in sp.test_ids]
            all_control_ids = [sid for sp in study_matched.study_pairs for sid in sp.control_ids]
            study_ids = [sp.study_id for sp in study_matched.study_pairs]

            provenance = DEProvenance.create(
                query_disease=disease,
                query_tissue=tissue,
                search_pattern_test=study_matched.test_query,
                search_pattern_control=study_matched.control_query,
                test_sample_ids=all_test_ids,
                control_sample_ids=all_control_ids,
                test_studies=study_ids,
                control_studies=study_ids,
                organisms=[species] if species != "both" else ["human", "mouse"],
                normalization_method=config.method,
                test_method=config.method,
                fdr_method="fdr_bh",
                pvalue_threshold=config.fdr_threshold,
                fdr_threshold=config.fdr_threshold,
                log2fc_threshold=config.log2fc_threshold,
                query_spec=query_spec.to_dict() if query_spec else None,
            )
            provenance.analysis_mode = "study-matched"
            provenance.study_matching = {
                "total_studies_with_test": study_matched.n_studies + study_matched.studies_with_test_only,
                "total_studies_with_control": study_matched.n_studies + study_matched.studies_with_control_only,
                "studies_with_both": study_matched.n_studies,
                "studies_used": [
                    {"study_id": sp.study_id, "n_test": sp.n_test, "n_control": sp.n_control}
                    for sp in study_matched.study_pairs
                ],
                "studies_excluded": {
                    "test_only": study_matched.studies_with_test_only,
                    "control_only": study_matched.studies_with_control_only,
                },
            }

            if verbose:
                print("Running per-study DE + meta-analysis...")

            meta_result = meta_analyzer.analyze_study_matched(
                study_matched, client, provenance,
                meta_method=meta_method,
                min_studies_per_gene=2,
            )

            if verbose:
                print(f"  Meta-analysis: {meta_result.genes_tested} genes tested, "
                      f"{meta_result.genes_significant} significant "
                      f"({meta_result.n_upregulated} up, {meta_result.n_downregulated} down)")
                print()

        else:
            n_found = study_matched.n_studies if study_matched else 0
            fallback_reason = f"only {n_found} matched studies, needed {min_studies}"
            if verbose:
                print(f"  Study-matched: {fallback_reason}")
            if mode == "study-matched":
                # Explicit mode requested but not enough studies
                print(f"Warning: {fallback_reason}; falling back to pooled")

    # --- Pooled path (either direct or fallback from auto) ---
    if meta_result is None:
        if mode == "auto" and fallback_reason:
            if verbose:
                print(f"Falling back from study-matched ({fallback_reason})")

        # Try study-prioritized pooled first (auto mode), then basic pooled
        pooled = None
        if mode == "auto":
            actual_mode = "study-prioritized-pooled"
            if verbose:
                print("Using study-prioritized pooled mode...")
            pooled = _find_pooled_samples(
                finder, disease, tissue, max_test_samples, max_control_samples,
                query_spec, use_ontology, verbose, study_prioritized=True,
                platform_filter=platform_filter,
            )
        if pooled is None or pooled.n_test == 0 or pooled.n_control == 0:
            actual_mode = "pooled"
            if mode == "auto" and verbose:
                print("Falling back to basic pooled mode...")
            pooled = _find_pooled_samples(
                finder, disease, tissue, max_test_samples, max_control_samples,
                query_spec, use_ontology, verbose, study_prioritized=False,
                platform_filter="none",
            )
            if mode == "auto" and fallback_reason:
                fallback_reason += "; study-prioritized also insufficient"

        if pooled.n_test == 0:
            print(f"Error: No test samples found for '{disease}'")
            sys.exit(1)
        if pooled.n_control == 0:
            print(f"Error: No control samples found")
            sys.exit(1)

        if verbose:
            print(f"Found {pooled.n_test} test samples, {pooled.n_control} control samples")
            print()

        # Get expression data
        if verbose:
            print("Retrieving expression data...")

        test_expr = client.get_expression_by_samples(pooled.test_ids)
        control_expr = client.get_expression_by_samples(pooled.control_ids)

        if test_expr.empty or control_expr.empty:
            print("Error: Could not retrieve expression data")
            sys.exit(1)

        if verbose:
            print(f"Expression matrix: {len(test_expr)} genes x {test_expr.shape[1]} test samples")
            print()

        # Extract study IDs
        test_studies = list(set(pooled.test_samples["series_id"].tolist())) if "series_id" in pooled.test_samples.columns else []
        control_studies = list(set(pooled.control_samples["series_id"].tolist())) if "series_id" in pooled.control_samples.columns else []

        provenance = DEProvenance.create(
            query_disease=disease,
            query_tissue=tissue,
            search_pattern_test=pooled.test_query,
            search_pattern_control=pooled.control_query,
            test_sample_ids=pooled.test_ids,
            control_sample_ids=pooled.control_ids,
            test_studies=test_studies,
            control_studies=control_studies,
            organisms=[species] if species != "both" else ["human", "mouse"],
            normalization_method=config.method,
            test_method=config.method,
            fdr_method="deseq2" if config.method == "deseq2" else "fdr_bh",
            pvalue_threshold=config.fdr_threshold,
            fdr_threshold=config.fdr_threshold,
            log2fc_threshold=config.log2fc_threshold,
            query_spec=pooled.query_spec,
            sample_filtering=pooled.filtering_stats,
        )
        provenance.analysis_mode = actual_mode
        provenance.mode_fallback_reason = fallback_reason
        provenance.platform_filter = platform_filter

        if verbose:
            print("Running differential expression analysis...")

        result = analyzer.analyze_pooled(
            test_expr=test_expr,
            control_expr=control_expr,
            provenance=provenance,
        )

        if verbose:
            print(f"Tested {result.genes_tested} genes")
            print(f"Found {result.genes_significant} significant genes")
            print()

    # =========================================================================
    # Build unified result from either meta-analysis or pooled DE
    # =========================================================================
    if meta_result is not None:
        # Unify meta-analysis result into standard return format
        all_sig = meta_result.combined_upregulated + meta_result.combined_downregulated
        result_for_output = meta_result  # for enrichment, which expects .upregulated/.downregulated
        genes_tested = meta_result.genes_tested
        genes_significant = meta_result.genes_significant
        provenance = meta_result.provenance
        upregulated = meta_result.combined_upregulated
        downregulated = meta_result.combined_downregulated
    else:
        all_sig = result.upregulated + result.downregulated
        result_for_output = result
        genes_tested = result.genes_tested
        genes_significant = result.genes_significant
        upregulated = result.upregulated
        downregulated = result.downregulated

    # Run enrichment analysis
    enrichment_result = None
    if upregulated or downregulated:
        try:
            from .enrichment_analyzer import EnrichmentAnalyzer, EnrichmentConfig

            enrichment_config = EnrichmentConfig(
                organism="hsapiens",
                sources=["GO:BP", "GO:CC", "GO:MF", "KEGG", "REAC"],
                significance_threshold=0.05,
            )
            enrichment_analyzer = EnrichmentAnalyzer(config=enrichment_config)

            if verbose:
                print("Running enrichment analysis...")

            enrichment_result = enrichment_analyzer.analyze(result_for_output)

            if verbose:
                print(f"  Total enriched terms: {enrichment_result.total_terms}")
                print(f"  Upregulated terms: {enrichment_result.upregulated.n_terms}")
                print(f"  Downregulated terms: {enrichment_result.downregulated.n_terms}")
                print()
        except ImportError as e:
            if verbose:
                print(f"  Enrichment skipped (missing dependency): {e}")
        except Exception as e:
            if verbose:
                print(f"  Enrichment failed: {e}")

    # Output results
    if meta_result is None:
        if output_format == "summary" or (output_format != "json" and not output_path):
            reporter.print_summary(result)

    if output_path:
        output_path = Path(output_path)

        if output_path.is_dir() or not output_path.suffix:
            output_dir = output_path
            output_dir.mkdir(parents=True, exist_ok=True)
            result_file = output_dir / "results.json"
        else:
            output_dir = output_path.parent
            result_file = output_path

        if meta_result is None:
            if output_format == "tsv" or result_file.suffix == ".tsv":
                reporter.to_tsv(result, result_file)
            else:
                if enrichment_result is not None:
                    reporter.to_json_with_enrichment(result, enrichment_result, result_file)
                else:
                    reporter.to_json(result, result_file)
            reporter.to_tsv(result, output_dir / "genes.tsv")

        if enrichment_result is not None:
            reporter.enrichment_to_tsv(enrichment_result, output_dir / "enrichment.tsv")

        if meta_result is None:
            summary = reporter.to_console_summary(result, top_n=20)
        else:
            summary = (
                f"Meta-analysis ({meta_method}): {meta_result.n_studies} studies, "
                f"{genes_tested} genes tested, {genes_significant} significant\n"
                f"  Upregulated: {meta_result.n_upregulated}\n"
                f"  Downregulated: {meta_result.n_downregulated}\n"
            )
        if enrichment_result is not None:
            summary += "\n" + reporter.format_enrichment_summary(enrichment_result, top_n=10)
        (output_dir / "summary.txt").write_text(summary)

        interpretation_text = ""
        if interpret and meta_result is None:
            try:
                from .interpretation import interpret_results, save_interpretation

                if verbose:
                    print("Generating AI interpretation...")

                interpretation_text = interpret_results(result, enrichment_result)
                save_interpretation(interpretation_text, output_dir, result)

                if verbose:
                    print(f"  Saved interpretation to: {output_dir / 'interpretation.md'}")
            except (ImportError, ValueError) as e:
                if verbose:
                    print(f"  Interpretation skipped: {e}")

        if rdf and meta_result is None:
            try:
                from chatgeo.rdf_export import from_chatgeo
                from okn_wobd.de_rdf import RdfConfig

                rdf_config = RdfConfig(
                    base_uri=rdf_base_uri,
                    output_format=rdf_format,
                )

                if verbose:
                    print("Generating RDF export...")

                writer = from_chatgeo(
                    result, enrichment_result, config=rdf_config,
                    summary=summary, interpretation=interpretation_text,
                )
                ext = "ttl" if rdf_format == "turtle" else "nt"
                rdf_path = output_dir / f"results.{ext}"
                writer.write(rdf_path, fmt=rdf_format)

                if verbose:
                    print(f"  RDF: {writer.get_triple_count()} triples → {rdf_path}")
            except ImportError as e:
                if verbose:
                    print(f"  RDF export skipped (missing dependency): {e}")
            except Exception as e:
                if verbose:
                    print(f"  RDF export failed: {e}")

        print(f"Results written to: {output_dir}")

    # Return structured results for programmatic use
    return_dict = {
        "sample_discovery": {
            "n_disease_samples": provenance.n_test_samples,
            "n_control_samples": provenance.n_control_samples,
            "test_studies": provenance.test_studies,
            "control_studies": provenance.control_studies,
            "mode": actual_mode,
        },
        "de_results": {
            "genes_tested": genes_tested,
            "genes_significant": genes_significant,
            "significant_genes": [
                {
                    "gene": g.gene_symbol,
                    "log2_fold_change": g.log2_fold_change,
                    "padj": g.pvalue_adjusted,
                    "direction": g.direction,
                    "mean_test": g.mean_test,
                    "mean_control": g.mean_control,
                }
                for g in sorted(
                    upregulated + downregulated,
                    key=lambda g: abs(g.log2_fold_change),
                    reverse=True,
                )
            ],
        },
        "enrichment": _format_enrichment(enrichment_result) if enrichment_result else {},
        "provenance": provenance.to_dict(),
    }

    if meta_result is not None:
        return_dict["meta_analysis"] = {
            "n_studies": meta_result.n_studies,
            "method": meta_result.meta_method,
            "per_study": [
                {
                    "study_id": s.study_id,
                    "n_test": s.n_test_samples,
                    "n_control": s.n_control_samples,
                    "n_genes_tested": s.n_genes,
                }
                for s in meta_result.study_results
            ],
        }

    if fallback_reason:
        return_dict["sample_discovery"]["mode_fallback_reason"] = fallback_reason

    return return_dict


def _format_enrichment(enrichment_result) -> Dict[str, Any]:
    """Format enrichment result for programmatic return."""
    out: Dict[str, list] = {}
    for direction in [enrichment_result.upregulated, enrichment_result.downregulated]:
        for t in direction.terms:
            out.setdefault(t.source, []).append({
                "name": t.term_name,
                "p_value": t.pvalue_adjusted,
                "intersection_size": t.intersection_size,
                "source": t.source,
                "term_id": t.term_id,
            })
    return out


def _find_study_matched(finder, disease, tissue, query_spec, use_ontology, verbose):
    """Find study-matched samples, trying ontology first if enabled."""
    from .sample_finder import StudyMatchedResult

    result = None

    if use_ontology:
        if verbose:
            print("  Trying ontology-enhanced study matching...")
        try:
            result = finder.find_study_matched_samples_ontology(
                disease_term=disease,
                tissue=tissue,
                query_spec=query_spec,
            )
            if result is not None and verbose:
                print(f"  Ontology: found {result.n_studies} matched studies")
        except Exception as e:
            if verbose:
                print(f"  Ontology study matching failed ({e})")

    if result is None or result.n_studies == 0:
        if verbose:
            print("  Trying keyword study matching...")
        try:
            result = finder.find_study_matched_samples(
                disease_term=disease,
                tissue=tissue,
                query_spec=query_spec,
            )
            if verbose:
                print(f"  Keyword: found {result.n_studies} matched studies")
        except Exception as e:
            if verbose:
                print(f"  Keyword study matching failed ({e})")

    return result


def _find_pooled_samples(
    finder, disease, tissue, max_test, max_control,
    query_spec, use_ontology, verbose, study_prioritized=False,
    platform_filter="none",
):
    """Find pooled samples, optionally with study prioritization."""
    if study_prioritized:
        try:
            return finder.find_pooled_study_prioritized(
                disease_term=disease,
                tissue=tissue,
                max_test_samples=max_test,
                max_control_samples=max_control,
                query_spec=query_spec,
                platform_filter=platform_filter,
            )
        except Exception as e:
            if verbose:
                print(f"  Study-prioritized pooling failed ({e}), falling back")
            return None

    # Standard pooled with ontology
    pooled = None
    if use_ontology:
        if verbose:
            print("  Searching for samples (ontology-enhanced)...")
        try:
            pooled = finder.find_pooled_samples_ontology(
                disease_term=disease,
                tissue=tissue,
                max_test_samples=max_test,
                max_control_samples=max_control,
                query_spec=query_spec,
                keyword_fallback=True,
            )
            if pooled is not None and pooled.n_test == 0:
                pooled = None
        except Exception as e:
            if verbose:
                print(f"  Ontology search failed ({e}), falling back to keyword-only")
            pooled = None

    if pooled is None:
        if verbose:
            print("  Searching for samples (keyword)...")
        pooled = finder.find_pooled_samples(
            disease_term=disease,
            tissue=tissue,
            max_test_samples=max_test,
            max_control_samples=max_control,
            query_spec=query_spec,
        )

    return pooled


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="ChatGEO: Natural language differential expression analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    chatgeo "psoriasis in skin tissue" --output results.json
    chatgeo "lung fibrosis" --tissue lung --fdr 0.01
    chatgeo "breast cancer" --species human --format summary
        """,
    )

    # Positional argument
    parser.add_argument(
        "query",
        help="Natural language query (e.g., 'psoriasis in skin tissue')",
    )

    # Override arguments
    parser.add_argument(
        "--disease",
        help="Override parsed disease (use instead of query parsing)",
    )
    parser.add_argument(
        "--tissue",
        help="Override or specify tissue constraint",
    )

    # Analysis options
    parser.add_argument(
        "--species",
        choices=["human", "mouse", "both"],
        default="human",
        help="Species to analyze (default: human)",
    )
    parser.add_argument(
        "--method",
        choices=["mann-whitney", "welch-t", "deseq2"],
        default="mann-whitney",
        help="DE method (default: mann-whitney). Mann-Whitney U is "
             "recommended for ARCHS4 data (see README). DESeq2 is available "
             "but assumes raw counts, not ARCHS4 pseudocounts.",
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "pooled", "study-matched"],
        default="auto",
        help="Analysis mode (default: auto). 'auto' tries study-matched "
             "meta-analysis first, then study-prioritized pooling, then "
             "basic pooling. 'study-matched' runs per-study DE + meta-analysis. "
             "'pooled' uses original cross-study pooling.",
    )
    parser.add_argument(
        "--meta-method",
        choices=["stouffer", "fisher"],
        default="stouffer",
        help="Meta-analysis method for study-matched mode (default: stouffer).",
    )
    parser.add_argument(
        "--min-studies",
        type=int,
        default=3,
        help="Minimum matched studies for study-matched mode (default: 3).",
    )
    parser.add_argument(
        "--platform-filter",
        choices=["none", "majority"],
        default="none",
        help="Platform filter strategy (default: none). 'majority' filters "
             "controls to match the dominant test platform.",
    )

    # Gene filtering
    parser.add_argument(
        "--gene-filter",
        default="protein_coding",
        help="Comma-separated biotypes to keep (default: protein_coding). "
             "Use 'all' to disable biotype filtering.",
    )
    parser.add_argument(
        "--include-mt-genes",
        action="store_true",
        help="Keep mitochondrial (MT-) genes (useful for mitochondrial diseases)",
    )
    parser.add_argument(
        "--exclude-ribosomal",
        action="store_true",
        help="Remove ribosomal protein genes (RPS*/RPL*)",
    )
    parser.add_argument(
        "--min-library-size",
        type=int,
        default=1_000_000,
        help="Minimum total counts per sample (default: 1000000). "
             "Filters out non-mRNA-seq and failed runs from ARCHS4.",
    )

    # Threshold options
    parser.add_argument(
        "--fdr",
        type=float,
        default=0.01,
        help="FDR threshold (default: 0.01)",
    )
    parser.add_argument(
        "--log2fc",
        type=float,
        default=2.0,
        help="Log2 fold change threshold (default: 2.0)",
    )

    # Sample options
    parser.add_argument(
        "--max-test",
        type=int,
        default=500,
        help="Maximum test samples (default: 500)",
    )
    parser.add_argument(
        "--max-control",
        type=int,
        default=500,
        help="Maximum control samples (default: 500)",
    )

    # Interpretation
    parser.add_argument(
        "--interpret",
        action="store_true",
        default=True,
        help="Generate AI interpretation using Anthropic API (default: on)",
    )
    parser.add_argument(
        "--no-interpret",
        action="store_false",
        dest="interpret",
        help="Skip AI interpretation step",
    )

    # Output options
    parser.add_argument(
        "--output", "-o",
        help="Output directory or file path. If a directory, writes results.json + companion files there.",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["summary", "json", "tsv"],
        default="summary",
        help="Output format (default: summary)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print verbose output",
    )

    # RDF export options
    parser.add_argument(
        "--rdf",
        action="store_true",
        help="Export results as Biolink RDF (requires --output directory)",
    )
    parser.add_argument(
        "--rdf-format",
        choices=["turtle", "nt"],
        default="turtle",
        help="RDF serialization format (default: turtle)",
    )
    parser.add_argument(
        "--rdf-base-uri",
        default="https://okn.wobd.org/",
        help="Base URI for RDF export (default: https://okn.wobd.org/)",
    )

    args = parser.parse_args()

    # Parse query
    disease, tissue = parse_query(args.query)

    # Apply overrides
    if args.disease:
        disease = args.disease
    if args.tissue:
        tissue = args.tissue

    # Map method name
    method_map = {
        "deseq2": "deseq2",
        "mann-whitney": "mann_whitney_u",
        "welch-t": "welch_t",
    }
    method = method_map[args.method]

    # Map gene filter
    gene_filter_biotypes = None if args.gene_filter == "all" else args.gene_filter

    # Run analysis
    run_analysis(
        disease=disease,
        tissue=tissue,
        species=args.species,
        method=method,
        fdr_threshold=args.fdr,
        log2fc_threshold=args.log2fc,
        max_test_samples=args.max_test,
        max_control_samples=args.max_control,
        gene_filter_biotypes=gene_filter_biotypes,
        include_mt_genes=args.include_mt_genes,
        exclude_ribosomal=args.exclude_ribosomal,
        min_library_size=args.min_library_size,
        output_path=args.output,
        output_format=args.format,
        interpret=args.interpret,
        verbose=args.verbose,
        rdf=args.rdf,
        rdf_format=args.rdf_format,
        rdf_base_uri=args.rdf_base_uri,
        mode=args.mode,
        meta_method=args.meta_method,
        min_studies=args.min_studies,
        platform_filter=args.platform_filter,
    )


if __name__ == "__main__":
    main()
