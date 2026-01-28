"""
Group samples by GEO study for study-level analysis.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Set

import pandas as pd

from .sample_finder import SampleSet, TestControlPair


@dataclass
class StudyGroup:
    """Samples from a single GEO study."""

    study_id: str
    samples: pd.DataFrame

    @property
    def n_samples(self) -> int:
        """Number of samples in this study."""
        return len(self.samples)

    @property
    def sample_ids(self) -> List[str]:
        """List of sample accession IDs."""
        return list(self.samples["geo_accession"])

    @property
    def titles(self) -> List[str]:
        """Unique sample titles in this study."""
        if "title" in self.samples.columns:
            return list(self.samples["title"].dropna().unique())
        return []


class StudyGrouper:
    """
    Group samples by their GEO study (series) ID.

    Handles the comma-separated series_id field in ARCHS4 metadata
    by exploding to handle samples that appear in multiple series.

    Example:
        grouper = StudyGrouper()
        groups = grouper.group_by_study(sample_set)
        for study_id, group in groups.items():
            print(f"{study_id}: {group.n_samples} samples")
    """

    @staticmethod
    def extract_series_ids(series_id_value: str) -> List[str]:
        """
        Extract GSE IDs from a potentially comma-separated series_id field.

        Args:
            series_id_value: Raw series_id value from metadata

        Returns:
            List of GSE IDs
        """
        if pd.isna(series_id_value) or not series_id_value:
            return []

        # Split by comma, strip whitespace, filter to GSE IDs
        parts = str(series_id_value).split(",")
        return [p.strip() for p in parts if p.strip().startswith("GSE")]

    def group_by_study(self, sample_set: SampleSet) -> Dict[str, StudyGroup]:
        """
        Group samples by GEO study ID.

        Args:
            sample_set: SampleSet to group

        Returns:
            Dictionary mapping study ID to StudyGroup
        """
        if sample_set.is_empty:
            return {}

        df = sample_set.samples
        if "series_id" not in df.columns:
            return {}

        groups: Dict[str, StudyGroup] = {}

        # Vectorized approach: explode series_id to create sample-study pairs
        # This is much faster than applying a lambda to each row
        exploded = df.assign(
            _study_id=df["series_id"].str.split(",")
        ).explode("_study_id")
        exploded["_study_id"] = exploded["_study_id"].str.strip()

        # Filter to GSE IDs only
        exploded = exploded[exploded["_study_id"].str.startswith("GSE", na=False)]

        # Group by study ID
        for study_id, group_df in exploded.groupby("_study_id"):
            # Remove the helper column before storing
            study_samples = group_df.drop(columns=["_study_id"])
            groups[study_id] = StudyGroup(
                study_id=study_id,
                samples=study_samples,
            )

        return groups

    def _get_unique_study_ids(self, df: pd.DataFrame) -> Set[str]:
        """Extract all unique GSE IDs from a DataFrame."""
        all_ids = set()
        for series_id in df["series_id"].dropna():
            all_ids.update(self.extract_series_ids(series_id))
        return all_ids

    def find_matched_studies(
        self, pair: TestControlPair
    ) -> Dict[str, Dict[str, StudyGroup]]:
        """
        Find studies that have both test and control samples.

        Args:
            pair: TestControlPair to analyze

        Returns:
            Dictionary with study IDs as keys and dict with 'test' and 'control'
            StudyGroup values
        """
        test_groups = self.group_by_study(pair.test_samples)
        control_groups = self.group_by_study(pair.control_samples)

        # Find studies that appear in both
        shared_studies = set(test_groups.keys()) & set(control_groups.keys())

        return {
            study_id: {
                "test": test_groups[study_id],
                "control": control_groups[study_id],
            }
            for study_id in shared_studies
        }

    def get_study_summary(
        self, groups: Dict[str, StudyGroup]
    ) -> pd.DataFrame:
        """
        Create a summary DataFrame of studies.

        Args:
            groups: Dictionary of StudyGroups

        Returns:
            DataFrame with study_id, n_samples, and sample_titles columns
        """
        if not groups:
            return pd.DataFrame(columns=["study_id", "n_samples", "sample_titles"])

        rows = []
        for study_id, group in sorted(
            groups.items(), key=lambda x: x[1].n_samples, reverse=True
        ):
            rows.append(
                {
                    "study_id": study_id,
                    "n_samples": group.n_samples,
                    "sample_titles": "; ".join(group.titles[:3]),  # First 3 titles
                }
            )

        return pd.DataFrame(rows)
