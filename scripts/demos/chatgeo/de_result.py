"""
Result dataclasses for differential expression analysis with full provenance.

These dataclasses capture all information needed to reproduce and interpret
DE analysis results, including search patterns, sample IDs, statistical methods,
and thresholds.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class GeneResult:
    """
    Result for a single gene in differential expression analysis.

    Captures both statistical test results and effect size metrics.
    """

    gene_symbol: str
    log2_fold_change: float
    mean_test: float
    mean_control: float
    pvalue: Optional[float]
    pvalue_adjusted: Optional[float]  # FDR-corrected
    test_method: str
    direction: str  # "up" | "down"

    @property
    def is_significant(self) -> bool:
        """Check if gene passes FDR threshold (assumes 0.05 if checking)."""
        if self.pvalue_adjusted is None:
            return False
        return self.pvalue_adjusted < 0.05

    @property
    def effect_size(self) -> float:
        """Absolute effect size (|log2FC|)."""
        return abs(self.log2_fold_change)

    def __repr__(self) -> str:
        adj_p = f"{self.pvalue_adjusted:.2e}" if self.pvalue_adjusted else "N/A"
        return (
            f"GeneResult({self.gene_symbol}, log2FC={self.log2_fold_change:.2f}, "
            f"p_adj={adj_p}, {self.direction})"
        )


@dataclass
class DEProvenance:
    """
    Complete provenance record for a differential expression analysis.

    Captures all parameters and metadata needed to reproduce the analysis.
    """

    # Query information
    timestamp: str
    query_disease: str
    query_tissue: Optional[str]

    # Search patterns used
    search_pattern_test: str
    search_pattern_control: str

    # Sample counts
    n_test_samples: int
    n_control_samples: int

    # Sample identifiers (for reproducibility)
    test_sample_ids: List[str]
    control_sample_ids: List[str]

    # Study information
    test_studies: List[str]
    control_studies: List[str]

    # Species information
    organisms: List[str]

    # Analysis parameters
    normalization_method: str
    test_method: str
    fdr_method: str
    thresholds: Dict[str, float]

    @classmethod
    def create(
        cls,
        query_disease: str,
        query_tissue: Optional[str],
        search_pattern_test: str,
        search_pattern_control: str,
        test_sample_ids: List[str],
        control_sample_ids: List[str],
        test_studies: List[str],
        control_studies: List[str],
        organisms: List[str],
        normalization_method: str,
        test_method: str,
        fdr_method: str,
        pvalue_threshold: float,
        fdr_threshold: float,
        log2fc_threshold: float,
    ) -> "DEProvenance":
        """Create a provenance record with current timestamp."""
        return cls(
            timestamp=datetime.now().isoformat(),
            query_disease=query_disease,
            query_tissue=query_tissue,
            search_pattern_test=search_pattern_test,
            search_pattern_control=search_pattern_control,
            n_test_samples=len(test_sample_ids),
            n_control_samples=len(control_sample_ids),
            test_sample_ids=test_sample_ids,
            control_sample_ids=control_sample_ids,
            test_studies=test_studies,
            control_studies=control_studies,
            organisms=organisms,
            normalization_method=normalization_method,
            test_method=test_method,
            fdr_method=fdr_method,
            thresholds={
                "pvalue": pvalue_threshold,
                "fdr": fdr_threshold,
                "log2fc": log2fc_threshold,
            },
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "query": {
                "disease": self.query_disease,
                "tissue": self.query_tissue,
            },
            "search_patterns": {
                "test": self.search_pattern_test,
                "control": self.search_pattern_control,
            },
            "samples": {
                "n_test": self.n_test_samples,
                "n_control": self.n_control_samples,
                "test_ids": self.test_sample_ids,
                "control_ids": self.control_sample_ids,
            },
            "studies": {
                "test": self.test_studies,
                "control": self.control_studies,
            },
            "organisms": self.organisms,
            "methods": {
                "normalization": self.normalization_method,
                "test": self.test_method,
                "fdr": self.fdr_method,
            },
            "thresholds": self.thresholds,
        }


@dataclass
class DEResult:
    """
    Complete differential expression analysis result.

    Contains provenance, summary statistics, and gene-level results
    separated into upregulated and downregulated lists.
    """

    provenance: DEProvenance
    genes_tested: int
    genes_significant: int
    upregulated: List[GeneResult]
    downregulated: List[GeneResult]

    # Optional: all gene results (including non-significant)
    all_genes: List[GeneResult] = field(default_factory=list)

    @property
    def n_upregulated(self) -> int:
        """Number of significantly upregulated genes."""
        return len(self.upregulated)

    @property
    def n_downregulated(self) -> int:
        """Number of significantly downregulated genes."""
        return len(self.downregulated)

    @property
    def top_upregulated(self) -> Optional[GeneResult]:
        """Top upregulated gene by effect size."""
        if not self.upregulated:
            return None
        return max(self.upregulated, key=lambda g: g.effect_size)

    @property
    def top_downregulated(self) -> Optional[GeneResult]:
        """Top downregulated gene by effect size."""
        if not self.downregulated:
            return None
        return max(self.downregulated, key=lambda g: g.effect_size)

    def get_gene(self, symbol: str) -> Optional[GeneResult]:
        """Get result for a specific gene."""
        for gene in self.upregulated + self.downregulated + self.all_genes:
            if gene.gene_symbol == symbol:
                return gene
        return None

    def get_top_genes(self, n: int = 10, direction: str = "both") -> List[GeneResult]:
        """
        Get top N genes by absolute log2 fold change.

        Args:
            n: Number of genes to return
            direction: "up", "down", or "both"

        Returns:
            List of top genes sorted by effect size
        """
        if direction == "up":
            genes = self.upregulated
        elif direction == "down":
            genes = self.downregulated
        else:
            genes = self.upregulated + self.downregulated

        sorted_genes = sorted(genes, key=lambda g: g.effect_size, reverse=True)
        return sorted_genes[:n]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "provenance": self.provenance.to_dict(),
            "summary": {
                "genes_tested": self.genes_tested,
                "genes_significant": self.genes_significant,
                "n_upregulated": self.n_upregulated,
                "n_downregulated": self.n_downregulated,
            },
            "upregulated": [
                {
                    "gene_symbol": g.gene_symbol,
                    "log2_fold_change": g.log2_fold_change,
                    "mean_test": g.mean_test,
                    "mean_control": g.mean_control,
                    "pvalue": g.pvalue,
                    "pvalue_adjusted": g.pvalue_adjusted,
                    "test_method": g.test_method,
                    "direction": g.direction,
                }
                for g in self.upregulated
            ],
            "downregulated": [
                {
                    "gene_symbol": g.gene_symbol,
                    "log2_fold_change": g.log2_fold_change,
                    "mean_test": g.mean_test,
                    "mean_control": g.mean_control,
                    "pvalue": g.pvalue,
                    "pvalue_adjusted": g.pvalue_adjusted,
                    "test_method": g.test_method,
                    "direction": g.direction,
                }
                for g in self.downregulated
            ],
        }

    def __repr__(self) -> str:
        return (
            f"DEResult(genes_tested={self.genes_tested}, "
            f"significant={self.genes_significant}, "
            f"up={self.n_upregulated}, down={self.n_downregulated})"
        )


@dataclass
class StudyDEResult:
    """
    Differential expression result for a single study.

    Used in study-matched mode where DE is performed within each study
    before meta-analysis.
    """

    study_id: str
    n_test_samples: int
    n_control_samples: int
    gene_results: List[GeneResult]

    @property
    def n_genes(self) -> int:
        return len(self.gene_results)


@dataclass
class MetaAnalysisResult:
    """
    Result of meta-analysis across multiple studies.

    Combines study-level DE results using fixed or random effects models.
    """

    provenance: DEProvenance
    n_studies: int
    study_results: List[StudyDEResult]
    combined_upregulated: List[GeneResult]
    combined_downregulated: List[GeneResult]
    meta_method: str  # "stouffer" | "fisher" | "random_effects"
    heterogeneity_stats: Optional[Dict[str, float]] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "provenance": self.provenance.to_dict(),
            "meta_analysis": {
                "n_studies": self.n_studies,
                "method": self.meta_method,
                "heterogeneity": self.heterogeneity_stats,
            },
            "study_results": [
                {
                    "study_id": s.study_id,
                    "n_test": s.n_test_samples,
                    "n_control": s.n_control_samples,
                    "n_genes": s.n_genes,
                }
                for s in self.study_results
            ],
            "combined_upregulated": [
                {
                    "gene_symbol": g.gene_symbol,
                    "log2_fold_change": g.log2_fold_change,
                    "pvalue_adjusted": g.pvalue_adjusted,
                    "direction": g.direction,
                }
                for g in self.combined_upregulated
            ],
            "combined_downregulated": [
                {
                    "gene_symbol": g.gene_symbol,
                    "log2_fold_change": g.log2_fold_change,
                    "pvalue_adjusted": g.pvalue_adjusted,
                    "direction": g.direction,
                }
                for g in self.combined_downregulated
            ],
        }


# =============================================================================
# Enrichment Analysis Result Dataclasses
# =============================================================================


@dataclass
class EnrichedTerm:
    """
    A single enriched term from GO, KEGG, Reactome, etc.

    Captures statistical results and the genes contributing to enrichment.
    """

    term_id: str  # GO:XXXXXXX, REAC:R-HSA-XXXXX, KEGG:hsa00000
    term_name: str
    source: str  # GO:BP, GO:CC, GO:MF, KEGG, REAC
    pvalue: float
    pvalue_adjusted: float
    term_size: int  # Total genes in term
    query_size: int  # Genes submitted
    intersection_size: int  # Genes overlapping
    precision: float  # intersection_size / query_size
    recall: float  # intersection_size / term_size
    genes: List[str]  # Genes contributing to enrichment

    def __repr__(self) -> str:
        return (
            f"EnrichedTerm({self.term_id}, {self.term_name!r}, "
            f"p_adj={self.pvalue_adjusted:.2e}, genes={self.intersection_size})"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "term_id": self.term_id,
            "term_name": self.term_name,
            "source": self.source,
            "pvalue": self.pvalue,
            "pvalue_adjusted": self.pvalue_adjusted,
            "term_size": self.term_size,
            "query_size": self.query_size,
            "intersection_size": self.intersection_size,
            "precision": self.precision,
            "recall": self.recall,
            "genes": self.genes,
        }


@dataclass
class DirectionEnrichment:
    """
    Enrichment results for genes in one direction (up or down regulated).
    """

    direction: str  # "up" | "down"
    input_genes: List[str]
    n_genes_mapped: int
    terms: List[EnrichedTerm] = field(default_factory=list)

    @property
    def n_terms(self) -> int:
        """Number of significant enriched terms."""
        return len(self.terms)

    @property
    def go_bp_terms(self) -> List[EnrichedTerm]:
        """GO Biological Process terms."""
        return [t for t in self.terms if t.source == "GO:BP"]

    @property
    def go_cc_terms(self) -> List[EnrichedTerm]:
        """GO Cellular Component terms."""
        return [t for t in self.terms if t.source == "GO:CC"]

    @property
    def go_mf_terms(self) -> List[EnrichedTerm]:
        """GO Molecular Function terms."""
        return [t for t in self.terms if t.source == "GO:MF"]

    @property
    def reactome_terms(self) -> List[EnrichedTerm]:
        """Reactome pathway terms."""
        return [t for t in self.terms if t.source == "REAC"]

    @property
    def kegg_terms(self) -> List[EnrichedTerm]:
        """KEGG pathway terms."""
        return [t for t in self.terms if t.source == "KEGG"]

    def get_top_terms(self, n: int = 10, source: Optional[str] = None) -> List[EnrichedTerm]:
        """
        Get top N terms by adjusted p-value.

        Args:
            n: Number of terms to return
            source: Filter by source (GO:BP, GO:CC, GO:MF, KEGG, REAC)

        Returns:
            List of top enriched terms
        """
        terms = self.terms
        if source:
            terms = [t for t in terms if t.source == source]
        sorted_terms = sorted(terms, key=lambda t: t.pvalue_adjusted)
        return sorted_terms[:n]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "direction": self.direction,
            "input_genes": len(self.input_genes),
            "n_genes_mapped": self.n_genes_mapped,
            "n_significant_terms": self.n_terms,
            "terms": [t.to_dict() for t in self.terms],
        }


@dataclass
class EnrichmentProvenance:
    """
    Provenance record for enrichment analysis.

    Captures all parameters needed to reproduce the analysis.
    """

    backend: str  # "gprofiler"
    organism: str  # "hsapiens", "mmusculus"
    sources: List[str]  # ["GO:BP", "GO:CC", "GO:MF", "KEGG", "REAC"]
    significance_threshold: float
    correction_method: str  # "g_SCS", "fdr", "bonferroni"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "backend": self.backend,
            "organism": self.organism,
            "sources": self.sources,
            "significance_threshold": self.significance_threshold,
            "correction_method": self.correction_method,
            "timestamp": self.timestamp,
        }


@dataclass
class EnrichmentResult:
    """
    Complete enrichment analysis result.

    Contains provenance and results for both up and down regulated genes.
    """

    provenance: EnrichmentProvenance
    upregulated: DirectionEnrichment
    downregulated: DirectionEnrichment

    @property
    def total_terms(self) -> int:
        """Total number of significant terms across both directions."""
        return self.upregulated.n_terms + self.downregulated.n_terms

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "provenance": self.provenance.to_dict(),
            "summary": {
                "total_significant_terms": self.total_terms,
                "upregulated_terms": self.upregulated.n_terms,
                "downregulated_terms": self.downregulated.n_terms,
            },
            "upregulated": self.upregulated.to_dict(),
            "downregulated": self.downregulated.to_dict(),
        }

    def __repr__(self) -> str:
        return (
            f"EnrichmentResult(total_terms={self.total_terms}, "
            f"up={self.upregulated.n_terms}, down={self.downregulated.n_terms})"
        )
