"""HGNC-based gene symbol to NCBI Gene ID mapper with local caching.

Downloads the HGNC complete gene set on first use and caches it locally.
Uses only stdlib (csv, urllib) — no pandas dependency.
"""

import csv
import logging
import os
import time
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional
from urllib.request import urlopen
from urllib.error import URLError

logger = logging.getLogger(__name__)

# HGNC complete set download URL (TSV)
HGNC_DOWNLOAD_URL = (
    "https://ftp.ebi.ac.uk/pub/databases/genenames/hgnc/tsv/hgnc_complete_set.txt"
)

# Default cache location
DEFAULT_CACHE_DIR = Path.home() / ".okn_wobd"
DEFAULT_CACHE_FILE = DEFAULT_CACHE_DIR / "hgnc_gene_map.tsv"

# Cache expiry: 30 days in seconds
CACHE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60


class GeneMapper:
    """Maps gene symbols to NCBI Gene IDs using a local HGNC cache.

    The mapper downloads the HGNC complete gene set on first use and
    caches it as a simple TSV file. The cache is refreshed if it is
    older than 30 days.

    Args:
        cache_path: Path to the cache file. Defaults to
            ``~/.okn_wobd/hgnc_gene_map.tsv``, overridable via the
            ``HGNC_CACHE_PATH`` environment variable.
    """

    def __init__(self, cache_path: Optional[Path] = None) -> None:
        if cache_path is not None:
            self._cache_path = Path(cache_path)
        else:
            env_path = os.environ.get("HGNC_CACHE_PATH")
            if env_path:
                self._cache_path = Path(env_path)
            else:
                self._cache_path = DEFAULT_CACHE_FILE

        self._symbol_to_ncbi: Optional[Dict[str, str]] = None

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def resolve_symbols(self, symbols: List[str]) -> Dict[str, Optional[str]]:
        """Resolve a list of gene symbols to NCBI Gene IDs.

        Args:
            symbols: Gene symbols (e.g., ``["IDO1", "CXCL10"]``)

        Returns:
            Dict mapping each symbol to its NCBI Gene ID string
            (e.g., ``"3620"``), or ``None`` if not found.
        """
        mapping = self.get_symbol_to_ncbi_map()
        result: Dict[str, Optional[str]] = {}
        for sym in symbols:
            # Try exact match first, then uppercase
            ncbi_id = mapping.get(sym) or mapping.get(sym.upper())
            result[sym] = ncbi_id
        return result

    def get_symbol_to_ncbi_map(self) -> Dict[str, str]:
        """Return the full symbol → NCBI Gene ID mapping.

        Loads from cache (downloading if needed) on first access.

        Returns:
            Dict mapping approved gene symbols (uppercase) to NCBI Gene ID strings.
        """
        if self._symbol_to_ncbi is None:
            self._symbol_to_ncbi = self._load_or_download()
        return self._symbol_to_ncbi

    # -----------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------

    def _load_or_download(self) -> Dict[str, str]:
        """Load the mapping from cache, downloading if stale or missing."""
        if self._cache_is_valid():
            logger.info("Loading HGNC gene map from cache: %s", self._cache_path)
            return self._read_cache()

        logger.info("Downloading HGNC complete gene set...")
        try:
            mapping = self._download_and_parse()
            self._write_cache(mapping)
            logger.info(
                "Cached %d gene symbol → NCBI ID mappings to %s",
                len(mapping),
                self._cache_path,
            )
            return mapping
        except (URLError, OSError, ValueError) as exc:
            logger.warning(
                "Failed to download HGNC data: %s. "
                "Gene symbols will not be resolved to NCBI IDs.",
                exc,
            )
            # Try stale cache as fallback
            if self._cache_path.exists():
                logger.info("Falling back to stale cache")
                return self._read_cache()
            return {}

    def _cache_is_valid(self) -> bool:
        """Check if the cache file exists and is fresh enough."""
        if not self._cache_path.exists():
            return False
        age = time.time() - self._cache_path.stat().st_mtime
        return age < CACHE_MAX_AGE_SECONDS

    def _download_and_parse(self) -> Dict[str, str]:
        """Download HGNC TSV and parse symbol → NCBI Gene ID mapping."""
        with urlopen(HGNC_DOWNLOAD_URL, timeout=120) as resp:
            raw = resp.read().decode("utf-8")

        reader = csv.DictReader(StringIO(raw), delimiter="\t")
        mapping: Dict[str, str] = {}

        for row in reader:
            symbol = (row.get("symbol") or "").strip()
            # entrez_id column contains the NCBI Gene ID
            entrez_id = (row.get("entrez_id") or "").strip()

            if symbol and entrez_id:
                mapping[symbol.upper()] = entrez_id

            # Also index previous symbols so renamed genes still resolve
            prev_symbols = (row.get("prev_symbol") or "").strip()
            if prev_symbols and entrez_id:
                for prev in prev_symbols.split("|"):
                    prev = prev.strip().strip('"')
                    if prev:
                        # Don't overwrite current approved symbols
                        mapping.setdefault(prev.upper(), entrez_id)

            # Index alias symbols
            alias_symbols = (row.get("alias_symbol") or "").strip()
            if alias_symbols and entrez_id:
                for alias in alias_symbols.split("|"):
                    alias = alias.strip().strip('"')
                    if alias:
                        mapping.setdefault(alias.upper(), entrez_id)

        return mapping

    def _read_cache(self) -> Dict[str, str]:
        """Read the cached TSV file."""
        mapping: Dict[str, str] = {}
        with self._cache_path.open("r", encoding="utf-8") as fh:
            reader = csv.reader(fh, delimiter="\t")
            next(reader, None)  # skip header
            for row in reader:
                if len(row) >= 2:
                    mapping[row[0]] = row[1]
        return mapping

    def _write_cache(self, mapping: Dict[str, str]) -> None:
        """Write the mapping to the cache file as TSV."""
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self._cache_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh, delimiter="\t")
            writer.writerow(["symbol", "ncbi_gene_id"])
            for symbol, ncbi_id in sorted(mapping.items()):
                writer.writerow([symbol, ncbi_id])
