#!/usr/bin/env python3
"""
Run all ChatGEO differential expression examples.

This script runs three example DE analyses and saves results to the examples folder.

Requirements:
    - ARCHS4_DATA_DIR environment variable set
    - Human ARCHS4 HDF5 file available

Usage:
    export ARCHS4_DATA_DIR=/path/to/archs4/data
    python run_all_examples.py
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directories for imports
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir.parent.parent))

def run_example(
    name: str,
    query: str,
    disease: str,
    tissue: str,
    output_dir: Path,
):
    """Run a single DE analysis example."""
    from archs4_client import ARCHS4Client
    from chatgeo import SampleFinder
    from chatgeo.de_analysis import DEConfig, DEMethod, DifferentialExpressionAnalyzer, GeneFilterConfig
    from chatgeo.de_result import DEProvenance
    from chatgeo.enrichment_analyzer import EnrichmentAnalyzer, EnrichmentConfig
    from chatgeo.query_builder import PatternQueryStrategy, QueryBuilder
    from chatgeo.report_generator import ReportGenerator

    data_dir = os.environ.get("ARCHS4_DATA_DIR")

    print(f"\n{'='*70}")
    print(f"EXAMPLE: {name}")
    print(f"Query: {query}")
    print(f"{'='*70}\n")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build command flags
    exclude_mt = name != "Mitochondrial Myopathy"
    mt_flag = "" if exclude_mt else " \\\n    --include-mt-genes"
    command = f'''#!/bin/bash
# ChatGEO Example: {name}
# Generated: {datetime.now().isoformat()}

export ARCHS4_DATA_DIR="{data_dir}"

python -m chatgeo.cli "{query}" \\
    --tissue {tissue} \\
    --method deseq2 \\
    --fdr 0.05 \\
    --log2fc 1.0 \\
    --max-test 200 \\
    --max-control 200 \\
    --output {output_dir}/results.json \\
    --verbose{mt_flag}
'''
    (output_dir / "command.sh").write_text(command)

    # Find samples
    print("Finding samples...")
    query_builder = QueryBuilder(strategy=PatternQueryStrategy())
    finder = SampleFinder(data_dir=data_dir, query_builder=query_builder)

    pooled = finder.find_pooled_samples(
        disease_term=disease,
        tissue=tissue,
        max_test_samples=200,
        max_control_samples=200,
    )

    print(f"  Test samples: {pooled.n_test}")
    print(f"  Control samples: {pooled.n_control}")

    if pooled.n_test == 0 or pooled.n_control == 0:
        print(f"  ERROR: Not enough samples found")
        return False

    # Get expression data
    print("Retrieving expression data...")
    client = ARCHS4Client(organism="human", data_dir=data_dir)

    test_expr = client.get_expression_by_samples(pooled.test_ids)
    control_expr = client.get_expression_by_samples(pooled.control_ids)

    print(f"  Test matrix: {test_expr.shape}")
    print(f"  Control matrix: {control_expr.shape}")

    # Extract study IDs
    test_studies = []
    control_studies = []
    if "series_id" in pooled.test_samples.columns:
        test_studies = list(set(pooled.test_samples["series_id"].dropna().tolist()))
    if "series_id" in pooled.control_samples.columns:
        control_studies = list(set(pooled.control_samples["series_id"].dropna().tolist()))

    # Configure gene filtering: protein-coding only, exclude MT genes
    # For the mitochondrial myopathy example, MT genes are kept
    exclude_mt = name != "Mitochondrial Myopathy"
    gene_filter = GeneFilterConfig(
        biotypes=frozenset({"protein_coding"}),
        exclude_mt_genes=exclude_mt,
        exclude_ribosomal=False,
    )

    # Create DE config using DESeq2 (handles normalization internally)
    config = DEConfig(
        method="deseq2",
        fdr_threshold=0.05,
        log2fc_threshold=1.0,
        gene_filter=gene_filter,
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
        normalization_method="deseq2",
        test_method="deseq2",
        fdr_method="deseq2",
        pvalue_threshold=config.fdr_threshold,
        fdr_threshold=config.fdr_threshold,
        log2fc_threshold=config.log2fc_threshold,
    )

    # Load biotype annotations and create analyzer
    print("Running differential expression analysis...")
    gene_biotypes = client.get_gene_biotypes()
    analyzer = DifferentialExpressionAnalyzer(config=config, gene_biotypes=gene_biotypes)

    result = analyzer.analyze_pooled(
        test_expr=test_expr,
        control_expr=control_expr,
        provenance=provenance,
    )

    print(f"  Genes tested: {result.genes_tested}")
    print(f"  Significant: {result.genes_significant}")
    print(f"  Upregulated: {result.n_upregulated}")
    print(f"  Downregulated: {result.n_downregulated}")

    # Run enrichment analysis
    print("Running enrichment analysis...")
    enrichment_config = EnrichmentConfig(
        organism="hsapiens",
        sources=["GO:BP", "GO:CC", "GO:MF", "KEGG", "REAC"],
        significance_threshold=0.05,
    )
    enrichment_analyzer = EnrichmentAnalyzer(config=enrichment_config)

    try:
        enrichment_result = enrichment_analyzer.analyze(result)
        print(f"  Total enriched terms: {enrichment_result.total_terms}")
        print(f"  Upregulated terms: {enrichment_result.upregulated.n_terms}")
        print(f"  Downregulated terms: {enrichment_result.downregulated.n_terms}")
        has_enrichment = True
    except ImportError as e:
        print(f"  WARNING: Enrichment analysis skipped - {e}")
        enrichment_result = None
        has_enrichment = False

    # Save results
    print("Saving results...")
    reporter = ReportGenerator()

    if has_enrichment and enrichment_result is not None:
        reporter.to_json_with_enrichment(
            result, enrichment_result, output_dir / "results.json"
        )
        reporter.enrichment_to_tsv(enrichment_result, output_dir / "enrichment.tsv")
        enrichment_summary = reporter.format_enrichment_summary(enrichment_result, top_n=10)
    else:
        reporter.to_json(result, output_dir / "results.json")
        enrichment_summary = ""

    reporter.to_tsv(result, output_dir / "genes.tsv")

    summary = reporter.to_console_summary(result, top_n=20)
    if enrichment_summary:
        summary += "\n" + enrichment_summary
    (output_dir / "summary.txt").write_text(summary)

    print(f"  Saved to: {output_dir}")
    return True


def main():
    """Run all examples."""
    print("=" * 70)
    print("CHATGEO DIFFERENTIAL EXPRESSION EXAMPLES")
    print("=" * 70)

    # Check environment
    data_dir = os.environ.get("ARCHS4_DATA_DIR")
    if not data_dir:
        print("\nERROR: ARCHS4_DATA_DIR environment variable not set")
        print("\nPlease set it to the directory containing ARCHS4 HDF5 files:")
        print("    export ARCHS4_DATA_DIR=/path/to/archs4/data")
        sys.exit(1)

    h5_path = Path(data_dir) / "human_gene_v2.latest.h5"
    if not h5_path.exists():
        print(f"\nERROR: ARCHS4 data file not found: {h5_path}")
        sys.exit(1)

    print(f"\nUsing ARCHS4 data from: {data_dir}")

    examples_dir = Path(__file__).parent

    # Define examples
    examples = [
        {
            "name": "Psoriasis in Skin",
            "query": "psoriasis in skin tissue",
            "disease": "psoriasis",
            "tissue": "skin",
            "output_dir": examples_dir / "01_psoriasis",
        },
        {
            "name": "Lung Fibrosis",
            "query": "lung fibrosis",
            "disease": "pulmonary fibrosis",
            "tissue": "lung",
            "output_dir": examples_dir / "02_fibrosis",
        },
        {
            "name": "Rheumatoid Arthritis",
            "query": "rheumatoid arthritis",
            "disease": "rheumatoid arthritis",
            "tissue": "synovial",
            "output_dir": examples_dir / "03_arthritis",
        },
        {
            "name": "Mitochondrial Myopathy",
            "query": "mitochondrial myopathy",
            "disease": "mitochondrial myopathy",
            "tissue": "muscle",
            "output_dir": examples_dir / "04_mitochondrial",
        },
        {
            "name": "Alzheimer's Disease",
            "query": "alzheimer disease",
            "disease": "alzheimer disease",
            "tissue": "brain",
            "output_dir": examples_dir / "05_alzheimers",
        },
    ]

    # Run each example
    results = []
    for ex in examples:
        try:
            success = run_example(**ex)
            results.append((ex["name"], success))
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append((ex["name"], False))

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for name, success in results:
        status = "SUCCESS" if success else "FAILED"
        print(f"  {name}: {status}")

    print("\n" + "=" * 70)
    print("Examples complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
