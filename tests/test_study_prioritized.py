"""Unit tests for study-prioritized pooled controls and platform filtering."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Ensure demos dir is on sys.path
_demos = str(Path(__file__).resolve().parents[1] / "scripts" / "demos")
if _demos not in sys.path:
    sys.path.insert(0, _demos)

from chatgeo.sample_finder import PooledPair, SampleFinder


def _make_sample_df(geo_ids, series_ids, platform_ids=None, source_names=None):
    """Create a sample metadata DataFrame."""
    data = {
        "geo_accession": geo_ids,
        "series_id": series_ids,
        "source_name_ch1": source_names or ["sample"] * len(geo_ids),
    }
    if platform_ids:
        data["platform_id"] = platform_ids
    return pd.DataFrame(data)


class TestFilterByPlatform:

    def test_filters_to_dominant_platform(self):
        """Should keep only samples matching the dominant platform."""
        reference = _make_sample_df(
            ["GSM1", "GSM2", "GSM3"],
            ["GSE001"] * 3,
            platform_ids=["GPL570", "GPL570", "GPL96"],
        )
        df = _make_sample_df(
            ["GSM10", "GSM11", "GSM12", "GSM13"],
            ["GSE002"] * 4,
            platform_ids=["GPL570", "GPL96", "GPL570", "GPL1261"],
        )

        filtered = SampleFinder._filter_by_platform(df, reference)
        assert len(filtered) == 2
        assert set(filtered["platform_id"]) == {"GPL570"}

    def test_empty_dataframe(self):
        """Should return empty DataFrame when input is empty."""
        reference = _make_sample_df(["GSM1"], ["GSE001"], platform_ids=["GPL570"])
        df = pd.DataFrame()

        result = SampleFinder._filter_by_platform(df, reference)
        assert result.empty

    def test_no_platform_column(self):
        """Should return original DataFrame when no platform_id column."""
        reference = _make_sample_df(["GSM1"], ["GSE001"])
        df = _make_sample_df(["GSM10", "GSM11"], ["GSE002"] * 2)

        result = SampleFinder._filter_by_platform(df, reference)
        assert len(result) == 2

    def test_filtering_removes_all_returns_original(self):
        """When filtering would remove everything, return original."""
        reference = _make_sample_df(["GSM1"], ["GSE001"], platform_ids=["GPL570"])
        df = _make_sample_df(
            ["GSM10", "GSM11"],
            ["GSE002"] * 2,
            platform_ids=["GPL96", "GPL1261"],
        )

        result = SampleFinder._filter_by_platform(df, reference)
        assert len(result) == 2  # Original returned since filter removes all


class TestStudyPrioritizedPooled:

    @patch.object(SampleFinder, "find_pooled_samples")
    def test_within_study_controls_first(self, mock_pooled):
        """Controls from test studies should be selected first."""
        # Test samples from GSE001 and GSE002
        test_df = _make_sample_df(
            [f"GSM_T{i}" for i in range(10)],
            ["GSE001"] * 5 + ["GSE002"] * 5,
        )
        # Controls from GSE001 (matched), GSE002 (matched), GSE003 (unmatched)
        control_df = _make_sample_df(
            [f"GSM_C{i}" for i in range(15)],
            ["GSE001"] * 5 + ["GSE002"] * 5 + ["GSE003"] * 5,
        )

        mock_pooled.return_value = PooledPair(
            test_samples=test_df,
            control_samples=control_df,
            test_query="disease",
            control_query="control",
            total_test_found=10,
            total_control_found=15,
            overlap_removed=0,
        )

        finder = SampleFinder.__new__(SampleFinder)
        finder.data_dir = "/tmp"
        finder._client = MagicMock()

        result = finder.find_pooled_study_prioritized(
            disease_term="test",
            max_test_samples=10,
            max_control_samples=10,
        )

        assert isinstance(result, PooledPair)
        # Should have all 10 matched controls (from GSE001 + GSE002)
        # and 0 unmatched (budget filled)
        stats = result.filtering_stats.get("study_prioritized", {})
        assert stats["matched_controls_available"] == 10
        assert stats["matched_controls_used"] == 10
        assert stats["unmatched_controls_used"] == 0

    @patch.object(SampleFinder, "find_pooled_samples")
    def test_cross_study_fallback(self, mock_pooled):
        """When not enough within-study controls, add cross-study."""
        test_df = _make_sample_df(
            [f"GSM_T{i}" for i in range(5)],
            ["GSE001"] * 5,
        )
        control_df = _make_sample_df(
            [f"GSM_C{i}" for i in range(20)],
            ["GSE001"] * 3 + ["GSE999"] * 17,
        )

        mock_pooled.return_value = PooledPair(
            test_samples=test_df,
            control_samples=control_df,
            test_query="disease",
            control_query="control",
            total_test_found=5,
            total_control_found=20,
            overlap_removed=0,
        )

        finder = SampleFinder.__new__(SampleFinder)
        finder.data_dir = "/tmp"
        finder._client = MagicMock()

        result = finder.find_pooled_study_prioritized(
            disease_term="test",
            max_test_samples=5,
            max_control_samples=10,
        )

        stats = result.filtering_stats.get("study_prioritized", {})
        assert stats["matched_controls_available"] == 3
        assert stats["matched_controls_used"] == 3
        assert stats["unmatched_controls_used"] == 7
        assert result.n_control == 10

    @patch.object(SampleFinder, "find_pooled_samples")
    def test_no_overlap(self, mock_pooled):
        """Test and control sample IDs should not overlap."""
        test_ids = [f"GSM_T{i}" for i in range(5)]
        control_ids = [f"GSM_C{i}" for i in range(10)]

        test_df = _make_sample_df(test_ids, ["GSE001"] * 5)
        control_df = _make_sample_df(control_ids, ["GSE001"] * 5 + ["GSE002"] * 5)

        mock_pooled.return_value = PooledPair(
            test_samples=test_df,
            control_samples=control_df,
            test_query="disease",
            control_query="control",
            total_test_found=5,
            total_control_found=10,
            overlap_removed=0,
        )

        finder = SampleFinder.__new__(SampleFinder)
        finder.data_dir = "/tmp"
        finder._client = MagicMock()

        result = finder.find_pooled_study_prioritized(
            disease_term="test",
            max_test_samples=5,
            max_control_samples=10,
        )

        test_set = set(result.test_ids)
        control_set = set(result.control_ids)
        assert len(test_set & control_set) == 0

    @patch.object(SampleFinder, "find_pooled_samples")
    def test_platform_filter_majority(self, mock_pooled):
        """Majority platform filter should filter controls."""
        test_df = _make_sample_df(
            [f"GSM_T{i}" for i in range(4)],
            ["GSE001"] * 4,
            platform_ids=["GPL570", "GPL570", "GPL570", "GPL96"],
        )
        control_df = _make_sample_df(
            [f"GSM_C{i}" for i in range(6)],
            ["GSE001"] * 3 + ["GSE002"] * 3,
            platform_ids=["GPL570", "GPL96", "GPL570", "GPL1261", "GPL570", "GPL96"],
        )

        mock_pooled.return_value = PooledPair(
            test_samples=test_df,
            control_samples=control_df,
            test_query="disease",
            control_query="control",
            total_test_found=4,
            total_control_found=6,
            overlap_removed=0,
        )

        finder = SampleFinder.__new__(SampleFinder)
        finder.data_dir = "/tmp"
        finder._client = MagicMock()

        result = finder.find_pooled_study_prioritized(
            disease_term="test",
            max_test_samples=10,
            max_control_samples=10,
            platform_filter="majority",
        )

        stats = result.filtering_stats.get("study_prioritized", {})
        assert stats["platform_filter"] == "majority"

    @patch.object(SampleFinder, "find_pooled_samples")
    def test_empty_test_returns_base(self, mock_pooled):
        """Empty test samples should return the base pooled result."""
        mock_pooled.return_value = PooledPair(
            test_samples=pd.DataFrame(),
            control_samples=pd.DataFrame(),
            test_query="disease",
            control_query="control",
            total_test_found=0,
            total_control_found=0,
            overlap_removed=0,
        )

        finder = SampleFinder.__new__(SampleFinder)
        finder.data_dir = "/tmp"
        finder._client = MagicMock()

        result = finder.find_pooled_study_prioritized(disease_term="test")
        assert result.n_test == 0
        assert result.n_control == 0
