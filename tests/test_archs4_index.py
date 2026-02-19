#!/usr/bin/env python3
"""Tests for ARCHS4 SQLite metadata index."""

import sqlite3
import threading
import time
from pathlib import Path

import pytest

h5py = pytest.importorskip("h5py")
pd = pytest.importorskip("pandas")

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "demos"))

from clients.archs4_index import ARCHS4MetadataIndex, _pattern_to_fts5


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Sample data for mock HDF5
STUDIES = {
    "GSE10001": ["GSM250001", "GSM250002", "GSM250003"],
    "GSE10002": ["GSM250004", "GSM250005"],
    "GSE10003": ["GSM250006"],
}
ALL_GSMS = [gsm for gsms in STUDIES.values() for gsm in gsms]

TITLES = {
    "GSM250001": "psoriasis skin biopsy replicate 1",
    "GSM250002": "psoriasis skin biopsy replicate 2",
    "GSM250003": "healthy skin control",
    "GSM250004": "breast cancer tumor sample",
    "GSM250005": "breast cancer adjacent normal",
    "GSM250006": "lung adenocarcinoma biopsy",
}

SOURCES = {
    "GSM250001": "lesional skin",
    "GSM250002": "lesional skin",
    "GSM250003": "normal skin",
    "GSM250004": "tumor tissue",
    "GSM250005": "adjacent normal tissue",
    "GSM250006": "lung tissue",
}

CHARACTERISTICS = {
    "GSM250001": "disease: psoriasis; tissue: skin",
    "GSM250002": "disease: psoriasis; tissue: skin",
    "GSM250003": "disease: none; tissue: skin",
    "GSM250004": "disease: breast cancer; tissue: breast",
    "GSM250005": "disease: none; tissue: breast",
    "GSM250006": "disease: lung adenocarcinoma; tissue: lung",
}


def _build_gsm_to_gse():
    """Build GSM->GSE mapping."""
    result = {}
    for gse, gsms in STUDIES.items():
        for gsm in gsms:
            result[gsm] = gse
    return result


GSM_TO_GSE = _build_gsm_to_gse()


@pytest.fixture
def mock_h5(tmp_path):
    """Create a small mock ARCHS4 HDF5 file."""
    h5_path = tmp_path / "human_gene_v2.latest.h5"
    with h5py.File(str(h5_path), "w") as f:
        n = len(ALL_GSMS)
        samples_grp = f.create_group("meta/samples")

        def _encode_list(vals):
            return [v.encode("utf-8") for v in vals]

        samples_grp.create_dataset(
            "geo_accession",
            data=_encode_list(ALL_GSMS),
        )
        samples_grp.create_dataset(
            "series_id",
            data=_encode_list([GSM_TO_GSE[gsm] for gsm in ALL_GSMS]),
        )
        samples_grp.create_dataset(
            "title",
            data=_encode_list([TITLES.get(gsm, "") for gsm in ALL_GSMS]),
        )
        samples_grp.create_dataset(
            "source_name_ch1",
            data=_encode_list([SOURCES.get(gsm, "") for gsm in ALL_GSMS]),
        )
        samples_grp.create_dataset(
            "characteristics_ch1",
            data=_encode_list([CHARACTERISTICS.get(gsm, "") for gsm in ALL_GSMS]),
        )
        samples_grp.create_dataset(
            "extract_protocol_ch1",
            data=_encode_list(["RNA extraction" for _ in ALL_GSMS]),
        )
        samples_grp.create_dataset(
            "organism_ch1",
            data=_encode_list(["Homo sapiens" for _ in ALL_GSMS]),
        )
        samples_grp.create_dataset(
            "molecule_ch1",
            data=_encode_list(["total RNA" for _ in ALL_GSMS]),
        )
        samples_grp.create_dataset(
            "platform_id",
            data=_encode_list(["GPL570" for _ in ALL_GSMS]),
        )
        samples_grp.create_dataset(
            "singlecellprobability",
            data=[0.01 for _ in ALL_GSMS],
        )

    return h5_path


@pytest.fixture
def index(mock_h5):
    """Build an index from the mock HDF5 and return it."""
    idx = ARCHS4MetadataIndex(mock_h5)
    idx.build()
    return idx


# ---------------------------------------------------------------------------
# Build tests
# ---------------------------------------------------------------------------

class TestBuild:
    def test_build_creates_db(self, mock_h5):
        idx = ARCHS4MetadataIndex(mock_h5)
        assert not idx.db_path.exists()
        idx.build()
        assert idx.db_path.exists()

    def test_build_correct_sample_count(self, index):
        assert index.get_sample_count() == len(ALL_GSMS)

    def test_build_correct_series_count(self, index):
        assert index.get_series_count() == len(STUDIES)

    def test_progress_callback(self, mock_h5):
        progress = []
        idx = ARCHS4MetadataIndex(mock_h5)
        idx.build(progress_callback=lambda c, t: progress.append((c, t)))
        assert len(progress) > 0
        # Last call should report all samples
        assert progress[-1] == (len(ALL_GSMS), len(ALL_GSMS))

    def test_ensure_built_skips_if_current(self, index):
        """ensure_built should not rebuild if the index is current."""
        mtime_before = index.db_path.stat().st_mtime
        # Small sleep to ensure mtime would differ if rebuilt
        time.sleep(0.05)
        index.ensure_built()
        mtime_after = index.db_path.stat().st_mtime
        assert mtime_before == mtime_after

    def test_ensure_built_force(self, index):
        """ensure_built(force=True) should always rebuild."""
        mtime_before = index.db_path.stat().st_mtime
        time.sleep(0.05)
        index.close()
        index.ensure_built(force=True)
        mtime_after = index.db_path.stat().st_mtime
        assert mtime_after > mtime_before


# ---------------------------------------------------------------------------
# Staleness detection
# ---------------------------------------------------------------------------

class TestStaleness:
    def test_not_stale_after_build(self, index):
        assert not index.is_stale()

    def test_stale_when_no_db(self, mock_h5):
        idx = ARCHS4MetadataIndex(mock_h5)
        assert idx.is_stale()

    def test_stale_when_h5_mtime_changes(self, index, mock_h5):
        """Touching the HDF5 file should make the index stale."""
        index.close()
        time.sleep(0.05)
        mock_h5.touch()
        idx2 = ARCHS4MetadataIndex(mock_h5)
        assert idx2.is_stale()

    def test_stale_when_h5_size_changes(self, index, mock_h5):
        """Changing the HDF5 file size should make the index stale."""
        index.close()
        # Modify the meta table to simulate a size change
        conn = sqlite3.connect(str(index.db_path))
        conn.execute("UPDATE meta SET value = '0' WHERE key = 'h5_size'")
        conn.commit()
        conn.close()
        idx2 = ARCHS4MetadataIndex(mock_h5)
        assert idx2.is_stale()


# ---------------------------------------------------------------------------
# Series queries
# ---------------------------------------------------------------------------

class TestSeriesQueries:
    def test_has_series_true(self, index):
        assert index.has_series("GSE10001") is True

    def test_has_series_false(self, index):
        assert index.has_series("GSE99999") is False

    def test_get_samples_by_series(self, index):
        samples = index.get_samples_by_series("GSE10001")
        assert set(samples) == set(STUDIES["GSE10001"])

    def test_get_samples_by_series_empty(self, index):
        assert index.get_samples_by_series("GSE99999") == []


# ---------------------------------------------------------------------------
# Metadata queries
# ---------------------------------------------------------------------------

class TestMetadataQueries:
    def test_get_metadata_by_series(self, index):
        df = index.get_metadata_by_series("GSE10001")
        assert len(df) == 3
        assert "geo_accession" in df.columns
        assert "series_id" in df.columns
        assert set(df["geo_accession"]) == set(STUDIES["GSE10001"])

    def test_get_metadata_by_series_empty(self, index):
        df = index.get_metadata_by_series("GSE99999")
        assert len(df) == 0

    def test_get_metadata_by_samples(self, index):
        df = index.get_metadata_by_samples(["GSM250001", "GSM250004"])
        assert len(df) == 2
        assert set(df["geo_accession"]) == {"GSM250001", "GSM250004"}

    def test_get_metadata_by_samples_empty(self, index):
        df = index.get_metadata_by_samples([])
        assert len(df) == 0

    def test_get_metadata_by_samples_missing_ids(self, index):
        df = index.get_metadata_by_samples(["GSM250001", "GSM999999"])
        assert len(df) == 1

    def test_metadata_field_filtering(self, index):
        df = index.get_metadata_by_series(
            "GSE10001", fields=["geo_accession", "title"]
        )
        assert set(df.columns) == {"geo_accession", "title"}


# ---------------------------------------------------------------------------
# Column name compatibility
# ---------------------------------------------------------------------------

class TestColumnCompatibility:
    def test_archs4py_column_names(self, index):
        """Returned DataFrames should use archs4py-compatible column names."""
        df = index.get_metadata_by_series("GSE10001")
        expected_cols = {
            "geo_accession",
            "series_id",
            "title",
            "source_name_ch1",
            "characteristics_ch1",
            "extract_protocol_ch1",
            "organism_ch1",
            "molecule_ch1",
            "platform_id",
            "singlecellprobability",
        }
        assert expected_cols.issubset(set(df.columns))

    def test_column_values_correct(self, index):
        df = index.get_metadata_by_samples(["GSM250001"])
        row = df.iloc[0]
        assert row["geo_accession"] == "GSM250001"
        assert row["series_id"] == "GSE10001"
        assert "psoriasis" in row["title"]
        assert row["source_name_ch1"] == "lesional skin"
        assert row["organism_ch1"] == "Homo sapiens"


# ---------------------------------------------------------------------------
# Text search
# ---------------------------------------------------------------------------

class TestSearch:
    def test_fts5_simple_term(self, index):
        df = index.search_metadata("psoriasis")
        assert len(df) >= 2  # GSM250001, GSM250002 (title + characteristics)

    def test_fts5_or_pattern(self, index):
        df = index.search_metadata("psoriasis|breast cancer")
        # Should find psoriasis samples AND breast cancer samples
        gsms = set(df["geo_accession"])
        assert "GSM250001" in gsms  # psoriasis
        assert "GSM250004" in gsms  # breast cancer

    def test_regex_fallback(self, index):
        """Complex regex patterns should fall back to REGEXP."""
        df = index.search_metadata("psoria.*skin")
        assert len(df) >= 1
        assert "GSM250001" in set(df["geo_accession"])

    def test_search_no_results(self, index):
        df = index.search_metadata("nonexistent_disease_xyz")
        assert len(df) == 0

    def test_search_field_filtering(self, index):
        df = index.search_metadata(
            "psoriasis", fields=["geo_accession", "title"]
        )
        assert set(df.columns) == {"geo_accession", "title"}


# ---------------------------------------------------------------------------
# FTS5 pattern conversion
# ---------------------------------------------------------------------------

class TestPatternToFTS5:
    def test_simple_word(self):
        assert _pattern_to_fts5("psoriasis") == '"psoriasis"'

    def test_or_pattern(self):
        result = _pattern_to_fts5("psoriasis|psoriatic")
        assert result == '"psoriasis" OR "psoriatic"'

    def test_grouped_or(self):
        result = _pattern_to_fts5("(psoriasis|psoriatic)")
        assert result == '"psoriasis" OR "psoriatic"'

    def test_phrase(self):
        result = _pattern_to_fts5("breast cancer")
        assert result == '"breast cancer"'

    def test_regex_returns_none(self):
        assert _pattern_to_fts5("psoria.*skin") is None

    def test_dot_returns_none(self):
        assert _pattern_to_fts5("breast.cancer") is None

    def test_brackets_return_none(self):
        assert _pattern_to_fts5("[abc]") is None


# ---------------------------------------------------------------------------
# Sample indices
# ---------------------------------------------------------------------------

class TestSampleIndices:
    def test_get_sample_indices(self, index):
        indices = index.get_sample_indices(["GSM250001", "GSM250004"])
        assert len(indices) == 2
        assert "GSM250001" in indices
        assert "GSM250004" in indices
        # Indices should be valid integers
        assert all(isinstance(v, int) for v in indices.values())

    def test_get_sample_indices_empty(self, index):
        assert index.get_sample_indices([]) == {}


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_queries(self, index):
        """Multiple threads should be able to query concurrently."""
        results = {}
        errors = []

        def query_series(gse_id, result_key):
            try:
                samples = index.get_samples_by_series(gse_id)
                results[result_key] = samples
            except Exception as e:
                errors.append(e)

        threads = []
        for gse_id in STUDIES:
            t = threading.Thread(target=query_series, args=(gse_id, gse_id))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=5)

        assert not errors, f"Thread errors: {errors}"
        assert len(results) == len(STUDIES)
        for gse_id, expected_gsms in STUDIES.items():
            assert set(results[gse_id]) == set(expected_gsms)


# ---------------------------------------------------------------------------
# Graceful fallback
# ---------------------------------------------------------------------------

class TestFallback:
    def test_missing_h5_raises(self, tmp_path):
        """Index for non-existent HDF5 should raise on build."""
        idx = ARCHS4MetadataIndex(tmp_path / "nonexistent.h5")
        with pytest.raises(Exception):
            idx.build()

    def test_corrupted_db_detected_as_stale(self, index):
        """A corrupted DB file should be detected as stale."""
        index.close()
        # Overwrite with garbage
        index.db_path.write_bytes(b"not a database")
        idx2 = ARCHS4MetadataIndex(index.h5_path)
        assert idx2.is_stale()
