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
    MONDO_URI_PREFIX,
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

class TestDiscoverStudiesRest:
    """Tests for REST API-based discovery (fallback path)."""

    def _make_rest_discovery(self, mock_nde, mock_archs4=None):
        """Create a discovery instance that skips SPARQL (forces REST)."""
        d = NDEGeoDiscovery(nde_client=mock_nde, _archs4_client=mock_archs4)
        d._sparql_client = False  # force REST fallback
        return d

    def test_basic_discovery(self):
        mock_nde = MagicMock()
        mock_nde.fetch_all.return_value = [
            _make_hit(identifier="GSE12345", name="Atherosclerosis Study",
                      healthCondition=[{"identifier": "MONDO:0005311", "name": "atherosclerosis"}]),
        ]

        discovery = self._make_rest_discovery(mock_nde)
        result = discovery.discover_studies(["0005311"], filter_archs4=False)

        assert result.n_studies == 1
        assert result.studies[0].gse_id == "GSE12345"
        assert result.total_nde_records == 1

    def test_dedup_across_mondo_ids(self):
        mock_nde = MagicMock()
        hit = _make_hit(identifier="GSE12345")
        mock_nde.fetch_all.return_value = [hit]

        discovery = self._make_rest_discovery(mock_nde)
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

        discovery = self._make_rest_discovery(mock_nde, mock_archs4)
        result = discovery.discover_studies(["0005311"], filter_archs4=True)

        assert result.n_studies == 1
        assert result.studies[0].gse_id == "GSE12345"

    def test_species_filter_in_query(self):
        mock_nde = MagicMock()
        mock_nde.fetch_all.return_value = []

        discovery = self._make_rest_discovery(mock_nde)
        discovery.discover_studies(["0005311"], species_filter="Homo sapiens",
                                   filter_archs4=False)

        query_arg = mock_nde.fetch_all.call_args[1]["query"]
        assert 'Homo sapiens' in query_arg

    def test_nde_batch_failure_continues(self):
        """With batching, IDs are grouped. A failed batch is skipped but
        subsequent batches still succeed."""
        mock_nde = MagicMock()
        mock_nde.fetch_all.side_effect = [
            Exception("timeout"),  # first batch fails
            [_make_hit(identifier="GSE12345")],  # second batch succeeds
        ]

        discovery = self._make_rest_discovery(mock_nde)
        result = discovery.discover_studies(
            ["0005311", "0004993"], filter_archs4=False, batch_size=1
        )

        # Second batch should still succeed
        assert result.n_studies == 1

    def test_batched_or_query(self):
        """Multiple MONDO IDs should be combined into a single OR query."""
        mock_nde = MagicMock()
        mock_nde.fetch_all.return_value = [
            _make_hit(identifier="GSE12345"),
        ]

        discovery = self._make_rest_discovery(mock_nde)
        discovery.discover_studies(
            ["0005311", "0004993", "0002491"], filter_archs4=False, batch_size=10
        )

        # Should have made exactly 1 call (all 3 IDs in one batch)
        assert mock_nde.fetch_all.call_count == 1
        query_arg = mock_nde.fetch_all.call_args[1]["query"]
        assert "0005311" in query_arg
        assert "0004993" in query_arg
        assert "OR" in query_arg

    def test_empty_result(self):
        mock_nde = MagicMock()
        mock_nde.fetch_all.return_value = []

        discovery = self._make_rest_discovery(mock_nde)
        result = discovery.discover_studies(["9999999"], filter_archs4=False)

        assert result.n_studies == 0
        assert result.gse_ids == []


# ---------------------------------------------------------------------------
# SPARQL-based discovery
# ---------------------------------------------------------------------------

class TestDiscoverStudiesSparql:

    def _make_sparql_row(self, gse_id, mondo_id, name="Test Study"):
        """Build a row like SPARQLClient.query_simple returns."""
        return {
            "mondoUri": f"{MONDO_URI_PREFIX}{mondo_id}",
            "identifier": gse_id,
            "name": name,
        }

    def _make_sparql_discovery(self, sparql_rows):
        """Create a discovery with a mock SPARQL client."""
        mock_sparql = MagicMock()
        mock_sparql.query_simple.return_value = sparql_rows
        d = NDEGeoDiscovery()
        d._sparql_client = mock_sparql
        return d

    def test_basic_sparql_discovery(self):
        rows = [
            self._make_sparql_row("GSE12345", "0005311", "Atherosclerosis Study"),
            self._make_sparql_row("GSE67890", "0005311", "Plaque Study"),
        ]
        discovery = self._make_sparql_discovery(rows)

        result = discovery.discover_studies(["0005311"], filter_archs4=False)

        assert result.n_studies == 2
        assert {s.gse_id for s in result.studies} == {"GSE12345", "GSE67890"}
        assert result.total_nde_records == 2

    def test_sparql_dedup(self):
        """Same GSE returned for two MONDO IDs should be deduplicated."""
        rows = [
            self._make_sparql_row("GSE12345", "0005311"),
            self._make_sparql_row("GSE12345", "0004993"),
        ]
        discovery = self._make_sparql_discovery(rows)

        result = discovery.discover_studies(
            ["0005311", "0004993"], filter_archs4=False
        )

        assert result.n_studies == 1
        assert result.studies[0].gse_id == "GSE12345"

    def test_sparql_values_clause(self):
        """VALUES clause should contain all MONDO URIs."""
        mock_sparql = MagicMock()
        mock_sparql.query_simple.return_value = []
        d = NDEGeoDiscovery()
        d._sparql_client = mock_sparql

        d.discover_studies(
            ["0005311", "0004993"], filter_archs4=False
        )

        query_arg = mock_sparql.query_simple.call_args[0][0]
        assert "VALUES" in query_arg
        assert "MONDO_0005311" in query_arg
        assert "MONDO_0004993" in query_arg

    def test_sparql_species_filter(self):
        """Human species filter should add a taxonomy triple."""
        mock_sparql = MagicMock()
        mock_sparql.query_simple.return_value = []
        d = NDEGeoDiscovery()
        d._sparql_client = mock_sparql

        d.discover_studies(
            ["0005311"], species_filter="Homo sapiens", filter_archs4=False
        )

        query_arg = mock_sparql.query_simple.call_args[0][0]
        assert "taxonomy/9606" in query_arg

    def test_sparql_no_species_filter(self):
        """Empty species filter should not include taxonomy triple."""
        mock_sparql = MagicMock()
        mock_sparql.query_simple.return_value = []
        d = NDEGeoDiscovery()
        d._sparql_client = mock_sparql

        d.discover_studies(
            ["0005311"], species_filter="", filter_archs4=False
        )

        query_arg = mock_sparql.query_simple.call_args[0][0]
        assert "taxonomy" not in query_arg

    def test_sparql_archs4_filtering(self):
        rows = [
            self._make_sparql_row("GSE12345", "0005311"),
            self._make_sparql_row("GSE67890", "0005311"),
        ]
        mock_sparql = MagicMock()
        mock_sparql.query_simple.return_value = rows

        mock_archs4 = MagicMock()
        mock_archs4.has_series.side_effect = lambda gse: gse == "GSE12345"

        d = NDEGeoDiscovery(_archs4_client=mock_archs4)
        d._sparql_client = mock_sparql

        result = d.discover_studies(["0005311"], filter_archs4=True)

        assert result.n_studies == 1
        assert result.studies[0].gse_id == "GSE12345"

    def test_sparql_failure_falls_back_to_rest(self):
        """If SPARQL fails, discover_studies should fall back to REST."""
        mock_sparql = MagicMock()
        mock_sparql.query_simple.side_effect = Exception("SPARQL timeout")

        mock_nde = MagicMock()
        mock_nde.fetch_all.return_value = [
            _make_hit(identifier="GSE12345"),
        ]

        d = NDEGeoDiscovery(nde_client=mock_nde)
        d._sparql_client = mock_sparql

        result = d.discover_studies(["0005311"], filter_archs4=False)

        # Should have fallen back to REST
        assert mock_nde.fetch_all.called
        assert result.n_studies == 1
        assert result.studies[0].gse_id == "GSE12345"

    def test_sparql_empty_result(self):
        discovery = self._make_sparql_discovery([])

        result = discovery.discover_studies(["9999999"], filter_archs4=False)

        assert result.n_studies == 0
        assert result.gse_ids == []

    def test_sparql_single_query_call(self):
        """Should make exactly 1 SPARQL call regardless of MONDO ID count."""
        mock_sparql = MagicMock()
        mock_sparql.query_simple.return_value = []
        d = NDEGeoDiscovery()
        d._sparql_client = mock_sparql

        d.discover_studies(
            ["0005311", "0004993", "0002491"], filter_archs4=False
        )

        assert mock_sparql.query_simple.call_count == 1


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
