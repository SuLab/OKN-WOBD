#!/usr/bin/env python3
"""
Cross-Layer Query Demo: Combining SPARQL, NIAID, and ARCHS4 clients.

This demo shows how to answer a complex biomedical question by querying
across multiple data layers:

    "Find gene expression data for B cell activation in vaccination studies"

Workflow:
1. Knowledge Layer (Wikidata via SPARQL) - Get genes for GO:0042113 (B cell activation)
2. Discovery Layer (NIAID) - Find vaccination studies with RNA-seq data
3. Data Layer (ARCHS4) - Retrieve expression matrices for discovered studies

Requirements:
    - ARCHS4 data file (~15GB, downloaded once)
    - Set ARCHS4_DATA_DIR environment variable or use .env file

Usage:
    python demo_cross_layer_query.py
"""

import os
import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Import the three clients
from clients import SPARQLClient
from clients import NIAIDClient
from clients import ARCHS4Client

# Configuration
ARCHS4_DATA_DIR = os.environ.get("ARCHS4_DATA_DIR", "/tmp/archs4")


# =============================================================================
# Pretty Printing Utilities
# =============================================================================

def print_header(title: str, width: int = 80) -> None:
    """Print a formatted header."""
    print("=" * width)
    print(title)
    print("=" * width)
    print()


def print_step(step_num: int, description: str, width: int = 80) -> None:
    """Print a step header."""
    header = f"Step {step_num}: {description}"
    print(f"── {header} " + "─" * (width - len(header) - 4))


def print_result(message: str, indent: int = 0) -> None:
    """Print a result message."""
    prefix = "  " * indent
    print(f"{prefix}{message}")


def print_subresult(message: str) -> None:
    """Print an indented sub-result."""
    print(f"    {message}")


# =============================================================================
# Helper Functions
# =============================================================================

def extract_geo_accessions(hits: List[Dict[str, Any]]) -> List[Tuple[str, str, str]]:
    """
    Extract GEO accessions (GSE/GSM) from NIAID dataset records.

    Searches through various fields where GEO accessions might be stored:
    - identifier field
    - sameAs field
    - distribution URLs
    - url field

    Returns:
        List of tuples: (gse_id, study_name, source_field)
    """
    geo_pattern = re.compile(r'(GSE\d+)')
    accessions = []
    seen = set()

    for hit in hits:
        study_name = hit.get("name", "Unknown Study")[:60]

        # Check identifier field
        identifier = hit.get("identifier", "")
        if isinstance(identifier, str):
            matches = geo_pattern.findall(identifier)
            for m in matches:
                if m not in seen:
                    accessions.append((m, study_name, "identifier"))
                    seen.add(m)

        # Check sameAs field
        same_as = hit.get("sameAs", [])
        if isinstance(same_as, list):
            for item in same_as:
                if isinstance(item, str):
                    matches = geo_pattern.findall(item)
                    for m in matches:
                        if m not in seen:
                            accessions.append((m, study_name, "sameAs"))
                            seen.add(m)

        # Check URL field
        url = hit.get("url", "")
        if isinstance(url, str):
            matches = geo_pattern.findall(url)
            for m in matches:
                if m not in seen:
                    accessions.append((m, study_name, "url"))
                    seen.add(m)

        # Check distribution field
        distribution = hit.get("distribution", [])
        if isinstance(distribution, list):
            for dist in distribution:
                if isinstance(dist, dict):
                    content_url = dist.get("contentUrl", "")
                    if isinstance(content_url, str):
                        matches = geo_pattern.findall(content_url)
                        for m in matches:
                            if m not in seen:
                                accessions.append((m, study_name, "distribution"))
                                seen.add(m)

    return accessions


def generate_summary_report(
    genes: List[Dict[str, str]],
    studies: List[Dict[str, Any]],
    geo_accessions: List[Tuple[str, str, str]],
    expression_df: Optional[Any],
    gse_id: Optional[str],
) -> None:
    """Generate a summary report of the cross-layer query."""
    print()
    print("── Summary " + "─" * 68)
    print()

    # Gene summary
    gene_symbols = [g.get("symbol", "?") for g in genes]
    print(f"  GO Term:        GO:0042113 (B cell activation)")
    print(f"  Genes Found:    {len(genes)} from Wikidata")
    if gene_symbols:
        sample = ", ".join(gene_symbols[:8])
        print(f"                  [{sample}, ...]")

    # Study summary
    print()
    print(f"  Studies Found:  {len(studies)} in NIAID/ImmPort")
    print(f"  With GEO Data:  {len(geo_accessions)} studies have GSE accessions")

    # Expression data summary
    if expression_df is not None and not expression_df.empty:
        print()
        print(f"  GEO Series:     {gse_id}")
        print(f"  Expression:     {expression_df.shape[0]} genes × {expression_df.shape[1]} samples")
        genes_found = len([g for g in gene_symbols if g in expression_df.index])
        print(f"  Genes Matched:  {genes_found} of {len(gene_symbols)} B cell activation genes")
    elif gse_id:
        print()
        print(f"  GEO Series:     {gse_id} (not available in ARCHS4)")

    print()
    print("=" * 80)


# =============================================================================
# Main Demo
# =============================================================================

def demo_bcell_vaccine_response():
    """
    Demo: Find gene expression data for B cell activation in vaccination studies.

    This demonstrates a cross-layer query combining:
    1. Knowledge graph (Wikidata) for gene annotations
    2. Dataset discovery (NIAID) for relevant studies
    3. Expression data (ARCHS4) for actual measurements
    """
    print_header("Cross-Layer Query: B Cell Activation in Vaccination Studies")

    # =========================================================================
    # Step 1: Knowledge Layer (Wikidata via SPARQL)
    # =========================================================================
    print_step(1, "Knowledge Layer (Wikidata)")
    print_result("Querying for genes annotated to GO:0042113 (B cell activation)")
    print()

    try:
        sparql = SPARQLClient()
        genes = sparql.get_genes_for_go_term("GO:0042113")
        gene_symbols = [g["symbol"] for g in genes]

        print_result(f"Found {len(genes)} genes associated with B cell activation")
        if gene_symbols:
            sample = ", ".join(gene_symbols[:12])
            print_result(f"Sample: {sample}...")
    except Exception as e:
        print_result(f"Error querying Wikidata: {e}")
        genes = []
        gene_symbols = []

    print()

    # =========================================================================
    # Step 2: Discovery Layer (NIAID)
    # =========================================================================
    print_step(2, "Discovery Layer (NIAID)")
    print_result("Searching NCBI GEO for vaccination RNA-seq studies")
    print()

    try:
        niaid = NIAIDClient()
        # Search for vaccination studies in NCBI GEO (which has GSE accessions)
        result = niaid.search(
            'vaccination AND includedInDataCatalog.name:"NCBI GEO"',
            size=50
        )

        print_result(f"Found {result.total} matching studies in NCBI GEO")

        # Extract GEO accessions
        geo_accessions = extract_geo_accessions(result.hits)
        print_result(f"Extracted {len(geo_accessions)} GEO series accessions")

        if geo_accessions:
            print()
            print_result("Studies with GEO data:")
            for gse_id, study_name, source in geo_accessions[:5]:
                print_subresult(f"{gse_id}: {study_name}")
            if len(geo_accessions) > 5:
                print_subresult(f"... and {len(geo_accessions) - 5} more")

        studies = result.hits
    except Exception as e:
        print_result(f"Error querying NIAID: {e}")
        studies = []
        geo_accessions = []

    print()

    # =========================================================================
    # Step 3: Data Layer (ARCHS4)
    # =========================================================================
    print_step(3, "Data Layer (ARCHS4)")

    expression_df = None
    selected_gse = None

    if not geo_accessions:
        print_result("No GEO accessions found - skipping ARCHS4 query")
    elif not gene_symbols:
        print_result("No genes found - skipping ARCHS4 query")
    else:
        print_result(f"Data directory: {ARCHS4_DATA_DIR}")
        print()

        try:
            # Check if data file exists
            data_path = Path(ARCHS4_DATA_DIR)
            h5_file = data_path / "human_gene_v2.latest.h5"

            if not h5_file.exists():
                print_result("ARCHS4 data file not found.")
                print_result(f"Expected: {h5_file}")
                print()
                print_result("To download the data file (~15GB), run:")
                print_subresult("import archs4py as a4")
                print_subresult(f'a4.download.counts("human", path="{ARCHS4_DATA_DIR}")')
            else:
                archs4 = ARCHS4Client(organism="human", h5_path=str(h5_file))

                # Try each GEO series until we find one in ARCHS4
                for gse_id, study_name, _ in geo_accessions:
                    print_result(f"Checking {gse_id}...")
                    if archs4.has_series(gse_id):
                        print_result(f"Found {gse_id} in ARCHS4!")
                        selected_gse = gse_id

                        # Get expression data filtered to our gene list
                        print_result(f"Retrieving expression data for {len(gene_symbols)} genes...")
                        try:
                            expression_df = archs4.get_expression_by_series(
                                gse_id,
                                genes=gene_symbols
                            )
                            if expression_df is not None and not expression_df.empty:
                                print_result(
                                    f"Expression matrix: {expression_df.shape[0]} genes × "
                                    f"{expression_df.shape[1]} samples"
                                )

                                # Show sample of the data
                                print()
                                print_result("Sample expression values (first 5 genes, 3 samples):")
                                sample_df = expression_df.iloc[:5, :3]
                                for gene in sample_df.index:
                                    values = ", ".join(f"{v:.0f}" for v in sample_df.loc[gene])
                                    print_subresult(f"{gene}: {values}")
                            break
                        except ValueError as e:
                            print_result(f"No matching genes found in {gse_id}")
                            continue
                    else:
                        print_subresult(f"{gse_id} not in ARCHS4")

                if selected_gse is None:
                    print_result("No matching GEO series found in ARCHS4")

        except ImportError as e:
            print_result(f"ARCHS4 client not available: {e}")
        except Exception as e:
            print_result(f"Error querying ARCHS4: {e}")

    print()

    # =========================================================================
    # Summary Report
    # =========================================================================
    generate_summary_report(genes, studies, geo_accessions, expression_df, selected_gse)


def main():
    """Run the cross-layer query demo."""
    demo_bcell_vaccine_response()


if __name__ == "__main__":
    main()
