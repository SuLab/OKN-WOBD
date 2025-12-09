#!/usr/bin/env python3
"""
CellxGene Census client for querying single-cell RNA-seq expression data.

CellxGene Census (https://chanzuckerberg.github.io/cellxgene-census/) provides
access to a large corpus of single-cell RNA-seq data with standardized
cell type annotations.

This client provides:
1. Gene expression queries across cell types and tissues
2. Disease condition comparisons (e.g., normal vs fibrotic)
3. Fold change calculations with statistical tests
4. Dataset-level metadata retrieval

Usage:
    from cellxgene_client import CellxGeneClient

    with CellxGeneClient() as client:
        # Get ACTA2 expression in lung cell types
        stats = client.get_cell_type_expression("ACTA2", tissue="lung")

        # Compare normal vs fibrosis
        comparison = client.compare_conditions(
            "ACTA2", tissue="lung",
            condition_a="normal",
            condition_b="pulmonary fibrosis"
        )

Requirements:
    pip install cellxgene-census
"""

from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field
from contextlib import contextmanager
import warnings

# Attempt to import dependencies
try:
    import cellxgene_census
    HAS_CENSUS = True
except ImportError:
    HAS_CENSUS = False
    cellxgene_census = None

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None

try:
    from scipy import stats as scipy_stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    scipy_stats = None


@dataclass
class ExpressionStats:
    """Statistics for gene expression in a cell type or condition."""
    cell_type: str
    n_cells: int
    mean_expression: float
    median_expression: float
    std_expression: float
    pct_expressing: float  # Percentage of cells with non-zero expression
    disease: Optional[str] = None


@dataclass
class ConditionComparison:
    """Result of comparing gene expression between two conditions."""
    gene: str
    tissue: str
    condition_a: str
    condition_b: str
    mean_a: float
    mean_b: float
    fold_change: float
    log2_fold_change: float
    p_value: Optional[float]
    n_cells_a: int
    n_cells_b: int
    n_datasets: int
    supporting_datasets: List[str] = field(default_factory=list)


class CellxGeneClient:
    """
    Client for querying CellxGene Census single-cell RNA-seq data.

    CellxGene Census provides access to millions of cells from hundreds
    of datasets with standardized cell type and disease annotations.

    Example:
        with CellxGeneClient() as client:
            stats = client.get_cell_type_expression("ACTA2", tissue="lung")
            for ct in stats:
                print(f"{ct.cell_type}: {ct.mean_expression:.2f}")
    """

    def __init__(self, organism: str = "homo_sapiens"):
        """
        Initialize the CellxGene Census client.

        Args:
            organism: Organism to query ("homo_sapiens" or "mus_musculus")
        """
        if not HAS_CENSUS:
            raise ImportError(
                "cellxgene-census is required. Install with: pip install cellxgene-census"
            )
        if not HAS_PANDAS:
            raise ImportError("pandas is required. Install with: pip install pandas")

        self.organism = organism
        self._census = None

    def __enter__(self):
        """Open Census connection with specific version to suppress warning."""
        self._census = cellxgene_census.open_soma(census_version="2025-11-08")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close Census connection."""
        if self._census is not None:
            self._census.close()
            self._census = None

    @property
    def census(self):
        """Get the Census connection, opening if necessary."""
        if self._census is None:
            self._census = cellxgene_census.open_soma(census_version="2025-11-08")
        return self._census

    def close(self):
        """Close the Census connection."""
        if self._census is not None:
            self._census.close()
            self._census = None

    def get_gene_id(self, gene_symbol: str) -> Optional[str]:
        """
        Resolve a gene symbol to its Ensembl ID.

        Args:
            gene_symbol: Gene symbol (e.g., "ACTA2")

        Returns:
            Ensembl gene ID (e.g., "ENSG00000107796") or None if not found
        """
        gene_df = cellxgene_census.get_var(
            self.census,
            self.organism,
            value_filter=f"feature_name == '{gene_symbol}'",
            column_names=["feature_id", "feature_name"]
        )

        if gene_df.empty:
            return None
        return gene_df.iloc[0]["feature_id"]

    def get_expression_data(
        self,
        gene_symbol: str,
        tissue: Optional[str] = None,
        tissue_ontology_term_id: Optional[str] = None,
        cell_types: Optional[List[str]] = None,
        diseases: Optional[List[str]] = None,
        max_cells: int = 100000,
    ) -> Optional[Any]:  # Returns AnnData
        """
        Get expression data for a gene with optional filters.

        Args:
            gene_symbol: Gene symbol (e.g., "ACTA2")
            tissue: Tissue to filter by general name (e.g., "lung")
            tissue_ontology_term_id: UBERON ID to filter by (e.g., "UBERON:0000114")
            cell_types: List of cell types to include
            diseases: List of diseases to include
            max_cells: Maximum number of cells to retrieve

        Returns:
            AnnData object with expression and metadata, or None if no data
        """
        # Build observation filter
        filters = ["is_primary_data == True"]

        # Prefer specific ontology term over general tissue name
        if tissue_ontology_term_id:
            filters.append(f"tissue_ontology_term_id == '{tissue_ontology_term_id}'")
        elif tissue:
            filters.append(f"tissue_general == '{tissue}'")

        if cell_types:
            cell_type_filter = " or ".join([f"cell_type == '{ct}'" for ct in cell_types])
            filters.append(f"({cell_type_filter})")

        if diseases:
            disease_filter = " or ".join([f"disease == '{d}'" for d in diseases])
            filters.append(f"({disease_filter})")

        obs_filter = " and ".join(filters)

        try:
            adata = cellxgene_census.get_anndata(
                self.census,
                organism="Homo sapiens" if self.organism == "homo_sapiens" else "Mus musculus",
                var_value_filter=f"feature_name == '{gene_symbol}'",
                obs_value_filter=obs_filter,
                obs_column_names=["cell_type", "disease", "tissue", "dataset_id", "assay"],
            )

            if adata.n_obs == 0:
                return None

            # Limit cells if needed (random sample)
            if adata.n_obs > max_cells:
                indices = np.random.choice(adata.n_obs, max_cells, replace=False)
                adata = adata[indices].copy()

            return adata

        except Exception as e:
            warnings.warn(f"Error fetching expression data: {e}")
            return None

    def get_cell_type_expression(
        self,
        gene_symbol: str,
        tissue: Optional[str] = None,
        diseases: Optional[List[str]] = None,
        min_cells: int = 10,
    ) -> List[ExpressionStats]:
        """
        Get expression statistics per cell type.

        Args:
            gene_symbol: Gene symbol (e.g., "ACTA2")
            tissue: Tissue to filter by
            diseases: List of diseases to include (or None for all)
            min_cells: Minimum cells required per cell type

        Returns:
            List of ExpressionStats objects, one per cell type
        """
        adata = self.get_expression_data(
            gene_symbol,
            tissue=tissue,
            diseases=diseases,
        )

        if adata is None:
            return []

        # Extract expression values
        expr = adata.X.toarray().flatten() if hasattr(adata.X, 'toarray') else np.array(adata.X).flatten()

        results = []
        for cell_type in adata.obs["cell_type"].unique():
            mask = adata.obs["cell_type"] == cell_type
            ct_expr = expr[mask]

            if len(ct_expr) < min_cells:
                continue

            stats = ExpressionStats(
                cell_type=cell_type,
                n_cells=len(ct_expr),
                mean_expression=float(np.mean(ct_expr)),
                median_expression=float(np.median(ct_expr)),
                std_expression=float(np.std(ct_expr)),
                pct_expressing=float(np.sum(ct_expr > 0) / len(ct_expr) * 100),
            )
            results.append(stats)

        # Sort by mean expression descending
        results.sort(key=lambda x: x.mean_expression, reverse=True)
        return results

    def compare_conditions(
        self,
        gene_symbol: str,
        tissue: str,
        condition_a: str = "normal",
        condition_b: str = "pulmonary fibrosis",
        min_cells: int = 50,
    ) -> Optional[ConditionComparison]:
        """
        Compare gene expression between two disease conditions.

        Args:
            gene_symbol: Gene symbol (e.g., "ACTA2")
            tissue: Tissue to analyze (e.g., "lung")
            condition_a: First condition (e.g., "normal")
            condition_b: Second condition (e.g., "pulmonary fibrosis")
            min_cells: Minimum cells required per condition

        Returns:
            ConditionComparison object with fold change and statistics
        """
        adata = self.get_expression_data(
            gene_symbol,
            tissue=tissue,
            diseases=[condition_a, condition_b],
        )

        if adata is None:
            return None

        # Extract expression values
        expr = adata.X.toarray().flatten() if hasattr(adata.X, 'toarray') else np.array(adata.X).flatten()

        # Split by condition
        mask_a = adata.obs["disease"] == condition_a
        mask_b = adata.obs["disease"] == condition_b

        expr_a = expr[mask_a]
        expr_b = expr[mask_b]

        if len(expr_a) < min_cells or len(expr_b) < min_cells:
            return None

        # Calculate statistics
        mean_a = float(np.mean(expr_a))
        mean_b = float(np.mean(expr_b))

        # Fold change with pseudo-count for realistic values when one condition is zero
        pseudo_count = 0.01
        fold_change = (mean_b + pseudo_count) / (mean_a + pseudo_count)
        log2_fc = float(np.log2(fold_change))

        # Statistical test (Mann-Whitney U)
        p_value = None
        if HAS_SCIPY:
            try:
                _, p_value = scipy_stats.mannwhitneyu(
                    expr_a, expr_b, alternative='two-sided'
                )
                p_value = float(p_value)
            except Exception:
                pass

        # Get supporting datasets
        datasets = list(adata.obs["dataset_id"].unique())

        return ConditionComparison(
            gene=gene_symbol,
            tissue=tissue,
            condition_a=condition_a,
            condition_b=condition_b,
            mean_a=mean_a,
            mean_b=mean_b,
            fold_change=fold_change,
            log2_fold_change=log2_fc,
            p_value=p_value,
            n_cells_a=len(expr_a),
            n_cells_b=len(expr_b),
            n_datasets=len(datasets),
            supporting_datasets=datasets[:10],  # Limit to first 10
        )

    def get_cell_type_comparison(
        self,
        gene_symbol: str,
        tissue: Optional[str] = None,
        tissue_ontology_term_id: Optional[str] = None,
        condition_a: str = "normal",
        condition_b: str = "pulmonary fibrosis",
        min_cells: int = 20,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compare gene expression between conditions for each cell type.

        Args:
            gene_symbol: Gene symbol
            tissue: Tissue to analyze by general name (e.g., "lung")
            tissue_ontology_term_id: UBERON ID to filter by (e.g., "UBERON:0000114")
            condition_a: First condition
            condition_b: Second condition
            min_cells: Minimum cells per cell type per condition

        Returns:
            Dict mapping cell type to comparison stats
        """
        adata = self.get_expression_data(
            gene_symbol,
            tissue=tissue,
            tissue_ontology_term_id=tissue_ontology_term_id,
            diseases=[condition_a, condition_b],
        )

        if adata is None:
            return {}

        expr = adata.X.toarray().flatten() if hasattr(adata.X, 'toarray') else np.array(adata.X).flatten()

        results = {}
        for cell_type in adata.obs["cell_type"].unique():
            ct_mask = adata.obs["cell_type"] == cell_type

            mask_a = ct_mask & (adata.obs["disease"] == condition_a)
            mask_b = ct_mask & (adata.obs["disease"] == condition_b)

            expr_a = expr[mask_a]
            expr_b = expr[mask_b]

            if len(expr_a) < min_cells or len(expr_b) < min_cells:
                continue

            mean_a = float(np.mean(expr_a))
            mean_b = float(np.mean(expr_b))
            # Use pseudo-count of 0.01 for more realistic fold changes
            # when one condition has zero expression
            pseudo_count = 0.01
            fold_change = (mean_b + pseudo_count) / (mean_a + pseudo_count)

            results[cell_type] = {
                "mean_normal": mean_a,
                "mean_disease": mean_b,
                "fold_change": fold_change,
                "n_cells_normal": len(expr_a),
                "n_cells_disease": len(expr_b),
            }

        return results

    def get_available_diseases(self, tissue: Optional[str] = None) -> List[str]:
        """
        Get list of available disease annotations.

        Args:
            tissue: Optional tissue filter

        Returns:
            List of disease names
        """
        filters = ["is_primary_data == True"]
        if tissue:
            filters.append(f"tissue_general == '{tissue}'")

        obs_filter = " and ".join(filters)

        try:
            obs_df = cellxgene_census.get_obs(
                self.census,
                self.organism,
                value_filter=obs_filter,
                column_names=["disease"]
            )
            return sorted(obs_df["disease"].unique().tolist())
        except Exception:
            return []

    def get_available_cell_types(
        self,
        tissue: Optional[str] = None,
        disease: Optional[str] = None,
    ) -> List[str]:
        """
        Get list of available cell type annotations.

        Args:
            tissue: Optional tissue filter
            disease: Optional disease filter

        Returns:
            List of cell type names
        """
        filters = ["is_primary_data == True"]
        if tissue:
            filters.append(f"tissue_general == '{tissue}'")
        if disease:
            filters.append(f"disease == '{disease}'")

        obs_filter = " and ".join(filters)

        try:
            obs_df = cellxgene_census.get_obs(
                self.census,
                self.organism,
                value_filter=obs_filter,
                column_names=["cell_type"]
            )
            return sorted(obs_df["cell_type"].unique().tolist())
        except Exception:
            return []

    def get_dataset_info(
        self,
        tissue: Optional[str] = None,
        disease: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get information about datasets matching filters.

        Args:
            tissue: Optional tissue filter
            disease: Optional disease filter

        Returns:
            List of dataset info dicts
        """
        filters = ["is_primary_data == True"]
        if tissue:
            filters.append(f"tissue_general == '{tissue}'")
        if disease:
            filters.append(f"disease == '{disease}'")

        obs_filter = " and ".join(filters)

        try:
            obs_df = cellxgene_census.get_obs(
                self.census,
                self.organism,
                value_filter=obs_filter,
                column_names=["dataset_id", "assay", "tissue", "disease"]
            )

            # Aggregate by dataset
            datasets = []
            for dataset_id in obs_df["dataset_id"].unique():
                ds_df = obs_df[obs_df["dataset_id"] == dataset_id]
                datasets.append({
                    "dataset_id": dataset_id,
                    "n_cells": len(ds_df),
                    "assays": list(ds_df["assay"].unique()),
                    "tissues": list(ds_df["tissue"].unique()),
                    "diseases": list(ds_df["disease"].unique()),
                })

            return datasets
        except Exception:
            return []


def demo():
    """Demonstrate CellxGene client capabilities."""
    print("=" * 70)
    print("CellxGene Census Client Demo")
    print("=" * 70)

    print("\nConnecting to CellxGene Census...")

    try:
        with CellxGeneClient() as client:
            print("Connected successfully!")

            # Demo 1: Get cell types expressing ACTA2 in lung
            print("\n" + "-" * 70)
            print("1. ACTA2 Expression by Cell Type in Lung")
            print("-" * 70)

            stats = client.get_cell_type_expression("ACTA2", tissue="lung")
            print(f"Found {len(stats)} cell types")
            for s in stats[:10]:
                print(f"  {s.cell_type}: mean={s.mean_expression:.2f}, "
                      f"n={s.n_cells}, {s.pct_expressing:.1f}% expressing")

            # Demo 2: Compare normal vs fibrosis
            print("\n" + "-" * 70)
            print("2. ACTA2: Normal vs Pulmonary Fibrosis")
            print("-" * 70)

            comparison = client.compare_conditions(
                "ACTA2",
                tissue="lung",
                condition_a="normal",
                condition_b="pulmonary fibrosis"
            )

            if comparison:
                print(f"  Normal: mean={comparison.mean_a:.2f} (n={comparison.n_cells_a})")
                print(f"  Fibrosis: mean={comparison.mean_b:.2f} (n={comparison.n_cells_b})")
                print(f"  Fold change: {comparison.fold_change:.2f}x")
                print(f"  Log2 FC: {comparison.log2_fold_change:.2f}")
                if comparison.p_value:
                    print(f"  P-value: {comparison.p_value:.2e}")
                print(f"  Supporting datasets: {comparison.n_datasets}")
            else:
                print("  Insufficient data for comparison")

            # Demo 3: Cell type-specific fold changes
            print("\n" + "-" * 70)
            print("3. Cell Type-Specific ACTA2 Changes in Fibrosis")
            print("-" * 70)

            ct_comparison = client.get_cell_type_comparison(
                "ACTA2",
                tissue="lung",
                condition_a="normal",
                condition_b="pulmonary fibrosis"
            )

            for ct, data in sorted(ct_comparison.items(),
                                   key=lambda x: x[1]["fold_change"],
                                   reverse=True)[:10]:
                print(f"  {ct}: {data['fold_change']:.2f}x "
                      f"(normal={data['mean_normal']:.1f}, disease={data['mean_disease']:.1f})")

    except ImportError as e:
        print(f"Error: {e}")
        print("\nInstall required packages:")
        print("  pip install cellxgene-census")
    except Exception as e:
        print(f"Error: {e}")

    print("\n" + "=" * 70)
    print("Demo complete!")
    print("=" * 70)


if __name__ == "__main__":
    demo()
