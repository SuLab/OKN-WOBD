"""
Shared configuration for demo scripts.

Loads environment variables from .env and provides common paths and constants.

Usage:
    from config import load_config

    cfg = load_config()
    archs4_dir = cfg["archs4_data_dir"]
"""

import os
from pathlib import Path


def load_config() -> dict:
    """
    Load .env and return common paths/keys.

    Returns:
        Dict with configuration values:
        - archs4_data_dir: Path to ARCHS4 HDF5 files
        - anthropic_api_key: API key for Anthropic LLMs
        - data_dir: General data directory
        - demos_dir: Path to demos/ directory
    """
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    demos_dir = Path(__file__).parent

    return {
        "archs4_data_dir": os.environ.get("ARCHS4_DATA_DIR"),
        "anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY"),
        "data_dir": os.environ.get("DATA_DIR", str(demos_dir / "data")),
        "demos_dir": str(demos_dir),
    }
