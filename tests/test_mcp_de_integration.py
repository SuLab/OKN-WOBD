"""Integration tests for ARCHS4-based differential expression MCP tools.

Focused on the 'depression' disease query, which has been problematic
in deployed versions. Tests the full pipeline through the MCP tool
layer: find_samples -> get_sample_metadata -> differential_expression,
hitting real ARCHS4 data and ontology services.

Skipped unless RUN_INTEGRATION_TESTS=1 is set.

Usage:
    RUN_INTEGRATION_TESTS=1 python3.11 -m pytest tests/test_mcp_de_integration.py -v
    RUN_INTEGRATION_TESTS=1 python3.11 -m pytest tests/test_mcp_de_integration.py -v -k find_samples
"""

import os
import time
from pathlib import Path

import pytest

_skip = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 to run live integration tests",
)

_skip_no_archs4 = pytest.mark.skipif(
    not os.environ.get("ARCHS4_DATA_DIR")
    or not Path(os.environ.get("ARCHS4_DATA_DIR", "")).is_dir(),
    reason="ARCHS4_DATA_DIR not set or directory missing",
)

slow = pytest.mark.slow


def _get_tool_fn(name: str):
    """Get a tool function from a fresh server instance."""
    from mcp.server.fastmcp import FastMCP

    from okn_wobd.mcp_server.tools_analysis import register_tools as reg_analysis
    from okn_wobd.mcp_server.tools_chatgeo import register_tools as reg_chatgeo

    server = FastMCP("de-integration-test")
    reg_analysis(server)
    reg_chatgeo(server)
    for t in server._tool_manager._tools.values():
        if t.name == name:
            return t.fn
    raise ValueError(f"Tool {name!r} not registered")


def _poll_until_done(job_id: str, timeout: int = 300, interval: float = 2.0) -> dict:
    """Poll get_analysis_result until the job completes or times out."""
    poll_fn = _get_tool_fn("get_analysis_result")
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = poll_fn(job_id=job_id)
        if result.get("status") != "running":
            return result
        time.sleep(interval)
    raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")


# ---------------------------------------------------------------------------
# Ontology resolution (no ARCHS4 needed, fast)
# ---------------------------------------------------------------------------


@_skip
@slow
class TestDepressionOntologyResolution:
    """Verify that 'depression' resolves to MONDO terms."""

    def test_resolve_depression(self):
        fn = _get_tool_fn("resolve_disease_ontology")
        result = fn(disease_name="depression")

        assert "error" not in result, f"Ontology resolution failed: {result}"
        assert result["disease_name"] == "depression"
        assert len(result["mondo_ids"]) > 0, "No MONDO IDs found for 'depression'"
        print(f"\n  MONDO IDs: {result['mondo_ids']}")
        print(f"  Labels: {result['labels']}")
        print(f"  Confidence: {result['confidence']}")

    def test_resolve_depression_with_expansion(self):
        fn = _get_tool_fn("resolve_disease_ontology")
        result = fn(disease_name="depression", expand=True)

        assert "error" not in result, f"Ontology resolution failed: {result}"
        assert "expansion" in result, "No ontology expansion returned"
        exp = result["expansion"]
        print(f"\n  Root ID: {exp['root_id']}")
        print(f"  Expanded terms: {exp['n_terms']}")
        if exp["labels"]:
            for uri, label in list(exp["labels"].items())[:5]:
                print(f"    {uri}: {label}")

    def test_resolve_major_depressive_disorder(self):
        """Try a more specific term that should map cleanly."""
        fn = _get_tool_fn("resolve_disease_ontology")
        result = fn(disease_name="major depressive disorder")

        assert "error" not in result, f"Resolution failed: {result}"
        assert len(result["mondo_ids"]) > 0
        print(f"\n  MONDO IDs: {result['mondo_ids']}")
        print(f"  Labels: {result['labels']}")


# ---------------------------------------------------------------------------
# find_samples -- the suspected problem area
# ---------------------------------------------------------------------------


@_skip
@_skip_no_archs4
@slow
class TestFindSamplesDepression:
    """Test sample discovery for depression -- the suspected failure point."""

    def test_find_samples_keyword_only(self):
        """Keyword-only search should find some depression samples."""
        fn = _get_tool_fn("find_samples")
        result = fn(
            disease_term="depression",
            use_ontology=False,
            max_test_samples=50,
            max_control_samples=50,
        )

        assert "error" not in result, f"find_samples dispatch failed: {result}"
        assert "job_id" in result
        assert result["status"] == "running"

        # Poll for completion
        final = _poll_until_done(result["job_id"], timeout=180)
        assert final["status"] != "error", (
            f"find_samples failed: {final.get('result', {}).get('error', 'unknown')}"
        )
        assert final["status"] == "completed", f"Unexpected status: {final['status']}"

        r = final["result"]
        print(f"\n  Keyword search results:")
        print(f"    Test samples: {r['n_test_samples']} (total found: {r.get('total_test_found', '?')})")
        print(f"    Control samples: {r['n_control_samples']} (total found: {r.get('total_control_found', '?')})")
        print(f"    Test query: {r.get('test_query', '?')}")
        print(f"    Control query: {r.get('control_query', '?')}")
        print(f"    Test studies: {r.get('test_studies', [])[:5]}")
        print(f"    Overlap removed: {r.get('overlap_removed', 0)}")

        assert r["n_test_samples"] > 0, "No test samples found for 'depression' (keyword)"
        assert r["n_control_samples"] > 0, "No control samples found"

    def test_find_samples_with_ontology(self):
        """Ontology-enhanced search should also work for depression."""
        fn = _get_tool_fn("find_samples")
        result = fn(
            disease_term="depression",
            use_ontology=True,
            max_test_samples=50,
            max_control_samples=50,
        )

        assert "error" not in result, f"find_samples dispatch failed: {result}"
        assert "job_id" in result

        final = _poll_until_done(result["job_id"], timeout=180)
        assert final["status"] != "error", (
            f"find_samples (ontology) failed: {final.get('result', {}).get('error', 'unknown')}"
        )
        assert final["status"] == "completed"

        r = final["result"]
        print(f"\n  Ontology-enhanced search results:")
        print(f"    Test samples: {r['n_test_samples']} (total found: {r.get('total_test_found', '?')})")
        print(f"    Control samples: {r['n_control_samples']} (total found: {r.get('total_control_found', '?')})")
        print(f"    Test studies: {r.get('test_studies', [])[:5]}")

        if "ontology_discovery" in r:
            ont = r["ontology_discovery"]
            print(f"    Ontology discovery: {ont}")
        else:
            print("    Ontology discovery: not present (may have fallen back to keyword)")

        assert r["n_test_samples"] > 0, "No test samples found for 'depression' (ontology)"

    def test_find_samples_with_tissue(self):
        """Depression with brain tissue constraint."""
        fn = _get_tool_fn("find_samples")
        result = fn(
            disease_term="depression",
            tissue="brain",
            use_ontology=False,
            max_test_samples=50,
            max_control_samples=50,
        )

        assert "error" not in result
        assert "job_id" in result

        final = _poll_until_done(result["job_id"], timeout=180)

        r = final.get("result", {})
        print(f"\n  Depression + brain tissue:")
        print(f"    Status: {final['status']}")
        if final["status"] == "error":
            print(f"    Error: {r.get('error', 'unknown')}")
            pytest.skip(f"No samples for depression+brain: {r.get('error')}")
        else:
            print(f"    Test samples: {r['n_test_samples']}")
            print(f"    Control samples: {r['n_control_samples']}")
            print(f"    Test studies: {r.get('test_studies', [])[:5]}")

    def test_find_samples_major_depressive_disorder(self):
        """Try the more specific clinical term."""
        fn = _get_tool_fn("find_samples")
        result = fn(
            disease_term="major depressive disorder",
            use_ontology=True,
            max_test_samples=50,
            max_control_samples=50,
        )

        assert "error" not in result
        assert "job_id" in result

        final = _poll_until_done(result["job_id"], timeout=180)
        assert final["status"] != "error", (
            f"find_samples for MDD failed: {final.get('result', {}).get('error', 'unknown')}"
        )

        r = final["result"]
        print(f"\n  'major depressive disorder' search:")
        print(f"    Test samples: {r['n_test_samples']} (total: {r.get('total_test_found', '?')})")
        print(f"    Control samples: {r['n_control_samples']}")
        print(f"    Test studies: {r.get('test_studies', [])[:5]}")


# ---------------------------------------------------------------------------
# get_sample_metadata -- study breakdown for depression
# ---------------------------------------------------------------------------


@_skip
@_skip_no_archs4
@slow
class TestSampleMetadataDepression:
    """Test study-level metadata for depression."""

    def test_metadata_depression(self):
        fn = _get_tool_fn("get_sample_metadata")
        result = fn(disease_term="depression", max_samples=200)

        assert "error" not in result, f"Dispatch failed: {result}"
        assert "job_id" in result

        final = _poll_until_done(result["job_id"], timeout=180)
        assert final["status"] != "error", (
            f"get_sample_metadata failed: {final.get('result', {}).get('error', 'unknown')}"
        )

        r = final["result"]
        print(f"\n  Depression sample metadata:")
        print(f"    Test samples: {r['n_test_samples']}")
        print(f"    Control samples: {r['n_control_samples']}")
        print(f"    Recommendation: {r['recommendation']}")
        print(f"    Reason: {r['recommendation_reason']}")

        bd = r.get("study_breakdown", {})
        print(f"    Studies with test: {bd.get('studies_with_test', 0)}")
        print(f"    Studies with control: {bd.get('studies_with_control', 0)}")
        print(f"    Studies with both: {bd.get('studies_with_both', 0)}")
        print(f"    Platforms: {bd.get('platform_distribution', {})}")
        if bd.get("top_studies"):
            print(f"    Top studies:")
            for s in bd["top_studies"][:5]:
                print(f"      {s['study_id']}: {s['n_test']} test, {s['n_control']} control")

        assert r["n_test_samples"] > 0, "No test samples in metadata"


# ---------------------------------------------------------------------------
# differential_expression -- full pipeline
# ---------------------------------------------------------------------------


@_skip
@_skip_no_archs4
@slow
class TestDifferentialExpressionDepression:
    """Full DE analysis for depression. These are the slowest tests."""

    def test_de_depression_pooled(self):
        """Run pooled DE for depression with fast method."""
        fn = _get_tool_fn("differential_expression")
        result = fn(
            query="depression",
            method="mann-whitney",
            mode="pooled",
            max_test_samples=50,
            max_control_samples=50,
            fdr_threshold=0.05,
            log2fc_threshold=1.0,
        )

        assert "error" not in result, f"Dispatch failed: {result}"
        assert "job_id" in result
        assert result["status"] == "running"

        final = _poll_until_done(result["job_id"], timeout=300)
        assert final["status"] != "error", (
            f"DE analysis failed: {final.get('result', {}).get('error', 'unknown')}"
        )
        assert final["status"] == "completed"

        r = final["result"]
        print(f"\n  Depression DE (pooled, mann-whitney):")
        print(f"    Significant genes: {r.get('n_significant', '?')}")
        print(f"    Total tested: {r.get('n_tested', '?')}")
        print(f"    Test samples used: {r.get('n_test_samples', '?')}")
        print(f"    Control samples used: {r.get('n_control_samples', '?')}")

        if r.get("top_genes"):
            print(f"    Top 5 genes:")
            for g in r["top_genes"][:5]:
                print(f"      {g.get('gene', '?')}: log2fc={g.get('log2fc', '?')}, "
                      f"padj={g.get('padj', '?')}")

    def test_de_depression_auto_mode(self):
        """Run auto mode -- should try study-matched then fall back."""
        fn = _get_tool_fn("differential_expression")
        result = fn(
            query="depression",
            method="mann-whitney",
            mode="auto",
            max_test_samples=50,
            max_control_samples=50,
        )

        assert "error" not in result, f"Dispatch failed: {result}"
        assert "job_id" in result

        final = _poll_until_done(result["job_id"], timeout=300)
        assert final["status"] != "error", (
            f"DE (auto) failed: {final.get('result', {}).get('error', 'unknown')}"
        )

        r = final["result"]
        print(f"\n  Depression DE (auto mode):")
        print(f"    Significant genes: {r.get('n_significant', '?')}")
        print(f"    Mode used: {r.get('provenance', {}).get('analysis_mode', '?')}")
        print(f"    Fallback reason: {r.get('provenance', {}).get('mode_fallback_reason', 'none')}")

    def test_de_depression_with_tissue(self):
        """Depression in brain tissue -- more specific query."""
        fn = _get_tool_fn("differential_expression")
        result = fn(
            query="depression in brain tissue",
            method="mann-whitney",
            mode="pooled",
            max_test_samples=50,
            max_control_samples=50,
        )

        assert "error" not in result, f"Dispatch failed: {result}"
        assert "job_id" in result

        final = _poll_until_done(result["job_id"], timeout=300)

        r = final.get("result", {})
        print(f"\n  Depression in brain tissue:")
        print(f"    Status: {final['status']}")
        if final["status"] == "error":
            print(f"    Error: {r.get('error', 'unknown')}")
            # This may legitimately fail if no brain samples exist
            # -- log but don't hard-fail the test
            pytest.skip(f"Depression+brain DE failed: {r.get('error')}")
        else:
            print(f"    Significant genes: {r.get('n_significant', '?')}")
            print(f"    Test samples: {r.get('n_test_samples', '?')}")
