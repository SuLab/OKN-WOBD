"""
Gene set enrichment analysis using g:Profiler.

Provides over-representation analysis (ORA) for Gene Ontology terms,
KEGG pathways, and Reactome pathways using the g:Profiler API.

Example:
    from chatgeo.enrichment_analyzer import EnrichmentAnalyzer, EnrichmentConfig

    config = EnrichmentConfig(
        organism="hsapiens",
        sources=["GO:BP", "GO:CC", "GO:MF", "KEGG", "REAC"],
    )
    analyzer = EnrichmentAnalyzer(config=config)
    result = analyzer.analyze(de_result)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Protocol

from .de_result import (
    DEResult,
    DirectionEnrichment,
    EnrichedTerm,
    EnrichmentProvenance,
    EnrichmentResult,
)


@dataclass
class EnrichmentConfig:
    """
    Configuration for enrichment analysis.

    Attributes:
        organism: Organism identifier (hsapiens, mmusculus, etc.)
        sources: Data sources to query (GO:BP, GO:CC, GO:MF, KEGG, REAC)
        significance_threshold: P-value threshold for significance
        correction_method: Multiple testing correction (g_SCS, fdr, bonferroni)
        min_genes: Minimum genes required to run analysis
    """

    organism: str = "hsapiens"
    sources: List[str] = field(
        default_factory=lambda: ["GO:BP", "GO:CC", "GO:MF", "KEGG", "REAC"]
    )
    significance_threshold: float = 0.05
    correction_method: str = "g_SCS"
    min_genes: int = 5


class EnrichmentBackend(Protocol):
    """Protocol for enrichment analysis backends."""

    def analyze(
        self,
        genes: List[str],
        organism: str,
        sources: List[str],
        threshold: float,
        correction: str,
    ) -> tuple[List[EnrichedTerm], int]:
        """
        Run enrichment analysis on a gene list.

        Args:
            genes: List of gene symbols
            organism: Organism identifier
            sources: Data sources to query
            threshold: Significance threshold
            correction: Multiple testing correction method

        Returns:
            Tuple of (list of enriched terms, number of genes mapped)
        """
        ...


class GProfilerBackend:
    """
    Enrichment analysis using g:Profiler API.

    Uses the gprofiler-official package for server-side computation.
    This is fast and requires no local database.
    """

    def __init__(self):
        """Initialize g:Profiler backend."""
        self._gp = None

    def _get_client(self):
        """Lazy initialization of g:Profiler client."""
        if self._gp is None:
            try:
                from gprofiler import GProfiler

                self._gp = GProfiler(return_dataframe=False)
            except ImportError as e:
                raise ImportError(
                    "gprofiler-official package required. "
                    "Install with: pip install gprofiler-official"
                ) from e
        return self._gp

    def analyze(
        self,
        genes: List[str],
        organism: str,
        sources: List[str],
        threshold: float,
        correction: str,
    ) -> tuple[List[EnrichedTerm], int]:
        """
        Run g:Profiler enrichment analysis.

        Args:
            genes: List of gene symbols
            organism: Organism identifier (hsapiens, mmusculus)
            sources: Data sources (GO:BP, GO:CC, GO:MF, KEGG, REAC)
            threshold: Significance threshold
            correction: Correction method (g_SCS, fdr, bonferroni)

        Returns:
            Tuple of (list of EnrichedTerm objects, number of genes mapped)
        """
        if not genes:
            return [], 0

        gp = self._get_client()

        # Run g:Profiler query
        result = gp.profile(
            organism=organism,
            query=genes,
            sources=sources,
            user_threshold=threshold,
            significance_threshold_method=correction,
            no_evidences=False,  # Include intersections (gene lists)
        )

        if not result:
            return [], 0

        # Extract number of genes mapped (from first result's query_size)
        n_mapped = result[0].get("query_size", len(genes)) if result else 0

        # Convert to EnrichedTerm objects
        terms = []
        for r in result:
            term = EnrichedTerm(
                term_id=r["native"],
                term_name=r["name"],
                source=r["source"],
                pvalue=r["p_value"],
                pvalue_adjusted=r["p_value"],  # g:Profiler returns adjusted by default
                term_size=r["term_size"],
                query_size=r["query_size"],
                intersection_size=r["intersection_size"],
                precision=r["precision"],
                recall=r["recall"],
                genes=r.get("intersections", []),
            )
            terms.append(term)

        return terms, n_mapped


class EnrichmentAnalyzer:
    """
    Gene set enrichment analyzer.

    Performs over-representation analysis on differentially expressed genes
    using configurable backends (default: g:Profiler).

    Example:
        config = EnrichmentConfig(organism="hsapiens")
        analyzer = EnrichmentAnalyzer(config=config)
        result = analyzer.analyze(de_result)
    """

    def __init__(
        self,
        config: Optional[EnrichmentConfig] = None,
        backend: Optional[EnrichmentBackend] = None,
    ):
        """
        Initialize enrichment analyzer.

        Args:
            config: Analysis configuration
            backend: Enrichment backend (default: GProfilerBackend)
        """
        self.config = config or EnrichmentConfig()
        self.backend = backend or GProfilerBackend()

    def analyze(self, de_result: DEResult) -> EnrichmentResult:
        """
        Run enrichment analysis on DE results.

        Performs separate analysis for upregulated and downregulated genes.

        Args:
            de_result: Differential expression result

        Returns:
            EnrichmentResult with terms for both directions
        """
        # Extract gene lists
        up_genes = [g.gene_symbol for g in de_result.upregulated]
        down_genes = [g.gene_symbol for g in de_result.downregulated]

        # Analyze each direction
        up_enrichment = self.analyze_gene_list(up_genes, direction="up")
        down_enrichment = self.analyze_gene_list(down_genes, direction="down")

        # Create provenance
        provenance = EnrichmentProvenance(
            backend="gprofiler",
            organism=self.config.organism,
            sources=self.config.sources,
            significance_threshold=self.config.significance_threshold,
            correction_method=self.config.correction_method,
        )

        return EnrichmentResult(
            provenance=provenance,
            upregulated=up_enrichment,
            downregulated=down_enrichment,
        )

    def analyze_gene_list(
        self,
        genes: List[str],
        direction: str,
    ) -> DirectionEnrichment:
        """
        Analyze a single gene list.

        Args:
            genes: List of gene symbols
            direction: "up" or "down"

        Returns:
            DirectionEnrichment result
        """
        if len(genes) < self.config.min_genes:
            return DirectionEnrichment(
                direction=direction,
                input_genes=genes,
                n_genes_mapped=0,
                terms=[],
            )

        terms, n_mapped = self.backend.analyze(
            genes=genes,
            organism=self.config.organism,
            sources=self.config.sources,
            threshold=self.config.significance_threshold,
            correction=self.config.correction_method,
        )

        return DirectionEnrichment(
            direction=direction,
            input_genes=genes,
            n_genes_mapped=n_mapped,
            terms=terms,
        )


def run_enrichment(
    de_result: DEResult,
    organism: str = "hsapiens",
    sources: Optional[List[str]] = None,
    significance_threshold: float = 0.05,
) -> EnrichmentResult:
    """
    Convenience function for running enrichment analysis.

    Args:
        de_result: Differential expression result
        organism: Organism identifier
        sources: Data sources to query
        significance_threshold: P-value threshold

    Returns:
        EnrichmentResult

    Example:
        result = run_enrichment(de_result, organism="hsapiens")
    """
    config = EnrichmentConfig(
        organism=organism,
        sources=sources or ["GO:BP", "GO:CC", "GO:MF", "KEGG", "REAC"],
        significance_threshold=significance_threshold,
    )
    analyzer = EnrichmentAnalyzer(config=config)
    return analyzer.analyze(de_result)
