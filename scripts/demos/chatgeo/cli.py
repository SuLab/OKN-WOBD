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

    # Find samples
    if verbose:
        print("Searching for samples...")

    pooled = finder.find_pooled_samples(
        disease_term=disease,
        tissue=tissue,
        max_test_samples=max_test_samples,
        max_control_samples=max_control_samples,
        query_spec=query_spec,
    )

    if verbose and pooled.filtering_stats:
        ts = pooled.filtering_stats.get("test", {})
        print(f"  Test tissue filtering: {ts.get('before', '?')} candidates → "
              f"{ts.get('after_include', '?')} after include → "
              f"{ts.get('after_exclude', '?')} after exclude")
        cs = pooled.filtering_stats.get("control", {})
        fallback = " (exclude-only fallback)" if cs.get("fallback") else ""
        print(f"  Control tissue filtering: {cs.get('before', '?')} candidates → "
              f"{cs.get('after_include', '?')} after include → "
              f"{cs.get('after_exclude', '?')} after exclude{fallback}")
        if pooled.filtering_stats.get("overlap_removed", 0) > 0:
            print(f"  Overlap removed: {pooled.filtering_stats['overlap_removed']}")

    if pooled.n_test == 0:
        print(f"Error: No test samples found for '{disease}'")
        sys.exit(1)

    if pooled.n_control == 0:
        print(f"Error: No control samples found")
        sys.exit(1)

    if verbose:
        print(f"Found {pooled.n_test} test samples, {pooled.n_control} control samples")
        print()

    # Get expression data (raw counts — DESeq2 normalizes internally)
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

    # Extract study IDs from sample metadata
    test_studies = list(set(pooled.test_samples["series_id"].tolist())) if "series_id" in pooled.test_samples.columns else []
    control_studies = list(set(pooled.control_samples["series_id"].tolist())) if "series_id" in pooled.control_samples.columns else []

    # Create provenance
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

    # Run DE analysis
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

    # Run enrichment analysis
    enrichment_result = None
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

        enrichment_result = enrichment_analyzer.analyze(result)

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
    if output_format == "summary" or (output_format != "json" and not output_path):
        reporter.print_summary(result)

    if output_path:
        output_path = Path(output_path)

        # If output_path is a directory (or has no file extension), treat as directory
        if output_path.is_dir() or not output_path.suffix:
            output_dir = output_path
            output_dir.mkdir(parents=True, exist_ok=True)
            result_file = output_dir / "results.json"
        else:
            output_dir = output_path.parent
            result_file = output_path

        # Write primary output file
        if output_format == "tsv" or result_file.suffix == ".tsv":
            reporter.to_tsv(result, result_file)
        else:
            if enrichment_result is not None:
                reporter.to_json_with_enrichment(result, enrichment_result, result_file)
            else:
                reporter.to_json(result, result_file)

        # Write companion files in the same directory
        reporter.to_tsv(result, output_dir / "genes.tsv")

        if enrichment_result is not None:
            reporter.enrichment_to_tsv(enrichment_result, output_dir / "enrichment.tsv")

        summary = reporter.to_console_summary(result, top_n=20)
        if enrichment_result is not None:
            summary += "\n" + reporter.format_enrichment_summary(enrichment_result, top_n=10)
        (output_dir / "summary.txt").write_text(summary)

        # AI interpretation
        interpretation_text = ""
        if interpret:
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

        # RDF export (opt-in)
        if rdf:
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
    return {
        "sample_discovery": {
            "n_disease_samples": provenance.n_test_samples,
            "n_control_samples": provenance.n_control_samples,
            "test_studies": provenance.test_studies,
            "control_studies": provenance.control_studies,
            "mode": "pooled",
        },
        "de_results": {
            "genes_tested": result.genes_tested,
            "genes_significant": result.genes_significant,
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
                    result.upregulated + result.downregulated,
                    key=lambda g: abs(g.log2_fold_change),
                    reverse=True,
                )
            ],
        },
        "enrichment": _format_enrichment(enrichment_result) if enrichment_result else {},
        "provenance": provenance.to_dict(),
    }


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
    )


if __name__ == "__main__":
    main()
