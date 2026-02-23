"""
Meta-analysis engine for combining per-study differential expression results.

Runs DE independently within each GEO study (eliminating batch effects),
then combines results using Stouffer's weighted Z or Fisher's method.

Usage:
    from chatgeo.meta_analysis import MetaAnalyzer
    from chatgeo.sample_finder import SampleFinder

    finder = SampleFinder()
    matched = finder.find_study_matched_samples("psoriasis", tissue="skin")
    analyzer = MetaAnalyzer()
    result = analyzer.analyze_study_matched(matched, client, provenance)
"""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import combine_pvalues

from .de_analysis import DEConfig, DifferentialExpressionAnalyzer, GeneFilterConfig
from .de_result import (
    DEProvenance,
    GeneResult,
    MetaAnalysisResult,
    StudyDEResult,
)
from .sample_finder import StudyMatchedResult, StudyPair

try:
    from statsmodels.stats.multitest import multipletests

    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False

logger = logging.getLogger(__name__)


class MetaAnalyzer:
    """Combine per-study DE results via meta-analysis.

    For each study with matched test/control samples, runs DE independently
    (default: Mann-Whitney U), then combines p-values across studies using
    Stouffer's weighted Z method or Fisher's method.

    Stouffer's method is preferred because it preserves direction information
    (up/down regulation) and allows weighting by sample size.
    """

    def __init__(
        self,
        de_config: Optional[DEConfig] = None,
        gene_biotypes: Optional[pd.Series] = None,
    ):
        self.de_config = de_config or DEConfig(method="mann_whitney_u")
        self.gene_biotypes = gene_biotypes

    def analyze_study_matched(
        self,
        study_matched: StudyMatchedResult,
        client,  # ARCHS4Client
        provenance: DEProvenance,
        meta_method: str = "stouffer",
        min_studies_per_gene: int = 2,
    ) -> MetaAnalysisResult:
        """Run per-study DE and combine via meta-analysis.

        Args:
            study_matched: StudyMatchedResult with list of StudyPairs
            client: ARCHS4Client for expression retrieval
            provenance: DEProvenance for the overall analysis
            meta_method: "stouffer" (default) or "fisher"
            min_studies_per_gene: minimum studies a gene must appear in

        Returns:
            MetaAnalysisResult with combined up/downregulated genes
        """
        logger.info(
            "Starting meta-analysis: %d studies, method=%s, min_studies=%d",
            study_matched.n_studies,
            meta_method,
            min_studies_per_gene,
        )

        # Run per-study DE
        study_results: List[StudyDEResult] = []
        for pair in study_matched.study_pairs:
            study_de = self._run_study_de(pair, client)
            if study_de is not None:
                study_results.append(study_de)
                logger.info(
                    "  %s: %d test, %d control → %d genes tested",
                    pair.study_id,
                    study_de.n_test_samples,
                    study_de.n_control_samples,
                    study_de.n_genes,
                )

        if not study_results:
            logger.warning("No studies produced DE results")
            return MetaAnalysisResult(
                provenance=provenance,
                n_studies=0,
                study_results=[],
                combined_upregulated=[],
                combined_downregulated=[],
                meta_method=meta_method,
                genes_tested=0,
                genes_significant=0,
                min_studies_per_gene=min_studies_per_gene,
            )

        # Combine across studies
        combined_up, combined_down, genes_tested = self._combine_studies(
            study_results,
            meta_method=meta_method,
            min_studies_per_gene=min_studies_per_gene,
        )

        genes_significant = len(combined_up) + len(combined_down)

        logger.info(
            "Meta-analysis complete: %d studies, %d genes tested, "
            "%d significant (%d up, %d down)",
            len(study_results),
            genes_tested,
            genes_significant,
            len(combined_up),
            len(combined_down),
        )

        return MetaAnalysisResult(
            provenance=provenance,
            n_studies=len(study_results),
            study_results=study_results,
            combined_upregulated=combined_up,
            combined_downregulated=combined_down,
            meta_method=meta_method,
            genes_tested=genes_tested,
            genes_significant=genes_significant,
            min_studies_per_gene=min_studies_per_gene,
        )

    def _run_study_de(
        self,
        pair: StudyPair,
        client,
    ) -> Optional[StudyDEResult]:
        """Run DE for a single study pair.

        Returns None if expression retrieval fails.
        """
        try:
            test_expr = client.get_expression_by_samples(pair.test_ids)
            control_expr = client.get_expression_by_samples(pair.control_ids)
        except Exception as e:
            logger.warning(
                "Expression retrieval failed for %s: %s", pair.study_id, e
            )
            return None

        if test_expr is None or test_expr.empty:
            logger.warning("No test expression data for %s", pair.study_id)
            return None
        if control_expr is None or control_expr.empty:
            logger.warning("No control expression data for %s", pair.study_id)
            return None

        # Create a minimal provenance for per-study DE
        study_provenance = DEProvenance.create(
            query_disease=pair.study_id,
            query_tissue=None,
            search_pattern_test="study-matched",
            search_pattern_control="study-matched",
            test_sample_ids=pair.test_ids,
            control_sample_ids=pair.control_ids,
            test_studies=[pair.study_id],
            control_studies=[pair.study_id],
            organisms=["human"],
            normalization_method=self.de_config.method,
            test_method=self.de_config.method,
            fdr_method="fdr_bh",
            pvalue_threshold=1.0,  # no filtering at per-study level
            fdr_threshold=1.0,
            log2fc_threshold=0.0,
        )

        # Use a permissive config for per-study DE (no significance filtering)
        per_study_config = DEConfig(
            method=self.de_config.method,
            fdr_threshold=1.0,  # keep all genes
            log2fc_threshold=0.0,
            min_total_count=self.de_config.min_total_count,
            min_library_size=self.de_config.min_library_size,
            gene_filter=self.de_config.gene_filter,
        )

        analyzer = DifferentialExpressionAnalyzer(
            config=per_study_config,
            gene_biotypes=self.gene_biotypes,
        )

        try:
            result = analyzer.analyze_pooled(test_expr, control_expr, study_provenance)
        except Exception as e:
            logger.warning("DE failed for %s: %s", pair.study_id, e)
            return None

        # Detect platform_id from metadata
        platform_id = None
        if hasattr(pair, "test_samples") and "platform_id" in pair.test_samples.columns:
            platforms = pair.test_samples["platform_id"].dropna().unique()
            if len(platforms) == 1:
                platform_id = str(platforms[0])

        return StudyDEResult(
            study_id=pair.study_id,
            n_test_samples=result.provenance.n_test_samples,
            n_control_samples=result.provenance.n_control_samples,
            gene_results=result.all_genes,
            platform_id=platform_id,
            test_sample_ids=pair.test_ids,
            control_sample_ids=pair.control_ids,
        )

    def _combine_studies(
        self,
        study_results: List[StudyDEResult],
        meta_method: str = "stouffer",
        min_studies_per_gene: int = 2,
    ) -> Tuple[List[GeneResult], List[GeneResult], int]:
        """Combine per-study results into meta-analysis.

        Returns:
            (upregulated, downregulated, genes_tested)
        """
        # Collect per-gene data across studies
        # gene_data[gene] = list of (pvalue, log2fc, n_samples) tuples
        gene_data: Dict[str, List[Tuple[float, float, int, float, float]]] = {}

        for study in study_results:
            n_samples = study.n_test_samples + study.n_control_samples
            for gene in study.gene_results:
                if gene.pvalue is None or np.isnan(gene.pvalue):
                    continue
                if gene.pvalue == 0:
                    # Avoid log(0) in Stouffer; use smallest representable
                    pval = np.finfo(float).tiny
                else:
                    pval = gene.pvalue
                gene_data.setdefault(gene.gene_symbol, []).append(
                    (pval, gene.log2_fold_change, n_samples, gene.mean_test, gene.mean_control)
                )

        # Filter to genes appearing in enough studies
        eligible_genes = {
            g: data
            for g, data in gene_data.items()
            if len(data) >= min_studies_per_gene
        }

        genes_tested = len(eligible_genes)
        if genes_tested == 0:
            return [], [], 0

        # Combine p-values and effect sizes
        combined_results: List[Dict] = []
        raw_pvalues: List[float] = []

        for gene, data in eligible_genes.items():
            pvals = [d[0] for d in data]
            log2fcs = [d[1] for d in data]
            n_samples_list = [d[2] for d in data]
            mean_tests = [d[3] for d in data]
            mean_controls = [d[4] for d in data]

            if meta_method == "stouffer":
                combined_p, combined_log2fc = self._stouffer_combine(
                    pvals, log2fcs, n_samples_list
                )
            else:
                combined_p = self._fisher_combine(pvals)
                # Weighted mean log2FC for Fisher
                weights = [np.sqrt(n) for n in n_samples_list]
                total_w = sum(weights)
                combined_log2fc = sum(
                    w * fc for w, fc in zip(weights, log2fcs)
                ) / total_w

            # Weighted mean of per-group means
            weights = [np.sqrt(n) for n in n_samples_list]
            total_w = sum(weights)
            mean_test = sum(w * m for w, m in zip(weights, mean_tests)) / total_w
            mean_control = sum(w * m for w, m in zip(weights, mean_controls)) / total_w

            combined_results.append({
                "gene_symbol": gene,
                "pvalue": combined_p,
                "log2_fold_change": combined_log2fc,
                "mean_test": mean_test,
                "mean_control": mean_control,
                "direction": "up" if combined_log2fc > 0 else "down",
                "n_studies": len(data),
            })
            raw_pvalues.append(combined_p)

        # FDR correction
        if raw_pvalues and HAS_STATSMODELS:
            _, adjusted, _, _ = multipletests(raw_pvalues, method="fdr_bh")
            for i, r in enumerate(combined_results):
                r["pvalue_adjusted"] = adjusted[i]
        elif raw_pvalues:
            adjusted = np.minimum(np.array(raw_pvalues) * len(raw_pvalues), 1.0)
            for i, r in enumerate(combined_results):
                r["pvalue_adjusted"] = adjusted[i]

        # Build GeneResult objects and filter by significance
        fdr_threshold = self.de_config.fdr_threshold
        log2fc_threshold = self.de_config.log2fc_threshold

        upregulated = []
        downregulated = []

        for r in combined_results:
            padj = r.get("pvalue_adjusted", r["pvalue"])
            gene_result = GeneResult(
                gene_symbol=r["gene_symbol"],
                log2_fold_change=r["log2_fold_change"],
                mean_test=r["mean_test"],
                mean_control=r["mean_control"],
                pvalue=r["pvalue"],
                pvalue_adjusted=padj,
                test_method=f"meta_{meta_method}",
                direction=r["direction"],
            )

            if padj < fdr_threshold and abs(r["log2_fold_change"]) >= log2fc_threshold:
                if r["direction"] == "up":
                    upregulated.append(gene_result)
                else:
                    downregulated.append(gene_result)

        upregulated.sort(key=lambda g: g.log2_fold_change, reverse=True)
        downregulated.sort(key=lambda g: g.log2_fold_change)

        return upregulated, downregulated, genes_tested

    @staticmethod
    def _stouffer_combine(
        pvalues: List[float],
        log2fcs: List[float],
        n_samples: List[float],
    ) -> Tuple[float, float]:
        """Combine p-values using Stouffer's weighted Z method.

        Converts two-sided p-values to signed Z-scores using log2FC direction,
        combines with sqrt(n) weighting, then converts back.

        Returns:
            (combined_pvalue, weighted_mean_log2fc)
        """
        weights = [np.sqrt(n) for n in n_samples]
        total_w = sum(w**2 for w in weights) ** 0.5

        # Convert p-values to signed Z-scores
        z_scores = []
        for p, fc in zip(pvalues, log2fcs):
            # Two-sided p to one-sided z
            z = stats.norm.ppf(1 - p / 2)
            # Apply sign from log2FC direction
            if fc < 0:
                z = -z
            z_scores.append(z)

        # Weighted combination
        combined_z = sum(w * z for w, z in zip(weights, z_scores)) / total_w

        # Convert back to two-sided p-value
        combined_p = 2 * stats.norm.sf(abs(combined_z))
        combined_p = max(combined_p, np.finfo(float).tiny)

        # Weighted mean log2FC
        w_total = sum(weights)
        combined_log2fc = sum(w * fc for w, fc in zip(weights, log2fcs)) / w_total

        return combined_p, combined_log2fc

    @staticmethod
    def _fisher_combine(pvalues: List[float]) -> float:
        """Combine p-values using Fisher's method.

        Returns:
            Combined p-value
        """
        _, combined_p = combine_pvalues(pvalues, method="fisher")
        return max(float(combined_p), np.finfo(float).tiny)
