"""
Differential expression analysis engine.

Provides statistical testing, normalization, and FDR correction for
comparing gene expression between test and control sample groups.
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from .de_result import DEProvenance, DEResult, GeneResult, StudyDEResult

# Try to import statsmodels for FDR correction
try:
    from statsmodels.stats.multitest import multipletests

    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False


TestMethod = Literal["mann_whitney_u", "welch_t", "student_t"]
FDRMethod = Literal["fdr_bh", "bonferroni", "holm"]
NormMethod = Literal["log_quantile", "log2", "cpm", "none"]


@dataclass
class DEConfig:
    """Configuration for differential expression analysis."""

    # Statistical test
    test_method: TestMethod = "mann_whitney_u"

    # Multiple testing correction
    fdr_method: FDRMethod = "fdr_bh"

    # Normalization (applied before DE if not already normalized)
    normalization: NormMethod = "log_quantile"

    # Significance thresholds
    pvalue_threshold: float = 0.05
    fdr_threshold: float = 0.05
    log2fc_threshold: float = 1.0

    # Filtering
    min_expression: float = 1.0  # Minimum mean expression to test gene
    min_samples_expressed: int = 3  # Minimum samples where gene is expressed
    pseudocount: float = 1.0  # Added before log transform

    def __post_init__(self):
        """Validate configuration."""
        if not HAS_STATSMODELS and self.fdr_method != "bonferroni":
            print(
                "Warning: statsmodels not available, falling back to Bonferroni correction"
            )
            self.fdr_method = "bonferroni"


class DifferentialExpressionAnalyzer:
    """
    Performs differential expression analysis between test and control groups.

    Supports both pooled mode (all samples in single comparison) and
    study-matched mode (within-study comparisons followed by meta-analysis).

    Example:
        analyzer = DifferentialExpressionAnalyzer()
        result = analyzer.analyze_pooled(
            test_expr=test_df,
            control_expr=control_df,
            provenance=provenance
        )
        print(f"Found {result.n_upregulated} upregulated genes")
    """

    def __init__(self, config: Optional[DEConfig] = None):
        """
        Initialize the analyzer.

        Args:
            config: Analysis configuration (uses defaults if None)
        """
        self.config = config or DEConfig()

    def analyze_pooled(
        self,
        test_expr: pd.DataFrame,
        control_expr: pd.DataFrame,
        provenance: DEProvenance,
        normalize: bool = True,
    ) -> DEResult:
        """
        Perform differential expression analysis on pooled samples.

        Args:
            test_expr: Expression matrix for test samples (genes x samples)
            control_expr: Expression matrix for control samples (genes x samples)
            provenance: Provenance information for the analysis
            normalize: Whether to apply normalization

        Returns:
            DEResult with significant upregulated and downregulated genes
        """
        # Filter to keep only gene symbols (exclude ENSEMBL IDs which start with ENSG)
        # ARCHS4 data contains a mix of gene symbols and ENSEMBL IDs
        test_gene_mask = ~test_expr.index.str.startswith('ENSG')
        control_gene_mask = ~control_expr.index.str.startswith('ENSG')
        test_expr = test_expr.loc[test_gene_mask]
        control_expr = control_expr.loc[control_gene_mask]

        # Handle duplicate gene symbols by keeping the first occurrence
        # (ARCHS4 data may have duplicate gene symbols for different transcripts)
        if not test_expr.index.is_unique:
            test_expr = test_expr[~test_expr.index.duplicated(keep='first')]
        if not control_expr.index.is_unique:
            control_expr = control_expr[~control_expr.index.duplicated(keep='first')]

        # Ensure both DataFrames have the same genes
        common_genes = list(set(test_expr.index) & set(control_expr.index))
        if not common_genes:
            raise ValueError("No common genes between test and control samples")

        test_expr = test_expr.loc[common_genes]
        control_expr = control_expr.loc[common_genes]

        # Apply normalization if requested
        if normalize and self.config.normalization != "none":
            test_expr = self._normalize(test_expr)
            control_expr = self._normalize(control_expr)

        # Filter low-expression genes
        test_expr, control_expr = self._filter_low_expression(test_expr, control_expr)

        if len(test_expr) == 0:
            raise ValueError("No genes passed expression filtering")

        # Calculate statistics for each gene
        gene_results = []
        pvalues = []
        genes_tested = []

        for gene in test_expr.index:
            test_values = test_expr.loc[gene].values
            control_values = control_expr.loc[gene].values

            # Skip if too few non-zero values
            if (
                np.sum(test_values > 0) < self.config.min_samples_expressed
                or np.sum(control_values > 0) < self.config.min_samples_expressed
            ):
                continue

            # Calculate means
            mean_test = np.mean(test_values)
            mean_control = np.mean(control_values)

            # Calculate log2 fold change with pseudocount
            log2fc = np.log2(
                (mean_test + self.config.pseudocount)
                / (mean_control + self.config.pseudocount)
            )

            # Perform statistical test
            pvalue = self._perform_test(test_values, control_values)

            genes_tested.append(gene)
            pvalues.append(pvalue)

            gene_results.append(
                {
                    "gene_symbol": gene,
                    "log2_fold_change": log2fc,
                    "mean_test": mean_test,
                    "mean_control": mean_control,
                    "pvalue": pvalue,
                    "direction": "up" if log2fc > 0 else "down",
                }
            )

        # Apply FDR correction
        if pvalues:
            adjusted_pvalues = self._correct_pvalues(pvalues)
            for i, result in enumerate(gene_results):
                result["pvalue_adjusted"] = adjusted_pvalues[i]

        # Create GeneResult objects and filter significant ones
        all_gene_results = [
            GeneResult(
                gene_symbol=r["gene_symbol"],
                log2_fold_change=r["log2_fold_change"],
                mean_test=r["mean_test"],
                mean_control=r["mean_control"],
                pvalue=r["pvalue"],
                pvalue_adjusted=r.get("pvalue_adjusted"),
                test_method=self.config.test_method,
                direction=r["direction"],
            )
            for r in gene_results
        ]

        # Filter significant genes
        upregulated = []
        downregulated = []

        for gene in all_gene_results:
            if gene.pvalue_adjusted is None:
                continue
            if (
                gene.pvalue_adjusted < self.config.fdr_threshold
                and abs(gene.log2_fold_change) >= self.config.log2fc_threshold
            ):
                if gene.direction == "up":
                    upregulated.append(gene)
                else:
                    downregulated.append(gene)

        # Sort by effect size
        upregulated.sort(key=lambda g: g.log2_fold_change, reverse=True)
        downregulated.sort(key=lambda g: g.log2_fold_change)

        return DEResult(
            provenance=provenance,
            genes_tested=len(genes_tested),
            genes_significant=len(upregulated) + len(downregulated),
            upregulated=upregulated,
            downregulated=downregulated,
            all_genes=all_gene_results,
        )

    def analyze_study_matched(
        self,
        study_pairs: List[Tuple[str, pd.DataFrame, pd.DataFrame]],
        provenance: DEProvenance,
        normalize: bool = True,
    ) -> List[StudyDEResult]:
        """
        Perform within-study DE analysis for multiple studies.

        Args:
            study_pairs: List of (study_id, test_expr, control_expr) tuples
            provenance: Provenance information
            normalize: Whether to apply normalization

        Returns:
            List of StudyDEResult objects
        """
        results = []

        for study_id, test_expr, control_expr in study_pairs:
            # Filter to keep only gene symbols (exclude ENSEMBL IDs)
            test_gene_mask = ~test_expr.index.str.startswith('ENSG')
            control_gene_mask = ~control_expr.index.str.startswith('ENSG')
            test_expr = test_expr.loc[test_gene_mask]
            control_expr = control_expr.loc[control_gene_mask]

            # Handle duplicate gene symbols by keeping the first occurrence
            if not test_expr.index.is_unique:
                test_expr = test_expr[~test_expr.index.duplicated(keep='first')]
            if not control_expr.index.is_unique:
                control_expr = control_expr[~control_expr.index.duplicated(keep='first')]

            # Find common genes
            common_genes = list(set(test_expr.index) & set(control_expr.index))
            if not common_genes:
                continue

            test_expr = test_expr.loc[common_genes]
            control_expr = control_expr.loc[common_genes]

            if normalize and self.config.normalization != "none":
                test_expr = self._normalize(test_expr)
                control_expr = self._normalize(control_expr)

            gene_results = []
            pvalues = []
            genes_tested = []

            for gene in test_expr.index:
                test_values = test_expr.loc[gene].values
                control_values = control_expr.loc[gene].values

                mean_test = np.mean(test_values)
                mean_control = np.mean(control_values)

                log2fc = np.log2(
                    (mean_test + self.config.pseudocount)
                    / (mean_control + self.config.pseudocount)
                )

                pvalue = self._perform_test(test_values, control_values)

                genes_tested.append(gene)
                pvalues.append(pvalue)

                gene_results.append(
                    {
                        "gene_symbol": gene,
                        "log2_fold_change": log2fc,
                        "mean_test": mean_test,
                        "mean_control": mean_control,
                        "pvalue": pvalue,
                        "direction": "up" if log2fc > 0 else "down",
                    }
                )

            # FDR correction within study
            if pvalues:
                adjusted_pvalues = self._correct_pvalues(pvalues)
                for i, result in enumerate(gene_results):
                    result["pvalue_adjusted"] = adjusted_pvalues[i]

            study_gene_results = [
                GeneResult(
                    gene_symbol=r["gene_symbol"],
                    log2_fold_change=r["log2_fold_change"],
                    mean_test=r["mean_test"],
                    mean_control=r["mean_control"],
                    pvalue=r["pvalue"],
                    pvalue_adjusted=r.get("pvalue_adjusted"),
                    test_method=self.config.test_method,
                    direction=r["direction"],
                )
                for r in gene_results
            ]

            results.append(
                StudyDEResult(
                    study_id=study_id,
                    n_test_samples=test_expr.shape[1],
                    n_control_samples=control_expr.shape[1],
                    gene_results=study_gene_results,
                )
            )

        return results

    def _normalize(self, expr: pd.DataFrame) -> pd.DataFrame:
        """Apply normalization to expression matrix."""
        if self.config.normalization == "log2":
            return np.log2(expr + self.config.pseudocount)

        elif self.config.normalization == "cpm":
            # Counts per million
            lib_sizes = expr.sum(axis=0)
            return expr.div(lib_sizes, axis=1) * 1e6

        elif self.config.normalization == "log_quantile":
            # Log2 transform then quantile normalize
            log_expr = np.log2(expr + self.config.pseudocount)
            return self._quantile_normalize(log_expr)

        return expr

    def _quantile_normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """Quantile normalize expression matrix."""
        # Rank each column
        rank_mean = df.stack().groupby(df.rank(method="first").stack().astype(int)).mean()

        # Replace values with rank means
        normalized = df.rank(method="min").stack().astype(int).map(rank_mean).unstack()
        return normalized

    def _filter_low_expression(
        self, test_expr: pd.DataFrame, control_expr: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Filter genes with low expression."""
        # Combine for filtering decision
        combined_mean = (test_expr.mean(axis=1) + control_expr.mean(axis=1)) / 2

        # Keep genes above minimum expression
        keep_genes = combined_mean[combined_mean >= self.config.min_expression].index

        return test_expr.loc[keep_genes], control_expr.loc[keep_genes]

    def _perform_test(
        self, test_values: np.ndarray, control_values: np.ndarray
    ) -> float:
        """Perform statistical test between two groups."""
        # Remove NaN values
        test_values = test_values[~np.isnan(test_values)]
        control_values = control_values[~np.isnan(control_values)]

        if len(test_values) < 2 or len(control_values) < 2:
            return 1.0

        if self.config.test_method == "mann_whitney_u":
            try:
                _, pvalue = stats.mannwhitneyu(
                    test_values, control_values, alternative="two-sided"
                )
            except ValueError:
                pvalue = 1.0

        elif self.config.test_method == "welch_t":
            try:
                _, pvalue = stats.ttest_ind(
                    test_values, control_values, equal_var=False
                )
            except ValueError:
                pvalue = 1.0

        elif self.config.test_method == "student_t":
            try:
                _, pvalue = stats.ttest_ind(
                    test_values, control_values, equal_var=True
                )
            except ValueError:
                pvalue = 1.0

        else:
            raise ValueError(f"Unknown test method: {self.config.test_method}")

        return pvalue if not np.isnan(pvalue) else 1.0

    def _correct_pvalues(self, pvalues: List[float]) -> List[float]:
        """Apply multiple testing correction."""
        pvalues = np.array(pvalues)

        if self.config.fdr_method == "bonferroni":
            adjusted = np.minimum(pvalues * len(pvalues), 1.0)

        elif HAS_STATSMODELS:
            _, adjusted, _, _ = multipletests(pvalues, method=self.config.fdr_method)

        else:
            # Fallback to Bonferroni
            adjusted = np.minimum(pvalues * len(pvalues), 1.0)

        return list(adjusted)


def calculate_log2fc(
    mean_test: float, mean_control: float, pseudocount: float = 1.0
) -> float:
    """
    Calculate log2 fold change with pseudocount.

    Args:
        mean_test: Mean expression in test group
        mean_control: Mean expression in control group
        pseudocount: Value added to prevent log(0)

    Returns:
        Log2 fold change (positive = upregulated in test)
    """
    return np.log2((mean_test + pseudocount) / (mean_control + pseudocount))


def calculate_effect_size(
    test_values: np.ndarray, control_values: np.ndarray
) -> Dict[str, float]:
    """
    Calculate multiple effect size metrics.

    Args:
        test_values: Expression values in test group
        control_values: Expression values in control group

    Returns:
        Dictionary with effect size metrics
    """
    mean_test = np.mean(test_values)
    mean_control = np.mean(control_values)
    std_test = np.std(test_values, ddof=1)
    std_control = np.std(control_values, ddof=1)

    # Pooled standard deviation for Cohen's d
    n_test = len(test_values)
    n_control = len(control_values)
    pooled_std = np.sqrt(
        ((n_test - 1) * std_test**2 + (n_control - 1) * std_control**2)
        / (n_test + n_control - 2)
    )

    cohens_d = (mean_test - mean_control) / pooled_std if pooled_std > 0 else 0

    return {
        "mean_test": mean_test,
        "mean_control": mean_control,
        "log2fc": calculate_log2fc(mean_test, mean_control),
        "cohens_d": cohens_d,
        "std_test": std_test,
        "std_control": std_control,
    }
