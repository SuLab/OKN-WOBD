"""Unit tests for ChatGEO MCP tools (mocked ARCHS4 / g:Profiler)."""

import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure demos dir is on sys.path
_demos = str(Path(__file__).resolve().parents[1] / "scripts" / "demos")
if _demos not in sys.path:
    sys.path.insert(0, _demos)

from okn_wobd.mcp_server.server import _setup_demo_imports

_setup_demo_imports()

# Pre-import so patches work
import okn_wobd.mcp_server.tools_chatgeo  # noqa: F401


def _get_tool_fn(name: str):
    from mcp.server.fastmcp import FastMCP
    from okn_wobd.mcp_server.tools_chatgeo import register_tools

    server = FastMCP("test")
    register_tools(server)
    for t in server._tool_manager._tools.values():
        if t.name == name:
            return t.fn
    raise ValueError(f"Tool {name!r} not registered")


# ---------------------------------------------------------------------------
# ARCHS4 availability check
# ---------------------------------------------------------------------------

class TestArchs4Check:

    def test_missing_env_var(self):
        from okn_wobd.mcp_server.tools_chatgeo import _check_archs4

        with patch.dict(os.environ, {}, clear=True):
            err = _check_archs4()
            assert err is not None
            assert "ARCHS4_DATA_DIR" in err

    def test_nonexistent_directory(self):
        from okn_wobd.mcp_server.tools_chatgeo import _check_archs4

        with patch.dict(os.environ, {"ARCHS4_DATA_DIR": "/nonexistent/path"}):
            err = _check_archs4()
            assert err is not None
            assert "does not exist" in err

    def test_valid_directory(self, tmp_path):
        from okn_wobd.mcp_server.tools_chatgeo import _check_archs4

        with patch.dict(os.environ, {"ARCHS4_DATA_DIR": str(tmp_path)}):
            err = _check_archs4()
            assert err is None


# ---------------------------------------------------------------------------
# differential_expression
# ---------------------------------------------------------------------------

class TestDifferentialExpressionTool:

    def test_returns_error_without_archs4(self):
        fn = _get_tool_fn("differential_expression")
        with patch.dict(os.environ, {}, clear=True):
            result = fn(query="psoriasis in skin tissue")
            assert "error" in result
            assert "ARCHS4_DATA_DIR" in result["error"]

    @patch("chatgeo.cli.run_analysis")
    def test_wraps_run_analysis(self, mock_run):
        mock_run.return_value = {
            "sample_discovery": {"n_disease_samples": 50, "n_control_samples": 100},
            "de_results": {"genes_tested": 15000, "genes_significant": 42, "significant_genes": []},
            "enrichment": {},
            "provenance": {},
        }

        fn = _get_tool_fn("differential_expression")
        with patch.dict(os.environ, {"ARCHS4_DATA_DIR": "/tmp"}):
            with patch("os.path.isdir", return_value=True):
                with patch("pathlib.Path.is_dir", return_value=True):
                    result = fn(query="psoriasis in skin tissue")

        assert "error" not in result
        assert result["de_results"]["genes_significant"] == 42
        # Verify it passed interpret=False
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["interpret"] is False

    @patch("chatgeo.cli.run_analysis")
    def test_catches_system_exit(self, mock_run):
        mock_run.side_effect = SystemExit(1)

        fn = _get_tool_fn("differential_expression")
        with patch.dict(os.environ, {"ARCHS4_DATA_DIR": "/tmp"}):
            with patch("pathlib.Path.is_dir", return_value=True):
                result = fn(query="nonexistent disease")

        assert "error" in result
        assert "exit code" in result["error"].lower()

    @patch("chatgeo.cli.run_analysis")
    def test_catches_exceptions(self, mock_run):
        mock_run.side_effect = RuntimeError("HDF5 file corrupted")

        fn = _get_tool_fn("differential_expression")
        with patch.dict(os.environ, {"ARCHS4_DATA_DIR": "/tmp"}):
            with patch("pathlib.Path.is_dir", return_value=True):
                result = fn(query="psoriasis")

        assert "error" in result
        assert "HDF5" in result["error"]

    @patch("chatgeo.cli.run_analysis")
    def test_disease_tissue_override(self, mock_run):
        mock_run.return_value = {
            "sample_discovery": {},
            "de_results": {"genes_tested": 0, "genes_significant": 0, "significant_genes": []},
            "enrichment": {},
            "provenance": {},
        }

        fn = _get_tool_fn("differential_expression")
        with patch.dict(os.environ, {"ARCHS4_DATA_DIR": "/tmp"}):
            with patch("pathlib.Path.is_dir", return_value=True):
                fn(query="something", disease="asthma", tissue="lung")

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["disease"] == "asthma"
        assert call_kwargs["tissue"] == "lung"


# ---------------------------------------------------------------------------
# find_samples
# ---------------------------------------------------------------------------

class TestFindSamplesTool:

    def test_returns_error_without_archs4(self):
        fn = _get_tool_fn("find_samples")
        with patch.dict(os.environ, {}, clear=True):
            result = fn(disease_term="psoriasis")
            assert "error" in result

    @patch("chatgeo.sample_finder.SampleFinder")
    def test_returns_sample_info(self, MockFinder):
        import pandas as pd

        mock_pooled = MagicMock()
        mock_pooled.n_test = 10
        mock_pooled.n_control = 20
        mock_pooled.total_test_found = 15
        mock_pooled.total_control_found = 25
        mock_pooled.test_query = "psoriasis"
        mock_pooled.control_query = "healthy|control|normal"
        mock_pooled.test_ids = [f"GSM{i}" for i in range(10)]
        mock_pooled.control_ids = [f"GSM{i}" for i in range(100, 120)]
        mock_pooled.overlap_removed = 2
        mock_pooled.test_samples = pd.DataFrame({"series_id": ["GSE001"] * 10, "geo_accession": [f"GSM{i}" for i in range(10)]})
        mock_pooled.control_samples = pd.DataFrame({"series_id": ["GSE002"] * 20, "geo_accession": [f"GSM{i}" for i in range(100, 120)]})

        instance = MockFinder.return_value
        instance.find_pooled_samples.return_value = mock_pooled

        fn = _get_tool_fn("find_samples")
        with patch.dict(os.environ, {"ARCHS4_DATA_DIR": "/tmp"}):
            with patch("pathlib.Path.is_dir", return_value=True):
                result = fn(disease_term="psoriasis", tissue="skin")

        assert result["n_test_samples"] == 10
        assert result["n_control_samples"] == 20
        assert "GSE001" in result["test_studies"]
        assert result["overlap_removed"] == 2


# ---------------------------------------------------------------------------
# enrichment_analysis
# ---------------------------------------------------------------------------

class TestEnrichmentAnalysisTool:

    def test_empty_gene_list(self):
        fn = _get_tool_fn("enrichment_analysis")
        result = fn(gene_list=[])
        assert "error" in result
        assert "empty" in result["error"]

    @patch("chatgeo.enrichment_analyzer.GProfilerBackend")
    def test_returns_enrichment(self, MockBackend):
        from chatgeo.de_result import EnrichedTerm

        mock_term = EnrichedTerm(
            term_id="GO:0006915",
            term_name="apoptotic process",
            source="GO:BP",
            pvalue=1e-6,
            pvalue_adjusted=1e-5,
            term_size=500,
            query_size=4,
            intersection_size=3,
            precision=0.75,
            recall=0.006,
            genes=["TP53", "BRCA1", "MYC"],
        )
        instance = MockBackend.return_value
        instance.analyze.return_value = ([mock_term], 4)

        fn = _get_tool_fn("enrichment_analysis")
        result = fn(gene_list=["TP53", "BRCA1", "MYC", "EGFR"])

        assert result["input_genes"] == 4
        assert result["genes_mapped"] == 4
        assert result["total_terms"] == 1
        assert "GO:BP" in result["by_source"]
        assert result["by_source"]["GO:BP"][0]["term_name"] == "apoptotic process"

    @patch("chatgeo.enrichment_analyzer.GProfilerBackend")
    def test_handles_import_error(self, MockBackend):
        instance = MockBackend.return_value
        instance.analyze.side_effect = ImportError("No module named 'gprofiler'")

        fn = _get_tool_fn("enrichment_analysis")
        result = fn(gene_list=["TP53"])

        assert "error" in result
        assert "gprofiler" in result["error"].lower()

    @patch("chatgeo.enrichment_analyzer.GProfilerBackend")
    def test_no_results(self, MockBackend):
        instance = MockBackend.return_value
        instance.analyze.return_value = ([], 3)

        fn = _get_tool_fn("enrichment_analysis")
        result = fn(gene_list=["TP53", "BRCA1", "MYC"])

        assert result["total_terms"] == 0
        assert result["by_source"] == {}


# ---------------------------------------------------------------------------
# Background job dispatch (deseq2)
# ---------------------------------------------------------------------------

class TestBackgroundJobDispatch:

    def test_deseq2_returns_job_id(self):
        """DESeq2 method should dispatch to background and return job_id."""
        fn = _get_tool_fn("differential_expression")
        with patch.dict(os.environ, {"ARCHS4_DATA_DIR": "/tmp"}):
            with patch("pathlib.Path.is_dir", return_value=True):
                # Don't actually run the analysis — it will fail in the
                # background thread, but we only need to verify the dispatch
                result = fn(query="psoriasis in skin", method="deseq2")

        assert "job_id" in result
        assert result["status"] == "running"
        assert "get_analysis_result" in result["message"]

    @patch("chatgeo.cli.run_analysis")
    def test_mann_whitney_runs_synchronously(self, mock_run):
        """Mann-Whitney should NOT dispatch to background."""
        mock_run.return_value = {
            "sample_discovery": {},
            "de_results": {"genes_tested": 0, "genes_significant": 0, "significant_genes": []},
            "enrichment": {},
            "provenance": {},
        }

        fn = _get_tool_fn("differential_expression")
        with patch.dict(os.environ, {"ARCHS4_DATA_DIR": "/tmp"}):
            with patch("pathlib.Path.is_dir", return_value=True):
                result = fn(query="psoriasis in skin", method="mann-whitney")

        # Should get direct results, not a job_id
        assert "job_id" not in result
        assert "de_results" in result


# ---------------------------------------------------------------------------
# get_analysis_result
# ---------------------------------------------------------------------------

class TestGetAnalysisResult:

    def test_unknown_job_id(self):
        fn = _get_tool_fn("get_analysis_result")
        result = fn(job_id="nonexistent")
        assert "error" in result

    def test_completed_job(self):
        from okn_wobd.mcp_server.tools_chatgeo import _jobs, _jobs_lock

        job_id = "test-done"
        with _jobs_lock:
            _jobs[job_id] = {
                "status": "completed",
                "result": {"de_results": {"genes_significant": 42}},
                "finished_at": time.time(),
            }

        fn = _get_tool_fn("get_analysis_result")
        result = fn(job_id=job_id)

        assert result["status"] == "completed"
        assert result["result"]["de_results"]["genes_significant"] == 42

        # Cleanup
        with _jobs_lock:
            _jobs.pop(job_id, None)

    def test_running_job(self):
        from okn_wobd.mcp_server.tools_chatgeo import _jobs, _jobs_lock

        job_id = "test-running"
        with _jobs_lock:
            _jobs[job_id] = {
                "status": "running",
                "result": None,
                "started_at": time.time() - 30,
            }

        fn = _get_tool_fn("get_analysis_result")
        result = fn(job_id=job_id)

        assert result["status"] == "running"
        assert result["elapsed_seconds"] >= 29
        assert "poll again" in result["message"].lower()

        # Cleanup
        with _jobs_lock:
            _jobs.pop(job_id, None)

    def test_error_job(self):
        from okn_wobd.mcp_server.tools_chatgeo import _jobs, _jobs_lock

        job_id = "test-error"
        with _jobs_lock:
            _jobs[job_id] = {
                "status": "error",
                "result": {"error": "No test samples found"},
                "finished_at": time.time(),
            }

        fn = _get_tool_fn("get_analysis_result")
        result = fn(job_id=job_id)

        assert result["status"] == "error"
        assert "No test samples" in result["result"]["error"]

        # Cleanup
        with _jobs_lock:
            _jobs.pop(job_id, None)
