"""Unit tests for ontology-enhanced sample discovery in SampleFinder."""

import json
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
        # Per-study metadata (used by _classify_study_samples)
        mock_client.get_metadata_by_series.side_effect = (
            archs4_meta_by_series if callable(archs4_meta_by_series)
            else lambda gse: archs4_meta_by_series.get(gse, pd.DataFrame())
        )
        # Per-study sample IDs (used by _classify_studies_batch)
        def _get_sample_ids(gse):
            df = archs4_meta_by_series.get(gse, pd.DataFrame())
            if df.empty:
                return []
            return df["geo_accession"].tolist()
        mock_client.get_series_sample_ids.side_effect = _get_sample_ids

        # Batch metadata by sample IDs (used by _classify_studies_batch)
        def _get_meta_by_samples(sample_ids, fields=None):
            dfs = []
            for df in archs4_meta_by_series.values():
                if not df.empty:
                    mask = df["geo_accession"].isin(sample_ids)
                    if mask.any():
                        dfs.append(df[mask])
            return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
        mock_client.get_metadata_by_samples.side_effect = _get_meta_by_samples

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
            classification_method="llm",
            tissue_control_samples=15,
            merged_test_samples=55,
            merged_control_samples=50,
        )
        d = stats.to_dict()
        assert d["mondo_ids_resolved"] == ["0005311"]
        assert d["nde_records_found"] == 50
        assert d["classification_method"] == "llm"
        assert d["tissue_control_samples"] == 15

    def test_defaults(self):
        stats = OntologyDiscoveryStats(
            mondo_ids_resolved=["0005311"],
            mondo_labels={},
            resolution_confidence="exact",
            expanded_mondo_ids=["0005311"],
            nde_records_found=10,
            gse_studies_discovered=5,
            gse_studies_in_archs4=3,
            studies_with_classifiable_samples=2,
            ontology_test_samples=20,
            ontology_control_samples=10,
        )
        assert stats.classification_method == "regex"
        assert stats.tissue_control_samples == 0
        assert stats.keyword_test_samples == 0


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
        mock_ont.expand_mondo_ids_batch.return_value = {
            "0005311": MagicMock(expanded_ids=["0005311", "0004993"]),
        }

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

    def test_full_pipeline_regex_fallback(self):
        """Test the full pipeline without LLM (regex fallback)."""
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
            archs4_search=pd.DataFrame(),
        )
        self._setup_mocks(finder)

        # No ANTHROPIC_API_KEY → regex fallback
        with patch.dict("os.environ", {}, clear=False):
            env = dict(**{k: v for k, v in __import__("os").environ.items()
                        if k != "ANTHROPIC_API_KEY"})
            with patch.dict("os.environ", env, clear=True):
                result = finder.find_pooled_samples_ontology(
                    disease_term="atherosclerosis",
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

    def test_nde_samples_without_disease_keyword_are_test(self):
        """NDE-discovered studies don't need disease regex matches.

        The LLM (or regex fallback) classifies samples without requiring
        the disease name to appear in the metadata.
        """
        study_meta = {
            "GSE100": _make_metadata(
                ["GSM1", "GSM2", "GSM3", "GSM4"],
                series_id="GSE100",
                titles=[
                    "MDD patient prefrontal cortex",
                    "major depressive disorder subject",
                    "unaffected subject prefrontal cortex",
                    "healthy control brain",
                ],
            ),
        }
        finder = _make_finder(
            archs4_meta_by_series=study_meta,
            archs4_search=pd.DataFrame(),
        )
        self._setup_mocks(finder)

        # Patch out ANTHROPIC_API_KEY to force regex fallback
        with patch.dict("os.environ", {}, clear=False):
            env = {k: v for k, v in __import__("os").environ.items()
                   if k != "ANTHROPIC_API_KEY"}
            with patch.dict("os.environ", env, clear=True):
                result = finder.find_pooled_samples_ontology(
                    disease_term="depression",
                )

        assert result is not None
        # Regex fallback: "unaffected" matches control regex, "healthy control" matches
        # GSM1, GSM2 should be test; GSM3 (unaffected), GSM4 (healthy control) → control
        assert result.n_test >= 2
        assert result.n_control >= 1
        assert "GSM4" in result.control_ids

    def test_tissue_control_search(self):
        """If within-study controls are insufficient, search ARCHS4 for tissue controls."""
        study_meta = {
            "GSE100": _make_metadata(
                ["GSM1", "GSM2", "GSM3"],
                series_id="GSE100",
                titles=[
                    "depression patient brain",
                    "depression patient brain",
                    "depression patient brain",
                ],
            ),
        }
        # ARCHS4 search for tissue controls returns some
        tissue_controls = _make_metadata(
            ["GSM90", "GSM91", "GSM92"],
            series_id="GSE999",
            titles=["healthy brain tissue", "normal brain control", "healthy brain"],
            sources=["brain", "brain", "brain"],
        )

        finder = _make_finder(
            archs4_meta_by_series=study_meta,
            archs4_search=tissue_controls,
        )
        self._setup_mocks(finder)

        with patch.dict("os.environ", {}, clear=False):
            env = {k: v for k, v in __import__("os").environ.items()
                   if k != "ANTHROPIC_API_KEY"}
            with patch.dict("os.environ", env, clear=True):
                result = finder.find_pooled_samples_ontology(
                    disease_term="depression",
                    tissue="brain",
                )

        assert result is not None
        # All 3 NDE samples are test (no control keywords)
        assert result.n_test == 3
        # Tissue search should have found controls
        assert result.n_control >= 1


# ---------------------------------------------------------------------------
# LLM Classification
# ---------------------------------------------------------------------------

class TestClassifyNdeSamplesLlm:

    def _setup_finder_and_mocks(self):
        study_meta = {
            "GSE100": _make_metadata(
                ["GSM1", "GSM2", "GSM3", "GSM4"],
                series_id="GSE100",
                titles=[
                    "MDD patient prefrontal cortex",
                    "MDD patient hippocampus",
                    "healthy control prefrontal cortex",
                    "healthy control hippocampus",
                ],
            ),
        }
        finder = _make_finder(archs4_meta_by_series=study_meta)
        return finder, study_meta

    def test_regex_fallback_when_no_api_key(self):
        """Without ANTHROPIC_API_KEY, falls back to regex."""
        finder, _ = self._setup_finder_and_mocks()

        with patch.dict("os.environ", {}, clear=False):
            env = {k: v for k, v in __import__("os").environ.items()
                   if k != "ANTHROPIC_API_KEY"}
            with patch.dict("os.environ", env, clear=True):
                test_df, control_df, n_studies, stats = (
                    finder._classify_nde_samples_llm(["GSE100"], "depression")
                )

        assert stats["method"] == "regex_fallback"
        assert len(test_df) == 2  # MDD samples
        assert len(control_df) == 2  # healthy control samples
        assert n_studies == 1

    def test_llm_classification_success(self):
        """LLM classification parses JSON response correctly."""
        finder, _ = self._setup_finder_and_mocks()

        llm_response = json.dumps({
            "studies": {
                "GSE100": {
                    "test_samples": ["GSM1", "GSM2"],
                    "control_samples": ["GSM3", "GSM4"],
                    "reasoning": "MDD patients vs healthy controls",
                }
            }
        })

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=llm_response)]

        mock_anthropic_client = MagicMock()
        mock_anthropic_client.messages.create.return_value = mock_message

        mock_anthropic_module = MagicMock()
        mock_anthropic_module.Anthropic.return_value = mock_anthropic_client

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict("sys.modules", {"anthropic": mock_anthropic_module}):
                test_df, control_df, n_studies, stats = (
                    finder._classify_nde_samples_llm(["GSE100"], "depression")
                )

        assert stats["method"] == "llm"
        assert set(test_df["geo_accession"]) == {"GSM1", "GSM2"}
        assert set(control_df["geo_accession"]) == {"GSM3", "GSM4"}
        assert n_studies == 1
        assert stats["per_study"]["GSE100"]["reasoning"] == "MDD patients vs healthy controls"

    def test_llm_failure_falls_back_to_regex(self):
        """If LLM call fails, falls back to regex classification."""
        finder, _ = self._setup_finder_and_mocks()

        mock_anthropic_module = MagicMock()
        mock_anthropic_module.Anthropic.return_value.messages.create.side_effect = (
            Exception("API error")
        )

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict("sys.modules", {"anthropic": mock_anthropic_module}):
                test_df, control_df, n_studies, stats = (
                    finder._classify_nde_samples_llm(["GSE100"], "depression")
                )

        assert stats["method"] == "regex_fallback"
        assert not test_df.empty
        assert not control_df.empty

    def test_empty_studies(self):
        finder = _make_finder(archs4_meta_by_series={})
        test_df, control_df, n_studies, stats = (
            finder._classify_nde_samples_llm(["GSE_MISSING"], "depression")
        )

        assert test_df.empty
        assert control_df.empty
        assert n_studies == 0


# ---------------------------------------------------------------------------
# _build_llm_classification_prompt
# ---------------------------------------------------------------------------

class TestBuildLlmClassificationPrompt:

    def test_prompt_contains_study_info(self):
        meta = _make_metadata(
            ["GSM1", "GSM2"],
            series_id="GSE100",
            titles=["patient sample", "control sample"],
        )
        finder = _make_finder(archs4_meta_by_series={"GSE100": meta})

        prompt = finder._build_llm_classification_prompt(
            {"GSE100": meta}, "depression", "brain"
        )

        assert "GSE100" in prompt
        assert "depression" in prompt
        assert "brain" in prompt
        assert "GSM1" in prompt
        assert "patient sample" in prompt

    def test_prompt_groups_identical_metadata(self):
        meta = _make_metadata(
            ["GSM1", "GSM2", "GSM3"],
            titles=["patient brain", "patient brain", "control brain"],
        )
        finder = _make_finder()

        prompt = finder._build_llm_classification_prompt(
            {"GSE100": meta}, "depression"
        )

        # GSM1 and GSM2 should be grouped since they have identical titles
        assert "GSM1, GSM2" in prompt


# ---------------------------------------------------------------------------
# _find_tissue_controls
# ---------------------------------------------------------------------------

class TestFindTissueControls:

    def test_finds_tissue_matched_controls(self):
        controls = _make_metadata(
            ["GSM90", "GSM91"],
            titles=["healthy brain tissue", "normal brain control"],
            sources=["brain", "brain"],
        )
        finder = _make_finder(archs4_search=controls)

        result = finder._find_tissue_controls(
            tissue="brain",
            exclude_ids={"GSM1", "GSM2"},
            max_samples=100,
        )

        assert not result.empty
        assert "GSM90" in result["geo_accession"].values

    def test_excludes_already_assigned(self):
        controls = _make_metadata(
            ["GSM1", "GSM90"],
            titles=["healthy brain", "normal brain"],
        )
        finder = _make_finder(archs4_search=controls)

        result = finder._find_tissue_controls(
            tissue="brain",
            exclude_ids={"GSM1"},
            max_samples=100,
        )

        assert "GSM1" not in result["geo_accession"].values

    def test_empty_when_no_results(self):
        finder = _make_finder(archs4_search=pd.DataFrame())

        result = finder._find_tissue_controls(
            tissue="brain",
            exclude_ids=set(),
        )

        assert result.empty


# ---------------------------------------------------------------------------
# _split_nde_studies (legacy regex method, still used as part of fallback)
# ---------------------------------------------------------------------------

class TestSplitNdeStudies:
    """Tests for the NDE-trust-based sample splitting."""

    def test_all_non_control_samples_are_test(self):
        """Every sample from an NDE study is test unless it matches control regex."""
        meta = _make_metadata(
            ["GSM1", "GSM2", "GSM3", "GSM4", "GSM5"],
            titles=[
                "patient sample A",          # test (no control keyword)
                "disease biopsy",             # test
                "treated specimen",           # test
                "healthy control",            # control
                "normal tissue",              # control
            ],
        )
        finder = _make_finder(archs4_meta_by_series={"GSE1": meta})

        test_df, control_df, n_studies = finder._split_nde_studies(
            ["GSE1"], "healthy|control|normal"
        )

        assert set(test_df["geo_accession"]) == {"GSM1", "GSM2", "GSM3"}
        assert set(control_df["geo_accession"]) == {"GSM4", "GSM5"}
        assert n_studies == 1

    def test_empty_when_no_archs4_data(self):
        finder = _make_finder(archs4_meta_by_series={})

        test_df, control_df, n_studies = finder._split_nde_studies(
            ["GSE_MISSING"], "healthy|control"
        )

        assert test_df.empty
        assert control_df.empty
        assert n_studies == 0

    def test_multiple_studies_combined(self):
        study_meta = {
            "GSE100": _make_metadata(
                ["GSM1", "GSM2"],
                series_id="GSE100",
                titles=["patient biopsy", "healthy control"],
            ),
            "GSE200": _make_metadata(
                ["GSM3", "GSM4"],
                series_id="GSE200",
                titles=["disease tissue", "normal tissue"],
            ),
        }
        finder = _make_finder(archs4_meta_by_series=study_meta)

        test_df, control_df, n_studies = finder._split_nde_studies(
            ["GSE100", "GSE200"], "healthy|control|normal"
        )

        assert set(test_df["geo_accession"]) == {"GSM1", "GSM3"}
        assert set(control_df["geo_accession"]) == {"GSM2", "GSM4"}
        assert n_studies == 2

    def test_no_control_samples_in_study(self):
        """If a study has no control samples, all are test."""
        meta = _make_metadata(
            ["GSM1", "GSM2", "GSM3"],
            titles=["patient A", "patient B", "patient C"],
        )
        finder = _make_finder(archs4_meta_by_series={"GSE1": meta})

        test_df, control_df, _ = finder._split_nde_studies(
            ["GSE1"], "healthy|control|normal"
        )

        assert len(test_df) == 3
        assert control_df.empty
