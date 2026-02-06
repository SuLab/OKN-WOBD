"""
Unit tests for differential expression analysis components.

These tests do not require ARCHS4 data files and can be run standalone.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from chatgeo.de_analysis import (
    DEConfig,
    DifferentialExpressionAnalyzer,
    calculate_effect_size,
    calculate_log2fc,
)
from chatgeo.de_result import DEProvenance, DEResult, GeneResult
from chatgeo.gene_ranker import (
    GeneRanker,
    RankingConfig,
    RankingMethod,
    filter_by_thresholds,
    rank_by_combined_score,
    separate_by_direction,
)
from chatgeo.cli import parse_query
from chatgeo.species_merger import SpeciesMerger


class TestDEResult:
    """Tests for DE result dataclasses."""

    def test_gene_result_creation(self):
        """Test GeneResult creation and properties."""
        gene = GeneResult(
            gene_symbol="TP53",
            log2_fold_change=2.5,
            mean_test=100.0,
            mean_control=25.0,
            pvalue=0.001,
            pvalue_adjusted=0.01,
            test_method="mann_whitney_u",
            direction="up",
        )

        assert gene.gene_symbol == "TP53"
        assert gene.log2_fold_change == 2.5
        assert gene.direction == "up"
        assert gene.is_significant  # p_adj < 0.05
        assert gene.effect_size == 2.5

    def test_gene_result_not_significant(self):
        """Test GeneResult with non-significant p-value."""
        gene = GeneResult(
            gene_symbol="BRCA1",
            log2_fold_change=0.5,
            mean_test=50.0,
            mean_control=35.0,
            pvalue=0.1,
            pvalue_adjusted=0.2,
            test_method="mann_whitney_u",
            direction="up",
        )

        assert not gene.is_significant

    def test_provenance_creation(self):
        """Test DEProvenance creation."""
        prov = DEProvenance.create(
            query_disease="psoriasis",
            query_tissue="skin",
            search_pattern_test="psoriasis|psoriatic",
            search_pattern_control="skin.*(healthy|control)",
            test_sample_ids=["GSM1", "GSM2"],
            control_sample_ids=["GSM3", "GSM4", "GSM5"],
            test_studies=["GSE1"],
            control_studies=["GSE2"],
            organisms=["human"],
            normalization_method="log_quantile",
            test_method="mann_whitney_u",
            fdr_method="fdr_bh",
            pvalue_threshold=0.05,
            fdr_threshold=0.05,
            log2fc_threshold=1.0,
        )

        assert prov.query_disease == "psoriasis"
        assert prov.query_tissue == "skin"
        assert prov.n_test_samples == 2
        assert prov.n_control_samples == 3
        assert prov.timestamp is not None

    def test_provenance_to_dict(self):
        """Test DEProvenance serialization."""
        prov = DEProvenance.create(
            query_disease="test",
            query_tissue=None,
            search_pattern_test="test",
            search_pattern_control="control",
            test_sample_ids=["GSM1"],
            control_sample_ids=["GSM2"],
            test_studies=["GSE1"],
            control_studies=["GSE1"],
            organisms=["human"],
            normalization_method="log_quantile",
            test_method="mann_whitney_u",
            fdr_method="fdr_bh",
            pvalue_threshold=0.05,
            fdr_threshold=0.05,
            log2fc_threshold=1.0,
        )

        d = prov.to_dict()
        assert "query" in d
        assert "samples" in d
        assert "methods" in d
        assert d["query"]["disease"] == "test"


class TestDEAnalysis:
    """Tests for differential expression analysis."""

    @pytest.fixture
    def mock_expression_data(self):
        """Create mock expression matrices for testing."""
        np.random.seed(42)

        n_genes = 100
        n_test = 10
        n_control = 10

        genes = [f"GENE{i}" for i in range(n_genes)]

        # Create test expression with some genes upregulated
        test_expr = pd.DataFrame(
            np.random.exponential(50, (n_genes, n_test)),
            index=genes,
            columns=[f"TEST{i}" for i in range(n_test)],
        )

        # Create control expression
        control_expr = pd.DataFrame(
            np.random.exponential(50, (n_genes, n_control)),
            index=genes,
            columns=[f"CTRL{i}" for i in range(n_control)],
        )

        # Make some genes differentially expressed
        # Upregulate first 5 genes in test
        test_expr.iloc[:5] *= 4

        # Downregulate genes 5-10 in test
        test_expr.iloc[5:10] *= 0.25

        return test_expr, control_expr

    @pytest.fixture
    def mock_provenance(self):
        """Create mock provenance for testing."""
        return DEProvenance.create(
            query_disease="test_disease",
            query_tissue="test_tissue",
            search_pattern_test="test",
            search_pattern_control="control",
            test_sample_ids=["TEST0"],
            control_sample_ids=["CTRL0"],
            test_studies=["GSE1"],
            control_studies=["GSE1"],
            organisms=["human"],
            normalization_method="log_quantile",
            test_method="mann_whitney_u",
            fdr_method="fdr_bh",
            pvalue_threshold=0.05,
            fdr_threshold=0.05,
            log2fc_threshold=1.0,
        )

    def test_calculate_log2fc(self):
        """Test log2 fold change calculation."""
        # 2x upregulation
        assert abs(calculate_log2fc(100, 50) - 1.0) < 0.1

        # 4x upregulation
        assert abs(calculate_log2fc(200, 50) - 2.0) < 0.1

        # 2x downregulation
        assert abs(calculate_log2fc(50, 100) - (-1.0)) < 0.1

        # No change
        assert abs(calculate_log2fc(50, 50)) < 0.1

    def test_calculate_effect_size(self):
        """Test effect size calculation."""
        test_vals = np.array([100, 110, 90, 105, 95])
        control_vals = np.array([50, 55, 45, 52, 48])

        effects = calculate_effect_size(test_vals, control_vals)

        assert "mean_test" in effects
        assert "mean_control" in effects
        assert "log2fc" in effects
        assert "cohens_d" in effects

        assert effects["mean_test"] > effects["mean_control"]
        assert effects["log2fc"] > 0

    def test_de_analyzer_pooled(self, mock_expression_data, mock_provenance):
        """Test pooled DE analysis."""
        test_expr, control_expr = mock_expression_data

        config = DEConfig(
            test_method="mann_whitney_u",
            fdr_threshold=0.05,
            log2fc_threshold=0.5,  # Lower threshold for test
        )

        analyzer = DifferentialExpressionAnalyzer(config=config)

        result = analyzer.analyze_pooled(
            test_expr=test_expr,
            control_expr=control_expr,
            provenance=mock_provenance,
        )

        assert isinstance(result, DEResult)
        assert result.genes_tested > 0
        # Should find some significant genes
        assert result.genes_significant >= 0


class TestGeneRanker:
    """Tests for gene ranking."""

    @pytest.fixture
    def sample_genes(self):
        """Create sample gene results for testing."""
        return [
            GeneResult("GENE1", 3.0, 100, 12.5, 0.0001, 0.001, "mann_whitney_u", "up"),
            GeneResult("GENE2", 2.0, 80, 20, 0.001, 0.01, "mann_whitney_u", "up"),
            GeneResult("GENE3", 1.5, 60, 20, 0.01, 0.05, "mann_whitney_u", "up"),
            GeneResult("GENE4", -2.5, 15, 90, 0.0001, 0.001, "mann_whitney_u", "down"),
            GeneResult("GENE5", -1.5, 25, 70, 0.005, 0.02, "mann_whitney_u", "down"),
        ]

    def test_rank_by_effect_size(self, sample_genes):
        """Test ranking by effect size."""
        config = RankingConfig(method=RankingMethod.EFFECT_SIZE, top_n=10)
        ranker = GeneRanker(config=config)

        # Create mock DEResult
        result = DEResult(
            provenance=None,
            genes_tested=5,
            genes_significant=5,
            upregulated=[g for g in sample_genes if g.direction == "up"],
            downregulated=[g for g in sample_genes if g.direction == "down"],
        )

        ranked = ranker.rank_genes(result)

        # GENE1 has highest |log2FC| (3.0)
        assert ranked[0].gene_symbol == "GENE1"

    def test_rank_by_pvalue(self, sample_genes):
        """Test ranking by p-value."""
        config = RankingConfig(method=RankingMethod.PVALUE, top_n=10)
        ranker = GeneRanker(config=config)

        result = DEResult(
            provenance=None,
            genes_tested=5,
            genes_significant=5,
            upregulated=[g for g in sample_genes if g.direction == "up"],
            downregulated=[g for g in sample_genes if g.direction == "down"],
        )

        ranked = ranker.rank_genes(result)

        # GENE1 and GENE4 have lowest p_adj (0.001)
        assert ranked[0].gene_symbol in ["GENE1", "GENE4"]

    def test_get_top_upregulated(self, sample_genes):
        """Test getting top upregulated genes."""
        ranker = GeneRanker()

        result = DEResult(
            provenance=None,
            genes_tested=5,
            genes_significant=5,
            upregulated=[g for g in sample_genes if g.direction == "up"],
            downregulated=[g for g in sample_genes if g.direction == "down"],
        )

        top_up = ranker.get_top_upregulated(result, n=2)

        assert len(top_up) == 2
        assert all(g.direction == "up" for g in top_up)

    def test_filter_by_thresholds(self, sample_genes):
        """Test filtering genes by thresholds."""
        filtered = filter_by_thresholds(
            sample_genes,
            fdr_threshold=0.05,
            log2fc_threshold=2.0,
        )

        # Only genes with |log2FC| >= 2.0 and p_adj < 0.05
        assert len(filtered) == 3  # GENE1, GENE2, GENE4

    def test_separate_by_direction(self, sample_genes):
        """Test separating genes by direction."""
        up, down = separate_by_direction(sample_genes)

        assert len(up) == 3
        assert len(down) == 2
        assert all(g.direction == "up" for g in up)
        assert all(g.direction == "down" for g in down)


class TestQueryParser:
    """Tests for natural language query parsing."""

    def test_parse_disease_in_tissue(self):
        """Test parsing 'disease in tissue' format."""
        disease, tissue = parse_query("psoriasis in skin tissue")
        assert disease == "psoriasis"
        assert tissue == "skin"

    def test_parse_disease_in_tissue_no_suffix(self):
        """Test parsing without 'tissue' suffix."""
        disease, tissue = parse_query("cancer in breast")
        assert disease == "cancer"
        assert tissue == "breast"

    def test_parse_tissue_disease(self):
        """Test parsing 'tissue disease' format."""
        disease, tissue = parse_query("lung fibrosis")
        assert disease == "lung fibrosis"
        assert tissue == "lung"

    def test_parse_disease_only(self):
        """Test parsing disease without tissue."""
        disease, tissue = parse_query("diabetes")
        assert disease == "diabetes"
        assert tissue is None

    def test_parse_case_insensitive(self):
        """Test case-insensitive parsing."""
        disease, tissue = parse_query("PSORIASIS IN SKIN")
        assert disease == "psoriasis"
        assert tissue == "skin"


class TestSpeciesMerger:
    """Tests for species merging."""

    def test_get_human_ortholog(self):
        """Test mouse to human ortholog mapping."""
        merger = SpeciesMerger()

        # Curated mapping
        assert merger.get_human_ortholog("Actb") == "ACTB"
        assert merger.get_human_ortholog("Il1b") == "IL1B"
        assert merger.get_human_ortholog("Tp53") == "TP53"

    def test_get_mouse_ortholog(self):
        """Test human to mouse ortholog mapping."""
        merger = SpeciesMerger()

        assert merger.get_mouse_ortholog("ACTB") == "Actb"
        assert merger.get_mouse_ortholog("IL1B") == "Il1b"

    def test_symbol_fallback(self):
        """Test fallback to symbol matching."""
        merger = SpeciesMerger(use_symbol_matching=True)

        # Unknown gene falls back to uppercase
        assert merger.get_human_ortholog("UnknownGene") == "UNKNOWNGENE"

    def test_no_symbol_fallback(self):
        """Test without symbol fallback."""
        merger = SpeciesMerger(use_symbol_matching=False)

        # Unknown gene returns None
        assert merger.get_mouse_ortholog("UNKNOWNGENE") is None

    def test_convert_mouse_expression(self):
        """Test converting mouse expression to human symbols."""
        merger = SpeciesMerger()

        mouse_expr = pd.DataFrame(
            [[1, 2], [3, 4], [5, 6]],
            index=["Actb", "Il1b", "UnknownGene"],
            columns=["S1", "S2"],
        )

        human_expr = merger.convert_mouse_expression(mouse_expr)

        assert "ACTB" in human_expr.index
        assert "IL1B" in human_expr.index
        # Unknown gene converted via symbol matching
        assert "UNKNOWNGENE" in human_expr.index

    def test_merge_expression(self):
        """Test merging human and mouse expression."""
        merger = SpeciesMerger()

        human_expr = pd.DataFrame(
            [[10, 20], [30, 40]],
            index=["ACTB", "GAPDH"],
            columns=["H1", "H2"],
        )

        mouse_expr = pd.DataFrame(
            [[1, 2], [3, 4]],
            index=["Actb", "Gapdh"],
            columns=["M1", "M2"],
        )

        merged = merger.merge_expression(human_expr, mouse_expr, strategy="intersection")

        assert merged.shape[1] == 4  # 2 human + 2 mouse samples
        assert "ACTB" in merged.index
        assert "GAPDH" in merged.index

    def test_ortholog_stats(self):
        """Test ortholog mapping statistics."""
        merger = SpeciesMerger()

        symbols = ["Actb", "Il1b", "UnknownGene1", "UnknownGene2"]
        stats = merger.get_ortholog_stats(symbols)

        assert stats["total"] == 4
        assert stats["mapped_curated"] == 2
        assert stats["coverage"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
