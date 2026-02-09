"""
Search quality evaluation metrics for ARCHS4 sample finding.

Supports reporting for both modes:
- Pooled mode (PooledPair): Single DE analysis
- Study-matched mode (StudyMatchedResult): Multiple within-study DEs
"""

import time
from dataclasses import dataclass
from typing import Optional, Union

from .sample_finder import (
    SampleSet,
    TestControlPair,
    PooledPair,
    StudyMatchedResult,
)
from .study_grouper import StudyGrouper


@dataclass
class SearchStats:
    """Statistics for a single search result."""

    n_samples: int
    n_studies: int
    samples_per_study: float
    search_time_ms: Optional[float] = None
    query_term: str = ""
    strategy_name: str = ""

    def __str__(self) -> str:
        time_str = (
            f", time={self.search_time_ms:.1f}ms" if self.search_time_ms else ""
        )
        return (
            f"SearchStats(samples={self.n_samples}, studies={self.n_studies}, "
            f"samples/study={self.samples_per_study:.1f}{time_str})"
        )


@dataclass
class PairQualityMetrics:
    """Quality metrics for a test/control pair."""

    test_stats: SearchStats
    control_stats: SearchStats
    overlap_removed: int
    shared_studies: int
    total_shared_study_samples: int

    @property
    def has_valid_pair(self) -> bool:
        """Check if both test and control have samples."""
        return self.test_stats.n_samples > 0 and self.control_stats.n_samples > 0

    @property
    def test_control_ratio(self) -> float:
        """Ratio of test to control samples."""
        if self.control_stats.n_samples == 0:
            return float("inf")
        return self.test_stats.n_samples / self.control_stats.n_samples


class SearchMetrics:
    """Static methods for calculating and reporting search quality metrics."""

    @staticmethod
    def calculate_stats(
        sample_set: SampleSet,
        search_time_ms: Optional[float] = None,
    ) -> SearchStats:
        """
        Calculate statistics for a sample set.

        Args:
            sample_set: The sample set to analyze
            search_time_ms: Optional search time in milliseconds

        Returns:
            SearchStats with computed metrics
        """
        if sample_set.is_empty:
            return SearchStats(
                n_samples=0,
                n_studies=0,
                samples_per_study=0.0,
                search_time_ms=search_time_ms,
                query_term=sample_set.query_term,
                strategy_name=sample_set.expansion.strategy_name,
            )

        grouper = StudyGrouper()
        groups = grouper.group_by_study(sample_set)

        n_studies = len(groups)
        samples_per_study = (
            sample_set.n_samples / n_studies if n_studies > 0 else 0.0
        )

        return SearchStats(
            n_samples=sample_set.n_samples,
            n_studies=n_studies,
            samples_per_study=samples_per_study,
            search_time_ms=search_time_ms,
            query_term=sample_set.query_term,
            strategy_name=sample_set.expansion.strategy_name,
        )

    @staticmethod
    def evaluate_pair(pair: TestControlPair) -> PairQualityMetrics:
        """
        Evaluate the quality of a test/control pair.

        Args:
            pair: The TestControlPair to evaluate

        Returns:
            PairQualityMetrics with computed metrics
        """
        test_stats = SearchMetrics.calculate_stats(pair.test_samples)
        control_stats = SearchMetrics.calculate_stats(pair.control_samples)

        # Find shared studies
        grouper = StudyGrouper()
        matched = grouper.find_matched_studies(pair)
        shared_studies = len(matched)

        # Count total samples in shared studies
        total_shared = 0
        for study_id, groups in matched.items():
            total_shared += groups["test"].n_samples
            total_shared += groups["control"].n_samples

        return PairQualityMetrics(
            test_stats=test_stats,
            control_stats=control_stats,
            overlap_removed=pair.overlap_removed,
            shared_studies=shared_studies,
            total_shared_study_samples=total_shared,
        )

    @staticmethod
    def format_report(metrics: PairQualityMetrics) -> str:
        """
        Format metrics as a human-readable report.

        Args:
            metrics: PairQualityMetrics to format

        Returns:
            Multi-line string report
        """
        lines = [
            "=" * 60,
            "SEARCH QUALITY REPORT",
            "=" * 60,
            "",
            "TEST SAMPLES",
            f"  Query: {metrics.test_stats.query_term}",
            f"  Strategy: {metrics.test_stats.strategy_name}",
            f"  Samples found: {metrics.test_stats.n_samples}",
            f"  Studies: {metrics.test_stats.n_studies}",
            f"  Samples/study: {metrics.test_stats.samples_per_study:.1f}",
            "",
            "CONTROL SAMPLES",
            f"  Query: {metrics.control_stats.query_term}",
            f"  Strategy: {metrics.control_stats.strategy_name}",
            f"  Samples found: {metrics.control_stats.n_samples}",
            f"  Studies: {metrics.control_stats.n_studies}",
            f"  Samples/study: {metrics.control_stats.samples_per_study:.1f}",
            "",
            "PAIR QUALITY",
            f"  Overlap removed: {metrics.overlap_removed}",
            f"  Shared studies: {metrics.shared_studies}",
            f"  Total samples in shared studies: {metrics.total_shared_study_samples}",
            f"  Test/control ratio: {metrics.test_control_ratio:.2f}",
            f"  Valid pair: {'Yes' if metrics.has_valid_pair else 'No'}",
            "=" * 60,
        ]
        return "\n".join(lines)

    @staticmethod
    def time_search(finder, search_term: str) -> tuple:
        """
        Time a search and return both results and timing.

        Args:
            finder: SampleFinder instance
            search_term: Term to search

        Returns:
            Tuple of (SampleSet, search_time_ms)
        """
        start = time.perf_counter()
        result = finder.search_samples(search_term)
        elapsed_ms = (time.perf_counter() - start) * 1000
        return result, elapsed_ms

    @staticmethod
    def compare_strategies(
        finder,
        search_term: str,
        strategies: list,
    ) -> dict:
        """
        Compare multiple query strategies for the same search term.

        Args:
            finder: SampleFinder instance
            search_term: Term to search
            strategies: List of QueryStrategy instances to compare

        Returns:
            Dictionary mapping strategy name to SearchStats
        """
        from .query_builder import QueryBuilder

        results = {}
        original_builder = finder.query_builder

        for strategy in strategies:
            finder.query_builder = QueryBuilder(strategy=strategy)
            sample_set, search_time = SearchMetrics.time_search(finder, search_term)
            stats = SearchMetrics.calculate_stats(sample_set, search_time)
            results[strategy.name] = stats

        # Restore original builder
        finder.query_builder = original_builder
        return results

    # =========================================================================
    # Mode-Specific Reporting
    # =========================================================================

    @staticmethod
    def format_pooled_report(pooled: PooledPair) -> str:
        """
        Format a pooled pair result as a human-readable report.

        Args:
            pooled: PooledPair from find_pooled_samples()

        Returns:
            Multi-line string report
        """
        lines = [
            "=" * 60,
            "POOLED SAMPLES (Single DE Analysis)",
            "=" * 60,
            "",
            "TEST SAMPLES",
            f"  Query: {pooled.test_query}",
            f"  Samples selected: {pooled.n_test}",
            f"  Total available: {pooled.total_test_found}",
            "",
            "CONTROL SAMPLES",
            f"  Query: {pooled.control_query}",
            f"  Samples selected: {pooled.n_control}",
            f"  Total available: {pooled.total_control_found}",
            "",
            "SUMMARY",
            f"  Overlap removed: {pooled.overlap_removed}",
            f"  Subsampled: {'Yes' if pooled.was_subsampled else 'No'}",
            f"  Ready for DE: {'Yes' if pooled.n_test > 0 and pooled.n_control > 0 else 'No'}",
            "=" * 60,
        ]
        return "\n".join(lines)

    @staticmethod
    def format_study_matched_report(result: StudyMatchedResult) -> str:
        """
        Format a study-matched result as a human-readable report.

        Args:
            result: StudyMatchedResult from find_study_matched_samples()

        Returns:
            Multi-line string report
        """
        lines = [
            "=" * 60,
            "STUDY-MATCHED SAMPLES (Multiple DE Analyses)",
            "=" * 60,
            "",
            "SEARCH SUMMARY",
            f"  Test query: {result.test_query}",
            f"  Control query: {result.control_query}",
            f"  Total test found: {result.total_test_found}",
            f"  Total control found: {result.total_control_found}",
            f"  Overlap removed: {result.overlap_removed}",
            "",
            "STUDY MATCHING",
            f"  Studies with both test & control: {result.n_studies}",
            f"  Studies with test only: {result.studies_with_test_only}",
            f"  Studies with control only: {result.studies_with_control_only}",
            "",
            f"MATCHED STUDIES ({result.n_studies} total)",
        ]

        if result.study_pairs:
            lines.append("-" * 60)
            lines.append(f"  {'Study ID':<12} {'Test':>8} {'Control':>8} {'Total':>8}")
            lines.append("-" * 60)

            for pair in result.study_pairs[:15]:  # Show top 15
                lines.append(
                    f"  {pair.study_id:<12} {pair.n_test:>8} {pair.n_control:>8} "
                    f"{pair.n_test + pair.n_control:>8}"
                )

            if len(result.study_pairs) > 15:
                lines.append(f"  ... and {len(result.study_pairs) - 15} more studies")

            lines.append("-" * 60)
            lines.append(
                f"  {'TOTAL':<12} {result.n_test_total:>8} {result.n_control_total:>8} "
                f"{result.n_test_total + result.n_control_total:>8}"
            )
        else:
            lines.append("  No studies with both test and control samples found.")

        lines.append("=" * 60)
        return "\n".join(lines)
