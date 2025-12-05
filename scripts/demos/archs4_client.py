#!/usr/bin/env python3
"""
ARCHS4 Client - Interface for querying ARCHS4 gene expression data.

ARCHS4 (https://maayanlab.cloud/archs4/) is a repository of uniformly processed
RNA-seq data from GEO. This client wraps the archs4py library to provide a
convenient interface for:
- Downloading ARCHS4 data files (HDF5 format)
- Querying expression data by GEO series, sample IDs, or metadata search
- Retrieving sample metadata
- Normalizing expression data
- Filtering low-expression genes

Data Requirements:
    ARCHS4 stores data in large HDF5 files that must be downloaded first.
    Available files:
    - human_gene_v2.latest.h5 (human gene counts, ~15GB)
    - mouse_gene_v2.latest.h5 (mouse gene counts, ~23GB)
    - human_transcript_v2.latest.h5 (human transcript counts)
    - mouse_transcript_v2.latest.h5 (mouse transcript counts)

Usage:
    from archs4_client import ARCHS4Client

    # Initialize client (downloads data if needed)
    client = ARCHS4Client(organism="human", data_dir="./data")

    # Check if a series exists
    if client.has_series("GSE64016"):
        expr = client.get_expression_by_series("GSE64016")
        meta = client.get_metadata_by_series("GSE64016")

    # Search by metadata keywords
    expr = client.search_expression("myoblast differentiation")

References:
    - ARCHS4: https://maayanlab.cloud/archs4/
    - archs4py: https://github.com/MaayanLab/archs4py
"""

import os
from pathlib import Path
from typing import List, Dict, Optional, Union, Literal
from dataclasses import dataclass

try:
    import pandas as pd
except ImportError:
    pd = None  # type: ignore

try:
    import archs4py as a4
    HAS_ARCHS4 = True
except ImportError:
    HAS_ARCHS4 = False
    a4 = None  # type: ignore


# Default metadata fields commonly used for sample annotation
DEFAULT_META_FIELDS = [
    "geo_accession",
    "series_id",
    "title",
    "source_name_ch1",
    "characteristics_ch1",
    "extract_protocol_ch1",
    "organism_ch1",
    "molecule_ch1",
    "platform_id",
]

# Normalization methods supported by archs4py
NormMethod = Literal["log_quantile", "quantile", "cpm", "tmm"]


@dataclass
class ARCHS4DataFile:
    """Information about an ARCHS4 data file."""
    organism: str
    data_type: str  # "gene" or "transcript"
    path: Path
    exists: bool

    @property
    def filename(self) -> str:
        return self.path.name


class ARCHS4Client:
    """
    Client for querying ARCHS4 gene expression data.

    ARCHS4 provides uniformly processed RNA-seq data from GEO. This client
    supports querying by:
    - GEO series accession (GSE IDs)
    - Sample accessions (GSM IDs)
    - Metadata search (keywords, regex patterns)
    - Random sampling
    - Direct index access

    Example:
        client = ARCHS4Client(organism="human")

        # Get expression for a GEO series
        expr_df = client.get_expression_by_series("GSE64016")

        # Search by tissue/cell type
        expr_df = client.search_expression("pancreatic beta cell")

        # Get specific samples
        expr_df = client.get_expression_by_samples(["GSM1158284", "GSM1482938"])
    """

    # File naming convention for ARCHS4 data
    FILE_PATTERNS = {
        ("human", "gene"): "human_gene_v2.latest.h5",
        ("human", "transcript"): "human_transcript_v2.latest.h5",
        ("mouse", "gene"): "mouse_gene_v2.latest.h5",
        ("mouse", "transcript"): "mouse_transcript_v2.latest.h5",
    }

    def __init__(
        self,
        organism: Literal["human", "mouse"] = "human",
        data_type: Literal["gene", "transcript"] = "gene",
        data_dir: Optional[Union[str, Path]] = None,
        h5_path: Optional[Union[str, Path]] = None,
        auto_download: bool = False,
    ):
        """
        Initialize the ARCHS4 client.

        Args:
            organism: Species ("human" or "mouse")
            data_type: Count type ("gene" or "transcript")
            data_dir: Directory containing ARCHS4 H5 files. If None, uses current dir.
            h5_path: Direct path to H5 file (overrides organism/data_type/data_dir)
            auto_download: If True, automatically download data file if missing

        Raises:
            ImportError: If archs4py or pandas not installed
            FileNotFoundError: If H5 file not found and auto_download is False
        """
        if not HAS_ARCHS4:
            raise ImportError(
                "archs4py is required. Install with: pip install archs4py"
            )
        if pd is None:
            raise ImportError(
                "pandas is required. Install with: pip install pandas"
            )

        self.organism = organism
        self.data_type = data_type

        # Resolve H5 file path
        if h5_path:
            self.h5_path = Path(h5_path)
        else:
            data_dir = Path(data_dir) if data_dir else Path.cwd()
            filename = self.FILE_PATTERNS.get((organism, data_type))
            if not filename:
                raise ValueError(
                    f"Invalid organism/data_type: {organism}/{data_type}. "
                    f"Valid combinations: {list(self.FILE_PATTERNS.keys())}"
                )
            self.h5_path = data_dir / filename

        # Check if file exists
        if not self.h5_path.exists():
            if auto_download:
                self.download_data()
            else:
                raise FileNotFoundError(
                    f"ARCHS4 data file not found: {self.h5_path}\n"
                    f"Download with: client.download_data() or set auto_download=True\n"
                    f"Or download manually from: https://maayanlab.cloud/archs4/download.html"
                )

    # =========================================================================
    # Data Download
    # =========================================================================

    def download_data(
        self,
        version: str = "latest",
        path: Optional[Union[str, Path]] = None,
    ) -> Path:
        """
        Download ARCHS4 data file.

        Args:
            version: Data version ("latest" or specific version)
            path: Download directory (defaults to h5_path parent directory)

        Returns:
            Path to downloaded file

        Note:
            Files are large (15-25GB) and download may take time.
        """
        download_path = path or self.h5_path.parent
        download_path = Path(download_path)
        download_path.mkdir(parents=True, exist_ok=True)

        print(f"Downloading ARCHS4 {self.organism} {self.data_type} data...")
        print(f"This may take a while (file is 15-25GB)")

        a4.download.counts(
            self.organism,
            path=str(download_path),
            version=version
        )

        print(f"Download complete: {self.h5_path}")
        return self.h5_path

    @staticmethod
    def list_versions() -> None:
        """Display available ARCHS4 data versions."""
        a4.versions()

    def list_contents(self) -> None:
        """List the structure and contents of the H5 file."""
        a4.ls(str(self.h5_path))

    # =========================================================================
    # Expression Data Retrieval
    # =========================================================================

    def get_expression_by_series(
        self,
        geo_accession: str,
        genes: Optional[List[str]] = None,
        normalize: Optional[NormMethod] = None,
    ) -> pd.DataFrame:
        """
        Get expression data for all samples in a GEO series.

        Args:
            geo_accession: GEO series ID (e.g., "GSE64016")
            genes: Optional list of gene symbols to filter
            normalize: Optional normalization method

        Returns:
            DataFrame with genes as rows, samples as columns

        Example:
            expr = client.get_expression_by_series("GSE64016")
            expr = client.get_expression_by_series("GSE64016", genes=["TP53", "BRCA1"])
        """
        matrix = a4.data.series(str(self.h5_path), geo_accession)
        return self._process_expression(matrix, genes, normalize)

    def get_expression_by_samples(
        self,
        sample_ids: List[str],
        genes: Optional[List[str]] = None,
        normalize: Optional[NormMethod] = None,
    ) -> pd.DataFrame:
        """
        Get expression data for specific samples.

        Args:
            sample_ids: List of GEO sample IDs (e.g., ["GSM1158284", "GSM1482938"])
            genes: Optional list of gene symbols to filter
            normalize: Optional normalization method

        Returns:
            DataFrame with genes as rows, samples as columns

        Note:
            Sample IDs not found in ARCHS4 will be silently ignored.
        """
        matrix = a4.data.samples(str(self.h5_path), sample_ids)
        return self._process_expression(matrix, genes, normalize)

    def search_expression(
        self,
        search_term: str,
        genes: Optional[List[str]] = None,
        normalize: Optional[NormMethod] = None,
        remove_single_cell: bool = False,
        meta_fields: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Search for samples by metadata and return expression data.

        Args:
            search_term: Search query (supports regex, whitespace-insensitive)
            genes: Optional list of gene symbols to filter
            normalize: Optional normalization method
            remove_single_cell: If True, exclude single-cell RNA-seq samples
            meta_fields: Metadata fields to search (default: all fields)

        Returns:
            DataFrame with genes as rows, samples as columns

        Example:
            # Search for myoblast samples
            expr = client.search_expression("myoblast")

            # Search with regex
            expr = client.search_expression("pancrea.*beta")
        """
        kwargs = {
            "remove_sc": remove_single_cell,
        }
        if meta_fields:
            kwargs["meta_fields"] = meta_fields

        matrix = a4.data.meta(str(self.h5_path), search_term, **kwargs)
        return self._process_expression(matrix, genes, normalize)

    def get_expression_by_index(
        self,
        indices: List[int],
        genes: Optional[List[str]] = None,
        normalize: Optional[NormMethod] = None,
    ) -> pd.DataFrame:
        """
        Get expression data for samples at specific indices.

        Args:
            indices: List of sample indices in the H5 file
            genes: Optional list of gene symbols to filter
            normalize: Optional normalization method

        Returns:
            DataFrame with genes as rows, samples as columns
        """
        matrix = a4.data.index(str(self.h5_path), indices)
        return self._process_expression(matrix, genes, normalize)

    def get_random_samples(
        self,
        n: int = 100,
        genes: Optional[List[str]] = None,
        normalize: Optional[NormMethod] = None,
        remove_single_cell: bool = False,
    ) -> pd.DataFrame:
        """
        Get expression data for N random samples.

        Args:
            n: Number of random samples to retrieve
            genes: Optional list of gene symbols to filter
            normalize: Optional normalization method
            remove_single_cell: If True, exclude single-cell samples

        Returns:
            DataFrame with genes as rows, samples as columns
        """
        matrix = a4.data.rand(str(self.h5_path), n, remove_sc=remove_single_cell)
        return self._process_expression(matrix, genes, normalize)

    def _process_expression(
        self,
        matrix: pd.DataFrame,
        genes: Optional[List[str]] = None,
        normalize: Optional[NormMethod] = None,
    ) -> pd.DataFrame:
        """Apply gene filtering and normalization to expression matrix."""
        if matrix is None or matrix.empty:
            return pd.DataFrame()

        # Filter to specific genes
        if genes:
            available = [g for g in genes if g in matrix.index]
            if not available:
                raise ValueError(
                    f"None of the requested genes found. "
                    f"Requested: {genes[:5]}... Available: {list(matrix.index[:5])}..."
                )
            matrix = matrix.loc[available]

        # Apply normalization
        if normalize:
            matrix = a4.normalize(matrix, normalize)

        return matrix

    # =========================================================================
    # Metadata Retrieval
    # =========================================================================

    def get_metadata_by_series(
        self,
        geo_accession: str,
        fields: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Get metadata for all samples in a GEO series.

        Args:
            geo_accession: GEO series ID (e.g., "GSE64016")
            fields: Metadata fields to retrieve (default: common fields)

        Returns:
            DataFrame with samples as rows, metadata fields as columns
        """
        fields = fields or DEFAULT_META_FIELDS
        samples = a4.meta.series(str(self.h5_path), geo_accession)

        if not samples:
            return pd.DataFrame()

        return a4.meta.samples(str(self.h5_path), samples, fields)

    def get_metadata_by_samples(
        self,
        sample_ids: List[str],
        fields: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Get metadata for specific samples.

        Args:
            sample_ids: List of GEO sample IDs
            fields: Metadata fields to retrieve (default: common fields)

        Returns:
            DataFrame with samples as rows, metadata fields as columns
        """
        fields = fields or DEFAULT_META_FIELDS
        return a4.meta.samples(str(self.h5_path), sample_ids, fields)

    def search_metadata(
        self,
        search_term: str,
        fields: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Search for samples by metadata and return their metadata.

        Args:
            search_term: Search query (supports regex)
            fields: Metadata fields to retrieve (default: common fields)

        Returns:
            DataFrame with matching samples' metadata
        """
        fields = fields or DEFAULT_META_FIELDS
        return a4.meta.meta(str(self.h5_path), search_term, meta_fields=fields)

    def get_all_field_values(self, field: str) -> List[str]:
        """
        Get all unique values for a metadata field across all samples.

        Args:
            field: Metadata field name (e.g., "geo_accession", "series_id")

        Returns:
            List of all values for that field

        Example:
            # Get all series IDs in the database
            all_series = client.get_all_field_values("series_id")
        """
        return a4.meta.field(str(self.h5_path), field)

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    def has_series(self, geo_accession: str) -> bool:
        """
        Check if a GEO series exists in ARCHS4.

        Args:
            geo_accession: GEO series ID (e.g., "GSE64016")

        Returns:
            True if series has samples in ARCHS4, False otherwise
        """
        try:
            samples = a4.meta.series(str(self.h5_path), geo_accession)
            return len(samples) > 0 if samples else False
        except Exception:
            return False

    def get_series_sample_ids(self, geo_accession: str) -> List[str]:
        """
        Get all sample IDs (GSM) for a GEO series.

        Args:
            geo_accession: GEO series ID

        Returns:
            List of sample GEO accession IDs
        """
        samples = a4.meta.series(str(self.h5_path), geo_accession)
        return samples if samples else []

    def count_samples(self, search_term: Optional[str] = None) -> int:
        """
        Count samples matching a search term, or total samples if no term.

        Args:
            search_term: Optional search query

        Returns:
            Number of matching samples
        """
        if search_term:
            meta = self.search_metadata(search_term, fields=["geo_accession"])
            return len(meta) if meta is not None else 0
        else:
            all_ids = self.get_all_field_values("geo_accession")
            return len(all_ids)

    # =========================================================================
    # Data Processing Utilities
    # =========================================================================

    @staticmethod
    def normalize_expression(
        expression: pd.DataFrame,
        method: NormMethod = "log_quantile",
    ) -> pd.DataFrame:
        """
        Normalize expression data.

        Args:
            expression: Expression DataFrame (genes x samples)
            method: Normalization method:
                - "log_quantile": Log2 transform + quantile normalization
                - "quantile": Quantile normalization only
                - "cpm": Counts per million
                - "tmm": Trimmed mean of M-values

        Returns:
            Normalized expression DataFrame
        """
        return a4.normalize(expression, method)

    @staticmethod
    def filter_low_expression(
        expression: pd.DataFrame,
        read_threshold: int = 50,
        sample_threshold: float = 0.05,
        deterministic: bool = True,
        aggregate_duplicates: bool = True,
    ) -> pd.DataFrame:
        """
        Filter genes with low expression.

        Args:
            expression: Expression DataFrame (genes x samples)
            read_threshold: Minimum read count to consider expressed
            sample_threshold: Fraction of samples gene must be expressed in
            deterministic: Use deterministic filtering
            aggregate_duplicates: Sum counts for duplicate gene symbols

        Returns:
            Filtered expression DataFrame
        """
        return a4.utils.filter_genes(
            expression,
            readThreshold=read_threshold,
            sampleThreshold=sample_threshold,
            deterministic=deterministic,
            aggregate=aggregate_duplicates,
        )

    @staticmethod
    def aggregate_duplicates(expression: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregate duplicate gene symbols by summing their counts.

        Args:
            expression: Expression DataFrame with potentially duplicate gene symbols

        Returns:
            Expression DataFrame with unique gene symbols
        """
        return a4.utils.aggregate_duplicate_genes(expression)


def demo():
    """Demonstrate ARCHS4 client capabilities."""
    print("=" * 70)
    print("ARCHS4 Client Demo")
    print("=" * 70)

    # Show available versions
    print("\nAvailable ARCHS4 data versions:")
    try:
        ARCHS4Client.list_versions()
    except Exception as e:
        print(f"  Could not fetch versions: {e}")

    print("\n" + "-" * 70)
    print("Client Configuration")
    print("-" * 70)
    print("""
To use the ARCHS4 client, you need to download the data files first:

    from archs4_client import ARCHS4Client

    # Option 1: Download via client
    client = ARCHS4Client(organism="human", data_dir="./data", auto_download=True)

    # Option 2: Download manually from https://maayanlab.cloud/archs4/download.html
    # Then point to the file:
    client = ARCHS4Client(h5_path="/path/to/human_gene_v2.latest.h5")
""")

    # Check if we have data file available
    default_paths = [
        Path("human_gene_v2.latest.h5"),
        Path("./data/human_gene_v2.latest.h5"),
        Path.home() / "archs4" / "human_gene_v2.latest.h5",
    ]

    h5_path = None
    for path in default_paths:
        if path.exists():
            h5_path = path
            break

    if not h5_path:
        print("\n" + "-" * 70)
        print("Demo Data Not Available")
        print("-" * 70)
        print(f"""
No ARCHS4 data file found in default locations:
{chr(10).join(f'  - {p}' for p in default_paths)}

To run the full demo, download the data first:

    # Download using archs4py
    import archs4py as a4
    a4.download.counts("human", path="./data", version="latest")
""")
        return

    print("\n" + "-" * 70)
    print(f"Running demo with: {h5_path}")
    print("-" * 70)

    try:
        client = ARCHS4Client(h5_path=str(h5_path))

        # Demo 1: Check series availability
        print("\n1. Checking if GSE64016 exists in ARCHS4...")
        exists = client.has_series("GSE64016")
        print(f"   GSE64016 available: {exists}")

        if exists:
            # Demo 2: Get series metadata
            print("\n2. Getting metadata for GSE64016...")
            meta = client.get_metadata_by_series("GSE64016")
            print(f"   Found {len(meta)} samples")
            if len(meta) > 0:
                print(f"   Sample fields: {list(meta.columns)[:5]}...")
                print(f"   First sample: {meta.iloc[0]['geo_accession'] if 'geo_accession' in meta.columns else 'N/A'}")

            # Demo 3: Get expression data
            print("\n3. Getting expression data for GSE64016 (first 5 genes)...")
            expr = client.get_expression_by_series("GSE64016")
            print(f"   Expression matrix shape: {expr.shape}")
            print(f"   Genes: {list(expr.index[:5])}...")
            print(f"   Samples: {list(expr.columns[:3])}...")

        # Demo 4: Random sample
        print("\n4. Getting 5 random samples...")
        random_expr = client.get_random_samples(n=5)
        print(f"   Random samples shape: {random_expr.shape}")

        # Demo 5: Count total samples
        print("\n5. Counting samples...")
        total = client.count_samples()
        print(f"   Total samples in database: {total:,}")

    except Exception as e:
        print(f"\nError during demo: {e}")

    print("\n" + "=" * 70)
    print("Demo complete!")
    print("=" * 70)


if __name__ == "__main__":
    demo()