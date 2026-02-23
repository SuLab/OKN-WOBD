"""Unit tests for SPARQL-based MCP analysis tools (mocked SPARQL)."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure demos dir is on sys.path
_demos = str(Path(__file__).resolve().parents[1] / "scripts" / "demos")
if _demos not in sys.path:
    sys.path.insert(0, _demos)

from okn_wobd.mcp_server.server import _setup_demo_imports

_setup_demo_imports()

# Pre-import the tool module so patches target the right namespace
import okn_wobd.mcp_server.tools_analysis  # noqa: F401


# Helper: create a fresh FastMCP, register tools, extract tool fn by name
def _get_tool_fn(name: str):
    from mcp.server.fastmcp import FastMCP
    from okn_wobd.mcp_server.tools_analysis import register_tools

    server = FastMCP("test")
    register_tools(server)
    for t in server._tool_manager._tools.values():
        if t.name == name:
            return t.fn
    raise ValueError(f"Tool {name!r} not registered")


# ---------------------------------------------------------------------------
# gene_disease_paths
# ---------------------------------------------------------------------------

class TestGeneDiseasePathsTool:

    @patch("analysis_tools.GeneDiseasePathFinder")
    def test_returns_connections(self, MockFinder):
        from analysis_tools.gene_paths import GeneDiseaseConnection

        mock_conn = GeneDiseaseConnection(
            gene_symbol="SFRP2",
            disease_id="MONDO:0005015",
            disease_name="diabetes mellitus",
            path_type="positive_marker",
            source="SPOKE-OKN",
        )
        instance = MockFinder.return_value
        instance.find_all_connections.return_value = [mock_conn]

        fn = _get_tool_fn("gene_disease_paths")
        result = fn(gene_symbol="sfrp2")

        assert result["gene"] == "SFRP2"
        assert result["total_connections"] == 1
        assert result["connections"][0]["disease_name"] == "diabetes mellitus"
        assert result["summary"]["by_source"]["SPOKE-OKN"] == 1

    @patch("analysis_tools.GeneDiseasePathFinder")
    def test_empty_results(self, MockFinder):
        instance = MockFinder.return_value
        instance.find_all_connections.return_value = []

        fn = _get_tool_fn("gene_disease_paths")
        result = fn(gene_symbol="NONEXISTENT")

        assert result["total_connections"] == 0
        assert result["connections"] == []

    @patch("analysis_tools.GeneDiseasePathFinder")
    def test_error_handling(self, MockFinder):
        instance = MockFinder.return_value
        instance.find_all_connections.side_effect = RuntimeError("SPARQL timeout")

        fn = _get_tool_fn("gene_disease_paths")
        result = fn(gene_symbol="TP53")

        assert "error" in result
        assert "SPARQL timeout" in result["error"]


# ---------------------------------------------------------------------------
# gene_neighborhood
# ---------------------------------------------------------------------------

class TestGeneNeighborhoodTool:

    def test_requires_gene_identifier(self):
        fn = _get_tool_fn("gene_neighborhood")
        result = fn()
        assert "error" in result
        assert "gene_symbol" in result["error"]

    @patch("analysis_tools.GeneNeighborhoodQuery")
    def test_returns_neighborhood(self, MockQuery):
        from analysis_tools.gene_neighborhood import GeneNeighborhood, GraphResult

        mock_neighborhood = GeneNeighborhood(
            gene_symbol="CD19",
            ncbi_gene_id="930",
            gene_iri="http://identifiers.org/ncbigene/930",
            timestamp="2026-02-09",
            graphs=[
                GraphResult(
                    graph_name="spoke-okn",
                    endpoint="https://frink.apps.renci.org/spoke-okn/sparql",
                    entities=[],
                )
            ],
        )
        instance = MockQuery.return_value
        instance.query_all.return_value = mock_neighborhood

        fn = _get_tool_fn("gene_neighborhood")
        result = fn(gene_symbol="CD19", limit=5)

        assert result["gene_symbol"] == "CD19"
        assert len(result["graphs"]) == 1

    @patch("analysis_tools.GeneNeighborhoodQuery")
    def test_handles_system_exit(self, MockQuery):
        """Gene resolution failure triggers sys.exit(1) — tool catches it."""
        instance = MockQuery.return_value
        instance.query_all.side_effect = SystemExit(1)

        fn = _get_tool_fn("gene_neighborhood")
        result = fn(gene_symbol="DOESNOTEXIST")
        assert "error" in result
        assert "not found" in result["error"].lower()

    @patch("analysis_tools.GeneNeighborhoodQuery")
    def test_ncbi_id_input(self, MockQuery):
        from analysis_tools.gene_neighborhood import GeneNeighborhood

        mock_neighborhood = GeneNeighborhood(
            gene_symbol="CD19",
            ncbi_gene_id="930",
            gene_iri="http://identifiers.org/ncbigene/930",
            timestamp="2026-02-09",
            graphs=[],
        )
        instance = MockQuery.return_value
        instance.query_all.return_value = mock_neighborhood

        fn = _get_tool_fn("gene_neighborhood")
        result = fn(ncbi_gene_id="930")
        assert result["ncbi_gene_id"] == "930"


# ---------------------------------------------------------------------------
# drug_disease_opposing_expression
# ---------------------------------------------------------------------------

class TestDrugDiseaseOpposingExpressionTool:

    def test_invalid_direction(self):
        fn = _get_tool_fn("drug_disease_opposing_expression")
        result = fn(drug_direction="sideways")
        assert "error" in result

    @patch("analysis_tools.find_drug_disease_genes")
    def test_returns_results(self, mock_fn):
        mock_fn.return_value = (
            [
                {
                    "gene": "TP53",
                    "gene_uri": "http://example.org/TP53",
                    "drug_study": "study1",
                    "drug_title": "Drug study",
                    "drug_log2fc": -3.5,
                    "drug_test_group": "treatment",
                    "drug_ref_group": "control",
                    "drug_name": "cisplatin",
                    "drug_id": "CHEMBL:11359",
                    "disease_study": "study2",
                    "disease_title": "Disease study",
                    "disease_log2fc": 2.5,
                    "disease": "lung cancer",
                    "disease_id": "EFO:0001071",
                    "disease_test_group": "disease",
                    "disease_ref_group": "normal",
                },
            ],
            "DOWN",
            "UP",
        )

        fn = _get_tool_fn("drug_disease_opposing_expression")
        result = fn(drug_direction="down", disease_direction="up")

        assert result["drug_label"] == "DOWN"
        assert result["disease_label"] == "UP"
        assert result["total_combinations"] == 1
        assert result["results"][0]["gene"] == "TP53"
        assert result["summary"]["unique_genes"] == 1

    @patch("analysis_tools.find_drug_disease_genes")
    def test_empty_results(self, mock_fn):
        mock_fn.return_value = ([], "DOWN", "UP")

        fn = _get_tool_fn("drug_disease_opposing_expression")
        result = fn()

        assert result["total_combinations"] == 0
        assert result["results"] == []

    @patch("analysis_tools.find_drug_disease_genes")
    def test_max_results_truncation(self, mock_fn):
        mock_fn.return_value = (
            [{"gene": f"GENE{i}", "drug_name": "drug", "drug_test_group": "t",
              "disease": "dis"} for i in range(100)],
            "DOWN",
            "UP",
        )

        fn = _get_tool_fn("drug_disease_opposing_expression")
        result = fn(max_results=5)

        assert len(result["results"]) == 5
        assert result["total_combinations"] == 100

    @patch("analysis_tools.find_drug_disease_genes")
    def test_error_handling(self, mock_fn):
        mock_fn.side_effect = RuntimeError("endpoint down")

        fn = _get_tool_fn("drug_disease_opposing_expression")
        result = fn()
        assert "error" in result
