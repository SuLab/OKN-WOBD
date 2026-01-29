#!/usr/bin/env python3
"""
Demo: Differential Expression Analysis for Psoriasis in Skin

This script demonstrates the ChatGEO differential expression analysis pipeline
using psoriasis as an example disease.

Requirements:
    - ARCHS4_DATA_DIR environment variable set to ARCHS4 data location
    - Human ARCHS4 HDF5 file (human_gene_v2.latest.h5)

Usage:
    export ARCHS4_DATA_DIR=/path/to/archs4/data
    python demo_psoriasis_de.py
"""

import os
import sys
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))


def main():
    """Run psoriasis differential expression analysis demo."""
    print("=" * 70)
    print("CHATGEO DEMO: Psoriasis Differential Expression Analysis")
    print("=" * 70)
    print()

    # Check environment
    data_dir = os.environ.get("ARCHS4_DATA_DIR")
    if not data_dir:
        print("ERROR: ARCHS4_DATA_DIR environment variable not set")
        print()
        print("Please set it to the directory containing ARCHS4 HDF5 files:")
        print("    export ARCHS4_DATA_DIR=/path/to/archs4/data")
        print()
        print("Required file: human_gene_v2.latest.h5")
        sys.exit(1)

    h5_path = Path(data_dir) / "human_gene_v2.latest.h5"
    if not h5_path.exists():
        print(f"ERROR: ARCHS4 data file not found: {h5_path}")
        print()
        print("Download from: https://maayanlab.cloud/archs4/download.html")
        sys.exit(1)

    print(f"Using ARCHS4 data from: {data_dir}")
    print()

    # Import modules
    from archs4_client import ARCHS4Client
    from chatgeo import SampleFinder, SearchMetrics
    from chatgeo.de_analysis import DEConfig, DifferentialExpressionAnalyzer
    from chatgeo.de_result import DEProvenance
    from chatgeo.gene_ranker import GeneRanker, RankingMethod
    from chatgeo.query_builder import PatternQueryStrategy, QueryBuilder
    from chatgeo.report_generator import ReportGenerator

    # Configuration
    disease = "psoriasis"
    tissue = "skin"
    max_samples = 100  # Limit for demo

    print(f"Disease: {disease}")
    print(f"Tissue: {tissue}")
    print(f"Max samples per group: {max_samples}")
    print()

    # Step 1: Find samples
    print("-" * 70)
    print("STEP 1: Finding samples")
    print("-" * 70)

    query_builder = QueryBuilder(strategy=PatternQueryStrategy())
    finder = SampleFinder(data_dir=data_dir, query_builder=query_builder)

    pooled = finder.find_pooled_samples(
        disease_term=disease,
        tissue=tissue,
        max_test_samples=max_samples,
        max_control_samples=max_samples,
    )

    print(f"Test samples found: {pooled.n_test} (from {pooled.total_test_found} total)")
    print(f"Control samples found: {pooled.n_control} (from {pooled.total_control_found} total)")
    print(f"Test query: {pooled.test_query}")
    print(f"Control query: {pooled.control_query}")
    print()

    if pooled.n_test == 0 or pooled.n_control == 0:
        print("ERROR: Not enough samples found")
        sys.exit(1)

    # Step 2: Get expression data
    print("-" * 70)
    print("STEP 2: Retrieving expression data")
    print("-" * 70)

    client = ARCHS4Client(organism="human", data_dir=data_dir)

    print(f"Fetching expression for {pooled.n_test} test samples...")
    test_expr = client.get_expression_by_samples(pooled.test_ids)
    print(f"  Got {len(test_expr)} genes x {test_expr.shape[1]} samples")

    print(f"Fetching expression for {pooled.n_control} control samples...")
    control_expr = client.get_expression_by_samples(pooled.control_ids)
    print(f"  Got {len(control_expr)} genes x {control_expr.shape[1]} samples")
    print()

    # Step 3: Create provenance
    print("-" * 70)
    print("STEP 3: Setting up analysis")
    print("-" * 70)

    # Extract study IDs
    test_studies = []
    control_studies = []
    if "series_id" in pooled.test_samples.columns:
        test_studies = list(set(pooled.test_samples["series_id"].tolist()))
    if "series_id" in pooled.control_samples.columns:
        control_studies = list(set(pooled.control_samples["series_id"].tolist()))

    print(f"Test samples from {len(test_studies)} studies")
    print(f"Control samples from {len(control_studies)} studies")
    print()

    config = DEConfig(
        test_method="mann_whitney_u",
        fdr_method="fdr_bh",
        normalization="log_quantile",
        pvalue_threshold=0.05,
        fdr_threshold=0.05,
        log2fc_threshold=1.0,
    )

    provenance = DEProvenance.create(
        query_disease=disease,
        query_tissue=tissue,
        search_pattern_test=pooled.test_query,
        search_pattern_control=pooled.control_query,
        test_sample_ids=pooled.test_ids,
        control_sample_ids=pooled.control_ids,
        test_studies=test_studies,
        control_studies=control_studies,
        organisms=["human"],
        normalization_method=config.normalization,
        test_method=config.test_method,
        fdr_method=config.fdr_method,
        pvalue_threshold=config.pvalue_threshold,
        fdr_threshold=config.fdr_threshold,
        log2fc_threshold=config.log2fc_threshold,
    )

    # Step 4: Run DE analysis
    print("-" * 70)
    print("STEP 4: Running differential expression analysis")
    print("-" * 70)

    analyzer = DifferentialExpressionAnalyzer(config=config)

    print("Performing statistical tests...")
    result = analyzer.analyze_pooled(
        test_expr=test_expr,
        control_expr=control_expr,
        provenance=provenance,
    )

    print(f"Genes tested: {result.genes_tested:,}")
    print(f"Genes significant: {result.genes_significant:,}")
    print(f"Upregulated: {result.n_upregulated:,}")
    print(f"Downregulated: {result.n_downregulated:,}")
    print()

    # Step 5: Generate report
    print("-" * 70)
    print("STEP 5: Results")
    print("-" * 70)
    print()

    reporter = ReportGenerator()
    reporter.print_summary(result, top_n=15)

    # Step 6: Save results
    output_dir = Path(__file__).parent / "psoriasis"
    output_dir.mkdir(exist_ok=True)

    json_path = output_dir / "psoriasis_de_results.json"
    tsv_path = output_dir / "psoriasis_de_genes.tsv"

    print()
    print("-" * 70)
    print("STEP 6: Saving results")
    print("-" * 70)

    reporter.to_json(result, json_path)
    print(f"Full results saved to: {json_path}")

    reporter.to_tsv(result, tsv_path)
    print(f"Gene table saved to: {tsv_path}")

    # Known psoriasis genes to check
    print()
    print("-" * 70)
    print("VALIDATION: Known psoriasis-associated genes")
    print("-" * 70)

    known_psoriasis_genes = [
        "IL17A", "IL17F", "IL22", "IL23A",  # IL-17/IL-23 axis
        "S100A7", "S100A8", "S100A9",       # S100 proteins
        "DEFB4A", "DEFB4B",                  # Defensins
        "KRT16", "KRT17",                    # Keratins
        "SERPINB4",                          # Squamous cell markers
        "CCL20", "CXCL1", "CXCL8",          # Chemokines
    ]

    print(f"{'Gene':<12} {'Status':<15} {'Log2FC':>10} {'P-adj':>12}")
    print("-" * 50)

    for gene_symbol in known_psoriasis_genes:
        gene = result.get_gene(gene_symbol)
        if gene:
            p_adj = f"{gene.pvalue_adjusted:.2e}" if gene.pvalue_adjusted else "N/A"
            status = "SIGNIFICANT" if gene in result.upregulated or gene in result.downregulated else "not sig"
            print(f"{gene_symbol:<12} {status:<15} {gene.log2_fold_change:>10.2f} {p_adj:>12}")
        else:
            print(f"{gene_symbol:<12} {'not tested':<15}")

    print()
    print("=" * 70)
    print("Demo complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
