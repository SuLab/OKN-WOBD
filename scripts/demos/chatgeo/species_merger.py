"""
Human and mouse data integration for cross-species DE analysis.

Provides ortholog mapping and expression data merging for combining
human and mouse samples in differential expression analysis.
"""

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


# Common human-mouse ortholog pairs (high-confidence 1:1 orthologs)
# This is a curated subset; full mapping would come from MGI/Ensembl
HUMAN_MOUSE_ORTHOLOGS = {
    # Common marker genes
    "Actb": "ACTB",
    "Gapdh": "GAPDH",
    "B2m": "B2M",
    # Inflammatory/immune genes
    "Il1b": "IL1B",
    "Il6": "IL6",
    "Tnf": "TNF",
    "Ifng": "IFNG",
    "Il10": "IL10",
    "Il17a": "IL17A",
    "Il4": "IL4",
    "Il13": "IL13",
    "Tgfb1": "TGFB1",
    "Ccl2": "CCL2",
    "Cxcl10": "CXCL10",
    # Fibrosis-related
    "Col1a1": "COL1A1",
    "Col1a2": "COL1A2",
    "Col3a1": "COL3A1",
    "Fn1": "FN1",
    "Acta2": "ACTA2",
    "Vim": "VIM",
    "Ctgf": "CTGF",
    "Mmp2": "MMP2",
    "Mmp9": "MMP9",
    "Timp1": "TIMP1",
    # Cancer-related
    "Tp53": "TP53",
    "Rb1": "RB1",
    "Myc": "MYC",
    "Kras": "KRAS",
    "Braf": "BRAF",
    "Egfr": "EGFR",
    "Erbb2": "ERBB2",
    "Pten": "PTEN",
    "Brca1": "BRCA1",
    "Brca2": "BRCA2",
    # Apoptosis
    "Bcl2": "BCL2",
    "Bax": "BAX",
    "Casp3": "CASP3",
    "Casp9": "CASP9",
    # Metabolism
    "Pparg": "PPARG",
    "Ppara": "PPARA",
    "Srebf1": "SREBF1",
    "Fasn": "FASN",
    "Scd1": "SCD",
    # Skin/psoriasis related
    "Krt1": "KRT1",
    "Krt5": "KRT5",
    "Krt10": "KRT10",
    "Krt14": "KRT14",
    "S100a8": "S100A8",
    "S100a9": "S100A9",
    "Defb4": "DEFB4A",
    # Signaling
    "Stat3": "STAT3",
    "Jak2": "JAK2",
    "Mapk1": "MAPK1",
    "Mapk3": "MAPK3",
    "Akt1": "AKT1",
    "Mtor": "MTOR",
    "Nfkb1": "NFKB1",
}

# Reverse mapping (human -> mouse)
MOUSE_HUMAN_ORTHOLOGS = {v: k for k, v in HUMAN_MOUSE_ORTHOLOGS.items()}


@dataclass
class OrthologMapping:
    """Result of ortholog mapping."""

    human_symbol: str
    mouse_symbol: str
    confidence: str  # "high", "medium", "low"
    source: str  # "curated", "symbol_match", "ensembl"


class SpeciesMerger:
    """
    Merges human and mouse expression data using ortholog mapping.

    Supports:
    - Converting mouse gene symbols to human orthologs
    - Merging expression matrices from both species
    - Finding samples for both species for a given condition

    Example:
        merger = SpeciesMerger()
        human_symbol = merger.get_human_ortholog("Acta2")
        merged_expr = merger.merge_expression(human_expr, mouse_expr)
    """

    def __init__(
        self,
        custom_orthologs: Optional[Dict[str, str]] = None,
        use_symbol_matching: bool = True,
    ):
        """
        Initialize the species merger.

        Args:
            custom_orthologs: Additional mouse->human ortholog mappings
            use_symbol_matching: Fall back to symbol matching for unmapped genes
        """
        self.orthologs = HUMAN_MOUSE_ORTHOLOGS.copy()
        if custom_orthologs:
            self.orthologs.update(custom_orthologs)

        self.use_symbol_matching = use_symbol_matching

        # Build reverse mapping
        self.reverse_orthologs = {v: k for k, v in self.orthologs.items()}

    def get_human_ortholog(self, mouse_symbol: str) -> Optional[str]:
        """
        Get human ortholog for a mouse gene symbol.

        Args:
            mouse_symbol: Mouse gene symbol (e.g., "Acta2")

        Returns:
            Human gene symbol or None if not found
        """
        # Check curated mapping
        if mouse_symbol in self.orthologs:
            return self.orthologs[mouse_symbol]

        # Try case-insensitive match
        mouse_lower = mouse_symbol.lower()
        for m, h in self.orthologs.items():
            if m.lower() == mouse_lower:
                return h

        # Fall back to symbol matching (uppercase)
        if self.use_symbol_matching:
            return mouse_symbol.upper()

        return None

    def get_mouse_ortholog(self, human_symbol: str) -> Optional[str]:
        """
        Get mouse ortholog for a human gene symbol.

        Args:
            human_symbol: Human gene symbol (e.g., "ACTA2")

        Returns:
            Mouse gene symbol or None if not found
        """
        # Check reverse mapping
        if human_symbol in self.reverse_orthologs:
            return self.reverse_orthologs[human_symbol]

        # Try case-insensitive match
        human_upper = human_symbol.upper()
        for h, m in self.reverse_orthologs.items():
            if h.upper() == human_upper:
                return m

        # Fall back to symbol matching (title case)
        if self.use_symbol_matching:
            return human_symbol.title()

        return None

    def map_mouse_to_human(
        self, mouse_symbols: List[str]
    ) -> Dict[str, Optional[str]]:
        """
        Map a list of mouse gene symbols to human orthologs.

        Args:
            mouse_symbols: List of mouse gene symbols

        Returns:
            Dictionary mapping mouse symbols to human symbols (or None)
        """
        return {m: self.get_human_ortholog(m) for m in mouse_symbols}

    def convert_mouse_expression(
        self,
        mouse_expr: pd.DataFrame,
        drop_unmapped: bool = True,
    ) -> pd.DataFrame:
        """
        Convert mouse expression matrix to human gene symbols.

        Args:
            mouse_expr: Expression matrix with mouse gene symbols as index
            drop_unmapped: Whether to drop genes without human orthologs

        Returns:
            Expression matrix with human gene symbols as index
        """
        # Map all genes
        mapping = self.map_mouse_to_human(list(mouse_expr.index))

        # Create new index
        new_index = []
        rows_to_keep = []

        for i, mouse_symbol in enumerate(mouse_expr.index):
            human_symbol = mapping.get(mouse_symbol)
            if human_symbol:
                new_index.append(human_symbol)
                rows_to_keep.append(i)
            elif not drop_unmapped:
                new_index.append(mouse_symbol)  # Keep original
                rows_to_keep.append(i)

        # Create new DataFrame
        result = mouse_expr.iloc[rows_to_keep].copy()
        result.index = new_index

        # Handle duplicate human symbols by averaging
        if result.index.duplicated().any():
            result = result.groupby(result.index).mean()

        return result

    def merge_expression(
        self,
        human_expr: pd.DataFrame,
        mouse_expr: pd.DataFrame,
        strategy: str = "intersection",
    ) -> pd.DataFrame:
        """
        Merge human and mouse expression matrices.

        Args:
            human_expr: Human expression matrix (genes x samples)
            mouse_expr: Mouse expression matrix (genes x samples)
            strategy: How to handle genes:
                - "intersection": Only genes in both
                - "union": All genes (NaN for missing)

        Returns:
            Merged expression matrix with human gene symbols
        """
        # Convert mouse to human symbols
        mouse_converted = self.convert_mouse_expression(mouse_expr)

        if strategy == "intersection":
            # Find common genes
            common_genes = list(
                set(human_expr.index) & set(mouse_converted.index)
            )
            human_subset = human_expr.loc[common_genes]
            mouse_subset = mouse_converted.loc[common_genes]

            # Concatenate samples
            merged = pd.concat([human_subset, mouse_subset], axis=1)

        elif strategy == "union":
            # All genes from both
            all_genes = list(
                set(human_expr.index) | set(mouse_converted.index)
            )
            human_reindexed = human_expr.reindex(all_genes)
            mouse_reindexed = mouse_converted.reindex(all_genes)

            merged = pd.concat([human_reindexed, mouse_reindexed], axis=1)

        else:
            raise ValueError(f"Unknown strategy: {strategy}")

        return merged

    def find_samples_both_species(
        self,
        disease: str,
        tissue: Optional[str] = None,
        data_dir: Optional[str] = None,
    ) -> Tuple[Optional["PooledPair"], Optional["PooledPair"]]:
        """
        Find samples for both human and mouse.

        Args:
            disease: Disease term to search
            tissue: Optional tissue constraint
            data_dir: ARCHS4 data directory

        Returns:
            Tuple of (human_pair, mouse_pair) PooledPair objects
        """
        from .query_builder import PatternQueryStrategy, QueryBuilder
        from .sample_finder import SampleFinder

        data_dir = data_dir or os.environ.get("ARCHS4_DATA_DIR")
        if not data_dir:
            raise ValueError("ARCHS4_DATA_DIR not set")

        query_builder = QueryBuilder(strategy=PatternQueryStrategy())

        # Search human
        human_pair = None
        try:
            human_finder = SampleFinder(
                data_dir=data_dir,
                query_builder=query_builder,
            )
            # Override to use human file
            from archs4_client import ARCHS4Client
            human_finder._client = ARCHS4Client(
                organism="human",
                data_dir=data_dir,
            )
            human_pair = human_finder.find_pooled_samples(
                disease_term=disease,
                tissue=tissue,
            )
        except Exception as e:
            print(f"Warning: Could not find human samples: {e}")

        # Search mouse
        mouse_pair = None
        try:
            mouse_finder = SampleFinder(
                data_dir=data_dir,
                query_builder=query_builder,
            )
            from archs4_client import ARCHS4Client
            mouse_finder._client = ARCHS4Client(
                organism="mouse",
                data_dir=data_dir,
            )
            mouse_pair = mouse_finder.find_pooled_samples(
                disease_term=disease,
                tissue=tissue,
            )
        except Exception as e:
            print(f"Warning: Could not find mouse samples: {e}")

        return human_pair, mouse_pair

    def get_ortholog_stats(self, mouse_symbols: List[str]) -> Dict[str, int]:
        """
        Get statistics on ortholog mapping coverage.

        Args:
            mouse_symbols: List of mouse gene symbols

        Returns:
            Dictionary with mapping statistics
        """
        mapped_curated = 0
        mapped_symbol = 0
        unmapped = 0

        for symbol in mouse_symbols:
            if symbol in self.orthologs:
                mapped_curated += 1
            elif self.use_symbol_matching:
                mapped_symbol += 1
            else:
                unmapped += 1

        return {
            "total": len(mouse_symbols),
            "mapped_curated": mapped_curated,
            "mapped_symbol": mapped_symbol,
            "unmapped": unmapped,
            "coverage": (mapped_curated + mapped_symbol) / len(mouse_symbols)
            if mouse_symbols
            else 0,
        }


def load_ortholog_table(path: str) -> Dict[str, str]:
    """
    Load ortholog mapping from a TSV file.

    Expected format:
        mouse_symbol<TAB>human_symbol

    Args:
        path: Path to TSV file

    Returns:
        Dictionary mapping mouse to human symbols
    """
    orthologs = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                mouse, human = parts[0], parts[1]
                orthologs[mouse] = human
    return orthologs
