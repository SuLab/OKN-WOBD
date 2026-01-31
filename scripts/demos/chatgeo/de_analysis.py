"""
Differential expression analysis engine.

Uses PyDESeq2 (Python implementation of DESeq2) for statistical testing.
DESeq2 handles library-size normalization internally via median-of-ratios,
models count data with a negative binomial distribution, and applies
log2 fold change shrinkage — solving the normalization, variance, and
multiple-testing issues inherent in raw count comparisons.

The pre-processing steps (sample quality filtering, biotype filtering,
ENSG removal) are applied before handing raw integer counts to PyDESeq2.
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from .de_result import DEProvenance, DEResult, GeneResult, StudyDEResult

# Try to import PyDESeq2
try:
    from pydeseq2.dds import DeseqDataSet
    from pydeseq2.ds import DeseqStats

    HAS_PYDESEQ2 = True
except ImportError:
    HAS_PYDESEQ2 = False

# Try to import statsmodels for FDR correction (legacy fallback)
try:
    from statsmodels.stats.multitest import multipletests
    from scipy import stats

    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False


DEMethod = Literal["deseq2", "mann_whitney_u", "welch_t"]


# Default biotypes to keep for standard DE analysis
DEFAULT_BIOTYPES = frozenset({"protein_coding"})

# Biotypes that include all gene categories (no filtering)
ALL_BIOTYPES = None


@dataclass
class GeneFilterConfig:
    """Configuration for gene filtering before DE analysis.

    Controls which genes are included based on biotype annotations from
    the ARCHS4 H5 file (meta/genes/biotype field, Ensembl 107).

    Attributes:
        biotypes: Set of biotype strings to keep (case-insensitive).
            Default is {"protein_coding"} which removes pseudogenes,
            lncRNAs, and other non-coding features that add noise.
            Set to None to disable biotype filtering.
        exclude_mt_genes: If True, remove mitochondrial genes (MT- prefix).
            Set to False when studying mitochondrial diseases.
        exclude_ribosomal: If True, remove ribosomal protein genes (RPS/RPL prefix).
            These are often uninformative housekeeping genes.
    """

    biotypes: Optional[frozenset] = field(default_factory=lambda: frozenset({"protein_coding"}))
    exclude_mt_genes: bool = True
    exclude_ribosomal: bool = False


@dataclass
class DEConfig:
    """Configuration for differential expression analysis.

    The default method is DESeq2, which handles normalization internally
    using the median-of-ratios method and models counts with a negative
    binomial distribution. Raw integer counts should be passed directly.

    Legacy methods (mann_whitney_u, welch_t) are available as fallbacks
    and use log2(CPM+1) normalization.
    """

    # DE method: "deseq2" (recommended), "mann_whitney_u", or "welch_t"
    method: DEMethod = "deseq2"

    # Significance thresholds
    fdr_threshold: float = 0.05
    log2fc_threshold: float = 1.0

    # Minimum raw count sum across all samples for a gene to be tested.
    # DESeq2 pre-filters genes with very low counts automatically, but
    # this threshold removes the most sparse genes upfront.
    min_total_count: int = 10

    # Sample quality filtering: minimum total counts across all genes.
    # ARCHS4 includes all RNA-seq experiments (mRNA, miRNA, small RNA, etc.)
    # and some failed runs. Samples below this threshold are excluded.
    # Standard poly-A RNA-seq yields 10-50M reads; 1M is conservative.
    min_library_size: int = 1_000_000

    # Gene filtering (biotype, MT genes, etc.)
    gene_filter: GeneFilterConfig = field(default_factory=GeneFilterConfig)

    def __post_init__(self):
        """Validate configuration."""
        if self.method == "deseq2" and not HAS_PYDESEQ2:
            print(
                "Warning: pydeseq2 not installed. Install with: pip install pydeseq2"
            )
            print("Falling back to mann_whitney_u")
            self.method = "mann_whitney_u"


class DifferentialExpressionAnalyzer:
    """
    Performs differential expression analysis between test and control groups.

    Default method is PyDESeq2 which expects raw integer counts and handles
    normalization, dispersion estimation, and statistical testing internally.

    Example:
        analyzer = DifferentialExpressionAnalyzer()
        result = analyzer.analyze_pooled(
            test_expr=test_df,       # raw counts (genes x samples)
            control_expr=control_df, # raw counts (genes x samples)
            provenance=provenance
        )
        print(f"Found {result.n_upregulated} upregulated genes")
    """

    def __init__(
        self,
        config: Optional[DEConfig] = None,
        gene_biotypes: Optional[pd.Series] = None,
    ):
        """
        Initialize the analyzer.

        Args:
            config: Analysis configuration (uses defaults if None)
            gene_biotypes: Optional Series mapping gene symbols to biotype
                strings (from ARCHS4 H5 meta/genes/biotype). Required for
                biotype-based filtering.
        """
        self.config = config or DEConfig()
        self.gene_biotypes = gene_biotypes

    def analyze_pooled(
        self,
        test_expr: pd.DataFrame,
        control_expr: pd.DataFrame,
        provenance: DEProvenance,
    ) -> DEResult:
        """
        Perform differential expression analysis on pooled samples.

        Args:
            test_expr: Raw count matrix for test samples (genes x samples)
            control_expr: Raw count matrix for control samples (genes x samples)
            provenance: Provenance information for the analysis

        Returns:
            DEResult with significant upregulated and downregulated genes
        """
        # === Pre-processing: filter samples and genes ===
        test_expr, control_expr = self._preprocess(test_expr, control_expr)

        n_test = test_expr.shape[1]
        n_control = control_expr.shape[1]
        print(f"  Samples after filtering: {n_test} test, {n_control} control")
        print(f"  Genes after filtering: {len(test_expr):,}")

        # === Run DE method ===
        if self.config.method == "deseq2":
            return self._run_deseq2(test_expr, control_expr, provenance)
        else:
            return self._run_legacy(test_expr, control_expr, provenance)

    def _preprocess(
        self,
        test_expr: pd.DataFrame,
        control_expr: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Apply all pre-processing filters to raw count matrices.

        Steps (in order):
        1. Remove low-quality samples (library size < threshold)
        2. Remove ENSEMBL IDs (keep only gene symbols)
        3. Deduplicate gene symbols
        4. Filter by biotype (protein-coding, MT genes, etc.)
        5. Intersect to common gene set
        6. Remove genes with very low total counts
        """
        # 1. Sample quality filter
        test_expr, control_expr = self._filter_low_quality_samples(
            test_expr, control_expr
        )

        # 2. Keep only gene symbols (exclude ENSEMBL IDs starting with ENSG)
        test_expr = test_expr.loc[~test_expr.index.str.startswith("ENSG")]
        control_expr = control_expr.loc[~control_expr.index.str.startswith("ENSG")]

        # 3. Deduplicate gene symbols (keep first occurrence)
        if not test_expr.index.is_unique:
            test_expr = test_expr[~test_expr.index.duplicated(keep="first")]
        if not control_expr.index.is_unique:
            control_expr = control_expr[~control_expr.index.duplicated(keep="first")]

        # 4. Biotype filtering
        test_expr, control_expr = self._filter_by_biotype(test_expr, control_expr)

        # 5. Common genes
        common_genes = sorted(set(test_expr.index) & set(control_expr.index))
        if not common_genes:
            raise ValueError("No common genes between test and control samples")
        test_expr = test_expr.loc[common_genes]
        control_expr = control_expr.loc[common_genes]

        # 6. Remove genes with very low total counts across all samples
        total_counts = test_expr.sum(axis=1) + control_expr.sum(axis=1)
        keep = total_counts[total_counts >= self.config.min_total_count].index
        n_removed = len(test_expr) - len(keep)
        if n_removed > 0:
            print(f"  Low-count filter: removed {n_removed:,} genes (total count < {self.config.min_total_count})")
        test_expr = test_expr.loc[keep]
        control_expr = control_expr.loc[keep]

        return test_expr, control_expr

    def _run_deseq2(
        self,
        test_expr: pd.DataFrame,
        control_expr: pd.DataFrame,
        provenance: DEProvenance,
    ) -> DEResult:
        """Run DESeq2 analysis via PyDESeq2.

        Expects raw integer counts (genes x samples). DESeq2 handles
        normalization (median-of-ratios), dispersion estimation, and
        Wald test internally.
        """
        # Combine into single counts matrix (genes x samples)
        counts = pd.concat([test_expr, control_expr], axis=1)

        # Ensure integer counts (ARCHS4 stores uint32, DESeq2 needs int)
        counts = counts.round().astype(int)

        # Make sample IDs unique (ARCHS4 can return duplicate column names)
        if counts.columns.duplicated().any():
            counts.columns = [f"{c}_{i}" for i, c in enumerate(counts.columns)]

        # Build metadata
        n_test = test_expr.shape[1]
        n_control = control_expr.shape[1]
        sample_ids = list(counts.columns)
        conditions = ["disease"] * n_test + ["control"] * n_control
        metadata = pd.DataFrame(
            {"condition": conditions},
            index=sample_ids,
        )

        print(f"  Running DESeq2 ({n_test} disease vs {n_control} control)...")

        # PyDESeq2 expects (samples x genes)
        dds = DeseqDataSet(
            counts=counts.T,
            metadata=metadata,
            design_factors="condition",
        )
        dds.deseq2()

        # Extract results: disease vs control
        stat_res = DeseqStats(
            dds,
            contrast=["condition", "disease", "control"],
        )
        stat_res.summary()
        results_df = stat_res.results_df

        # Build GeneResult objects
        genes_tested = len(results_df)
        all_gene_results = []
        upregulated = []
        downregulated = []

        for gene_symbol, row in results_df.iterrows():
            log2fc = row.get("log2FoldChange", 0.0)
            pvalue = row.get("pvalue", 1.0)
            padj = row.get("padj", 1.0)

            # Handle NaN values
            if pd.isna(log2fc):
                log2fc = 0.0
            if pd.isna(pvalue):
                pvalue = 1.0
            if pd.isna(padj):
                padj = 1.0

            base_mean = row.get("baseMean", 0.0)
            if pd.isna(base_mean):
                base_mean = 0.0

            direction = "up" if log2fc > 0 else "down"

            # Compute per-group means from the raw counts
            gene_idx = str(gene_symbol)
            if gene_idx in test_expr.index:
                mean_t = float(test_expr.loc[gene_idx].mean())
                mean_c = float(control_expr.loc[gene_idx].mean())
            else:
                mean_t = float(base_mean)
                mean_c = float(base_mean)

            gene_result = GeneResult(
                gene_symbol=gene_idx,
                log2_fold_change=float(log2fc),
                mean_test=mean_t,
                mean_control=mean_c,
                pvalue=float(pvalue),
                pvalue_adjusted=float(padj),
                test_method="deseq2",
                direction=direction,
            )
            all_gene_results.append(gene_result)

            # Filter significant
            if padj < self.config.fdr_threshold and abs(log2fc) >= self.config.log2fc_threshold:
                if direction == "up":
                    upregulated.append(gene_result)
                else:
                    downregulated.append(gene_result)

        # Sort by effect size
        upregulated.sort(key=lambda g: g.log2_fold_change, reverse=True)
        downregulated.sort(key=lambda g: g.log2_fold_change)

        print(f"  DESeq2 complete: {len(upregulated)} up, {len(downregulated)} down")

        return DEResult(
            provenance=provenance,
            genes_tested=genes_tested,
            genes_significant=len(upregulated) + len(downregulated),
            upregulated=upregulated,
            downregulated=downregulated,
            all_genes=all_gene_results,
        )

    def _run_legacy(
        self,
        test_expr: pd.DataFrame,
        control_expr: pd.DataFrame,
        provenance: DEProvenance,
    ) -> DEResult:
        """Legacy DE using Mann-Whitney U or Welch t-test with log2(CPM+1).

        Provided as a fallback when PyDESeq2 is unavailable.
        """
        # Normalize: CPM + log2
        n_test_cols = test_expr.shape[1]
        combined = pd.concat([test_expr, control_expr], axis=1)
        lib_sizes = combined.sum(axis=0)
        cpm = combined.div(lib_sizes, axis=1) * 1e6
        log_expr = np.log2(cpm + 1.0)
        test_norm = log_expr.iloc[:, :n_test_cols]
        control_norm = log_expr.iloc[:, n_test_cols:]

        gene_results = []
        pvalues = []
        genes_tested = []

        for gene in test_norm.index:
            test_values = test_norm.loc[gene].values
            control_values = control_norm.loc[gene].values

            # Skip if too few non-zero values
            if np.sum(test_values > 0) < 3 or np.sum(control_values > 0) < 3:
                continue

            mean_test = np.mean(test_values)
            mean_control = np.mean(control_values)
            log2fc = mean_test - mean_control  # already in log space

            # Statistical test
            if self.config.method == "welch_t":
                try:
                    _, pvalue = stats.ttest_ind(test_values, control_values, equal_var=False)
                except ValueError:
                    pvalue = 1.0
            else:
                try:
                    _, pvalue = stats.mannwhitneyu(test_values, control_values, alternative="two-sided")
                except ValueError:
                    pvalue = 1.0

            if np.isnan(pvalue):
                pvalue = 1.0

            genes_tested.append(gene)
            pvalues.append(pvalue)
            gene_results.append({
                "gene_symbol": gene,
                "log2_fold_change": log2fc,
                "mean_test": mean_test,
                "mean_control": mean_control,
                "pvalue": pvalue,
                "direction": "up" if log2fc > 0 else "down",
            })

        # FDR correction
        if pvalues and HAS_STATSMODELS:
            _, adjusted, _, _ = multipletests(pvalues, method="fdr_bh")
            for i, result in enumerate(gene_results):
                result["pvalue_adjusted"] = adjusted[i]
        elif pvalues:
            adjusted = np.minimum(np.array(pvalues) * len(pvalues), 1.0)
            for i, result in enumerate(gene_results):
                result["pvalue_adjusted"] = adjusted[i]

        all_gene_results = [
            GeneResult(
                gene_symbol=r["gene_symbol"],
                log2_fold_change=r["log2_fold_change"],
                mean_test=r["mean_test"],
                mean_control=r["mean_control"],
                pvalue=r["pvalue"],
                pvalue_adjusted=r.get("pvalue_adjusted"),
                test_method=self.config.method,
                direction=r["direction"],
            )
            for r in gene_results
        ]

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

    def _filter_low_quality_samples(
        self,
        test_expr: pd.DataFrame,
        control_expr: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Remove samples with low total counts (library size).

        ARCHS4 includes all RNA-seq experiments — mRNA-seq, miRNA-seq,
        small RNA-seq, and even failed runs. Samples with very low total
        counts are not standard poly-A RNA-seq and would confound DE.
        """
        min_lib = self.config.min_library_size
        if min_lib <= 0:
            return test_expr, control_expr

        test_lib = test_expr.sum(axis=0)
        ctrl_lib = control_expr.sum(axis=0)

        test_keep = test_lib[test_lib >= min_lib].index
        ctrl_keep = ctrl_lib[ctrl_lib >= min_lib].index

        n_test_removed = test_expr.shape[1] - len(test_keep)
        n_ctrl_removed = control_expr.shape[1] - len(ctrl_keep)

        if n_test_removed > 0 or n_ctrl_removed > 0:
            print(
                f"  Library size filter (>={min_lib:,}): "
                f"removed {n_test_removed} test, {n_ctrl_removed} control samples"
            )

        test_expr = test_expr[test_keep]
        control_expr = control_expr[ctrl_keep]

        if test_expr.shape[1] == 0:
            raise ValueError("No test samples passed library size filter")
        if control_expr.shape[1] == 0:
            raise ValueError("No control samples passed library size filter")

        return test_expr, control_expr

    def _filter_by_biotype(
        self,
        test_expr: pd.DataFrame,
        control_expr: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Filter genes by biotype, MT-gene prefix, and ribosomal prefix.

        Uses gene_biotypes Series (from ARCHS4 H5 meta/genes/biotype) when
        available. Falls back gracefully when biotype data is not provided.

        Filtering is controlled by self.config.gene_filter:
          - biotypes: set of biotype strings to keep (e.g. {"protein_coding"})
          - exclude_mt_genes: remove MT- prefix genes
          - exclude_ribosomal: remove RPS/RPL prefix genes
        """
        gf = self.config.gene_filter
        n_before = len(test_expr)

        # Biotype filtering
        if gf.biotypes is not None and self.gene_biotypes is not None:
            allowed = gf.biotypes
            keep = self.gene_biotypes[
                self.gene_biotypes.str.lower().isin({b.lower() for b in allowed})
            ].index
            test_expr = test_expr.loc[test_expr.index.isin(keep)]
            control_expr = control_expr.loc[control_expr.index.isin(keep)]

        # MT gene filtering
        if gf.exclude_mt_genes:
            mt_mask_t = ~test_expr.index.str.startswith("MT-")
            mt_mask_c = ~control_expr.index.str.startswith("MT-")
            test_expr = test_expr.loc[mt_mask_t]
            control_expr = control_expr.loc[mt_mask_c]

        # Ribosomal protein filtering
        if gf.exclude_ribosomal:
            ribo_t = ~(test_expr.index.str.startswith("RPS") | test_expr.index.str.startswith("RPL"))
            ribo_c = ~(control_expr.index.str.startswith("RPS") | control_expr.index.str.startswith("RPL"))
            test_expr = test_expr.loc[ribo_t]
            control_expr = control_expr.loc[ribo_c]

        n_after = len(test_expr)
        if n_before != n_after:
            print(f"  Gene filter: {n_before:,} → {n_after:,} genes")

        return test_expr, control_expr
