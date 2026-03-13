"""ChatGEO adapter: converts DEResult + EnrichmentResult to RDF.

Bridges the ChatGEO result dataclasses (local scripts path) with the
``okn_wobd.de_rdf`` library (pip-installed core package).

Usage::

    from chatgeo.rdf_export import from_chatgeo

    writer = from_chatgeo(de_result, enrichment_result)
    writer.write("results.ttl")
"""

import logging
from datetime import datetime
from typing import Optional

from okn_wobd.de_rdf import (
    DEExperiment,
    DEGene,
    EnrichmentAssociation,
    GeneMapper,
    RdfConfig,
    TurtleWriter,
    build_rdf,
)

from .de_result import DEResult, EnrichmentResult

logger = logging.getLogger(__name__)


def from_chatgeo(
    de_result: DEResult,
    enrichment_result: Optional[EnrichmentResult] = None,
    experiment_id: Optional[str] = None,
    config: Optional[RdfConfig] = None,
    summary: str = "",
    interpretation: str = "",
) -> TurtleWriter:
    """Convert ChatGEO results to an RDF graph.

    Args:
        de_result: The differential expression result from ChatGEO
        enrichment_result: Optional enrichment analysis result
        experiment_id: Optional experiment identifier. If not provided,
            auto-generated from disease, tissue, and date.
        config: Optional RDF configuration
        summary: Text summary of DE results
        interpretation: AI-generated interpretation of results

    Returns:
        A populated TurtleWriter ready for serialization
    """
    config = config or RdfConfig()
    prov = de_result.provenance

    # Auto-generate experiment ID if not provided
    if not experiment_id:
        disease_slug = _slugify(prov.query_disease)
        tissue_slug = _slugify(prov.query_tissue) if prov.query_tissue else "all"
        date_str = datetime.now().strftime("%Y%m%d")
        experiment_id = f"{disease_slug}_{tissue_slug}_{date_str}"

    # Resolve gene symbols to NCBI Gene IDs
    all_gene_results = de_result.upregulated + de_result.downregulated
    symbols = [g.gene_symbol for g in all_gene_results]

    mapper = GeneMapper()
    symbol_to_ncbi = mapper.resolve_symbols(symbols)

    resolved = sum(1 for v in symbol_to_ncbi.values() if v is not None)
    logger.info(
        "Resolved %d/%d gene symbols to NCBI Gene IDs", resolved, len(symbols)
    )

    # Build DEGene list
    genes = []
    for g in all_gene_results:
        ncbi_id = symbol_to_ncbi.get(g.gene_symbol)
        genes.append(
            DEGene(
                gene_symbol=g.gene_symbol,
                gene_id=ncbi_id,
                gene_id_source="NCBI" if ncbi_id else None,
                log2_fold_change=g.log2_fold_change,
                pvalue=g.pvalue,
                pvalue_adjusted=g.pvalue_adjusted,
                mean_test=g.mean_test,
                mean_control=g.mean_control,
                direction=g.direction,
                is_significant=True,
            )
        )

    # Build enrichment associations
    enrichment_assocs = []
    if enrichment_result:
        for direction_enrichment in [
            enrichment_result.upregulated,
            enrichment_result.downregulated,
        ]:
            for term in direction_enrichment.terms:
                enrichment_assocs.append(
                    EnrichmentAssociation(
                        term_id=term.term_id,
                        term_name=term.term_name,
                        source=term.source,
                        direction=direction_enrichment.direction,
                        pvalue_adjusted=term.pvalue_adjusted,
                        intersection_size=term.intersection_size,
                        term_size=term.term_size,
                        query_size=term.query_size,
                        precision=term.precision,
                        recall=term.recall,
                        genes=term.genes,
                    )
                )

    # Build experiment name
    tissue_part = f" in {prov.query_tissue}" if prov.query_tissue else ""
    name = f"DE: {prov.query_disease}{tissue_part}"

    # Extract search terms from query_spec (if LLM-generated)
    disease_terms = []
    tissue_include = []
    tissue_exclude = []
    if prov.query_spec:
        disease_terms = prov.query_spec.get("disease_terms", [])
        tissue_include = prov.query_spec.get("tissue_include", [])
        tissue_exclude = prov.query_spec.get("tissue_exclude", [])

    # Construct DEExperiment
    experiment = DEExperiment(
        id=experiment_id,
        name=name,
        description=f"Differential expression analysis of {prov.query_disease}"
        f"{tissue_part} using {prov.test_method}",
        organism="Homo sapiens" if "human" in prov.organisms else prov.organisms[0] if prov.organisms else "Homo sapiens",
        taxon_id="9606",
        test_condition=prov.query_disease,
        control_condition="healthy",
        tissue=prov.query_tissue,
        timestamp=prov.timestamp,
        sample_ids_test=prov.test_sample_ids,
        sample_ids_control=prov.control_sample_ids,
        study_ids_test=prov.test_studies,
        study_ids_control=prov.control_studies,
        platform="ARCHS4",
        search_pattern_test=prov.search_pattern_test,
        search_pattern_control=prov.search_pattern_control,
        disease_terms=disease_terms,
        tissue_include_terms=tissue_include,
        tissue_exclude_terms=tissue_exclude,
        test_method=prov.test_method,
        normalization_method=prov.normalization_method,
        fdr_method=prov.fdr_method,
        fdr_threshold=prov.thresholds.get("fdr", 0.01),
        log2fc_threshold=prov.thresholds.get("log2fc", 2.0),
        summary=summary,
        interpretation=interpretation,
        genes=genes,
        enrichment_results=enrichment_assocs,
    )

    return build_rdf(experiment, config)


def _slugify(text: Optional[str]) -> str:
    """Convert text to a URL-safe slug."""
    if not text:
        return "unknown"
    result = text.strip().lower()
    result = result.replace(" ", "_")
    # Keep only alphanumeric and underscores
    result = "".join(c for c in result if c.isalnum() or c == "_")
    return result or "unknown"
