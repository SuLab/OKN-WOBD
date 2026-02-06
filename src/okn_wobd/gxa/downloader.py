"""
GXA FTP Downloader - Incremental download from EBI Gene Expression Atlas.

Downloads experiment data from the EBI FTP server, filtering to only include
files needed by the GXA processing pipeline. Supports resume after interruption.
"""

import ftplib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# FTP server configuration
FTP_HOST = "ftp.ebi.ac.uk"
FTP_PATH = "/pub/databases/microarray/data/atlas/experiments"
DEFAULT_PREFIX = "E-GEOD"
DEFAULT_MAX_SIZE_MB = 10.0

# File extensions to skip
SKIP_EXTENSIONS = {
    ".png", ".eps", ".jpg", ".jpeg", ".gif", ".pdf", ".bedgraph", ".rdata",
}

SKIP_PATTERNS = [".undecorated", ".unrounded"]

# File patterns we want to download
WANTED_PATTERNS = [
    r"\.idf\.txt$",
    r"\.condensed-sdrf\.tsv$",
    r"\.sdrf\.tsv$",
    r"-configuration\.xml$",
    r"-analytics\.tsv$",
    r"\.go\.gsea\.tsv$",
    r"\.reactome\.gsea\.tsv$",
    r"\.interpro\.gsea\.tsv$",
    r"normalized-expressions\.tsv$",
]


@dataclass
class DownloadState:
    """Track download progress for resume capability."""

    completed_experiments: Set[str] = field(default_factory=set)
    in_progress: Optional[str] = None
    completed_files: Set[str] = field(default_factory=set)
    failed_files: Set[str] = field(default_factory=set)

    def save(self, path: Path) -> None:
        data = {
            "completed_experiments": list(self.completed_experiments),
            "in_progress": self.in_progress,
            "completed_files": list(self.completed_files),
            "failed_files": list(self.failed_files),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: Path) -> "DownloadState":
        if not path.exists():
            return cls()
        try:
            with open(path) as f:
                data = json.load(f)
            return cls(
                completed_experiments=set(data.get("completed_experiments", [])),
                in_progress=data.get("in_progress"),
                completed_files=set(data.get("completed_files", [])),
                failed_files=set(data.get("failed_files", [])),
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Could not load state file: {e}. Starting fresh.")
            return cls()


class GXADownloader:
    """Downloads GXA experiment data from EBI FTP server."""

    def __init__(
        self,
        data_dir: Path,
        prefix: str = DEFAULT_PREFIX,
        max_size_mb: float = DEFAULT_MAX_SIZE_MB,
        dry_run: bool = False,
    ):
        self.data_dir = Path(data_dir)
        self.prefix = prefix
        self.max_size = int(max_size_mb * 1024 * 1024)
        self.dry_run = dry_run
        self.state_file = self.data_dir / ".download_state.json"
        self.ftp: Optional[ftplib.FTP] = None
        self.state = DownloadState.load(self.state_file)
        self._wanted_regex = [re.compile(p, re.IGNORECASE) for p in WANTED_PATTERNS]

    def connect(self) -> None:
        logger.info(f"Connecting to {FTP_HOST}...")
        self.ftp = ftplib.FTP(FTP_HOST)
        self.ftp.login()
        self.ftp.cwd(FTP_PATH)
        logger.info("Connected successfully.")

    def disconnect(self) -> None:
        if self.ftp:
            try:
                self.ftp.quit()
            except Exception:
                pass
            self.ftp = None

    def list_experiments(self) -> List[str]:
        if not self.ftp:
            raise RuntimeError("Not connected to FTP server")

        logger.info(f"Listing experiments with prefix '{self.prefix}'...")
        experiments = []
        lines: List[str] = []
        self.ftp.dir(lines.append)

        for line in lines:
            parts = line.split()
            if not parts:
                continue
            name = parts[-1]
            if line.startswith("d") and name.startswith(self.prefix):
                experiments.append(name)

        experiments.sort()
        logger.info(f"Found {len(experiments)} experiments matching '{self.prefix}'")
        return experiments

    def list_files(self, experiment: str) -> List[Dict[str, Any]]:
        if not self.ftp:
            raise RuntimeError("Not connected to FTP server")

        files: List[Dict[str, Any]] = []
        try:
            self.ftp.cwd(f"{FTP_PATH}/{experiment}")
            try:
                for name, facts in self.ftp.mlsd():
                    if facts.get("type") == "file":
                        size = int(facts.get("size", 0))
                        files.append({"name": name, "size": size})
            except ftplib.error_perm:
                lines: List[str] = []
                self.ftp.dir(lines.append)
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 5 and not line.startswith("d"):
                        try:
                            size = int(parts[4])
                            name = parts[-1]
                            files.append({"name": name, "size": size})
                        except (ValueError, IndexError):
                            continue
        except ftplib.error_perm as e:
            logger.warning(f"Could not list files in {experiment}: {e}")

        return files

    def should_download(self, filename: str, size: int) -> bool:
        filename_lower = filename.lower()

        for ext in SKIP_EXTENSIONS:
            if filename_lower.endswith(ext):
                return False
        for pattern in SKIP_PATTERNS:
            if pattern in filename_lower:
                return False
        if size > self.max_size:
            return False

        for regex in self._wanted_regex:
            if regex.search(filename):
                return True
        return False

    def download_file(self, experiment: str, filename: str, size: int) -> bool:
        if not self.ftp:
            raise RuntimeError("Not connected to FTP server")

        local_dir_name = f"{experiment}-gea" if not experiment.endswith("-gea") else experiment
        local_dir = self.data_dir / local_dir_name
        local_dir.mkdir(parents=True, exist_ok=True)
        local_path = local_dir / filename
        file_key = f"{experiment}/{filename}"

        if file_key in self.state.completed_files:
            return True

        if local_path.exists():
            local_size = local_path.stat().st_size
            if local_size == size:
                self.state.completed_files.add(file_key)
                return True
            elif local_size < size:
                mode = "ab"
                rest = local_size
            else:
                mode = "wb"
                rest = None
        else:
            mode = "wb"
            rest = None

        if self.dry_run:
            logger.info(f"[DRY-RUN] Would download: {file_key} ({size:,} bytes)")
            return True

        try:
            self.ftp.cwd(f"{FTP_PATH}/{experiment}")
            with open(local_path, mode) as f:
                if rest:
                    self.ftp.retrbinary(f"RETR {filename}", f.write, rest=rest)
                else:
                    self.ftp.retrbinary(f"RETR {filename}", f.write)

            if local_path.stat().st_size == size:
                self.state.completed_files.add(file_key)
                logger.info(f"Downloaded: {file_key}")
                return True
            else:
                logger.warning(f"Size mismatch after download: {file_key}")
                return False

        except ftplib.error_perm as e:
            logger.error(f"FTP error downloading {file_key}: {e}")
            self.state.failed_files.add(file_key)
            return False
        except Exception as e:
            logger.error(f"Error downloading {file_key}: {e}")
            self.state.failed_files.add(file_key)
            return False

    def download_experiment(self, accession: str) -> tuple:
        """Download all needed files for a single experiment.

        Returns:
            Tuple of (success, files_downloaded)
        """
        if accession in self.state.completed_experiments:
            local_dir = self.data_dir / f"{accession}-gea"
            existing_files = len(list(local_dir.glob("*"))) if local_dir.exists() else 0
            return True, existing_files

        self.state.in_progress = accession
        self.state.save(self.state_file)

        files = self.list_files(accession)
        downloaded = 0
        failed = 0

        for file_info in files:
            filename = file_info["name"]
            size = file_info["size"]

            if self.should_download(filename, size):
                if self.download_file(accession, filename, size):
                    downloaded += 1
                else:
                    failed += 1

        if failed == 0:
            self.state.completed_experiments.add(accession)
            self.state.in_progress = None

        self.state.save(self.state_file)
        return failed == 0, downloaded

    def run(self, single_experiment: Optional[str] = None) -> int:
        """Main download orchestration. Returns number of experiments processed."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        processed = 0

        try:
            self.connect()

            if single_experiment:
                experiments = [single_experiment]
            else:
                experiments = self.list_experiments()

            remaining = [
                e for e in experiments
                if e not in self.state.completed_experiments
            ]

            logger.info(
                f"Processing {len(remaining)} experiments "
                f"({len(self.state.completed_experiments)} already completed)"
            )

            for i, experiment in enumerate(remaining, 1):
                logger.info(f"[{i}/{len(remaining)}] Downloading: {experiment}")
                try:
                    success, num_files = self.download_experiment(experiment)
                    if success:
                        logger.info(f"  Downloaded {num_files} files")
                        processed += 1
                    else:
                        logger.error(f"  Download failed for {experiment}")
                except Exception as e:
                    logger.error(f"  Error: {e}")
                    try:
                        self.disconnect()
                        self.connect()
                    except Exception:
                        pass

        finally:
            self.disconnect()

        return processed
