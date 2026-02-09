"""
OKN-WOBD MCP Server.

Exposes biomedical analysis tools (gene-disease paths, gene neighborhood,
drug-disease opposing expression, ChatGEO differential expression) over
the Model Context Protocol (MCP) stdio transport.

Usage:
    python -m okn_wobd.mcp_server
    okn-wobd-mcp
"""

import contextlib
import io
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

__version__ = "0.1.0"

# ---------------------------------------------------------------------------
# Path / env setup
# ---------------------------------------------------------------------------

def _setup_demo_imports():
    """Add ``scripts/demos/`` to sys.path so analysis_tools, chatgeo, clients,
    frink are importable.  Also load ``.env`` from that directory."""
    demos_dir = Path(__file__).resolve().parents[3] / "scripts" / "demos"
    demos_str = str(demos_dir)
    if demos_str not in sys.path:
        sys.path.insert(0, demos_str)

    # Load .env (matches chatgeo/cli.py pattern)
    try:
        from dotenv import load_dotenv
        load_dotenv(demos_dir / ".env")
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# stdout redirect — MCP uses stdout for JSON-RPC; tools print extensively
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def redirect_prints():
    """Context manager that redirects stdout to stderr so tool prints
    don't corrupt the MCP JSON-RPC channel."""
    old = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = old


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

mcp = FastMCP("OKN-WOBD Analysis Server")


@mcp.tool()
def health_check() -> dict:
    """Check server status and available capabilities.

    Returns a dict with server version, and availability flags for
    analysis_tools, chatgeo, ARCHS4 data, and Anthropic API key.
    """
    status: dict = {
        "server": "OKN-WOBD Analysis Server",
        "version": __version__,
        "capabilities": {},
    }

    # analysis_tools (SPARQL-based)
    try:
        import analysis_tools  # noqa: F401
        status["capabilities"]["analysis_tools"] = True
    except ImportError:
        status["capabilities"]["analysis_tools"] = False

    # chatgeo
    try:
        import chatgeo  # noqa: F401
        status["capabilities"]["chatgeo"] = True
    except ImportError:
        status["capabilities"]["chatgeo"] = False

    # ARCHS4 data directory
    archs4_dir = os.environ.get("ARCHS4_DATA_DIR", "")
    status["capabilities"]["archs4_data"] = bool(archs4_dir) and Path(archs4_dir).is_dir()

    # Anthropic API key (for LLM interpretation)
    status["capabilities"]["anthropic_api_key"] = bool(os.environ.get("ANTHROPIC_API_KEY"))

    return status


# ---------------------------------------------------------------------------
# Tool registration — imported lazily from tool modules
# ---------------------------------------------------------------------------

def _register_analysis_tools():
    """Register SPARQL-based analysis tools."""
    try:
        from okn_wobd.mcp_server.tools_analysis import register_tools
        register_tools(mcp)
    except ImportError:
        pass


def _register_chatgeo_tools():
    """Register ChatGEO tools."""
    try:
        from okn_wobd.mcp_server.tools_chatgeo import register_tools
        register_tools(mcp)
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    _setup_demo_imports()
    _register_analysis_tools()
    _register_chatgeo_tools()
    mcp.run(transport="stdio")
