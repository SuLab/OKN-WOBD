"""
Core sample search logic for finding test and control samples in ARCHS4.

Two modes of operation:
1. Pooled mode: All matching samples combined into single test/control groups
   → Use for single differential expression analysis

2. Study-matched mode: Samples grouped by GEO study with both test and control
   → Use for multiple within-study DE analyses with meta-analysis
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import pandas as pd

# Add parent directory for archs4_client import
sys.path.insert(0, str(Path(__file__).parent.parent))

from archs4_client import ARCHS4Client

from .query_builder import QueryBuilder, QueryExpansion, TextQueryStrategy


def _get_default_data_dir() -> Optional[str]:
    """Get ARCHS4 data directory from environment variable."""
    return os.environ.get("ARCHS4_DATA_DIR")


@dataclass
class SampleSet:
    """A set of samples matching a search query."""

    samples: pd.DataFrame
    query_term: str
    expansion: QueryExpansion
    search_pattern: str

    @property
    def n_samples(self) -> int:
        """Number of samples in the set."""
        return len(self.samples)

    @property
    def is_empty(self) -> bool:
        """Check if no samples were found."""
        return self.samples.empty

    @property
    def sample_ids(self) -> list:
        """List of GEO sample accession IDs."""
        if self.is_empty:
            return []
        return list(self.samples["geo_accession"])


@dataclass
class TestControlPair:
    """Matched test and control sample sets with overlap statistics."""

    test_samples: SampleSet
    control_samples: SampleSet
    overlap_removed: int = 0

    @property
    def n_test(self) -> int:
        """Number of test samples."""
        return self.test_samples.n_samples

    @property
    def n_control(self) -> int:
        """Number of control samples."""
        return self.control_samples.n_samples

    @property
    def test_ids(self) -> set:
        """Set of test sample IDs."""
        return set(self.test_samples.sample_ids)

    @property
    def control_ids(self) -> set:
        """Set of control sample IDs."""
        return set(self.control_samples.sample_ids)

    @property
    def has_overlap(self) -> bool:
        """Check if any samples appear in both test and control."""
        return len(self.test_ids & self.control_ids) > 0


# =============================================================================
# Pooled Mode: Single test/control groups for one DE analysis
# =============================================================================


@dataclass
class PooledPair:
    """
    Test and control samples pooled for a single DE analysis.

    All matching samples are combined into one test group and one control group,
    suitable for a single differential expression comparison.
    """

    test_samples: pd.DataFrame
    control_samples: pd.DataFrame
    test_query: str
    control_query: str
    total_test_found: int
    total_control_found: int
    overlap_removed: int = 0

    @property
    def n_test(self) -> int:
        return len(self.test_samples)

    @property
    def n_control(self) -> int:
        return len(self.control_samples)

    @property
    def test_ids(self) -> List[str]:
        if self.test_samples.empty:
            return []
        return list(self.test_samples["geo_accession"])

    @property
    def control_ids(self) -> List[str]:
        if self.control_samples.empty:
            return []
        return list(self.control_samples["geo_accession"])

    @property
    def was_subsampled(self) -> bool:
        """True if samples were limited from the total available."""
        return (
            self.n_test < self.total_test_found
            or self.n_control < self.total_control_found
        )


# =============================================================================
# Study-Matched Mode: Per-study pairs for multiple DE analyses
# =============================================================================


@dataclass
class StudyPair:
    """Test and control samples from a single GEO study."""

    study_id: str
    test_samples: pd.DataFrame
    control_samples: pd.DataFrame

    @property
    def n_test(self) -> int:
        return len(self.test_samples)

    @property
    def n_control(self) -> int:
        return len(self.control_samples)

    @property
    def test_ids(self) -> List[str]:
        return list(self.test_samples["geo_accession"])

    @property
    def control_ids(self) -> List[str]:
        return list(self.control_samples["geo_accession"])


@dataclass
class StudyMatchedResult:
    """
    Multiple study-level test/control pairs for aggregated DE analysis.

    Each study_pair contains samples from a single GEO study that has
    both test and control samples, suitable for within-study DE followed
    by meta-analysis across studies.
    """

    study_pairs: List[StudyPair]
    test_query: str
    control_query: str
    # Summary stats
    total_test_found: int
    total_control_found: int
    studies_with_test_only: int
    studies_with_control_only: int
    overlap_removed: int = 0

    @property
    def n_studies(self) -> int:
        """Number of studies with both test and control."""
        return len(self.study_pairs)

    @property
    def n_test_total(self) -> int:
        """Total test samples across all matched studies."""
        return sum(p.n_test for p in self.study_pairs)

    @property
    def n_control_total(self) -> int:
        """Total control samples across all matched studies."""
        return sum(p.n_control for p in self.study_pairs)

    def get_study(self, study_id: str) -> Optional[StudyPair]:
        """Get a specific study pair by ID."""
        for pair in self.study_pairs:
            if pair.study_id == study_id:
                return pair
        return None


@dataclass
class SampleFinder:
    """
    Main entry point for finding ARCHS4 samples.

    Wraps ARCHS4Client.search_metadata() with query expansion
    and test/control pair matching.

    Example:
        finder = SampleFinder()
        pair = finder.find_test_control_pair("pulmonary fibrosis", tissue="lung")
        print(f"Found {pair.n_test} test and {pair.n_control} control samples")
    """

    data_dir: Optional[str] = field(default_factory=_get_default_data_dir)
    query_builder: QueryBuilder = field(default_factory=QueryBuilder)
    _client: Optional[ARCHS4Client] = field(default=None, repr=False)

    def __post_init__(self):
        """Initialize ARCHS4 client lazily."""
        pass

    @property
    def client(self) -> ARCHS4Client:
        """Lazy initialization of ARCHS4 client."""
        if self._client is None:
            self._client = ARCHS4Client(data_dir=self.data_dir)
        return self._client

    def search_samples(self, search_term: str) -> SampleSet:
        """
        Search for samples matching a term.

        Uses the configured query builder to expand the search term
        before searching ARCHS4 metadata.

        Args:
            search_term: Disease, tissue, or other search term

        Returns:
            SampleSet containing matching samples and search metadata
        """
        expansion = self.query_builder.get_expansion_info(search_term)
        search_pattern = expansion.to_regex()

        metadata = self.client.search_metadata(search_pattern)

        return SampleSet(
            samples=metadata if metadata is not None else pd.DataFrame(),
            query_term=search_term,
            expansion=expansion,
            search_pattern=search_pattern,
        )

    def find_test_control_pair(
        self,
        disease_term: str,
        tissue: Optional[str] = None,
        control_keywords: Optional[list] = None,
    ) -> TestControlPair:
        """
        Find matched test (disease) and control (healthy) samples.

        Control samples are filtered to remove any overlap with test samples.

        Args:
            disease_term: Disease to search for test samples
            tissue: Optional tissue to constrain control search
            control_keywords: Keywords for identifying control samples
                             (default: healthy, control, normal)

        Returns:
            TestControlPair with non-overlapping test and control samples
        """
        # Search for disease samples
        test_pattern = self.query_builder.build_disease_query(disease_term)
        test_expansion = self.query_builder.get_expansion_info(disease_term)
        test_metadata = self.client.search_metadata(test_pattern)

        test_samples = SampleSet(
            samples=test_metadata if test_metadata is not None else pd.DataFrame(),
            query_term=disease_term,
            expansion=test_expansion,
            search_pattern=test_pattern,
        )

        # Search for control samples
        control_pattern = self.query_builder.build_control_query(
            tissue_term=tissue, control_keywords=control_keywords
        )
        control_expansion = self.query_builder.get_expansion_info(
            tissue if tissue else "control"
        )
        control_metadata = self.client.search_metadata(control_pattern)

        # Remove overlap: exclude any samples that appear in test set
        overlap_removed = 0
        if control_metadata is not None and not control_metadata.empty:
            if not test_samples.is_empty:
                test_ids = set(test_samples.sample_ids)
                original_count = len(control_metadata)
                control_metadata = control_metadata[
                    ~control_metadata["geo_accession"].isin(test_ids)
                ]
                overlap_removed = original_count - len(control_metadata)

        control_samples = SampleSet(
            samples=control_metadata if control_metadata is not None else pd.DataFrame(),
            query_term=f"{tissue or ''} control",
            expansion=control_expansion,
            search_pattern=control_pattern,
        )

        return TestControlPair(
            test_samples=test_samples,
            control_samples=control_samples,
            overlap_removed=overlap_removed,
        )

    def search_with_custom_pattern(self, pattern: str) -> SampleSet:
        """
        Search with a raw regex pattern (no expansion).

        Useful for advanced users who want full control over the query.

        Args:
            pattern: Raw regex pattern

        Returns:
            SampleSet containing matching samples
        """
        metadata = self.client.search_metadata(pattern)

        # Create a dummy expansion for tracking
        expansion = QueryExpansion(
            original_term=pattern,
            expanded_terms=[pattern],
            strategy_name="raw",
        )

        return SampleSet(
            samples=metadata if metadata is not None else pd.DataFrame(),
            query_term=pattern,
            expansion=expansion,
            search_pattern=pattern,
        )

    # =========================================================================
    # Pooled Mode: Single DE Analysis
    # =========================================================================

    def find_pooled_samples(
        self,
        disease_term: str,
        tissue: Optional[str] = None,
        control_keywords: Optional[list] = None,
        max_test_samples: int = 500,
        max_control_samples: int = 500,
    ) -> PooledPair:
        """
        Find pooled test and control samples for a single DE analysis.

        All matching samples are combined into one test group and one control
        group, with optional size limits. This mode ignores study boundaries
        and leverages ARCHS4's diversity for broad biological signal.

        Use this when:
        - You want a single differential expression analysis
        - You're okay with cross-study batch effects (or will normalize)
        - You want maximum sample size for statistical power

        Args:
            disease_term: Disease/condition to search for test samples
            tissue: Optional tissue to constrain control search
            control_keywords: Keywords for control samples
                             (default: healthy, control, normal)
            max_test_samples: Maximum test samples to return (0 = no limit)
            max_control_samples: Maximum control samples to return (0 = no limit)

        Returns:
            PooledPair with test and control DataFrames ready for DE analysis
        """
        # Get raw test/control pair
        pair = self.find_test_control_pair(
            disease_term=disease_term,
            tissue=tissue,
            control_keywords=control_keywords,
        )

        # Extract DataFrames
        test_df = pair.test_samples.samples
        control_df = pair.control_samples.samples

        total_test = len(test_df)
        total_control = len(control_df)

        # Apply size limits with random sampling
        if max_test_samples > 0 and len(test_df) > max_test_samples:
            test_df = test_df.sample(n=max_test_samples, random_state=42)

        if max_control_samples > 0 and len(control_df) > max_control_samples:
            control_df = control_df.sample(n=max_control_samples, random_state=42)

        return PooledPair(
            test_samples=test_df,
            control_samples=control_df,
            test_query=pair.test_samples.search_pattern,
            control_query=pair.control_samples.search_pattern,
            total_test_found=total_test,
            total_control_found=total_control,
            overlap_removed=pair.overlap_removed,
        )

    # =========================================================================
    # Study-Matched Mode: Multiple Within-Study DE Analyses
    # =========================================================================

    def find_study_matched_samples(
        self,
        disease_term: str,
        tissue: Optional[str] = None,
        control_keywords: Optional[list] = None,
        min_test_per_study: int = 3,
        min_control_per_study: int = 3,
    ) -> StudyMatchedResult:
        """
        Find study-matched test/control pairs for within-study DE analyses.

        Returns samples grouped by GEO study, only including studies that have
        both test and control samples meeting minimum size thresholds. This
        controls for batch effects by comparing within the same study.

        Use this when:
        - You want to run DE within each study, then aggregate results
        - Batch effect control is important
        - You plan to do meta-analysis across studies

        Args:
            disease_term: Disease/condition to search for test samples
            tissue: Optional tissue to constrain control search
            control_keywords: Keywords for control samples
            min_test_per_study: Minimum test samples required per study
            min_control_per_study: Minimum control samples required per study

        Returns:
            StudyMatchedResult with list of StudyPair objects
        """
        # Get raw test/control pair
        pair = self.find_test_control_pair(
            disease_term=disease_term,
            tissue=tissue,
            control_keywords=control_keywords,
        )

        # Group by study using StudyGrouper
        from .study_grouper import StudyGrouper

        grouper = StudyGrouper()

        test_groups = grouper.group_by_study(pair.test_samples)
        control_groups = grouper.group_by_study(pair.control_samples)

        test_study_ids = set(test_groups.keys())
        control_study_ids = set(control_groups.keys())

        # Find studies with both test and control meeting thresholds
        study_pairs = []
        for study_id in test_study_ids & control_study_ids:
            test_group = test_groups[study_id]
            control_group = control_groups[study_id]

            if (
                test_group.n_samples >= min_test_per_study
                and control_group.n_samples >= min_control_per_study
            ):
                study_pairs.append(
                    StudyPair(
                        study_id=study_id,
                        test_samples=test_group.samples,
                        control_samples=control_group.samples,
                    )
                )

        # Sort by total samples descending
        study_pairs.sort(key=lambda p: p.n_test + p.n_control, reverse=True)

        # Count studies with only test or only control
        studies_test_only = len(test_study_ids - control_study_ids)
        studies_control_only = len(control_study_ids - test_study_ids)

        return StudyMatchedResult(
            study_pairs=study_pairs,
            test_query=pair.test_samples.search_pattern,
            control_query=pair.control_samples.search_pattern,
            total_test_found=pair.n_test,
            total_control_found=pair.n_control,
            studies_with_test_only=studies_test_only,
            studies_with_control_only=studies_control_only,
            overlap_removed=pair.overlap_removed,
        )
