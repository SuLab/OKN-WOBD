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

Uses the SOMA API directly for reads (obs, var, X) instead of the
cellxgene_census.get_anndata() convenience function, which hangs
indefinitely in tiledbsoma's C-level code when assembling AnnData objects.

Usage:
    from clients import CellxGeneClient

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

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import warnings

# Attempt to import dependencies
try:
    import cellxgene_census
    HAS_CENSUS = True
except ImportError:
    HAS_CENSUS = False
    cellxgene_census = None

try:
    import pyarrow
    HAS_PYARROW = True
except ImportError:
    HAS_PYARROW = False
    pyarrow = None

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

    Uses the SOMA API directly for all data reads to avoid hangs in
    cellxgene_census.get_anndata().

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

    @property
    def _exp(self):
        """Get the experiment object for the configured organism."""
        return self.census["census_data"][self.organism]

    def close(self):
        """Close the Census connection."""
        if self._census is not None:
            self._census.close()
            self._census = None

    def _build_obs_filter(
        self,
        tissue: Optional[str] = None,
        tissue_ontology_term_id: Optional[str] = None,
        cell_types: Optional[List[str]] = None,
        diseases: Optional[List[str]] = None,
    ) -> str:
        """Build an observation value_filter string from common parameters."""
        filters = ["is_primary_data == True"]

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

        return " and ".join(filters)

    def get_gene_id(self, gene_symbol: str) -> Optional[str]:
        """
        Resolve a gene symbol to its Ensembl ID.

        Args:
            gene_symbol: Gene symbol (e.g., "ACTA2")

        Returns:
            Ensembl gene ID (e.g., "ENSG00000107796") or None if not found
        """
        gene_df = self._exp.ms["RNA"].var.read(
            value_filter=f"feature_name == '{gene_symbol}'",
            column_names=["soma_joinid", "feature_id", "feature_name"],
        ).concat().to_pandas()

        if gene_df.empty:
            return None
        return gene_df.iloc[0]["feature_id"]

    def _get_gene_joinid(self, gene_symbol: str) -> Optional[int]:
        """Get the soma_joinid for a gene symbol."""
        var_df = self._exp.ms["RNA"].var.read(
            value_filter=f"feature_name == '{gene_symbol}'",
            column_names=["soma_joinid"],
        ).concat().to_pandas()

        if var_df.empty:
            return None
        return int(var_df.iloc[0]["soma_joinid"])

    def get_expression_data(
        self,
        gene_symbol: str,
        tissue: Optional[str] = None,
        tissue_ontology_term_id: Optional[str] = None,
        cell_types: Optional[List[str]] = None,
        diseases: Optional[List[str]] = None,
        max_cells: int = 10000,
    ) -> Optional[Tuple[np.ndarray, pd.DataFrame]]:
        """
        Get expression data for a gene with optional filters.

        Uses SOMA API directly: reads obs metadata, var metadata, and
        the X sparse matrix separately, avoiding get_anndata() hangs.

        Args:
            gene_symbol: Gene symbol (e.g., "ACTA2")
            tissue: Tissue to filter by general name (e.g., "lung")
            tissue_ontology_term_id: UBERON ID to filter by (e.g., "UBERON:0000114")
            cell_types: List of cell types to include
            diseases: List of diseases to include
            max_cells: Maximum number of cells to retrieve (default 10000)

        Returns:
            Tuple of (expression_array, obs_dataframe) or None if no data.
            expression_array is a 1-D numpy array of raw counts aligned to obs_dataframe rows.
        """
        try:
            # Step 1: Resolve gene to soma_joinid (fast, ~2s)
            var_joinid = self._get_gene_joinid(gene_symbol)
            if var_joinid is None:
                warnings.warn(f"Gene '{gene_symbol}' not found in Census")
                return None

            # Step 2: Get matching cell metadata with soma_joinid.
            # The obs iterator returns rows in soma_joinid order. We take
            # at most max_cells rows, stopping early to avoid materializing
            # millions of rows for broad queries. Keeping soma_joinids
            # contiguous is critical for fast X matrix reads (tiledb seeks
            # are expensive for scattered IDs).
            #
            # When multiple diseases are specified, we query each disease
            # separately and take cells_per_disease from each so that rare
            # conditions (e.g., fibrosis) aren't drowned out by common ones
            # (e.g., normal).
            obs_columns = ["soma_joinid", "cell_type", "disease", "tissue", "dataset_id", "assay"]

            if diseases and len(diseases) > 1:
                cells_per_disease = max_cells // len(diseases)
                all_obs = []
                for disease in diseases:
                    disease_filter = self._build_obs_filter(
                        tissue=tissue,
                        tissue_ontology_term_id=tissue_ontology_term_id,
                        cell_types=cell_types,
                        diseases=[disease],
                    )
                    obs_iter = self._exp.obs.read(
                        value_filter=disease_filter,
                        column_names=obs_columns,
                    )
                    tables = []
                    n = 0
                    for arrow_table in obs_iter:
                        tables.append(arrow_table)
                        n += len(arrow_table)
                        if n >= cells_per_disease:
                            break
                    if tables:
                        df = pyarrow.concat_tables(tables).to_pandas()
                        all_obs.append(df.iloc[:cells_per_disease])

                if not all_obs:
                    return None
                obs_df = pd.concat(all_obs, ignore_index=True)
            else:
                obs_filter = self._build_obs_filter(
                    tissue=tissue,
                    tissue_ontology_term_id=tissue_ontology_term_id,
                    cell_types=cell_types,
                    diseases=diseases,
                )
                obs_iter = self._exp.obs.read(
                    value_filter=obs_filter,
                    column_names=obs_columns,
                )
                obs_tables = []
                total_rows = 0
                for arrow_table in obs_iter:
                    obs_tables.append(arrow_table)
                    total_rows += len(arrow_table)
                    if total_rows >= max_cells:
                        break

                if not obs_tables:
                    return None
                obs_df = pyarrow.concat_tables(obs_tables).to_pandas()
                if len(obs_df) > max_cells:
                    obs_df = obs_df.iloc[:max_cells]

            if obs_df.empty:
                return None

            # Step 3: Read expression values from X matrix.
            # Sort joinids for optimal tiledb read performance.
            obs_df = obs_df.sort_values("soma_joinid").reset_index(drop=True)
            obs_joinids = obs_df["soma_joinid"].tolist()
            tables = list(
                self._exp.ms["RNA"].X["raw"].read(
                    coords=(obs_joinids, [var_joinid])
                ).tables()
            )

            # Step 5: Build expression array aligned to obs_df rows
            # X read returns sparse (soma_dim_0, soma_dim_1, soma_data) columns
            # for non-zero entries only. We need a dense array matching obs_df order.
            obs_id_to_idx = pd.Series(
                range(len(obs_joinids)), index=obs_joinids
            )
            expr = np.zeros(len(obs_df), dtype=np.float64)

            if tables:
                combined = pyarrow.concat_tables(tables)
                dim0 = combined.column("soma_dim_0").to_numpy()
                data = combined.column("soma_data").to_numpy()
                # Map soma_joinids back to obs_df row positions
                indices = obs_id_to_idx.reindex(dim0).values
                valid = ~np.isnan(indices)
                expr[indices[valid].astype(int)] = data[valid]

            # Keep only the metadata columns callers expect
            keep_cols = [c for c in ["cell_type", "disease", "tissue", "dataset_id", "assay"]
                         if c in obs_df.columns]
            obs_df = obs_df[keep_cols]

            return (expr, obs_df)

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
        result = self.get_expression_data(
            gene_symbol,
            tissue=tissue,
            diseases=diseases,
        )

        if result is None:
            return []

        expr, obs_df = result

        results = []
        for cell_type in obs_df["cell_type"].unique():
            mask = (obs_df["cell_type"] == cell_type).values
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
        result = self.get_expression_data(
            gene_symbol,
            tissue=tissue,
            diseases=[condition_a, condition_b],
        )

        if result is None:
            return None

        expr, obs_df = result

        # Split by condition
        mask_a = (obs_df["disease"] == condition_a).values
        mask_b = (obs_df["disease"] == condition_b).values

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
        datasets = list(obs_df["dataset_id"].unique())

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
        result = self.get_expression_data(
            gene_symbol,
            tissue=tissue,
            tissue_ontology_term_id=tissue_ontology_term_id,
            diseases=[condition_a, condition_b],
        )

        if result is None:
            return {}

        expr, obs_df = result

        results = {}
        for cell_type in obs_df["cell_type"].unique():
            ct_mask = (obs_df["cell_type"] == cell_type).values

            mask_a = ct_mask & (obs_df["disease"] == condition_a).values
            mask_b = ct_mask & (obs_df["disease"] == condition_b).values

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
        obs_filter = self._build_obs_filter(tissue=tissue)

        try:
            obs_df = self._exp.obs.read(
                value_filter=obs_filter,
                column_names=["disease"],
            ).concat().to_pandas()
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
        obs_filter = self._build_obs_filter(tissue=tissue, diseases=[disease] if disease else None)

        try:
            obs_df = self._exp.obs.read(
                value_filter=obs_filter,
                column_names=["cell_type"],
            ).concat().to_pandas()
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
        obs_filter = self._build_obs_filter(tissue=tissue, diseases=[disease] if disease else None)

        try:
            obs_df = self._exp.obs.read(
                value_filter=obs_filter,
                column_names=["dataset_id", "assay", "tissue", "disease"],
            ).concat().to_pandas()

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
