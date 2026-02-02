#!/usr/bin/env python3
"""
Run all ChatGEO differential expression examples.

This script runs DE analyses and saves results to the examples folder.

Requirements:
    - ARCHS4_DATA_DIR environment variable set
    - Human ARCHS4 HDF5 file available
    - ANTHROPIC_API_KEY environment variable set (for interpretation)

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

# Load .env file if present
env_path = script_dir.parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# Default thresholds (more stringent than previous 0.05/1.0)
FDR_THRESHOLD = 0.01
LOG2FC_THRESHOLD = 2.0


def run_example(
    name: str,
    query: str,
    disease: str,
    tissue: str,
    output_dir: Path,
    include_mt_genes: bool = False,
):
    """Run a single DE analysis example."""
    from archs4_client import ARCHS4Client
    from chatgeo import SampleFinder
    from chatgeo.de_analysis import DEConfig, DifferentialExpressionAnalyzer, GeneFilterConfig
    from chatgeo.de_result import DEProvenance
    from chatgeo.enrichment_analyzer import EnrichmentAnalyzer, EnrichmentConfig
    from chatgeo.interpretation import interpret_results, save_interpretation
    from chatgeo.query_builder import (
        PatternQueryStrategy,
        QueryBuilder,
        build_query_spec,
        build_query_spec_fallback,
    )
    from chatgeo.report_generator import ReportGenerator

    data_dir = os.environ.get("ARCHS4_DATA_DIR")

    print(f"\n{'='*70}")
    print(f"EXAMPLE: {name}")
    print(f"Query: {query}")
    print(f"Thresholds: FDR < {FDR_THRESHOLD}, |log2FC| >= {LOG2FC_THRESHOLD}")
    print(f"{'='*70}\n")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build command flags
    mt_flag = "" if not include_mt_genes else " \\\n    --include-mt-genes"
    command = f'''#!/bin/bash
# ChatGEO Example: {name}
# Generated: {datetime.now().isoformat()}

export ARCHS4_DATA_DIR="{data_dir}"

python -m chatgeo.cli "{query}" \\
    --tissue {tissue} \\
    --method deseq2 \\
    --fdr {FDR_THRESHOLD} \\
    --log2fc {LOG2FC_THRESHOLD} \\
    --max-test 200 \\
    --max-control 200 \\
    --output {output_dir}/results.json \\
    --verbose{mt_flag}
'''
    (output_dir / "command.sh").write_text(command)

    # Build structured query spec for tissue-aware filtering
    query_spec = None
    if tissue:
        try:
            query_spec = build_query_spec(disease, tissue)
            print(f"  Query strategy: LLM")
            print(f"  Disease terms: {query_spec.disease_terms}")
            print(f"  Tissue include: {query_spec.tissue_include}")
            print(f"  Tissue exclude: {query_spec.tissue_exclude}")
            print(f"  Reasoning: {query_spec.reasoning}")
        except Exception as e:
            print(f"  LLM query builder failed ({e}), using pattern fallback")
            query_spec = build_query_spec_fallback(disease, tissue)

    # Find samples
    print("Finding samples...")
    query_builder = QueryBuilder(strategy=PatternQueryStrategy())
    finder = SampleFinder(data_dir=data_dir, query_builder=query_builder)

    pooled = finder.find_pooled_samples(
        disease_term=disease,
        tissue=tissue,
        max_test_samples=200,
        max_control_samples=200,
        query_spec=query_spec,
    )

    print(f"  Test samples: {pooled.n_test}")
    print(f"  Control samples: {pooled.n_control}")
    if pooled.filtering_stats:
        ts = pooled.filtering_stats.get("test", {})
        print(f"  Tissue filtering: {ts.get('before', '?')} → "
              f"{ts.get('after_include', '?')} (include) → "
              f"{ts.get('after_exclude', '?')} (exclude)")

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

    # Configure gene filtering
    gene_filter = GeneFilterConfig(
        biotypes=frozenset({"protein_coding"}),
        exclude_mt_genes=not include_mt_genes,
        exclude_ribosomal=False,
    )

    # Create DE config with stringent thresholds
    config = DEConfig(
        method="deseq2",
        fdr_threshold=FDR_THRESHOLD,
        log2fc_threshold=LOG2FC_THRESHOLD,
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
        query_spec=pooled.query_spec,
        sample_filtering=pooled.filtering_stats,
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

    enrichment_result = None
    try:
        enrichment_result = enrichment_analyzer.analyze(result)
        print(f"  Total enriched terms: {enrichment_result.total_terms}")
        print(f"  Upregulated terms: {enrichment_result.upregulated.n_terms}")
        print(f"  Downregulated terms: {enrichment_result.downregulated.n_terms}")
    except ImportError as e:
        print(f"  WARNING: Enrichment analysis skipped - {e}")
    except Exception as e:
        print(f"  WARNING: Enrichment failed - {e}")

    # Save results
    print("Saving results...")
    reporter = ReportGenerator()

    if enrichment_result is not None:
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

    # AI interpretation
    print("Generating AI interpretation...")
    try:
        interpretation = interpret_results(result, enrichment_result)
        save_interpretation(interpretation, output_dir, result)
        print(f"  Saved interpretation to: {output_dir / 'interpretation.md'}")
    except (ImportError, ValueError) as e:
        print(f"  WARNING: Interpretation skipped - {e}")
    except Exception as e:
        print(f"  WARNING: Interpretation failed - {e}")

    print(f"  Saved to: {output_dir}")
    return True


def main():
    """Run all examples."""
    print("=" * 70)
    print("CHATGEO DIFFERENTIAL EXPRESSION EXAMPLES")
    print(f"Thresholds: FDR < {FDR_THRESHOLD}, |log2FC| >= {LOG2FC_THRESHOLD}")
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

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("\nWARNING: ANTHROPIC_API_KEY not set - interpretation will be skipped")
    else:
        print(f"Anthropic API key: ...{api_key[-8:]}")

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
            "include_mt_genes": True,
        },
        {
            "name": "Alzheimer's Disease",
            "query": "alzheimer disease",
            "disease": "alzheimer disease",
            "tissue": "brain",
            "output_dir": examples_dir / "05_alzheimers",
        },
        {
            "name": "Systemic Lupus Erythematosus in Blood",
            "query": "systemic lupus erythematosus in blood",
            "disease": "systemic lupus erythematosus",
            "tissue": "blood",
            "output_dir": examples_dir / "08_sle",
        },
        {
            "name": "Colorectal Cancer vs Normal Colon",
            "query": "colorectal cancer in colon tissue",
            "disease": "colorectal cancer",
            "tissue": "colon",
            "output_dir": examples_dir / "09_colorectal_cancer",
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
            import traceback
            traceback.print_exc()
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
