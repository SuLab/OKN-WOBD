from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict


_HERE = Path(__file__).resolve()
_CONTEXT_DIR = _HERE.parent.parent / "context"
_NDE_CONTEXT_PATH = _CONTEXT_DIR / "nde_global.json"


@lru_cache()
def load_nde_context() :  # -> Dict[str, Any]:
    """
    Load the static NDE context JSON if present.

    Expects a file at `web/context/nde_global.json`, typically copied from
    the omnigraph-agent `dist/context/nde_global.json`. If the file is
    missing or invalid, returns an empty dict so callers can fail gracefully.
    """

    if not _NDE_CONTEXT_PATH.exists():
        return {}
    try:
        with _NDE_CONTEXT_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}

    return data if isinstance(data, dict) else {}


__all__ = ["load_nde_context"]

