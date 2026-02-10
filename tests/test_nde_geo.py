"""Unit tests for clients.nde_geo — NDE-to-GEO study discovery."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure demos dir is on sys.path
_demos = str(Path(__file__).resolve().parents[1] / "scripts" / "demos")
if _demos not in sys.path:
    sys.path.insert(0, _demos)

from clients.nde_geo import (
    GEOStudyMatch,
    NDEGeoDiscovery,
    NDEGeoDiscoveryResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hit(identifier="", url="", sameAs=None, distribution=None,
              name="Test Study", healthCondition=None):
    """Build a minimal NDE hit dict."""
    hit = {"name": name, "identifier": identifier, "url": url}
    if sameAs is not None:
        hit["sameAs"] = sameAs
    if distribution is not None:
        hit["distribution"] = distribution
    if healthCondition is not None:
        hit["healthCondition"] = healthCondition
    return hit


# ---------------------------------------------------------------------------
# GSE extraction
# ---------------------------------------------------------------------------

class TestExtractGseIds:

    def test_from_identifier(self):
        hit = _make_hit(identifier="GSE12345")
        assert NDEGeoDiscovery._extract_gse_ids(hit) == ["GSE12345"]

    def test_from_url(self):
        hit = _make_hit(url="https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE67890")
        assert NDEGeoDiscovery._extract_gse_ids(hit) == ["GSE67890"]

    def test_from_sameAs(self):
        hit = _make_hit(sameAs=["https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE11111"])
        assert NDEGeoDiscovery._extract_gse_ids(hit) == ["GSE11111"]

    def test_from_distribution(self):
        hit = _make_hit(distribution=[{"contentUrl": "https://example.com/GSE22222.tar.gz"}])
        assert NDEGeoDiscovery._extract_gse_ids(hit) == ["GSE22222"]

    def test_deduplication(self):
        hit = _make_hit(
            identifier="GSE12345",
            url="https://example.com/GSE12345",
        )
        assert NDEGeoDiscovery._extract_gse_ids(hit) == ["GSE12345"]

    def test_multiple_gse_in_one_field(self):
        hit = _make_hit(identifier="GSE12345,GSE67890")
        ids = NDEGeoDiscovery._extract_gse_ids(hit)
        assert "GSE12345" in ids
        assert "GSE67890" in ids

    def test_no_gse(self):
        hit = _make_hit(identifier="E-MTAB-1234")
        assert NDEGeoDiscovery._extract_gse_ids(hit) == []


# ---------------------------------------------------------------------------
# Health condition extraction
# ---------------------------------------------------------------------------

class TestExtractHealthConditions:

    def test_list_of_conditions(self):
        hit = _make_hit(healthCondition=[
            {"name": "atherosclerosis"},
            {"name": "coronary artery disease"},
        ])
        names = NDEGeoDiscovery._extract_health_conditions(hit)
        assert names == ["atherosclerosis", "coronary artery disease"]

    def test_single_condition_dict(self):
        hit = _make_hit(healthCondition={"name": "psoriasis"})
        assert NDEGeoDiscovery._extract_health_conditions(hit) == ["psoriasis"]

    def test_missing_health_condition(self):
        hit = _make_hit()
        assert NDEGeoDiscovery._extract_health_conditions(hit) == []


# ---------------------------------------------------------------------------
# MONDO ID extraction
# ---------------------------------------------------------------------------

class TestExtractMondoIds:

    def test_with_colon(self):
        hit = _make_hit(healthCondition=[
            {"identifier": "MONDO:0005311", "name": "atherosclerosis"}
        ])
        assert NDEGeoDiscovery._extract_mondo_ids(hit) == ["0005311"]

    def test_without_colon(self):
        hit = _make_hit(healthCondition=[
            {"identifier": "MONDO0005311", "name": "atherosclerosis"}
        ])
        assert NDEGeoDiscovery._extract_mondo_ids(hit) == ["0005311"]


# ---------------------------------------------------------------------------
# Discover studies
# ---------------------------------------------------------------------------

class TestDiscoverStudies:

    def test_basic_discovery(self):
        mock_nde = MagicMock()
        mock_nde.fetch_all.return_value = [
            _make_hit(identifier="GSE12345", name="Atherosclerosis Study",
                      healthCondition=[{"identifier": "MONDO:0005311", "name": "atherosclerosis"}]),
        ]

        discovery = NDEGeoDiscovery(nde_client=mock_nde)
        # Skip ARCHS4 filtering
        result = discovery.discover_studies(["0005311"], filter_archs4=False)

        assert result.n_studies == 1
        assert result.studies[0].gse_id == "GSE12345"
        assert result.total_nde_records == 1

    def test_dedup_across_mondo_ids(self):
        mock_nde = MagicMock()
        # Same GSE returned for two different MONDO IDs
        hit = _make_hit(identifier="GSE12345")
        mock_nde.fetch_all.return_value = [hit]

        discovery = NDEGeoDiscovery(nde_client=mock_nde)
        result = discovery.discover_studies(["0005311", "0004993"], filter_archs4=False)

        gse_ids = [s.gse_id for s in result.studies]
        assert gse_ids.count("GSE12345") == 1

    def test_archs4_filtering(self):
        mock_nde = MagicMock()
        mock_nde.fetch_all.return_value = [
            _make_hit(identifier="GSE12345"),
            _make_hit(identifier="GSE67890"),
        ]

        mock_archs4 = MagicMock()
        mock_archs4.has_series.side_effect = lambda gse: gse == "GSE12345"

        discovery = NDEGeoDiscovery(nde_client=mock_nde, _archs4_client=mock_archs4)
        result = discovery.discover_studies(["0005311"], filter_archs4=True)

        assert result.n_studies == 1
        assert result.studies[0].gse_id == "GSE12345"

    def test_species_filter_in_query(self):
        mock_nde = MagicMock()
        mock_nde.fetch_all.return_value = []

        discovery = NDEGeoDiscovery(nde_client=mock_nde)
        discovery.discover_studies(["0005311"], species_filter="Homo sapiens",
                                   filter_archs4=False)

        query_arg = mock_nde.fetch_all.call_args[1]["query"]
        assert 'Homo sapiens' in query_arg

    def test_nde_query_failure_continues(self):
        mock_nde = MagicMock()
        mock_nde.fetch_all.side_effect = [
            Exception("timeout"),
            [_make_hit(identifier="GSE12345")],
        ]

        discovery = NDEGeoDiscovery(nde_client=mock_nde)
        result = discovery.discover_studies(["0005311", "0004993"], filter_archs4=False)

        # Second MONDO ID should still succeed
        assert result.n_studies == 1

    def test_empty_result(self):
        mock_nde = MagicMock()
        mock_nde.fetch_all.return_value = []

        discovery = NDEGeoDiscovery(nde_client=mock_nde)
        result = discovery.discover_studies(["9999999"], filter_archs4=False)

        assert result.n_studies == 0
        assert result.gse_ids == []


# ---------------------------------------------------------------------------
# NDEGeoDiscoveryResult properties
# ---------------------------------------------------------------------------

class TestNDEGeoDiscoveryResult:

    def test_archs4_available(self):
        studies = [
            GEOStudyMatch("GSE1", "Study 1", [], [], in_archs4=True),
            GEOStudyMatch("GSE2", "Study 2", [], [], in_archs4=False),
            GEOStudyMatch("GSE3", "Study 3", [], [], in_archs4=True),
        ]
        result = NDEGeoDiscoveryResult(["0005311"], 3, studies)
        assert result.archs4_available == ["GSE1", "GSE3"]
