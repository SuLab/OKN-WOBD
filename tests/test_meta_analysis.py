"""Unit tests for the MetaAnalyzer engine."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

# Ensure demos dir is on sys.path
_demos = str(Path(__file__).resolve().parents[1] / "scripts" / "demos")
if _demos not in sys.path:
    sys.path.insert(0, _demos)

from chatgeo.de_result import (
    DEProvenance,
    GeneResult,
    MetaAnalysisResult,
    StudyDEResult,
)
from chatgeo.meta_analysis import MetaAnalyzer
from chatgeo.sample_finder import StudyMatchedResult, StudyPair


def _make_provenance(**overrides):
    defaults = dict(
        query_disease="test_disease",
        query_tissue="test_tissue",
        search_pattern_test="test",
        search_pattern_control="control",
        test_sample_ids=["GSM1", "GSM2"],
        control_sample_ids=["GSM3", "GSM4"],
        test_studies=["GSE001"],
        control_studies=["GSE001"],
        organisms=["human"],
        normalization_method="mann_whitney_u",
        test_method="mann_whitney_u",
        fdr_method="fdr_bh",
        pvalue_threshold=0.01,
        fdr_threshold=0.01,
        log2fc_threshold=2.0,
    )
    defaults.update(overrides)
    return DEProvenance.create(**defaults)


def _make_study_pair(study_id, n_test=5, n_control=5):
    test_df = pd.DataFrame({
        "geo_accession": [f"GSM_T{study_id}_{i}" for i in range(n_test)],
        "series_id": [study_id] * n_test,
        "source_name_ch1": ["disease sample"] * n_test,
    })
    control_df = pd.DataFrame({
        "geo_accession": [f"GSM_C{study_id}_{i}" for i in range(n_control)],
        "series_id": [study_id] * n_control,
        "source_name_ch1": ["healthy control"] * n_control,
    })
    return StudyPair(
        study_id=study_id,
        test_samples=test_df,
        control_samples=control_df,
    )


def _make_study_matched(n_studies=3, n_test=5, n_control=5):
    pairs = [_make_study_pair(f"GSE{i:03d}", n_test, n_control) for i in range(n_studies)]
    return StudyMatchedResult(
        study_pairs=pairs,
        test_query="disease",
        control_query="control",
        total_test_found=n_test * n_studies,
        total_control_found=n_control * n_studies,
        studies_with_test_only=0,
        studies_with_control_only=0,
    )


def _make_expression(n_genes=100, n_samples=5, seed=42):
    """Create a mock expression matrix."""
    rng = np.random.RandomState(seed)
    genes = [f"GENE{i}" for i in range(n_genes)]
    samples = [f"GSM{i}" for i in range(n_samples)]
    data = rng.poisson(lam=100, size=(n_genes, n_samples)).astype(float)
    return pd.DataFrame(data, index=genes, columns=samples)


class TestStoufferCombine:

    def test_consistent_direction_up(self):
        """P-values with consistent upregulation should combine well."""
        pvals = [0.01, 0.02, 0.03]
        log2fcs = [2.0, 1.8, 2.2]
        n_samples = [10, 10, 10]
        combined_p, combined_fc = MetaAnalyzer._stouffer_combine(pvals, log2fcs, n_samples)

        assert combined_p < 0.01
        assert combined_fc > 0

    def test_consistent_direction_down(self):
        """P-values with consistent downregulation should combine well."""
        pvals = [0.01, 0.02, 0.03]
        log2fcs = [-2.0, -1.8, -2.2]
        n_samples = [10, 10, 10]
        combined_p, combined_fc = MetaAnalyzer._stouffer_combine(pvals, log2fcs, n_samples)

        assert combined_p < 0.01
        assert combined_fc < 0

    def test_opposing_directions_weak(self):
        """Mixed directions should produce a weaker (larger) p-value."""
        pvals = [0.01, 0.01, 0.01]
        log2fcs = [2.0, -2.0, 2.0]
        n_samples = [10, 10, 10]
        combined_p, combined_fc = MetaAnalyzer._stouffer_combine(pvals, log2fcs, n_samples)

        # Should be less significant than fully consistent direction
        pvals_consistent = [0.01, 0.01, 0.01]
        log2fcs_consistent = [2.0, 2.0, 2.0]
        consistent_p, _ = MetaAnalyzer._stouffer_combine(pvals_consistent, log2fcs_consistent, n_samples)
        assert combined_p > consistent_p

    def test_sample_size_weighting(self):
        """Larger studies should have more influence."""
        pvals = [0.05, 0.05]
        log2fcs = [2.0, -2.0]
        # First study is much larger
        n_samples_weighted = [100, 10]
        combined_p, combined_fc = MetaAnalyzer._stouffer_combine(
            pvals, log2fcs, n_samples_weighted
        )
        # Combined FC should lean toward first study (positive)
        assert combined_fc > 0

    def test_returns_valid_pvalue(self):
        """Combined p-value should be in (0, 1]."""
        for _ in range(10):
            pvals = list(np.random.uniform(0.001, 0.1, 3))
            log2fcs = list(np.random.uniform(-3, 3, 3))
            n_samples = [10, 20, 15]
            combined_p, _ = MetaAnalyzer._stouffer_combine(pvals, log2fcs, n_samples)
            assert 0 < combined_p <= 1


class TestFisherCombine:

    def test_basic_combination(self):
        """Fisher combination of small p-values should be very small."""
        pvals = [0.01, 0.02, 0.03]
        combined_p = MetaAnalyzer._fisher_combine(pvals)
        assert combined_p < 0.01

    def test_large_pvalues(self):
        """Fisher combination of large p-values should be large."""
        pvals = [0.5, 0.6, 0.7]
        combined_p = MetaAnalyzer._fisher_combine(pvals)
        assert combined_p > 0.1


class TestCombineStudies:

    def test_min_studies_per_gene_filter(self):
        """Genes appearing in < min_studies should be excluded."""
        study1 = StudyDEResult(
            study_id="GSE001",
            n_test_samples=5,
            n_control_samples=5,
            gene_results=[
                GeneResult("GENE_A", 2.5, 100.0, 10.0, 0.001, None, "mann_whitney_u", "up"),
                GeneResult("GENE_B", -3.0, 10.0, 100.0, 0.01, None, "mann_whitney_u", "down"),
            ],
        )
        study2 = StudyDEResult(
            study_id="GSE002",
            n_test_samples=5,
            n_control_samples=5,
            gene_results=[
                GeneResult("GENE_A", 2.0, 80.0, 10.0, 0.005, None, "mann_whitney_u", "up"),
                # GENE_B not in this study
            ],
        )

        analyzer = MetaAnalyzer()
        up, down, n_tested = analyzer._combine_studies(
            [study1, study2], meta_method="stouffer", min_studies_per_gene=2
        )

        # GENE_A should be tested (appears in 2 studies), GENE_B should be excluded (only 1)
        assert n_tested == 1  # Only GENE_A
        all_genes = [g.gene_symbol for g in up + down]
        assert "GENE_A" in all_genes
        assert "GENE_B" not in all_genes

    def test_empty_studies(self):
        """No studies should return empty results."""
        analyzer = MetaAnalyzer()
        up, down, n_tested = analyzer._combine_studies([], meta_method="stouffer")
        assert up == []
        assert down == []
        assert n_tested == 0


class TestMetaAnalyzerEndToEnd:

    @patch.object(MetaAnalyzer, "_run_study_de")
    def test_full_pipeline(self, mock_run_de):
        """End-to-end meta-analysis with mocked per-study DE."""
        # Set up two studies with consistent results
        mock_run_de.side_effect = [
            StudyDEResult(
                study_id="GSE001",
                n_test_samples=5,
                n_control_samples=5,
                gene_results=[
                    GeneResult("GENE_A", 3.0, 200.0, 20.0, 0.001, 0.01, "mann_whitney_u", "up"),
                    GeneResult("GENE_B", -2.5, 10.0, 80.0, 0.005, 0.05, "mann_whitney_u", "down"),
                    GeneResult("GENE_C", 0.5, 50.0, 45.0, 0.3, 0.5, "mann_whitney_u", "up"),
                ],
            ),
            StudyDEResult(
                study_id="GSE002",
                n_test_samples=8,
                n_control_samples=8,
                gene_results=[
                    GeneResult("GENE_A", 2.8, 180.0, 18.0, 0.002, 0.02, "mann_whitney_u", "up"),
                    GeneResult("GENE_B", -2.2, 12.0, 70.0, 0.008, 0.08, "mann_whitney_u", "down"),
                    GeneResult("GENE_C", 0.3, 48.0, 42.0, 0.4, 0.6, "mann_whitney_u", "up"),
                ],
            ),
        ]

        matched = _make_study_matched(n_studies=2)
        provenance = _make_provenance()
        client = MagicMock()

        analyzer = MetaAnalyzer()
        result = analyzer.analyze_study_matched(
            matched, client, provenance,
            meta_method="stouffer",
            min_studies_per_gene=2,
        )

        assert isinstance(result, MetaAnalysisResult)
        assert result.n_studies == 2
        assert result.genes_tested == 3
        assert result.meta_method == "stouffer"

    @patch.object(MetaAnalyzer, "_run_study_de")
    def test_failed_study_skipped(self, mock_run_de):
        """Studies where expression retrieval fails should be skipped."""
        mock_run_de.side_effect = [
            None,  # First study fails
            StudyDEResult(
                study_id="GSE002",
                n_test_samples=5,
                n_control_samples=5,
                gene_results=[
                    GeneResult("GENE_A", 2.0, 100.0, 20.0, 0.01, 0.05, "mann_whitney_u", "up"),
                ],
            ),
            StudyDEResult(
                study_id="GSE003",
                n_test_samples=5,
                n_control_samples=5,
                gene_results=[
                    GeneResult("GENE_A", 2.5, 120.0, 22.0, 0.005, 0.03, "mann_whitney_u", "up"),
                ],
            ),
        ]

        matched = _make_study_matched(n_studies=3)
        provenance = _make_provenance()
        client = MagicMock()

        analyzer = MetaAnalyzer()
        result = analyzer.analyze_study_matched(matched, client, provenance)

        # Only 2 of 3 studies should have produced results
        assert result.n_studies == 2

    @patch.object(MetaAnalyzer, "_run_study_de")
    def test_all_studies_fail(self, mock_run_de):
        """All studies failing should return empty result."""
        mock_run_de.return_value = None

        matched = _make_study_matched(n_studies=3)
        provenance = _make_provenance()
        client = MagicMock()

        analyzer = MetaAnalyzer()
        result = analyzer.analyze_study_matched(matched, client, provenance)

        assert result.n_studies == 0
        assert result.genes_tested == 0
        assert result.combined_upregulated == []
        assert result.combined_downregulated == []

    @patch.object(MetaAnalyzer, "_run_study_de")
    def test_fisher_method(self, mock_run_de):
        """Fisher method should also produce valid results."""
        mock_run_de.side_effect = [
            StudyDEResult(
                study_id="GSE001",
                n_test_samples=5,
                n_control_samples=5,
                gene_results=[
                    GeneResult("GENE_A", 3.0, 200.0, 20.0, 0.001, 0.01, "mann_whitney_u", "up"),
                ],
            ),
            StudyDEResult(
                study_id="GSE002",
                n_test_samples=5,
                n_control_samples=5,
                gene_results=[
                    GeneResult("GENE_A", 2.5, 180.0, 18.0, 0.005, 0.02, "mann_whitney_u", "up"),
                ],
            ),
        ]

        matched = _make_study_matched(n_studies=2)
        provenance = _make_provenance()
        client = MagicMock()

        analyzer = MetaAnalyzer()
        result = analyzer.analyze_study_matched(
            matched, client, provenance, meta_method="fisher"
        )

        assert result.meta_method == "fisher"
        assert result.n_studies == 2


class TestMetaAnalysisResultDict:

    def test_to_dict_format(self):
        """MetaAnalysisResult.to_dict() should include all required fields."""
        provenance = _make_provenance()
        result = MetaAnalysisResult(
            provenance=provenance,
            n_studies=2,
            study_results=[
                StudyDEResult("GSE001", 5, 5, []),
                StudyDEResult("GSE002", 8, 8, []),
            ],
            combined_upregulated=[
                GeneResult("GENE_A", 2.5, 100.0, 10.0, 0.001, 0.01, "meta_stouffer", "up"),
            ],
            combined_downregulated=[
                GeneResult("GENE_B", -3.0, 10.0, 100.0, 0.002, 0.02, "meta_stouffer", "down"),
            ],
            meta_method="stouffer",
            genes_tested=1000,
            genes_significant=2,
            min_studies_per_gene=2,
        )

        d = result.to_dict()
        assert d["mode"] == "study-matched"
        assert d["summary"]["genes_tested"] == 1000
        assert d["summary"]["genes_significant"] == 2
        assert d["meta_analysis"]["n_studies"] == 2
        assert d["meta_analysis"]["method"] == "stouffer"
        assert d["meta_analysis"]["min_studies_per_gene"] == 2
        assert len(d["combined_upregulated"]) == 1
        assert len(d["combined_downregulated"]) == 1
        assert d["combined_upregulated"][0]["gene_symbol"] == "GENE_A"
