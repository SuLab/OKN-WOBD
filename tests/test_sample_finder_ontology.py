"""Unit tests for ontology-enhanced sample discovery in SampleFinder."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pandas as pd
import pytest

# Ensure demos dir is on sys.path
_demos = str(Path(__file__).resolve().parents[1] / "scripts" / "demos")
if _demos not in sys.path:
    sys.path.insert(0, _demos)

from chatgeo.query_builder import QueryBuilder, TextQueryStrategy
from chatgeo.sample_finder import OntologyDiscoveryStats, PooledPair, SampleFinder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_metadata(geo_accessions, series_id="GSE12345", titles=None, sources=None):
    """Create a sample metadata DataFrame."""
    n = len(geo_accessions)
    return pd.DataFrame({
        "geo_accession": geo_accessions,
        "series_id": [series_id] * n,
        "title": titles or [f"sample {i}" for i in range(n)],
        "source_name_ch1": sources or ["" for _ in range(n)],
    })


def _make_finder(archs4_meta_by_series=None, archs4_search=None):
    """Create a SampleFinder with mocked clients."""
    mock_client = MagicMock()
    if archs4_meta_by_series is not None:
        mock_client.get_metadata_by_series.side_effect = (
            archs4_meta_by_series if callable(archs4_meta_by_series)
            else lambda gse: archs4_meta_by_series.get(gse, pd.DataFrame())
        )
    if archs4_search is not None:
        mock_client.search_metadata.return_value = archs4_search

    finder = SampleFinder(
        data_dir="/fake",
        query_builder=QueryBuilder(strategy=TextQueryStrategy()),
        _client=mock_client,
    )
    return finder


# ---------------------------------------------------------------------------
# _classify_study_samples
# ---------------------------------------------------------------------------

class TestClassifyStudySamples:

    def test_basic_classification(self):
        meta = _make_metadata(
            ["GSM1", "GSM2", "GSM3", "GSM4"],
            titles=["psoriasis lesion", "psoriasis plaque", "healthy control", "untreated skin"],
        )
        finder = _make_finder(archs4_meta_by_series={"GSE1": meta})

        test_df, control_df = finder._classify_study_samples(
            "GSE1", "psoriasis", "healthy|control|normal"
        )

        assert len(test_df) == 2
        assert set(test_df["geo_accession"]) == {"GSM1", "GSM2"}
        assert len(control_df) == 1
        assert control_df.iloc[0]["geo_accession"] == "GSM3"

    def test_disease_takes_precedence_over_control(self):
        meta = _make_metadata(
            ["GSM1", "GSM2"],
            titles=["psoriasis control sample", "healthy control"],
        )
        finder = _make_finder(archs4_meta_by_series={"GSE1": meta})

        test_df, control_df = finder._classify_study_samples(
            "GSE1", "psoriasis", "healthy|control|normal"
        )

        # GSM1 matches both disease and control — should be test
        assert "GSM1" in test_df["geo_accession"].values
        assert "GSM1" not in control_df["geo_accession"].values

    def test_no_matching_samples(self):
        meta = _make_metadata(
            ["GSM1", "GSM2"],
            titles=["breast cancer biopsy", "tumor adjacent tissue"],
        )
        finder = _make_finder(archs4_meta_by_series={"GSE1": meta})

        test_df, control_df = finder._classify_study_samples(
            "GSE1", "psoriasis", "healthy|control|normal"
        )

        assert test_df.empty
        assert control_df.empty

    def test_metadata_unavailable(self):
        finder = _make_finder(archs4_meta_by_series={})

        test_df, control_df = finder._classify_study_samples(
            "GSE_MISSING", "psoriasis", "healthy|control"
        )

        assert test_df.empty
        assert control_df.empty


# ---------------------------------------------------------------------------
# _merge_sample_sources
# ---------------------------------------------------------------------------

class TestMergeSampleSources:

    def test_union_and_dedup(self):
        ont_test = _make_metadata(["GSM1", "GSM2"])
        kw_test = _make_metadata(["GSM2", "GSM3"])
        ont_ctrl = _make_metadata(["GSM4"])
        kw_ctrl = _make_metadata(["GSM5"])

        merged_test, merged_ctrl = SampleFinder._merge_sample_sources(
            ont_test, ont_ctrl, kw_test, kw_ctrl
        )

        assert set(merged_test["geo_accession"]) == {"GSM1", "GSM2", "GSM3"}
        assert set(merged_ctrl["geo_accession"]) == {"GSM4", "GSM5"}

    def test_conflict_resolved_to_test(self):
        """If a sample is test in one source and control in another → test."""
        ont_test = _make_metadata(["GSM1"])
        kw_test = pd.DataFrame()
        ont_ctrl = pd.DataFrame()
        kw_ctrl = _make_metadata(["GSM1"])  # same sample as control in keyword

        merged_test, merged_ctrl = SampleFinder._merge_sample_sources(
            ont_test, ont_ctrl, kw_test, kw_ctrl
        )

        assert "GSM1" in merged_test["geo_accession"].values
        assert "GSM1" not in merged_ctrl["geo_accession"].values

    def test_empty_inputs(self):
        merged_test, merged_ctrl = SampleFinder._merge_sample_sources(
            pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        )
        assert merged_test.empty
        assert merged_ctrl.empty


# ---------------------------------------------------------------------------
# OntologyDiscoveryStats
# ---------------------------------------------------------------------------

class TestOntologyDiscoveryStats:

    def test_to_dict(self):
        stats = OntologyDiscoveryStats(
            mondo_ids_resolved=["0005311"],
            mondo_labels={"0005311": "atherosclerosis"},
            resolution_confidence="exact",
            expanded_mondo_ids=["0005311", "0004993"],
            nde_records_found=50,
            gse_studies_discovered=10,
            gse_studies_in_archs4=8,
            studies_with_classifiable_samples=6,
            ontology_test_samples=40,
            ontology_control_samples=30,
            keyword_test_samples=20,
            keyword_control_samples=25,
            merged_test_samples=55,
            merged_control_samples=50,
        )
        d = stats.to_dict()
        assert d["mondo_ids_resolved"] == ["0005311"]
        assert d["nde_records_found"] == 50


# ---------------------------------------------------------------------------
# find_pooled_samples_ontology (full pipeline)
# ---------------------------------------------------------------------------

class TestFindPooledSamplesOntology:

    def _setup_mocks(self, finder):
        """Set up ontology and NDE mocks on a finder."""
        mock_ont = MagicMock()
        mock_ont.resolve_disease.return_value = MagicMock(
            mondo_ids=["0005311"],
            labels={"0005311": "atherosclerosis"},
            confidence="exact",
            top_id="0005311",
        )
        mock_ont.expand_mondo_id.return_value = MagicMock(
            expanded_ids=["0005311", "0004993"],
        )

        mock_nde = MagicMock()
        mock_nde.discover_studies.return_value = MagicMock(
            studies=[
                MagicMock(gse_id="GSE100"),
                MagicMock(gse_id="GSE200"),
            ],
            total_nde_records=10,
            n_studies=2,
        )

        finder._ontology_client = mock_ont
        finder._nde_discovery = mock_nde
        return mock_ont, mock_nde

    def test_full_pipeline(self):
        # Set up study metadata
        study_meta = {
            "GSE100": _make_metadata(
                ["GSM1", "GSM2", "GSM3"],
                series_id="GSE100",
                titles=["atherosclerosis plaque", "atherosclerosis tissue", "healthy control"],
            ),
            "GSE200": _make_metadata(
                ["GSM4", "GSM5"],
                series_id="GSE200",
                titles=["atherosclerosis sample", "normal aorta"],
            ),
        }
        finder = _make_finder(
            archs4_meta_by_series=study_meta,
            archs4_search=pd.DataFrame(),  # empty keyword search
        )
        self._setup_mocks(finder)

        result = finder.find_pooled_samples_ontology(
            disease_term="atherosclerosis",
            keyword_fallback=True,
        )

        assert result is not None
        assert result.n_test >= 3  # GSM1, GSM2, GSM4
        assert result.n_control >= 1  # GSM3 or GSM5
        assert result.filtering_stats is not None
        assert "ontology_discovery" in result.filtering_stats

    def test_returns_none_when_clients_unavailable(self):
        finder = _make_finder()
        finder._ontology_client = False
        finder._nde_discovery = False

        result = finder.find_pooled_samples_ontology("atherosclerosis")
        assert result is None

    def test_returns_none_when_no_mondo_ids(self):
        finder = _make_finder()
        mock_ont = MagicMock()
        mock_ont.resolve_disease.return_value = MagicMock(
            mondo_ids=[], labels={}, confidence="none", top_id=None
        )
        finder._ontology_client = mock_ont
        finder._nde_discovery = MagicMock()

        result = finder.find_pooled_samples_ontology("madeuposis")
        assert result is None

    def test_returns_none_when_no_studies(self):
        finder = _make_finder()
        mock_ont = MagicMock()
        mock_ont.resolve_disease.return_value = MagicMock(
            mondo_ids=["0005311"], labels={}, confidence="exact", top_id="0005311"
        )
        mock_ont.expand_mondo_id.return_value = MagicMock(expanded_ids=["0005311"])
        finder._ontology_client = mock_ont

        mock_nde = MagicMock()
        mock_nde.discover_studies.return_value = MagicMock(
            studies=[], total_nde_records=0, n_studies=0
        )
        finder._nde_discovery = mock_nde

        result = finder.find_pooled_samples_ontology("atherosclerosis")
        assert result is None

    def test_keyword_fallback_merges_samples(self):
        """Keyword fallback should add to ontology results."""
        study_meta = {
            "GSE100": _make_metadata(
                ["GSM1", "GSM2"],
                titles=["atherosclerosis", "healthy control"],
            ),
        }
        # Keyword search returns additional samples
        kw_search = _make_metadata(
            ["GSM10", "GSM11"],
            series_id="GSE999",
            titles=["atherosclerosis bulk", "healthy tissue"],
        )

        finder = _make_finder(
            archs4_meta_by_series=study_meta,
            archs4_search=kw_search,
        )
        self._setup_mocks(finder)

        result = finder.find_pooled_samples_ontology(
            disease_term="atherosclerosis",
            keyword_fallback=True,
        )

        assert result is not None
        # Should contain samples from both ontology and keyword
        all_ids = set(result.test_ids) | set(result.control_ids)
        assert len(all_ids) >= 2
