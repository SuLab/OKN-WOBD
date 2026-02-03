#!/usr/bin/env python3
"""
ACTA2 Lung Fibrosis Expression Demo

This demo retrieves ACTA2 (alpha smooth muscle actin) expression data across
lung cell types in healthy and fibrotic conditions, combining multiple data sources:

1. Knowledge Layer (Wikidata) - Gene annotations and identifiers
2. Single-Cell Layer (CellxGene Census) - Cell-type specific expression
3. Discovery Layer (NIAID) - Relevant bulk RNA-seq studies
4. Data Layer (ARCHS4) - Bulk expression values (when available)

Target Question:
    "Retrieve ACTA2 expression across lung cell types in healthy and fibrotic conditions"
    "Cross-reference with single-cell RNA-seq studies annotated with 'lung', 'fibrosis', 'myofibroblast'"

Usage:
    python demo_acta2_fibrosis.py

Output:
    Structured JSON metadata with computed fold changes and supporting evidence.
"""

import os
import re
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

# Import the clients
from clients import SPARQLClient
from clients import NIAIDClient
from clients import CellxGeneClient

# Optional ARCHS4 client (requires large data download)
try:
    from clients import ARCHS4Client
    HAS_ARCHS4 = True
except ImportError:
    HAS_ARCHS4 = False

# Configuration
ARCHS4_DATA_DIR = os.environ.get("ARCHS4_DATA_DIR", "/tmp/archs4")

# =============================================================================
# Output Data Structures
# =============================================================================

@dataclass
class CellTypeExpression:
    """Expression statistics for a cell type."""
    mean_expression: float
    fold_vs_normal: Optional[float] = None
    n_cells: int = 0
    pct_expressing: float = 0.0


@dataclass
class DiseaseContext:
    """Disease-specific expression context."""
    condition: str
    expression_change: str  # "upregulated", "downregulated", "unchanged"
    fold_change: float
    log2_fold_change: float
    p_value: Optional[float]
    evidence_quality: str  # "strong", "moderate", "weak"
    supporting_datasets: List[str]


@dataclass
class DataSourceSummary:
    """Summary of data sources used."""
    single_cell: Dict[str, int]  # n_cells, n_datasets
    bulk_rnaseq: Dict[str, int]  # n_samples, n_studies


@dataclass
class ACTA2FibrosisResult:
    """Complete result for ACTA2 fibrosis query."""
    gene: str
    tissue: str
    gene_info: Dict[str, Any]
    primary_expressing_cells: List[str]
    disease_context: Optional[DiseaseContext]
    cell_type_specificity: Dict[str, CellTypeExpression]
    data_sources: DataSourceSummary
    last_updated: str


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
    print(f"-- {header} " + "-" * (width - len(header) - 4))


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

def extract_geo_accessions(hits: List[Dict[str, Any]]) -> List[str]:
    """Extract GEO accessions (GSE) from NIAID dataset records."""
    geo_pattern = re.compile(r'(GSE\d+)')
    accessions = []
    seen = set()

    for hit in hits:
        # Check various fields where GEO accessions might be stored
        fields_to_check = [
            hit.get("identifier", ""),
            hit.get("url", ""),
            str(hit.get("sameAs", [])),
            str(hit.get("distribution", [])),
        ]

        for field in fields_to_check:
            if isinstance(field, str):
                matches = geo_pattern.findall(field)
                for m in matches:
                    if m not in seen:
                        accessions.append(m)
                        seen.add(m)

    return accessions


def determine_expression_change(fold_change: float) -> str:
    """Determine expression change category from fold change."""
    if fold_change >= 1.5:
        return "upregulated"
    elif fold_change <= 0.67:
        return "downregulated"
    else:
        return "unchanged"


def determine_evidence_quality(n_cells: int, n_datasets: int, p_value: Optional[float]) -> str:
    """Determine evidence quality from data quantity and significance."""
    score = 0

    # Cell count contribution
    if n_cells >= 10000:
        score += 3
    elif n_cells >= 1000:
        score += 2
    elif n_cells >= 100:
        score += 1

    # Dataset count contribution
    if n_datasets >= 5:
        score += 2
    elif n_datasets >= 2:
        score += 1

    # P-value contribution
    if p_value is not None:
        if p_value < 0.001:
            score += 2
        elif p_value < 0.05:
            score += 1

    # Map score to quality
    if score >= 5:
        return "strong"
    elif score >= 3:
        return "moderate"
    else:
        return "weak"


# =============================================================================
# Main Query Function
# =============================================================================

def query_acta2_in_fibrosis(
    gene_symbol: str = "ACTA2",
    tissue: str = "lung",
    disease_condition: str = "pulmonary fibrosis",
) -> ACTA2FibrosisResult:
    """
    Query ACTA2 expression in lung fibrosis across multiple data sources.

    Args:
        gene_symbol: Gene to query (default: ACTA2)
        tissue: Tissue to analyze (default: lung)
        disease_condition: Disease condition to compare against normal

    Returns:
        ACTA2FibrosisResult with comprehensive expression data
    """
    print_header(f"Cross-Layer Query: {gene_symbol} in {tissue.title()} Fibrosis")

    # Initialize result containers
    gene_info = {}
    cell_type_stats = {}
    disease_context = None
    primary_expressing_cells = []
    sc_n_cells = 0
    sc_n_datasets = 0
    bulk_n_samples = 0
    bulk_n_studies = 0
    supporting_datasets = []

    # =========================================================================
    # Step 1: Gene Context (Wikidata via SPARQL)
    # =========================================================================
    print_step(1, "Knowledge Layer (Wikidata)")
    print_result(f"Querying gene information for {gene_symbol}")
    print()

    try:
        sparql = SPARQLClient()
        gene_info = sparql.get_gene_info(gene_symbol)

        if gene_info:
            print_result(f"Gene: {gene_info.get('name', gene_symbol)}")
            print_result(f"Entrez ID: {gene_info.get('entrez_id', 'N/A')}")
            print_result(f"Ensembl ID: {gene_info.get('ensembl_id', 'N/A')}")
            print_result(f"UniProt: {', '.join(gene_info.get('uniprot_ids', [])[:3])}")
            if gene_info.get('go_terms'):
                print_result(f"GO Terms: {len(gene_info['go_terms'])} associated")
        else:
            print_result(f"Gene {gene_symbol} not found in Wikidata")
            gene_info = {"symbol": gene_symbol}
    except Exception as e:
        print_result(f"Error querying Wikidata: {e}")
        gene_info = {"symbol": gene_symbol}

    print()

    # =========================================================================
    # Step 2: Single-Cell Expression (CellxGene Census)
    # =========================================================================
    print_step(2, "Single-Cell Layer (CellxGene Census)")
    print_result(f"Querying {gene_symbol} expression in {tissue} (normal vs {disease_condition})")
    print()

    try:
        with CellxGeneClient() as cellxgene:
            # Get overall comparison between conditions
            comparison = cellxgene.compare_conditions(
                gene_symbol,
                tissue=tissue,
                condition_a="normal",
                condition_b=disease_condition,
            )

            if comparison:
                print_result(f"Normal: mean={comparison.mean_a:.2f} (n={comparison.n_cells_a:,} cells)")
                print_result(f"{disease_condition.title()}: mean={comparison.mean_b:.2f} (n={comparison.n_cells_b:,} cells)")
                print_result(f"Fold Change: {comparison.fold_change:.2f}x (log2={comparison.log2_fold_change:.2f})")
                if comparison.p_value:
                    print_result(f"P-value: {comparison.p_value:.2e}")
                print_result(f"Supporting datasets: {comparison.n_datasets}")

                sc_n_cells = comparison.n_cells_a + comparison.n_cells_b
                sc_n_datasets = comparison.n_datasets
                supporting_datasets.extend(comparison.supporting_datasets)

                # Create disease context
                disease_context = DiseaseContext(
                    condition=disease_condition.replace(" ", "_"),
                    expression_change=determine_expression_change(comparison.fold_change),
                    fold_change=round(comparison.fold_change, 2),
                    log2_fold_change=round(comparison.log2_fold_change, 2),
                    p_value=comparison.p_value,
                    evidence_quality=determine_evidence_quality(
                        sc_n_cells, sc_n_datasets, comparison.p_value
                    ),
                    supporting_datasets=comparison.supporting_datasets[:5],
                )

            # Get cell type-specific expression
            print()
            print_result("Cell type-specific expression:")

            ct_comparison = cellxgene.get_cell_type_comparison(
                gene_symbol,
                tissue=tissue,
                condition_a="normal",
                condition_b=disease_condition,
            )

            if ct_comparison:
                # Sort by fold change
                sorted_cts = sorted(
                    ct_comparison.items(),
                    key=lambda x: x[1]["fold_change"],
                    reverse=True
                )

                for ct, data in sorted_cts[:10]:
                    fc = data["fold_change"]
                    print_subresult(
                        f"{ct}: {fc:.2f}x "
                        f"(normal={data['mean_normal']:.1f}, disease={data['mean_disease']:.1f})"
                    )

                    cell_type_stats[ct] = CellTypeExpression(
                        mean_expression=round(data["mean_disease"], 2),
                        fold_vs_normal=round(fc, 2),
                        n_cells=data["n_cells_normal"] + data["n_cells_disease"],
                        pct_expressing=0.0,  # Would need separate query
                    )

                # Identify primary expressing cells (top by expression in disease)
                primary_expressing_cells = [
                    ct for ct, _ in sorted(
                        ct_comparison.items(),
                        key=lambda x: x[1]["mean_disease"],
                        reverse=True
                    )[:3]
                ]

            else:
                print_result("No cell type-specific data available")

    except ImportError as e:
        print_result(f"CellxGene Census not available: {e}")
        print_result("Install with: pip install cellxgene-census")
    except Exception as e:
        print_result(f"Error querying CellxGene: {e}")

    print()

    # =========================================================================
    # Step 3: Bulk RNA-seq Studies (NIAID)
    # =========================================================================
    print_step(3, "Discovery Layer (NIAID)")
    print_result(f"Searching for {tissue} fibrosis RNA-seq studies")
    print()

    geo_accessions = []
    try:
        niaid = NIAIDClient()
        # Search for lung fibrosis studies in NCBI GEO
        result = niaid.search(
            f'{tissue} fibrosis AND includedInDataCatalog.name:"NCBI GEO"',
            size=50
        )

        print_result(f"Found {result.total} matching studies in NCBI GEO")

        # Extract GEO accessions
        geo_accessions = extract_geo_accessions(result.hits)
        print_result(f"Extracted {len(geo_accessions)} GEO series accessions")
        bulk_n_studies = len(geo_accessions)

        if geo_accessions:
            print()
            print_result("Studies with GEO data:")
            for gse_id in geo_accessions[:5]:
                print_subresult(gse_id)
            if len(geo_accessions) > 5:
                print_subresult(f"... and {len(geo_accessions) - 5} more")

            # Add to supporting datasets
            supporting_datasets.extend(geo_accessions[:10])

    except Exception as e:
        print_result(f"Error querying NIAID: {e}")

    print()

    # =========================================================================
    # Step 4: Bulk Expression Data (ARCHS4) - Optional
    # =========================================================================
    print_step(4, "Data Layer (ARCHS4)")

    if not HAS_ARCHS4:
        print_result("ARCHS4 client not available")
    elif not geo_accessions:
        print_result("No GEO accessions to query")
    else:
        h5_file = Path(ARCHS4_DATA_DIR) / "human_gene_v2.latest.h5"
        if not h5_file.exists():
            print_result(f"ARCHS4 data file not found: {h5_file}")
            print_result("Download with: archs4py.download.counts('human', path=ARCHS4_DATA_DIR)")
        else:
            print_result(f"Checking ARCHS4 for {gene_symbol} expression")
            print()

            try:
                archs4 = ARCHS4Client(organism="human", h5_path=str(h5_file))

                samples_found = 0
                for gse_id in geo_accessions[:10]:
                    if archs4.has_series(gse_id):
                        try:
                            expr_df = archs4.get_expression_by_series(
                                gse_id,
                                genes=[gene_symbol]
                            )
                            if expr_df is not None and not expr_df.empty:
                                n_samples = expr_df.shape[1]
                                mean_expr = expr_df.iloc[0].mean()
                                print_subresult(f"{gse_id}: {n_samples} samples, mean={mean_expr:.1f}")
                                samples_found += n_samples
                                bulk_n_samples += n_samples
                        except Exception:
                            pass

                if samples_found > 0:
                    print_result(f"Total: {samples_found} bulk RNA-seq samples with {gene_symbol}")

            except Exception as e:
                print_result(f"Error querying ARCHS4: {e}")

    print()

    # =========================================================================
    # Build Result
    # =========================================================================
    result = ACTA2FibrosisResult(
        gene=gene_symbol,
        tissue=tissue,
        gene_info=gene_info or {"symbol": gene_symbol},
        primary_expressing_cells=primary_expressing_cells,
        disease_context=disease_context,
        cell_type_specificity=cell_type_stats,
        data_sources=DataSourceSummary(
            single_cell={"n_cells": sc_n_cells, "n_datasets": sc_n_datasets},
            bulk_rnaseq={"n_samples": bulk_n_samples, "n_studies": bulk_n_studies},
        ),
        last_updated=datetime.now().strftime("%Y-%m"),
    )

    return result


def result_to_dict(result: ACTA2FibrosisResult) -> Dict[str, Any]:
    """Convert result to JSON-serializable dict."""
    d = {
        "gene": result.gene,
        "tissue": result.tissue,
        "gene_info": result.gene_info,
        "primary_expressing_cells": result.primary_expressing_cells,
        "disease_context": asdict(result.disease_context) if result.disease_context else None,
        "cell_type_specificity": {
            ct: asdict(expr) for ct, expr in result.cell_type_specificity.items()
        },
        "data_sources": asdict(result.data_sources),
        "last_updated": result.last_updated,
    }
    return d


def print_summary(result: ACTA2FibrosisResult) -> None:
    """Print a summary of the results."""
    print()
    print("-- Summary " + "-" * 68)
    print()

    print(f"  Gene:           {result.gene}")
    print(f"  Tissue:         {result.tissue}")

    if result.gene_info.get("name"):
        print(f"  Full Name:      {result.gene_info['name']}")

    if result.primary_expressing_cells:
        print(f"  Top Cell Types: {', '.join(result.primary_expressing_cells)}")

    if result.disease_context:
        dc = result.disease_context
        print()
        print(f"  Disease:        {dc.condition}")
        print(f"  Expression:     {dc.expression_change} ({dc.fold_change}x)")
        print(f"  Evidence:       {dc.evidence_quality}")
        if dc.p_value:
            print(f"  P-value:        {dc.p_value:.2e}")

    print()
    ds = result.data_sources
    print(f"  Single-cell:    {ds.single_cell['n_cells']:,} cells from {ds.single_cell['n_datasets']} datasets")
    print(f"  Bulk RNA-seq:   {ds.bulk_rnaseq['n_samples']} samples from {ds.bulk_rnaseq['n_studies']} studies")

    print()
    print("=" * 80)


# =============================================================================
# Main
# =============================================================================

def main():
    """Run the ACTA2 fibrosis expression demo."""
    result = query_acta2_in_fibrosis(
        gene_symbol="ACTA2",
        tissue="lung",
        disease_condition="pulmonary fibrosis",
    )

    print_summary(result)

    # Output JSON
    print()
    print("JSON Output:")
    print("-" * 40)
    output = result_to_dict(result)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
