"""Tests for the MCP server skeleton: module imports and health_check."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest


# Ensure demos dir is on sys.path for analysis_tools / chatgeo imports
_demos = str(Path(__file__).resolve().parents[1] / "scripts" / "demos")
if _demos not in sys.path:
    sys.path.insert(0, _demos)


def test_server_module_imports():
    """Server module loads without error."""
    from okn_wobd.mcp_server import server  # noqa: F401


def test_health_check_returns_dict():
    """health_check returns a dict with required keys."""
    from okn_wobd.mcp_server.server import _setup_demo_imports, health_check

    _setup_demo_imports()
    result = health_check()

    assert isinstance(result, dict)
    assert "server" in result
    assert "version" in result
    assert "capabilities" in result

    caps = result["capabilities"]
    assert "analysis_tools" in caps
    assert "chatgeo" in caps
    assert "archs4_data" in caps
    assert "anthropic_api_key" in caps


def test_health_check_analysis_tools_available():
    """With demos on sys.path, analysis_tools should be importable."""
    from okn_wobd.mcp_server.server import _setup_demo_imports, health_check

    _setup_demo_imports()
    result = health_check()
    assert result["capabilities"]["analysis_tools"] is True


def test_health_check_archs4_missing():
    """When ARCHS4_DATA_DIR is unset, archs4_data should be False."""
    from okn_wobd.mcp_server.server import _setup_demo_imports, health_check

    _setup_demo_imports()
    with patch.dict("os.environ", {}, clear=False):
        # Remove the key if it exists
        env = dict(os.environ)
        env.pop("ARCHS4_DATA_DIR", None)
        with patch.dict("os.environ", env, clear=True):
            result = health_check()
            assert result["capabilities"]["archs4_data"] is False


def test_redirect_prints(capsys):
    """redirect_prints should send stdout to stderr."""
    from okn_wobd.mcp_server.server import redirect_prints

    with redirect_prints():
        print("redirected message")

    captured = capsys.readouterr()
    # The message should NOT be on stdout
    assert "redirected message" not in captured.out
    # It should be on stderr
    assert "redirected message" in captured.err


# Need os for the mock
import os  # noqa: E402
