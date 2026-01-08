#!/usr/bin/env python3
"""
Build Sample Visualizations

This script:
1. Runs query_drug_down_disease_up to find gene/drug/disease combinations
   with opposing expression patterns (potential therapeutic mechanisms)
2. Selects ~10 diverse examples from the results
3. Generates HTML visualizations for each using generate_gene_visualization

Usage:
    python build_samples.py
    python build_samples.py --count 15 --output ./my_samples
    python build_samples.py --pattern down-up  # Only drug-down/disease-up
    python build_samples.py --pattern up-down  # Only drug-up/disease-down
"""

import argparse
import os
import sys
from typing import List, Dict, Any

# Import the query function
from query_drug_down_disease_up import find_drug_disease_genes

# Import the visualization generator
from generate_gene_visualization import generate_visualization


def select_diverse_examples(
    results: List[Dict[str, Any]],
    count: int = 10,
) -> List[Dict[str, Any]]:
    """
    Select diverse examples from query results.

    Prioritizes:
    - Unique genes (avoid multiple entries for same gene)
    - Unique drugs (avoid multiple entries for same drug)
    - Unique diseases (variety of disease types)
    - Higher fold changes (more interesting biological signals)
    """
    if not results:
        return []

    selected = []
    seen_genes = set()
    seen_drugs = set()
    seen_diseases = set()

    # Sort by absolute disease fold change (most significant first)
    sorted_results = sorted(results, key=lambda x: -abs(x.get('disease_log2fc', 0)))

    # First pass: select entries with unique gene + drug + disease combinations
    for r in sorted_results:
        if len(selected) >= count:
            break

        gene = r.get('gene', '')
        drug = r.get('drug_name') or r.get('drug_test_group', '')
        disease = r.get('disease', '')

        # Skip if we've seen this gene already (prioritize gene diversity)
        if gene in seen_genes:
            continue

        # Add to selection
        selected.append(r)
        seen_genes.add(gene)
        seen_drugs.add(drug)
        seen_diseases.add(disease)

    # If we need more, relax constraints (allow same drug/disease, but different genes)
    if len(selected) < count:
        for r in sorted_results:
            if len(selected) >= count:
                break

            gene = r.get('gene', '')
            if gene not in seen_genes:
                selected.append(r)
                seen_genes.add(gene)

    return selected


def build_samples(
    output_dir: str = "./example_visualizations",
    count: int = 10,
    pattern: str = "both",
    verbose: bool = False,
):
    """
    Build sample visualizations from drug-disease opposing expression patterns.

    Args:
        output_dir: Directory to save HTML visualizations
        count: Number of samples to generate
        pattern: "down-up", "up-down", or "both"
        verbose: Enable verbose output
    """
    print("=" * 70)
    print("BUILD SAMPLE VISUALIZATIONS")
    print("=" * 70)

    all_results = []

    # Pattern 1: Drug DOWN, Disease UP
    if pattern in ("down-up", "both"):
        print("\n[Query] Finding Drug DOWN → Disease UP patterns...")
        results1, drug_label1, disease_label1 = find_drug_disease_genes(
            drug_direction="down",
            disease_direction="up",
            drug_fc_threshold=2.0,
            disease_fc_threshold=1.5,
        )
        print(f"  Found {len(results1)} combinations")

        # Tag results with pattern type
        for r in results1:
            r['pattern'] = 'down-up'
            r['drug_direction'] = 'DOWN'
            r['disease_direction'] = 'UP'
        all_results.extend(results1)

    # Pattern 2: Drug UP, Disease DOWN
    if pattern in ("up-down", "both"):
        print("\n[Query] Finding Drug UP → Disease DOWN patterns...")
        results2, drug_label2, disease_label2 = find_drug_disease_genes(
            drug_direction="up",
            disease_direction="down",
            drug_fc_threshold=2.0,
            disease_fc_threshold=1.5,
        )
        print(f"  Found {len(results2)} combinations")

        for r in results2:
            r['pattern'] = 'up-down'
            r['drug_direction'] = 'UP'
            r['disease_direction'] = 'DOWN'
        all_results.extend(results2)

    if not all_results:
        print("\nNo results found. Check that the Fuseki server is running.")
        return []

    # Select diverse examples
    print(f"\n[Selection] Choosing {count} diverse examples from {len(all_results)} total...")
    selected = select_diverse_examples(all_results, count=count)

    print(f"\nSelected {len(selected)} examples:")
    for i, r in enumerate(selected, 1):
        gene = r.get('gene', 'N/A')
        drug = r.get('drug_name') or r.get('drug_test_group', 'N/A')
        disease = r.get('disease', 'N/A')
        pattern_type = r.get('pattern', 'N/A')
        drug_fc = r.get('drug_log2fc', 0)
        disease_fc = r.get('disease_log2fc', 0)
        print(f"  {i:2}. {gene:10} | Drug: {drug[:25]:25} | Disease: {disease[:25]:25}")
        print(f"      Pattern: {pattern_type} | Drug FC: {drug_fc:+.1f} | Disease FC: {disease_fc:+.1f}")

    # Generate visualizations
    print(f"\n[Visualization] Generating {len(selected)} HTML files...")
    print("-" * 70)

    os.makedirs(output_dir, exist_ok=True)
    output_files = []

    for i, r in enumerate(selected, 1):
        gene = r.get('gene', '')
        drug = r.get('drug_name') or r.get('drug_test_group', '')
        disease = r.get('disease', '')

        print(f"\n[{i}/{len(selected)}] {gene} / {drug[:20]} / {disease[:20]}")

        try:
            output_file = generate_visualization(
                gene_symbol=gene,
                output_dir=output_dir,
                drug_name=drug if drug else None,
                disease_name=disease if disease else None,
                verbose=verbose,
            )
            output_files.append({
                'file': output_file,
                'gene': gene,
                'drug': drug,
                'disease': disease,
                'pattern': r.get('pattern', ''),
            })
        except Exception as e:
            print(f"  ERROR: {e}")

    # Summary
    print("\n" + "=" * 70)
    print("BUILD COMPLETE")
    print("=" * 70)
    print(f"\nGenerated {len(output_files)} visualizations in: {output_dir}/")
    print("\nFiles created:")
    for item in output_files:
        print(f"  - {os.path.basename(item['file'])}")
        print(f"    Gene: {item['gene']} | Drug: {item['drug'][:30]} | Disease: {item['disease'][:30]}")

    return output_files


def main():
    parser = argparse.ArgumentParser(
        description="Build sample visualizations from drug-disease expression patterns"
    )
    parser.add_argument(
        "--output", "-o",
        default="./example_visualizations",
        help="Output directory for HTML files (default: ./example_visualizations)"
    )
    parser.add_argument(
        "--count", "-n",
        type=int,
        default=10,
        help="Number of sample visualizations to generate (default: 10)"
    )
    parser.add_argument(
        "--pattern", "-p",
        choices=["down-up", "up-down", "both"],
        default="both",
        help="Expression pattern to query (default: both)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    args = parser.parse_args()

    build_samples(
        output_dir=args.output,
        count=args.count,
        pattern=args.pattern,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
