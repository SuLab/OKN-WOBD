"""
Gene ID mapping utilities.

Maps between Ensembl and NCBI gene identifiers using HGNC data.
Uses a persistent file cache at ~/.okn_wobd/ (same pattern as de_rdf/gene_mapper.py).
"""

import time
from pathlib import Path
from typing import Dict

import pandas as pd


HGNC_URL = "https://storage.googleapis.com/public-download-files/hgnc/tsv/tsv/hgnc_complete_set.txt"
CACHE_DIR = Path.home() / ".okn_wobd"
CACHE_FILE = CACHE_DIR / "hgnc_ensembl_ncbi_map.tsv"
CACHE_MAX_AGE_DAYS = 30

# Module-level cache
_ensembl_to_ncbi: Dict[str, str] | None = None


def _load_hgnc_mapping() -> pd.DataFrame:
    """Load HGNC gene mapping data, using file cache when possible."""
    # Check file cache
    if CACHE_FILE.exists():
        age_days = (time.time() - CACHE_FILE.stat().st_mtime) / 86400
        if age_days < CACHE_MAX_AGE_DAYS:
            return pd.read_csv(CACHE_FILE, sep="\t", dtype=str)

    # Download fresh
    print("Downloading HGNC gene ID mappings...")
    try:
        df = pd.read_csv(
            HGNC_URL,
            sep="\t",
            usecols=["symbol", "ensembl_gene_id", "entrez_id"],
            dtype=str,
        )
        df = df.dropna(subset=["ensembl_gene_id", "entrez_id"])
        print(f"  Loaded {len(df)} gene mappings")

        # Save to cache
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(CACHE_FILE, sep="\t", index=False)

        return df
    except Exception as e:
        # Fall back to cache even if expired
        if CACHE_FILE.exists():
            print(f"Warning: Failed to download HGNC ({e}), using cached version")
            return pd.read_csv(CACHE_FILE, sep="\t", dtype=str)
        print(f"Warning: Failed to load HGNC mappings: {e}")
        return pd.DataFrame(columns=["symbol", "ensembl_gene_id", "entrez_id"])


def get_ensembl_to_ncbi_map() -> Dict[str, str]:
    """
    Get a dictionary mapping Ensembl gene IDs to NCBI gene IDs.

    Returns:
        Dict mapping Ensembl ID -> NCBI gene ID
    """
    global _ensembl_to_ncbi
    if _ensembl_to_ncbi is None:
        df = _load_hgnc_mapping()
        _ensembl_to_ncbi = dict(zip(df["ensembl_gene_id"], df["entrez_id"]))
    return _ensembl_to_ncbi


def add_ncbi_gene_ids(
    df: pd.DataFrame,
    ensembl_col: str = "identifier",
    ncbi_col: str = "ncbi_gene_id",
) -> pd.DataFrame:
    """
    Add NCBI gene IDs to a DataFrame with Ensembl IDs.

    Args:
        df: DataFrame with Ensembl gene IDs
        ensembl_col: Column name containing Ensembl IDs
        ncbi_col: Column name for NCBI gene IDs (will be added)

    Returns:
        DataFrame with ncbi_gene_id column added
    """
    mapping = get_ensembl_to_ncbi_map()
    df = df.copy()
    df[ncbi_col] = df[ensembl_col].map(mapping)
    return df
