#!/usr/bin/env python3
"""
ARCHS4 SQLite Metadata Index — fast indexed lookups for ARCHS4 HDF5 metadata.

ARCHS4's HDF5 file contains ~1.05M samples across ~250K studies. The archs4py
library has no indexing, so every metadata lookup (e.g., "which samples belong
to GSE12345?") loads the entire 1.05M-element series_id array and does a linear
scan. This module builds a one-time SQLite index (~400-600MB) that reduces
metadata lookups from ~600ms to ~1ms.

Usage:
    from clients.archs4_index import ARCHS4MetadataIndex
    from pathlib import Path

    idx = ARCHS4MetadataIndex(Path("human_gene_v2.latest.h5"))
    idx.ensure_built()

    # ~1ms instead of ~600ms
    samples = idx.get_samples_by_series("GSE64016")
    meta = idx.get_metadata_by_series("GSE64016")

    # FTS5-accelerated text search
    results = idx.search_metadata("psoriasis|psoriatic")
"""

import logging
import os
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

try:
    import pandas as pd
except ImportError:
    pd = None  # type: ignore

logger = logging.getLogger(__name__)

# Current schema version — bump to force rebuild on schema changes
SCHEMA_VERSION = "1"

# Map from internal short column names to archs4py-compatible column names
COLUMN_MAP = {
    "gsm_id": "geo_accession",
    "gse_id": "series_id",
    "title": "title",
    "source": "source_name_ch1",
    "characteristics": "characteristics_ch1",
    "protocol": "extract_protocol_ch1",
    "organism": "organism_ch1",
    "molecule": "molecule_ch1",
    "platform": "platform_id",
}

# Reverse map: archs4py column name -> internal short name
REVERSE_COLUMN_MAP = {v: k for k, v in COLUMN_MAP.items()}

# HDF5 dataset paths for each metadata field
H5_FIELD_PATHS = {
    "gsm_id": "meta/samples/geo_accession",
    "gse_id": "meta/samples/series_id",
    "title": "meta/samples/title",
    "source": "meta/samples/source_name_ch1",
    "characteristics": "meta/samples/characteristics_ch1",
    "protocol": "meta/samples/extract_protocol_ch1",
    "organism": "meta/samples/organism_ch1",
    "molecule": "meta/samples/molecule_ch1",
    "platform": "meta/samples/platform_id",
    "singlecellprobability": "meta/samples/singlecellprobability",
}

# Fields searched by FTS5 text queries
FTS_FIELDS = ("gsm_id", "title", "source", "characteristics")

# Fields searched by regex fallback
REGEX_SEARCH_FIELDS = ("title", "source", "characteristics")


def _decode(val) -> str:
    """Decode bytes to str, handling HDF5 byte strings."""
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return str(val) if val is not None else ""


class ARCHS4MetadataIndex:
    """SQLite-backed metadata index for ARCHS4 HDF5 files.

    The index is stored as a .metadata.db file alongside the HDF5 file.
    It is automatically built on first use and rebuilt when the HDF5 file
    changes (detected via mtime/size) or the schema version is bumped.

    Thread-safe: uses per-thread SQLite connections via threading.local().
    """

    def __init__(self, h5_path: Path):
        """
        Args:
            h5_path: Path to ARCHS4 HDF5 file.
        """
        self.h5_path = Path(h5_path)
        self.db_path = self.h5_path.with_suffix(".metadata.db")
        self._local = threading.local()

    # =========================================================================
    # Connection management
    # =========================================================================

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create a per-thread SQLite connection."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
            # Register regexp function for regex search fallback
            conn.create_function("regexp", 2, _sqlite_regexp)
            self._local.conn = conn
        return conn

    def close(self):
        """Close the current thread's connection."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    # =========================================================================
    # Build / staleness detection
    # =========================================================================

    def is_stale(self) -> bool:
        """Check if the index needs to be (re)built."""
        if not self.db_path.exists():
            return True
        try:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT value FROM meta WHERE key='schema_version'"
            ).fetchone()
            if not row or row[0] != SCHEMA_VERSION:
                return True
            row = conn.execute(
                "SELECT value FROM meta WHERE key='h5_mtime'"
            ).fetchone()
            if not row:
                return True
            stored_mtime = float(row[0])
            row = conn.execute(
                "SELECT value FROM meta WHERE key='h5_size'"
            ).fetchone()
            stored_size = int(row[0]) if row else -1
            stat = self.h5_path.stat()
            return stat.st_mtime != stored_mtime or stat.st_size != stored_size
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            return True

    def ensure_built(
        self,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        force: bool = False,
    ):
        """Build the index if it doesn't exist or is stale.

        Args:
            progress_callback: Optional callback(current, total) for progress reporting.
            force: Force rebuild even if index is current.
        """
        if not force and not self.is_stale():
            return
        self.build(progress_callback=progress_callback)

    def build(
        self,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ):
        """Build (or rebuild) the SQLite index from the HDF5 file.

        This reads all sample metadata from the HDF5 file and inserts it
        into SQLite with appropriate indexes. Takes ~2-3 minutes for 1.05M samples.

        Args:
            progress_callback: Optional callback(current, total) for progress reporting.
        """
        import h5py

        # Close any existing connection since we're replacing the DB
        self.close()

        # Build into a temp file, then atomically replace
        tmp_path = self.db_path.with_suffix(".db.tmp")
        try:
            if tmp_path.exists():
                tmp_path.unlink()

            conn = sqlite3.connect(str(tmp_path))
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=OFF")  # Safe: we're building from scratch
            conn.execute("PRAGMA cache_size=-128000")  # 128MB for build

            # Create schema
            conn.executescript(_CREATE_SCHEMA_SQL)

            t0 = time.time()
            logger.info("Building ARCHS4 metadata index from %s ...", self.h5_path)

            with h5py.File(str(self.h5_path), "r") as f:
                # Read all metadata fields at once
                n_samples = len(f[H5_FIELD_PATHS["gsm_id"]])
                logger.info("Reading %d samples from HDF5...", n_samples)

                data = {}
                for field, path in H5_FIELD_PATHS.items():
                    if path in f or path.split("/")[-1] in f.get(
                        "/".join(path.split("/")[:-1]), {}
                    ):
                        try:
                            data[field] = f[path][:]
                        except KeyError:
                            data[field] = None
                    else:
                        data[field] = None

                # Batch insert
                batch_size = 50000
                for start in range(0, n_samples, batch_size):
                    end = min(start + batch_size, n_samples)
                    rows = []
                    for i in range(start, end):
                        row = [i]  # idx
                        for field in (
                            "gsm_id", "gse_id", "title", "source",
                            "characteristics", "protocol", "organism",
                            "molecule", "platform",
                        ):
                            arr = data.get(field)
                            if arr is not None:
                                row.append(_decode(arr[i]))
                            else:
                                row.append("")
                        # singlecellprobability
                        sc_arr = data.get("singlecellprobability")
                        if sc_arr is not None:
                            try:
                                row.append(float(sc_arr[i]))
                            except (ValueError, TypeError):
                                row.append(0.0)
                        else:
                            row.append(0.0)
                        rows.append(row)

                    conn.executemany(
                        "INSERT INTO samples "
                        "(idx, gsm_id, gse_id, title, source, characteristics, "
                        "protocol, organism, molecule, platform, sc_prob) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        rows,
                    )

                    if progress_callback:
                        progress_callback(end, n_samples)

            # Build FTS5 index
            logger.info("Building FTS5 full-text index...")
            conn.execute(
                "INSERT INTO samples_fts(rowid, gsm_id, title, source, characteristics) "
                "SELECT idx, gsm_id, title, source, characteristics FROM samples"
            )

            # Store build metadata
            stat = self.h5_path.stat()
            conn.executemany(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                [
                    ("h5_mtime", str(stat.st_mtime)),
                    ("h5_size", str(stat.st_size)),
                    ("schema_version", SCHEMA_VERSION),
                    ("n_samples", str(n_samples)),
                    ("build_timestamp", str(time.time())),
                ],
            )

            conn.commit()
            conn.execute("PRAGMA optimize")
            conn.close()

            # Atomic rename
            if self.db_path.exists():
                self.db_path.unlink()
            tmp_path.rename(self.db_path)

            elapsed = time.time() - t0
            db_size_mb = self.db_path.stat().st_size / 1e6
            logger.info(
                "Index built: %d samples, %.0f MB, %.1fs",
                n_samples, db_size_mb, elapsed,
            )

        except Exception:
            # Clean up temp file on failure
            if tmp_path.exists():
                tmp_path.unlink()
            raise

    # =========================================================================
    # Query methods
    # =========================================================================

    def has_series(self, gse_id: str) -> bool:
        """Check if a GEO series exists in the index. ~1ms."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT 1 FROM samples WHERE gse_id = ? LIMIT 1", (gse_id,)
        ).fetchone()
        return row is not None

    def get_samples_by_series(self, gse_id: str) -> List[str]:
        """Get all GSM IDs for a GEO series. ~1ms."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT gsm_id FROM samples WHERE gse_id = ?", (gse_id,)
        ).fetchall()
        return [r[0] for r in rows]

    def get_metadata_by_series(
        self,
        gse_id: str,
        fields: Optional[List[str]] = None,
    ) -> "pd.DataFrame":
        """Get metadata for all samples in a GEO series. ~5ms.

        Returns a DataFrame with archs4py-compatible column names.
        """
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM samples WHERE gse_id = ?", (gse_id,)
        ).fetchall()
        return self._rows_to_dataframe(rows, fields)

    def get_metadata_by_samples(
        self,
        gsm_ids: List[str],
        fields: Optional[List[str]] = None,
    ) -> "pd.DataFrame":
        """Get metadata for specific GSM IDs. ~10ms for typical batches.

        Uses chunked IN queries to avoid SQLite variable limits.
        """
        if not gsm_ids:
            return pd.DataFrame()

        conn = self._get_conn()
        all_rows = []
        # SQLite has a default SQLITE_MAX_VARIABLE_NUMBER of 999
        chunk_size = 900
        for i in range(0, len(gsm_ids), chunk_size):
            chunk = gsm_ids[i : i + chunk_size]
            placeholders = ",".join("?" * len(chunk))
            rows = conn.execute(
                f"SELECT * FROM samples WHERE gsm_id IN ({placeholders})",
                chunk,
            ).fetchall()
            all_rows.extend(rows)
        return self._rows_to_dataframe(all_rows, fields)

    def search_metadata(
        self,
        pattern: str,
        fields: Optional[List[str]] = None,
    ) -> "pd.DataFrame":
        """Search metadata by text pattern. ~0.1-0.5s.

        Uses FTS5 for simple OR patterns (e.g., "psoriasis|psoriatic"),
        falls back to SQLite REGEXP for complex regex patterns.
        """
        fts_query = _pattern_to_fts5(pattern)
        if fts_query is not None:
            return self._search_fts5(fts_query, fields)
        return self._search_regexp(pattern, fields)

    def _search_fts5(
        self,
        fts_query: str,
        fields: Optional[List[str]] = None,
    ) -> "pd.DataFrame":
        """FTS5 full-text search."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT s.* FROM samples s "
            "JOIN samples_fts f ON s.idx = f.rowid "
            "WHERE samples_fts MATCH ?",
            (fts_query,),
        ).fetchall()
        return self._rows_to_dataframe(rows, fields)

    def _search_regexp(
        self,
        pattern: str,
        fields: Optional[List[str]] = None,
    ) -> "pd.DataFrame":
        """Regex search using SQLite REGEXP function."""
        conn = self._get_conn()
        clauses = " OR ".join(
            f"regexp(?, {field})" for field in REGEX_SEARCH_FIELDS
        )
        params = [pattern] * len(REGEX_SEARCH_FIELDS)
        rows = conn.execute(
            f"SELECT * FROM samples WHERE {clauses}",
            params,
        ).fetchall()
        return self._rows_to_dataframe(rows, fields)

    def get_sample_indices(self, gsm_ids: List[str]) -> Dict[str, int]:
        """Get HDF5 row indices for GSM IDs. For expression retrieval."""
        if not gsm_ids:
            return {}
        conn = self._get_conn()
        result = {}
        chunk_size = 900
        for i in range(0, len(gsm_ids), chunk_size):
            chunk = gsm_ids[i : i + chunk_size]
            placeholders = ",".join("?" * len(chunk))
            rows = conn.execute(
                f"SELECT gsm_id, idx FROM samples WHERE gsm_id IN ({placeholders})",
                chunk,
            ).fetchall()
            for r in rows:
                result[r[0]] = r[1]
        return result

    def get_sample_count(self) -> int:
        """Get total number of indexed samples."""
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(*) FROM samples").fetchone()
        return row[0] if row else 0

    def get_series_count(self) -> int:
        """Get total number of unique series in the index."""
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(DISTINCT gse_id) FROM samples").fetchone()
        return row[0] if row else 0

    # =========================================================================
    # Helpers
    # =========================================================================

    def _rows_to_dataframe(
        self,
        rows: list,
        fields: Optional[List[str]] = None,
    ) -> "pd.DataFrame":
        """Convert SQLite rows to a pandas DataFrame with archs4py-compatible columns."""
        if not rows:
            return pd.DataFrame()

        # All columns from the samples table
        all_internal = [
            "idx", "gsm_id", "gse_id", "title", "source",
            "characteristics", "protocol", "organism", "molecule",
            "platform", "sc_prob",
        ]
        data = {col: [] for col in all_internal}
        for row in rows:
            for i, col in enumerate(all_internal):
                data[col].append(row[i])

        df = pd.DataFrame(data)

        # Rename to archs4py-compatible column names
        rename = {k: v for k, v in COLUMN_MAP.items() if k in df.columns}
        rename["sc_prob"] = "singlecellprobability"
        df = df.rename(columns=rename)
        df = df.drop(columns=["idx"], errors="ignore")

        # Filter to requested fields
        if fields:
            available = [f for f in fields if f in df.columns]
            if available:
                df = df[available]

        return df


def _sqlite_regexp(pattern: str, value: str) -> bool:
    """SQLite REGEXP function implementation."""
    if value is None:
        return False
    try:
        return re.search(pattern, value, re.IGNORECASE) is not None
    except re.error:
        return False


def _pattern_to_fts5(pattern: str) -> Optional[str]:
    """Convert a search pattern to FTS5 query if possible.

    Supports simple OR patterns like "psoriasis|psoriatic|skin rash"
    where each alternative is a simple word or phrase (no regex metacharacters).

    Returns None if the pattern uses regex features that FTS5 can't handle.
    """
    # Check for regex-only metacharacters (not just pipe)
    # Allow: alphanumeric, spaces, pipe, hyphen, parentheses for grouping
    # Reject: *, +, ?, [, ], {, }, ^, $, \, .
    if re.search(r'[*+?\[\]{\\^$.]', pattern):
        return None

    # Strip outer parentheses from group: (a|b|c) -> a|b|c
    stripped = pattern.strip()
    if stripped.startswith("(") and stripped.endswith(")"):
        stripped = stripped[1:-1]

    # Split on pipe
    terms = [t.strip() for t in stripped.split("|") if t.strip()]
    if not terms:
        return None

    # Each term becomes an FTS5 quoted phrase, joined with OR
    fts_terms = []
    for term in terms:
        # Remove any remaining parens
        term = term.replace("(", "").replace(")", "").strip()
        if term:
            # Quote the term for FTS5
            escaped = term.replace('"', '""')
            fts_terms.append(f'"{escaped}"')

    if not fts_terms:
        return None

    return " OR ".join(fts_terms)


# SQL to create the schema
_CREATE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS samples (
    idx        INTEGER PRIMARY KEY,
    gsm_id     TEXT NOT NULL,
    gse_id     TEXT NOT NULL,
    title      TEXT NOT NULL DEFAULT '',
    source     TEXT NOT NULL DEFAULT '',
    characteristics TEXT NOT NULL DEFAULT '',
    protocol   TEXT NOT NULL DEFAULT '',
    organism   TEXT NOT NULL DEFAULT '',
    molecule   TEXT NOT NULL DEFAULT '',
    platform   TEXT NOT NULL DEFAULT '',
    sc_prob    REAL DEFAULT 0.0
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_gsm ON samples(gsm_id);
CREATE INDEX IF NOT EXISTS ix_gse ON samples(gse_id);

CREATE VIRTUAL TABLE IF NOT EXISTS samples_fts USING fts5(
    gsm_id, title, source, characteristics,
    content=samples, content_rowid=idx
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""
