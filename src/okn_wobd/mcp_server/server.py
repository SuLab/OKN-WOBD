"""
OKN-WOBD MCP Server.

Exposes biomedical analysis tools (gene-disease paths, gene neighborhood,
drug-disease opposing expression, ChatGEO differential expression) over
the Model Context Protocol (MCP).

Supports three transports (set via ``OKN_MCP_TRANSPORT``):

* ``stdio`` (default) — local, launched by the client as a subprocess.
* ``streamable-http`` — remote, listens on HTTP (recommended for remote).
* ``sse`` — remote, Server-Sent Events (legacy).

For remote transports, set ``OKN_MCP_API_KEY`` to require Bearer-token
authentication.

Usage:
    python -m okn_wobd.mcp_server                          # stdio (default)
    OKN_MCP_TRANSPORT=streamable-http okn-wobd-mcp          # HTTP on :8000
    OKN_MCP_TRANSPORT=sse OKN_MCP_PORT=9000 okn-wobd-mcp    # SSE on :9000
"""

import contextlib
import io
import logging
import logging.handlers
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

__version__ = "0.1.0"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _configure_logging() -> None:
    """Set up file-based logging for the MCP server.

    Log file defaults to ``~/.okn_wobd/mcp_server.log`` (override with
    ``OKN_MCP_LOG_FILE``).  Level defaults to INFO (override with
    ``OKN_MCP_LOG_LEVEL``).  Uses a RotatingFileHandler (5 MB, 3 backups).
    """
    log_file = os.environ.get(
        "OKN_MCP_LOG_FILE",
        str(Path.home() / ".okn_wobd" / "mcp_server.log"),
    )
    log_level = os.environ.get("OKN_MCP_LOG_LEVEL", "INFO").upper()

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=3,
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    )

    logger = logging.getLogger("okn_wobd.mcp_server")
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    logger.addHandler(handler)

    logger.info("MCP server starting (version %s)", __version__)


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
# API-key auth middleware (for remote transports)
# ---------------------------------------------------------------------------

def _wrap_with_api_key_auth(app):
    """Wrap a Starlette app with Bearer-token API-key checking.

    Only active when ``OKN_MCP_API_KEY`` is set.  Requests must include
    ``Authorization: Bearer <key>``.  The MCP health/readiness probes and
    CORS preflight are allowed through without auth.
    """
    from starlette.middleware import Middleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    api_key = os.environ.get("OKN_MCP_API_KEY", "")
    if not api_key:
        return app  # no auth configured

    logger = logging.getLogger("okn_wobd.mcp_server")
    logger.info("API-key authentication enabled for remote transport")

    from starlette.middleware.base import BaseHTTPMiddleware

    class APIKeyMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            # Allow CORS preflight
            if request.method == "OPTIONS":
                return await call_next(request)
            auth = request.headers.get("Authorization", "")
            if auth == f"Bearer {api_key}":
                return await call_next(request)
            return JSONResponse(
                {"error": "Unauthorized"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )

    app.add_middleware(APIKeyMiddleware)
    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    _configure_logging()
    _setup_demo_imports()
    _register_analysis_tools()
    _register_chatgeo_tools()

    transport = os.environ.get("OKN_MCP_TRANSPORT", "stdio").lower()
    host = os.environ.get("OKN_MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("OKN_MCP_PORT", "8000"))

    logger = logging.getLogger("okn_wobd.mcp_server")

    if transport == "stdio":
        logger.info("Starting with stdio transport")
        mcp.run(transport="stdio")

    elif transport in ("streamable-http", "sse"):
        logger.info("Starting with %s transport on %s:%d", transport, host, port)

        # Update FastMCP settings for host/port
        mcp.settings.host = host
        mcp.settings.port = port

        # Build the Starlette ASGI app so we can add auth middleware
        if transport == "streamable-http":
            app = mcp.streamable_http_app()
        else:
            app = mcp.sse_app()

        app = _wrap_with_api_key_auth(app)

        # Run with uvicorn directly so middleware is included
        import uvicorn
        print(f"OKN-WOBD MCP server listening on http://{host}:{port}", file=sys.stderr)
        uvicorn.run(app, host=host, port=port, log_level="info")

    else:
        print(f"Unknown transport: {transport!r}. "
              f"Use 'stdio', 'streamable-http', or 'sse'.",
              file=sys.stderr)
        sys.exit(1)
