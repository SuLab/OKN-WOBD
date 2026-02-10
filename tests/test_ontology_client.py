"""Unit tests for clients.ontology — Disease ontology resolution & expansion."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure demos dir is on sys.path
_demos = str(Path(__file__).resolve().parents[1] / "scripts" / "demos")
if _demos not in sys.path:
    sys.path.insert(0, _demos)

from clients.ontology import (
    MONDO_URI_PREFIX,
    DiseaseOntologyClient,
    MondoResolution,
    OntologyExpansion,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_sparql():
    """Create a mock SPARQLClient."""
    return MagicMock()


def _make_client(sparql=None):
    return DiseaseOntologyClient(sparql=sparql or _mock_sparql())


# ---------------------------------------------------------------------------
# MondoResolution dataclass
# ---------------------------------------------------------------------------

class TestMondoResolution:

    def test_top_id(self):
        r = MondoResolution(query="test", mondo_ids=["0005311", "0004993"],
                            labels={}, confidence="exact")
        assert r.top_id == "0005311"

    def test_top_id_empty(self):
        r = MondoResolution(query="test", mondo_ids=[], labels={}, confidence="none")
        assert r.top_id is None

    def test_top_uri(self):
        r = MondoResolution(query="test", mondo_ids=["0005311"],
                            labels={}, confidence="exact")
        assert r.top_uri == f"{MONDO_URI_PREFIX}0005311"


# ---------------------------------------------------------------------------
# Resolve disease
# ---------------------------------------------------------------------------

class TestResolveDisease:

    def test_exact_match_ranked_first(self):
        client = _make_client()
        client.sparql.query_simple.return_value = [
            {"uri": f"{MONDO_URI_PREFIX}0005311", "label": "atherosclerosis"},
            {"uri": f"{MONDO_URI_PREFIX}0004993", "label": "coronary atherosclerosis"},
        ]

        result = client.resolve_disease("atherosclerosis")

        assert result.confidence == "exact"
        assert result.mondo_ids[0] == "0005311"
        assert result.labels["0005311"] == "atherosclerosis"

    def test_partial_match(self):
        client = _make_client()
        client.sparql.query_simple.return_value = [
            {"uri": f"{MONDO_URI_PREFIX}0004993", "label": "coronary atherosclerosis"},
        ]

        result = client.resolve_disease("atherosclerosis")

        assert result.confidence == "partial"
        assert "0004993" in result.mondo_ids

    def test_no_match(self):
        client = _make_client()
        client.sparql.query_simple.return_value = []

        result = client.resolve_disease("madeuposis")

        assert result.confidence == "none"
        assert result.mondo_ids == []

    def test_filters_non_mondo_uris(self):
        client = _make_client()
        client.sparql.query_simple.return_value = [
            {"uri": "http://purl.obolibrary.org/obo/HP_0001234", "label": "atherosclerosis symptom"},
            {"uri": f"{MONDO_URI_PREFIX}0005311", "label": "atherosclerosis"},
        ]

        result = client.resolve_disease("atherosclerosis")

        assert all(mid.isdigit() for mid in result.mondo_ids)
        assert "0005311" in result.mondo_ids

    def test_max_results_respected(self):
        client = _make_client()
        client.sparql.query_simple.return_value = [
            {"uri": f"{MONDO_URI_PREFIX}000000{i}", "label": f"disease {i}"}
            for i in range(10)
        ]

        result = client.resolve_disease("disease", max_results=3)
        assert len(result.mondo_ids) <= 3

    def test_caching(self):
        client = _make_client()
        client.sparql.query_simple.return_value = [
            {"uri": f"{MONDO_URI_PREFIX}0005311", "label": "atherosclerosis"},
        ]

        r1 = client.resolve_disease("atherosclerosis")
        r2 = client.resolve_disease("atherosclerosis")

        assert r1.mondo_ids == r2.mondo_ids
        # Should only have called SPARQL once
        assert client.sparql.query_simple.call_count == 1

    def test_ubergraph_failure_falls_back_to_nde(self):
        client = _make_client()
        client.sparql.query_simple.side_effect = Exception("timeout")

        # The _resolve_via_nde method does: from clients.niaid import NIAIDClient
        # We need to mock the NIAIDClient class at its source module.
        mock_nde_instance = MagicMock()
        mock_nde_instance.search_by_disease.return_value = MagicMock(hits=[{
            "healthCondition": [{"identifier": "MONDO:0005311", "name": "atherosclerosis"}]
        }])

        # Also mock the static method extract_ontology_annotations
        def mock_extract(hit):
            return {
                "healthCondition": hit.get("healthCondition", [])
            }

        with patch("clients.niaid.NIAIDClient", return_value=mock_nde_instance) as mock_cls:
            mock_cls.extract_ontology_annotations = mock_extract
            result = client.resolve_disease("atherosclerosis")

        assert result.mondo_ids == ["0005311"]
        assert result.confidence == "partial"


# ---------------------------------------------------------------------------
# Expand MONDO ID
# ---------------------------------------------------------------------------

class TestExpandMondoId:

    def test_basic_expansion(self):
        client = _make_client()
        client.sparql.get_subclasses.return_value = [
            {"subclass": f"{MONDO_URI_PREFIX}0005311", "label": "atherosclerosis"},
            {"subclass": f"{MONDO_URI_PREFIX}0004993", "label": "coronary atherosclerosis"},
            {"subclass": f"{MONDO_URI_PREFIX}0002491", "label": "cerebral atherosclerosis"},
        ]

        expansion = client.expand_mondo_id("0005311")

        assert "0005311" in expansion.expanded_ids
        assert "0004993" in expansion.expanded_ids
        assert expansion.root_id == "0005311"
        assert expansion.labels["0004993"] == "coronary atherosclerosis"

    def test_root_included_even_if_not_in_subclasses(self):
        client = _make_client()
        client.sparql.get_subclasses.return_value = [
            {"subclass": f"{MONDO_URI_PREFIX}0004993", "label": "coronary atherosclerosis"},
        ]

        expansion = client.expand_mondo_id("0005311")

        assert "0005311" in expansion.expanded_ids

    def test_deduplication(self):
        client = _make_client()
        client.sparql.get_subclasses.return_value = [
            {"subclass": f"{MONDO_URI_PREFIX}0005311", "label": "atherosclerosis"},
            {"subclass": f"{MONDO_URI_PREFIX}0005311", "label": "atherosclerosis"},
        ]

        expansion = client.expand_mondo_id("0005311")

        assert expansion.expanded_ids.count("0005311") == 1

    def test_caching(self):
        client = _make_client()
        client.sparql.get_subclasses.return_value = [
            {"subclass": f"{MONDO_URI_PREFIX}0005311", "label": "atherosclerosis"},
        ]

        client.expand_mondo_id("0005311")
        client.expand_mondo_id("0005311")

        assert client.sparql.get_subclasses.call_count == 1

    def test_uri_construction(self):
        client = _make_client()
        client.sparql.get_subclasses.return_value = []

        client.expand_mondo_id("0005311")

        uri_arg = client.sparql.get_subclasses.call_args[0][0]
        assert uri_arg == f"{MONDO_URI_PREFIX}0005311"


# ---------------------------------------------------------------------------
# Rank match helper
# ---------------------------------------------------------------------------

class TestRankMatch:

    def test_exact(self):
        assert DiseaseOntologyClient._rank_match("atherosclerosis", "atherosclerosis") == 0

    def test_starts_with(self):
        assert DiseaseOntologyClient._rank_match("athero", "atherosclerosis") == 1

    def test_contains(self):
        assert DiseaseOntologyClient._rank_match("sclerosis", "atherosclerosis") == 2
