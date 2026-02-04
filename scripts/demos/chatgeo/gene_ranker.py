"""
Gene ranking and prioritization for differential expression results.

Provides multiple ranking strategies and filtering options for
identifying the most significant and biologically relevant genes.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

import numpy as np

from .de_result import DEResult, GeneResult


class RankingMethod(Enum):
    """Methods for ranking genes."""

    EFFECT_SIZE = "effect_size"  # |log2FC|
    PVALUE = "pvalue"  # -log10(p_adj)
    COMBINED = "combined"  # -log10(p_adj) * sign(log2FC)
    VOLCANO = "volcano"  # |log2FC| * -log10(p_adj)


@dataclass
class RankingConfig:
    """Configuration for gene ranking."""

    method: RankingMethod = RankingMethod.COMBINED
    top_n: int = 50
    min_effect_size: float = 0.0  # Additional filter beyond log2fc_threshold
    max_pvalue: float = 1.0  # Additional filter beyond fdr_threshold


class GeneRanker:
    """
    Ranks genes from differential expression analysis.

    Provides multiple ranking strategies optimized for different use cases:
    - EFFECT_SIZE: Best for identifying genes with largest changes
    - PVALUE: Best for finding most statistically confident changes
    - COMBINED: Balanced ranking considering both significance and direction
    - VOLCANO: Similar to combined but emphasizes large, significant changes

    Example:
        ranker = GeneRanker()
        top_genes = ranker.rank_genes(de_result, top_n=20)
        up_genes = ranker.get_top_upregulated(de_result, n=10)
    """

    def __init__(self, config: Optional[RankingConfig] = None):
        """
        Initialize the ranker.

        Args:
            config: Ranking configuration (uses defaults if None)
        """
        self.config = config or RankingConfig()

    def rank_genes(
        self,
        result: DEResult,
        method: Optional[RankingMethod] = None,
        top_n: Optional[int] = None,
    ) -> List[GeneResult]:
        """
        Rank all significant genes from DE result.

        Args:
            result: DEResult from differential expression analysis
            method: Ranking method (uses config default if None)
            top_n: Number of top genes to return (uses config default if None)

        Returns:
            List of top ranked genes (up and down combined)
        """
        method = method or self.config.method
        top_n = top_n or self.config.top_n

        # Combine up and downregulated
        all_significant = result.upregulated + result.downregulated

        # Apply additional filtering
        filtered = self._apply_filters(all_significant)

        # Calculate ranking scores
        scored = [(gene, self._calculate_score(gene, method)) for gene in filtered]

        # Sort by score (descending)
        scored.sort(key=lambda x: x[1], reverse=True)

        return [gene for gene, _ in scored[:top_n]]

    def get_top_upregulated(
        self,
        result: DEResult,
        n: int = 10,
        method: Optional[RankingMethod] = None,
    ) -> List[GeneResult]:
        """
        Get top N upregulated genes.

        Args:
            result: DEResult from differential expression analysis
            n: Number of genes to return
            method: Ranking method

        Returns:
            List of top upregulated genes
        """
        method = method or self.config.method
        filtered = self._apply_filters(result.upregulated)
        scored = [(gene, self._calculate_score(gene, method)) for gene in filtered]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [gene for gene, _ in scored[:n]]

    def get_top_downregulated(
        self,
        result: DEResult,
        n: int = 10,
        method: Optional[RankingMethod] = None,
    ) -> List[GeneResult]:
        """
        Get top N downregulated genes.

        Args:
            result: DEResult from differential expression analysis
            n: Number of genes to return
            method: Ranking method

        Returns:
            List of top downregulated genes
        """
        method = method or self.config.method
        filtered = self._apply_filters(result.downregulated)
        scored = [(gene, self._calculate_score(gene, method)) for gene in filtered]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [gene for gene, _ in scored[:n]]

    def _calculate_score(self, gene: GeneResult, method: RankingMethod) -> float:
        """Calculate ranking score for a gene."""
        log2fc = gene.log2_fold_change
        pvalue = gene.pvalue_adjusted if gene.pvalue_adjusted else 1.0

        # Avoid log(0)
        pvalue = max(pvalue, 1e-300)

        if method == RankingMethod.EFFECT_SIZE:
            return abs(log2fc)

        elif method == RankingMethod.PVALUE:
            return -np.log10(pvalue)

        elif method == RankingMethod.COMBINED:
            # Sign-aware: positive for up, negative for down (then abs for ranking)
            return abs(-np.log10(pvalue) * np.sign(log2fc))

        elif method == RankingMethod.VOLCANO:
            # Product of effect size and significance
            return abs(log2fc) * -np.log10(pvalue)

        return 0.0

    def _apply_filters(self, genes: List[GeneResult]) -> List[GeneResult]:
        """Apply additional filtering based on config."""
        filtered = []
        for gene in genes:
            # Check effect size filter
            if abs(gene.log2_fold_change) < self.config.min_effect_size:
                continue

            # Check p-value filter
            if gene.pvalue_adjusted and gene.pvalue_adjusted > self.config.max_pvalue:
                continue

            filtered.append(gene)

        return filtered

    def calculate_volcano_coordinates(
        self, result: DEResult
    ) -> List[dict]:
        """
        Calculate coordinates for volcano plot visualization.

        Args:
            result: DEResult from differential expression analysis

        Returns:
            List of dicts with gene_symbol, x (log2FC), y (-log10 p_adj), significant
        """
        coords = []
        all_genes = result.all_genes if result.all_genes else (
            result.upregulated + result.downregulated
        )

        for gene in all_genes:
            pvalue = gene.pvalue_adjusted if gene.pvalue_adjusted else 1.0
            pvalue = max(pvalue, 1e-300)

            is_significant = gene in result.upregulated or gene in result.downregulated

            coords.append({
                "gene_symbol": gene.gene_symbol,
                "x": gene.log2_fold_change,
                "y": -np.log10(pvalue),
                "significant": is_significant,
                "direction": gene.direction,
            })

        return coords


def rank_by_combined_score(genes: List[GeneResult]) -> List[GeneResult]:
    """
    Convenience function to rank genes by combined score.

    Args:
        genes: List of GeneResult objects

    Returns:
        Sorted list (most significant first)
    """
    ranker = GeneRanker(RankingConfig(method=RankingMethod.COMBINED))
    scored = [(gene, ranker._calculate_score(gene, RankingMethod.COMBINED)) for gene in genes]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [gene for gene, _ in scored]


def filter_by_thresholds(
    genes: List[GeneResult],
    fdr_threshold: float = 0.05,
    log2fc_threshold: float = 1.0,
) -> List[GeneResult]:
    """
    Filter genes by significance thresholds.

    Args:
        genes: List of GeneResult objects
        fdr_threshold: Maximum adjusted p-value
        log2fc_threshold: Minimum absolute log2 fold change

    Returns:
        Filtered list of genes
    """
    return [
        g for g in genes
        if g.pvalue_adjusted is not None
        and g.pvalue_adjusted < fdr_threshold
        and abs(g.log2_fold_change) >= log2fc_threshold
    ]


def separate_by_direction(
    genes: List[GeneResult],
) -> tuple[List[GeneResult], List[GeneResult]]:
    """
    Separate genes into upregulated and downregulated lists.

    Args:
        genes: List of GeneResult objects

    Returns:
        Tuple of (upregulated, downregulated) lists
    """
    up = [g for g in genes if g.direction == "up"]
    down = [g for g in genes if g.direction == "down"]
    return up, down
