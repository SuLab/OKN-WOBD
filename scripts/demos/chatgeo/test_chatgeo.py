"""
Test suite for chatgeo ARCHS4 sample finder component.

Run unit tests (no ARCHS4 required):
    cd scripts/demos && python -m pytest chatgeo/test_chatgeo.py::TestQueryBuilder -v

Run integration tests (requires ARCHS4_DATA_DIR):
    export ARCHS4_DATA_DIR=/path/to/archs4
    cd scripts/demos && python -m pytest chatgeo/test_chatgeo.py -v

Run demo:
    cd scripts/demos && python chatgeo/test_chatgeo.py --demo
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from .query_builder import (
    QueryBuilder,
    QueryExpansion,
    TextQueryStrategy,
    PatternQueryStrategy,
    OntologyQueryStrategy,
)
from .sample_finder import (
    SampleFinder,
    SampleSet,
    TestControlPair,
    PooledPair,
    StudyPair,
    StudyMatchedResult,
)
from .study_grouper import StudyGrouper, StudyGroup
from .metrics import SearchMetrics, SearchStats, PairQualityMetrics


class TestQueryBuilder(unittest.TestCase):
    """Unit tests for query expansion (no ARCHS4 required)."""

    def test_text_query_no_expansion(self):
        """Baseline text strategy returns term unchanged."""
        strategy = TextQueryStrategy()
        builder = QueryBuilder(strategy=strategy)

        expansion = builder.get_expansion_info("pulmonary fibrosis")

        self.assertEqual(expansion.original_term, "pulmonary fibrosis")
        self.assertEqual(expansion.expanded_terms, ["pulmonary fibrosis"])
        self.assertEqual(expansion.strategy_name, "text")

    def test_pattern_expansion_lung(self):
        """Pattern strategy expands lung-related terms."""
        strategy = PatternQueryStrategy()
        builder = QueryBuilder(strategy=strategy)

        expansion = builder.get_expansion_info("lung")

        self.assertIn("lung", expansion.expanded_terms)
        self.assertIn("pulmonary", expansion.expanded_terms)
        self.assertIn("respiratory", expansion.expanded_terms)
        self.assertEqual(expansion.strategy_name, "pattern")

    def test_pattern_expansion_fibrosis(self):
        """Pattern strategy expands fibrosis-related terms."""
        strategy = PatternQueryStrategy()
        expansion = strategy.expand("fibrosis")

        self.assertIn("fibrosis", expansion.expanded_terms)
        self.assertIn("fibrotic", expansion.expanded_terms)
        self.assertIn("scarring", expansion.expanded_terms)

    def test_pattern_expansion_compound_term(self):
        """Pattern strategy handles compound terms."""
        strategy = PatternQueryStrategy()
        expansion = strategy.expand("pulmonary fibrosis")

        # Should expand both "pulmonary" (via lung pattern) and "fibrosis"
        self.assertIn("pulmonary fibrosis", expansion.all_terms)
        # The pattern should find lung-related terms
        all_terms_str = " ".join(expansion.all_terms)
        self.assertTrue(
            "lung" in all_terms_str or "pulmonary" in all_terms_str
        )

    def test_expansion_to_regex(self):
        """Expansion converts to regex pattern correctly."""
        expansion = QueryExpansion(
            original_term="lung",
            expanded_terms=["lung", "pulmonary", "respiratory"],
            strategy_name="pattern",
        )

        regex = expansion.to_regex()
        self.assertIn("lung", regex)
        self.assertIn("pulmonary", regex)
        self.assertIn("|", regex)

    def test_build_disease_query(self):
        """Build disease query uses expansion."""
        builder = QueryBuilder(strategy=PatternQueryStrategy())
        pattern = builder.build_disease_query("lung cancer")

        self.assertIn("cancer", pattern)
        self.assertIn("|", pattern)

    def test_build_control_query_with_tissue(self):
        """Build control query combines tissue and control keywords."""
        builder = QueryBuilder(strategy=PatternQueryStrategy())
        pattern = builder.build_control_query(tissue_term="lung")

        self.assertIn("lung", pattern)
        self.assertIn("healthy", pattern)

    def test_build_control_query_without_tissue(self):
        """Build control query without tissue uses only keywords."""
        builder = QueryBuilder(strategy=TextQueryStrategy())
        pattern = builder.build_control_query()

        self.assertIn("healthy", pattern)
        self.assertIn("control", pattern)
        self.assertIn("normal", pattern)

    def test_ontology_strategy_fallback(self):
        """Ontology strategy falls back to pattern matching."""
        strategy = OntologyQueryStrategy()
        expansion = strategy.expand("lung")

        # Should get pattern-like results due to fallback
        self.assertIn("lung", expansion.expanded_terms)
        self.assertEqual(expansion.strategy_name, "ontology")


class TestStudyGrouper(unittest.TestCase):
    """Unit tests for study grouping (no ARCHS4 required)."""

    def test_extract_series_ids_single(self):
        """Extract single series ID."""
        grouper = StudyGrouper()
        ids = grouper.extract_series_ids("GSE12345")
        self.assertEqual(ids, ["GSE12345"])

    def test_extract_series_ids_multiple(self):
        """Extract multiple comma-separated series IDs."""
        grouper = StudyGrouper()
        ids = grouper.extract_series_ids("GSE12345, GSE67890")
        self.assertEqual(ids, ["GSE12345", "GSE67890"])

    def test_extract_series_ids_filters_non_gse(self):
        """Filter out non-GSE identifiers."""
        grouper = StudyGrouper()
        ids = grouper.extract_series_ids("GSE12345, GPL570")
        self.assertEqual(ids, ["GSE12345"])

    def test_extract_series_ids_handles_nan(self):
        """Handle NaN values gracefully."""
        import numpy as np

        grouper = StudyGrouper()
        ids = grouper.extract_series_ids(np.nan)
        self.assertEqual(ids, [])

    def test_group_by_study_basic(self):
        """Group samples by study correctly."""
        grouper = StudyGrouper()

        # Create mock sample set
        df = pd.DataFrame(
            {
                "geo_accession": ["GSM1", "GSM2", "GSM3", "GSM4"],
                "series_id": ["GSE100", "GSE100", "GSE200", "GSE100, GSE200"],
                "title": ["A", "B", "C", "D"],
            }
        )
        sample_set = SampleSet(
            samples=df,
            query_term="test",
            expansion=QueryExpansion("test", ["test"], "text"),
            search_pattern="test",
        )

        groups = grouper.group_by_study(sample_set)

        self.assertIn("GSE100", groups)
        self.assertIn("GSE200", groups)
        self.assertEqual(groups["GSE100"].n_samples, 3)  # GSM1, GSM2, GSM4
        self.assertEqual(groups["GSE200"].n_samples, 2)  # GSM3, GSM4


class TestSearchMetrics(unittest.TestCase):
    """Unit tests for metrics calculation."""

    def test_calculate_stats_empty(self):
        """Calculate stats for empty sample set."""
        empty_set = SampleSet(
            samples=pd.DataFrame(),
            query_term="test",
            expansion=QueryExpansion("test", ["test"], "text"),
            search_pattern="test",
        )

        stats = SearchMetrics.calculate_stats(empty_set)

        self.assertEqual(stats.n_samples, 0)
        self.assertEqual(stats.n_studies, 0)
        self.assertEqual(stats.samples_per_study, 0.0)

    def test_calculate_stats_with_data(self):
        """Calculate stats for sample set with data."""
        df = pd.DataFrame(
            {
                "geo_accession": ["GSM1", "GSM2", "GSM3"],
                "series_id": ["GSE100", "GSE100", "GSE200"],
                "title": ["A", "B", "C"],
            }
        )
        sample_set = SampleSet(
            samples=df,
            query_term="test",
            expansion=QueryExpansion("test", ["test"], "text"),
            search_pattern="test",
        )

        stats = SearchMetrics.calculate_stats(sample_set)

        self.assertEqual(stats.n_samples, 3)
        self.assertEqual(stats.n_studies, 2)
        self.assertEqual(stats.samples_per_study, 1.5)

    def test_format_report(self):
        """Format report produces readable output."""
        metrics = PairQualityMetrics(
            test_stats=SearchStats(100, 10, 10.0, query_term="disease", strategy_name="text"),
            control_stats=SearchStats(50, 5, 10.0, query_term="control", strategy_name="text"),
            overlap_removed=5,
            shared_studies=3,
            total_shared_study_samples=30,
        )

        report = SearchMetrics.format_report(metrics)

        self.assertIn("TEST SAMPLES", report)
        self.assertIn("CONTROL SAMPLES", report)
        self.assertIn("100", report)  # test samples
        self.assertIn("50", report)  # control samples


class TestSampleFinder(unittest.TestCase):
    """Integration tests requiring ARCHS4 data."""

    @classmethod
    def setUpClass(cls):
        """Check if ARCHS4 data is available."""
        cls.archs4_available = "ARCHS4_DATA_DIR" in os.environ
        if not cls.archs4_available:
            print("\nSkipping ARCHS4 integration tests (ARCHS4_DATA_DIR not set)")

    def setUp(self):
        if not self.archs4_available:
            self.skipTest("ARCHS4_DATA_DIR not set")

    def test_pulmonary_fibrosis_search(self):
        """Search for pulmonary fibrosis finds samples."""
        finder = SampleFinder()
        result = finder.search_samples("pulmonary fibrosis")

        self.assertFalse(result.is_empty)
        self.assertGreater(result.n_samples, 0)
        print(f"\nFound {result.n_samples} pulmonary fibrosis samples")

    def test_test_control_pair_separation(self):
        """Test and control samples have zero overlap after filtering."""
        finder = SampleFinder()
        pair = finder.find_test_control_pair("pulmonary fibrosis", tissue="lung")

        # Check no overlap
        overlap = pair.test_ids & pair.control_ids
        self.assertEqual(len(overlap), 0, f"Found {len(overlap)} overlapping samples")

        print(f"\nTest: {pair.n_test}, Control: {pair.n_control}, Overlap removed: {pair.overlap_removed}")

    def test_search_with_pattern_strategy(self):
        """Pattern strategy expands search terms."""
        finder = SampleFinder(
            query_builder=QueryBuilder(strategy=PatternQueryStrategy())
        )

        result = finder.search_samples("lung fibrosis")
        self.assertFalse(result.is_empty)
        print(f"\nPattern search found {result.n_samples} samples")
        print(f"Search pattern: {result.search_pattern}")


class TestQueryExpansionEffectiveness(unittest.TestCase):
    """Compare expanded vs. baseline queries."""

    @classmethod
    def setUpClass(cls):
        cls.archs4_available = "ARCHS4_DATA_DIR" in os.environ

    def setUp(self):
        if not self.archs4_available:
            self.skipTest("ARCHS4_DATA_DIR not set")

    def test_expansion_increases_recall(self):
        """Pattern expansion should find >= text-only results."""
        # Text-only search
        text_finder = SampleFinder(
            query_builder=QueryBuilder(strategy=TextQueryStrategy())
        )
        text_result = text_finder.search_samples("lung")

        # Pattern-expanded search
        pattern_finder = SampleFinder(
            query_builder=QueryBuilder(strategy=PatternQueryStrategy())
        )
        pattern_result = pattern_finder.search_samples("lung")

        # Pattern should find at least as many (expansion includes synonyms)
        self.assertGreaterEqual(
            pattern_result.n_samples,
            text_result.n_samples,
            "Pattern expansion should find >= text-only results",
        )

        print(f"\nText search: {text_result.n_samples} samples")
        print(f"Pattern search: {pattern_result.n_samples} samples")
        print(f"Improvement: {pattern_result.n_samples - text_result.n_samples}")


def run_demo(output_file: str = "chatgeo_demo_output.txt"):
    """
    Demonstrate chatgeo functionality with real ARCHS4 data.

    Run with: python chatgeo/test_chatgeo.py --demo

    Args:
        output_file: Path to write demo output (default: chatgeo_demo_output.txt)
    """
    import datetime
    from pathlib import Path

    # Set up output to both console and file
    output_path = Path(__file__).parent / output_file
    output_lines = []

    def log(msg: str = ""):
        """Print to console and collect for file output."""
        print(msg)
        output_lines.append(msg)

    log("=" * 70)
    log("ChatGEO Demo: ARCHS4 Sample Finder")
    log(f"Run at: {datetime.datetime.now().isoformat()}")
    log("=" * 70)

    if "ARCHS4_DATA_DIR" not in os.environ:
        log("\nError: ARCHS4_DATA_DIR not set")
        log("Set this environment variable to the directory containing ARCHS4 HDF5 files")
        sys.exit(1)

    log(f"ARCHS4_DATA_DIR: {os.environ['ARCHS4_DATA_DIR']}")

    finder = SampleFinder(
        query_builder=QueryBuilder(strategy=PatternQueryStrategy())
    )

    # =========================================================================
    # Example 1: POOLED MODE - Single DE Analysis
    # =========================================================================
    log("\n" + "=" * 70)
    log("Example 1: POOLED MODE - Pulmonary Fibrosis")
    log("  Use case: Single differential expression analysis")
    log("=" * 70)

    pooled = finder.find_pooled_samples(
        "pulmonary fibrosis",
        tissue="lung",
        max_test_samples=200,
        max_control_samples=200,
    )
    log(SearchMetrics.format_pooled_report(pooled))

    log("\nSample IDs ready for DE analysis:")
    log(f"  Test samples: {len(pooled.test_ids)} IDs")
    log(f"  Control samples: {len(pooled.control_ids)} IDs")

    # =========================================================================
    # Example 2: STUDY-MATCHED MODE - Multiple DE Analyses
    # =========================================================================
    log("\n" + "=" * 70)
    log("Example 2: STUDY-MATCHED MODE - Pulmonary Fibrosis")
    log("  Use case: Within-study DE with meta-analysis")
    log("=" * 70)

    matched = finder.find_study_matched_samples(
        "pulmonary fibrosis",
        tissue="lung",
        min_test_per_study=3,
        min_control_per_study=3,
    )
    log(SearchMetrics.format_study_matched_report(matched))

    if matched.study_pairs:
        log("\nTop study details:")
        top_study = matched.study_pairs[0]
        log(f"  Study: {top_study.study_id}")
        log(f"  Test samples: {top_study.n_test}")
        if not top_study.test_samples.empty and "title" in top_study.test_samples.columns:
            titles = top_study.test_samples["title"].head(3).tolist()
            for t in titles:
                log(f"    - {str(t)[:60]}...")

    # =========================================================================
    # Example 3: Comparing Both Modes
    # =========================================================================
    log("\n" + "=" * 70)
    log("Example 3: Mode Comparison - Liver Fibrosis")
    log("=" * 70)

    # Pooled
    pooled = finder.find_pooled_samples("liver fibrosis", tissue="liver")
    log("\nPOOLED MODE:")
    log(f"  Test samples: {pooled.n_test} (from {pooled.total_test_found} total)")
    log(f"  Control samples: {pooled.n_control} (from {pooled.total_control_found} total)")
    log("  → Ready for 1 DE analysis")

    # Study-matched
    matched = finder.find_study_matched_samples("liver fibrosis", tissue="liver")
    log("\nSTUDY-MATCHED MODE:")
    log(f"  Matched studies: {matched.n_studies}")
    log(f"  Test samples in matched: {matched.n_test_total}")
    log(f"  Control samples in matched: {matched.n_control_total}")
    log(f"  → Ready for {matched.n_studies} within-study DE analyses")

    # =========================================================================
    # Example 4: Strategy Comparison
    # =========================================================================
    log("\n" + "=" * 70)
    log("Example 4: Query Strategy Comparison for 'liver fibrosis'")
    log("=" * 70)

    comparison = SearchMetrics.compare_strategies(
        finder,
        "liver fibrosis",
        [TextQueryStrategy(), PatternQueryStrategy()],
    )

    for strategy_name, stats in comparison.items():
        log(f"\n{strategy_name.upper()} Strategy:")
        log(f"  Samples: {stats.n_samples}")
        log(f"  Studies: {stats.n_studies}")
        if stats.search_time_ms:
            log(f"  Time: {stats.search_time_ms:.1f}ms")

    log("\n" + "=" * 70)
    log("Demo complete!")
    log("=" * 70)

    # Write output to file
    with open(output_path, "w") as f:
        f.write("\n".join(output_lines))
    print(f"\nOutput saved to: {output_path}")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        run_demo()
    else:
        # Run unit tests
        unittest.main(verbosity=2)
