"""Live integration tests for MCP tools.

Skipped unless RUN_INTEGRATION_TESTS=1 is set in the environment.
These tests hit real SPARQL endpoints and g:Profiler — they are slow
and require network access.

Usage:
    RUN_INTEGRATION_TESTS=1 python3.11 -m pytest tests/test_mcp_integration.py -v
"""

import os
import sys
from pathlib import Path

import pytest

# Ensure demos dir is on sys.path
_demos = str(Path(__file__).resolve().parents[1] / "scripts" / "demos")
if _demos not in sys.path:
    sys.path.insert(0, _demos)

from okn_wobd.mcp_server.server import _setup_demo_imports

_setup_demo_imports()

_skip = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 to run live integration tests",
)

slow = pytest.mark.slow


# Helper: get a tool function from a fresh server
def _get_tool_fn(name: str):
    from mcp.server.fastmcp import FastMCP
    from okn_wobd.mcp_server.tools_analysis import register_tools as reg_analysis
    from okn_wobd.mcp_server.tools_chatgeo import register_tools as reg_chatgeo

    server = FastMCP("integration-test")
    reg_analysis(server)
    reg_chatgeo(server)
    for t in server._tool_manager._tools.values():
        if t.name == name:
            return t.fn
    raise ValueError(f"Tool {name!r} not registered")


# ---------------------------------------------------------------------------
# Analysis tool integration tests
# ---------------------------------------------------------------------------

@_skip
@slow
class TestGeneDiseasePathsIntegration:

    def test_sfrp2_finds_connections(self):
        fn = _get_tool_fn("gene_disease_paths")
        result = fn(gene_symbol="SFRP2")

        assert "error" not in result
        assert result["gene"] == "SFRP2"
        assert result["total_connections"] > 0
        # Should find at least one connection from SPOKE
        sources = {c["source"] for c in result["connections"]}
        assert len(sources) >= 1

    def test_tp53_finds_connections(self):
        fn = _get_tool_fn("gene_disease_paths")
        result = fn(gene_symbol="TP53")

        assert "error" not in result
        assert result["total_connections"] > 0


@_skip
@slow
class TestGeneNeighborhoodIntegration:

    def test_cd19_neighborhood(self):
        fn = _get_tool_fn("gene_neighborhood")
        result = fn(gene_symbol="CD19", limit=5)

        assert "error" not in result
        assert result["gene_symbol"] == "CD19"
        assert len(result["graphs"]) > 0
        # At least one graph should return entities
        total = sum(g["entity_count"] for g in result["graphs"])
        assert total > 0


# ---------------------------------------------------------------------------
# Enrichment integration test (no ARCHS4 needed)
# ---------------------------------------------------------------------------

@_skip
@slow
class TestEnrichmentIntegration:

    def test_gene_list_enrichment(self):
        fn = _get_tool_fn("enrichment_analysis")
        result = fn(
            gene_list=["TP53", "BRCA1", "MYC", "EGFR", "KRAS", "PIK3CA", "AKT1"],
            organism="hsapiens",
        )

        assert "error" not in result
        assert result["genes_mapped"] > 0
        assert result["total_terms"] > 0
        # Cancer-related genes should enrich for at least some GO terms
        assert len(result["by_source"]) > 0


# ---------------------------------------------------------------------------
# Health check integration test
# ---------------------------------------------------------------------------

@_skip
class TestHealthCheckIntegration:

    def test_health_check(self):
        from okn_wobd.mcp_server.server import health_check

        result = health_check()
        assert result["server"] == "OKN-WOBD Analysis Server"
        assert result["capabilities"]["analysis_tools"] is True
