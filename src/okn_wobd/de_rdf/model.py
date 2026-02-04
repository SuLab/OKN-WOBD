"""Source-agnostic data model for differential expression RDF export.

These dataclasses define the intermediate representation that any DE
pipeline (ChatGEO, GeneLab, etc.) converts its results into before
calling ``build_rdf()``.  Pure dataclasses with no external imports.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class DEGene:
    """A single gene from a differential expression analysis."""

    gene_symbol: str
    gene_id: Optional[str] = None  # NCBI Gene ID (e.g., "3620")
    gene_id_source: Optional[str] = None  # "NCBI", "Ensembl", "HGNC", etc.
    log2_fold_change: float = 0.0
    pvalue: Optional[float] = None
    pvalue_adjusted: Optional[float] = None
    mean_test: Optional[float] = None
    mean_control: Optional[float] = None
    direction: str = "up"  # "up" | "down"
    is_significant: bool = True


@dataclass
class EnrichmentAssociation:
    """A single enrichment result (GO term, pathway, etc.)."""

    term_id: str  # e.g., "GO:0006955", "REAC:R-HSA-168256", "KEGG:hsa04060"
    term_name: str
    source: str  # "GO:BP", "GO:CC", "GO:MF", "KEGG", "REAC"
    direction: str  # "up" | "down"
    pvalue_adjusted: float
    intersection_size: int = 0
    term_size: int = 0
    query_size: int = 0
    precision: float = 0.0
    recall: float = 0.0
    genes: List[str] = field(default_factory=list)


@dataclass
class DEExperiment:
    """Complete differential expression experiment for RDF export.

    This is the top-level container that ``build_rdf()`` consumes.
    """

    # Identity
    id: str  # e.g., "psoriasis_skin_20260202"
    name: str  # e.g., "DE: psoriasis in skin"
    description: str = ""

    # Organism
    organism: str = "Homo sapiens"
    taxon_id: str = "9606"  # NCBITaxon ID (digits only)

    # Experimental conditions
    test_condition: str = ""  # e.g., "psoriasis"
    control_condition: str = "healthy"
    tissue: Optional[str] = None
    tissue_ontology_id: Optional[str] = None  # e.g., "UBERON:0002097"
    disease_ontology_id: Optional[str] = None  # e.g., "MONDO:0005083"

    # Provenance
    timestamp: str = ""
    sample_ids_test: List[str] = field(default_factory=list)
    sample_ids_control: List[str] = field(default_factory=list)
    study_ids: List[str] = field(default_factory=list)
    platform: str = "ARCHS4"

    # Methods
    test_method: str = "deseq2"
    normalization_method: str = ""
    fdr_method: str = ""
    fdr_threshold: float = 0.01
    log2fc_threshold: float = 2.0

    # Results
    genes: List[DEGene] = field(default_factory=list)
    enrichment_results: List[EnrichmentAssociation] = field(default_factory=list)

    @property
    def significant_genes(self) -> List[DEGene]:
        """Return only significant genes."""
        return [g for g in self.genes if g.is_significant]

    @property
    def n_test_samples(self) -> int:
        return len(self.sample_ids_test)

    @property
    def n_control_samples(self) -> int:
        return len(self.sample_ids_control)
