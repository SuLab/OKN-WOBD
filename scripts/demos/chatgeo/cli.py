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
from typing import Literal, Optional, Tuple

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


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
    mode: Literal["pooled", "study_matched", "auto"] = "pooled",
    test_method: Literal["mann_whitney_u", "welch_t"] = "mann_whitney_u",
    fdr_threshold: float = 0.05,
    log2fc_threshold: float = 1.0,
    max_test_samples: int = 500,
    max_control_samples: int = 500,
    output_path: Optional[str] = None,
    output_format: Literal["summary", "json", "tsv"] = "summary",
    verbose: bool = False,
) -> None:
    """
    Run differential expression analysis.

    Args:
        disease: Disease or condition to search
        tissue: Optional tissue constraint
        species: Species to analyze
        mode: Analysis mode (pooled or study-matched)
        test_method: Statistical test method
        fdr_threshold: FDR significance threshold
        log2fc_threshold: Log2 fold change threshold
        max_test_samples: Maximum test samples
        max_control_samples: Maximum control samples
        output_path: Output file path
        output_format: Output format
        verbose: Print verbose output
    """
    # Import here to defer ARCHS4 initialization
    from archs4_client import ARCHS4Client

    from .de_analysis import DEConfig, DifferentialExpressionAnalyzer
    from .de_result import DEProvenance
    from .query_builder import PatternQueryStrategy, QueryBuilder
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
        print()

    # Initialize components
    query_builder = QueryBuilder(strategy=PatternQueryStrategy())
    finder = SampleFinder(data_dir=data_dir, query_builder=query_builder)

    # Configure DE analysis
    config = DEConfig(
        test_method=test_method,
        fdr_threshold=fdr_threshold,
        log2fc_threshold=log2fc_threshold,
    )
    analyzer = DifferentialExpressionAnalyzer(config=config)
    reporter = ReportGenerator()

    # Find samples
    if verbose:
        print("Searching for samples...")

    pooled = finder.find_pooled_samples(
        disease_term=disease,
        tissue=tissue,
        max_test_samples=max_test_samples,
        max_control_samples=max_control_samples,
    )

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

    client = ARCHS4Client(organism="human", data_dir=data_dir)

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
        normalization_method=config.normalization,
        test_method=config.test_method,
        fdr_method=config.fdr_method,
        pvalue_threshold=config.pvalue_threshold,
        fdr_threshold=config.fdr_threshold,
        log2fc_threshold=config.log2fc_threshold,
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

    # Output results
    if output_format == "summary" or (output_format != "json" and not output_path):
        reporter.print_summary(result)

    if output_path:
        output_path = Path(output_path)

        if output_format == "json" or output_path.suffix == ".json":
            reporter.to_json(result, output_path)
            print(f"Results written to: {output_path}")

        elif output_format == "tsv" or output_path.suffix == ".tsv":
            reporter.to_tsv(result, output_path)
            print(f"Results written to: {output_path}")

        else:
            # Default to JSON
            reporter.to_json(result, output_path)
            print(f"Results written to: {output_path}")


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
        "--mode",
        choices=["pooled", "study_matched", "auto"],
        default="pooled",
        help="Analysis mode (default: pooled)",
    )
    parser.add_argument(
        "--test",
        choices=["mann-whitney", "welch-t"],
        default="mann-whitney",
        help="Statistical test (default: mann-whitney)",
    )

    # Threshold options
    parser.add_argument(
        "--fdr",
        type=float,
        default=0.05,
        help="FDR threshold (default: 0.05)",
    )
    parser.add_argument(
        "--log2fc",
        type=float,
        default=1.0,
        help="Log2 fold change threshold (default: 1.0)",
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

    # Output options
    parser.add_argument(
        "--output", "-o",
        help="Output file path (JSON or TSV)",
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

    args = parser.parse_args()

    # Parse query
    disease, tissue = parse_query(args.query)

    # Apply overrides
    if args.disease:
        disease = args.disease
    if args.tissue:
        tissue = args.tissue

    # Map test method
    test_method = "mann_whitney_u" if args.test == "mann-whitney" else "welch_t"

    # Run analysis
    run_analysis(
        disease=disease,
        tissue=tissue,
        species=args.species,
        mode=args.mode,
        test_method=test_method,
        fdr_threshold=args.fdr,
        log2fc_threshold=args.log2fc,
        max_test_samples=args.max_test,
        max_control_samples=args.max_control,
        output_path=args.output,
        output_format=args.format,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
