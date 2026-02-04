"""Orchestrates conversion of a DEExperiment into an RDF graph.

This is the main entry point: call ``build_rdf(experiment, config)`` to
get a populated ``TurtleWriter`` ready for serialization.
"""

import logging
import re
from typing import Optional

from rdflib import URIRef

from .config import (
    BIOLINK,
    GO,
    KEGG,
    MONDO,
    NCBIGENE,
    NCBITAXON,
    OKN_WOBD,
    REACTOME,
    UBERON,
    RdfConfig,
    create_node_uri,
)
from .model import DEExperiment, DEGene, EnrichmentAssociation
from .turtle_writer import TurtleWriter

logger = logging.getLogger(__name__)


def build_rdf(
    experiment: DEExperiment,
    config: Optional[RdfConfig] = None,
) -> TurtleWriter:
    """Build an RDF graph from a differential expression experiment.

    Args:
        experiment: The DE experiment data model
        config: Optional configuration (uses defaults if not provided)

    Returns:
        A populated TurtleWriter ready for ``serialize()`` or ``write()``
    """
    config = config or RdfConfig()
    writer = TurtleWriter()

    # --- Study node ---
    study_uri = create_node_uri("experiment", experiment.id)
    writer.add_node(study_uri, "DEExperiment", {
        "name": experiment.name,
        "description": experiment.description or None,
    })

    # Taxon
    taxon_uri = NCBITAXON[experiment.taxon_id]
    writer.add_node(taxon_uri, "OrganismTaxon", {
        "name": experiment.organism,
    })
    writer.add_relationship(study_uri, "IN_TAXON", taxon_uri)

    # Disease (if ontology ID provided)
    if experiment.disease_ontology_id:
        disease_uri = _ontology_uri(experiment.disease_ontology_id, MONDO)
        if disease_uri:
            writer.add_node(disease_uri, "Disease", {
                "name": experiment.test_condition or None,
            })
            writer.add_relationship(study_uri, "STUDIES", disease_uri)

    # Anatomy (if ontology ID provided)
    if experiment.tissue_ontology_id:
        anatomy_uri = _ontology_uri(experiment.tissue_ontology_id, UBERON)
        if anatomy_uri:
            writer.add_node(anatomy_uri, "AnatomicalEntity", {
                "name": experiment.tissue or None,
            })

    # --- Assay node ---
    assay_uri = create_node_uri("assay", f"{experiment.id}_comparison")
    assay_props = {
        "name": f"{experiment.test_condition} vs {experiment.control_condition}",
        "test_method": experiment.test_method,
        "platform": experiment.platform,
        "n_test_samples": experiment.n_test_samples,
        "n_control_samples": experiment.n_control_samples,
    }
    if config.include_provenance:
        if experiment.fdr_threshold:
            assay_props["fdr_threshold"] = experiment.fdr_threshold
        if experiment.log2fc_threshold:
            assay_props["log2fc_threshold"] = experiment.log2fc_threshold
        if experiment.test_condition:
            assay_props["test_condition"] = experiment.test_condition
        if experiment.control_condition:
            assay_props["control_condition"] = experiment.control_condition

    writer.add_node(assay_uri, "DEAssay", assay_props)
    writer.add_relationship(study_uri, "HAS_OUTPUT", assay_uri)

    # --- Provenance triples (sample/study IDs) ---
    if config.include_provenance:
        _add_provenance(writer, assay_uri, experiment)

    # --- Gene nodes + DE associations ---
    genes = experiment.genes
    if not config.include_all_genes:
        genes = [g for g in genes if g.is_significant]

    for gene in genes:
        _add_gene(writer, assay_uri, gene)

    # --- Enrichment associations ---
    if config.include_enrichment and experiment.enrichment_results:
        for enrichment in experiment.enrichment_results:
            _add_enrichment(writer, assay_uri, enrichment)

    triple_count = writer.get_triple_count()
    logger.info(
        "Built RDF graph: %d triples, %d genes, %d enrichment terms",
        triple_count,
        len(genes),
        len(experiment.enrichment_results),
    )

    return writer


# =============================================================================
# Internal helpers
# =============================================================================


def _add_gene(writer: TurtleWriter, assay_uri: URIRef, gene: DEGene) -> None:
    """Add a gene node and its DE association to the graph."""
    # Determine gene URI
    if gene.gene_id:
        gene_uri = NCBIGENE[gene.gene_id]
        gene_id_curie = f"NCBIGene:{gene.gene_id}"
    else:
        # Fallback: symbol-based URI
        gene_uri = create_node_uri("gene", gene.gene_symbol)
        gene_id_curie = f"symbol:{gene.gene_symbol}"

    # Gene node
    gene_props = {
        "symbol": gene.gene_symbol,
        "id": gene_id_curie,
    }
    writer.add_node(gene_uri, "Gene", gene_props)

    # Reified DE association
    assoc_props = {
        "log2fc": gene.log2_fold_change,
        "direction": gene.direction,
    }
    if gene.pvalue_adjusted is not None:
        assoc_props["adj_p_value"] = gene.pvalue_adjusted
    if gene.pvalue is not None:
        assoc_props["p_value"] = gene.pvalue
    if gene.mean_test is not None:
        assoc_props["mean_test"] = gene.mean_test
    if gene.mean_control is not None:
        assoc_props["mean_control"] = gene.mean_control

    writer.add_relationship(
        assay_uri, "MEASURED_DIFFERENTIAL_EXPRESSION", gene_uri, assoc_props
    )


def _add_enrichment(
    writer: TurtleWriter,
    assay_uri: URIRef,
    enrichment: EnrichmentAssociation,
) -> None:
    """Add an enrichment term node and its association to the graph."""
    term_uri = _term_uri(enrichment.term_id, enrichment.source)
    term_type = _term_type(enrichment.source)

    writer.add_node(term_uri, term_type, {
        "name": enrichment.term_name,
    })

    assoc_props = {
        "adj_p_value": enrichment.pvalue_adjusted,
        "direction": enrichment.direction,
        "intersection_size": enrichment.intersection_size,
        "enrichment_source": enrichment.source,
    }
    if enrichment.term_size:
        assoc_props["term_size"] = enrichment.term_size
    if enrichment.query_size:
        assoc_props["query_size"] = enrichment.query_size
    if enrichment.precision:
        assoc_props["precision"] = enrichment.precision
    if enrichment.recall:
        assoc_props["recall"] = enrichment.recall

    writer.add_relationship(assay_uri, "ENRICHED_IN", term_uri, assoc_props)


def _add_provenance(
    writer: TurtleWriter, assay_uri: URIRef, experiment: DEExperiment
) -> None:
    """Attach provenance triples (sample IDs, study IDs) to the assay node."""
    graph = writer.graph
    from .biolink_mapping import get_property_predicate
    from .turtle_writer import _to_literal

    sample_pred = get_property_predicate("sample_id")
    study_pred = get_property_predicate("study_id")

    for sid in experiment.sample_ids_test:
        graph.add((assay_uri, sample_pred, _to_literal(sid)))
    for sid in experiment.sample_ids_control:
        graph.add((assay_uri, sample_pred, _to_literal(sid)))
    for study in experiment.study_ids:
        graph.add((assay_uri, study_pred, _to_literal(study)))


def _ontology_uri(ontology_id: str, default_ns) -> Optional[URIRef]:
    """Convert an ontology ID like ``MONDO:0005083`` to a URI.

    Supports MONDO, UBERON, GO, DOID prefixes.
    """
    if not ontology_id:
        return None

    # Handle already-numeric IDs (e.g., just "0005083")
    if ontology_id.isdigit():
        return default_ns[ontology_id]

    # Handle CURIE-style IDs (e.g., "MONDO:0005083")
    if ":" in ontology_id:
        prefix, local = ontology_id.split(":", 1)
        prefix = prefix.upper()
        ns_map = {
            "MONDO": MONDO,
            "UBERON": UBERON,
            "GO": GO,
            "DOID": URIRef("http://purl.obolibrary.org/obo/DOID_"),
        }
        ns = ns_map.get(prefix, default_ns)
        return ns[local]

    return default_ns[ontology_id]


def _term_uri(term_id: str, source: str) -> URIRef:
    """Convert an enrichment term ID to a URI.

    Examples:
        GO:0006955 → GO namespace
        REAC:R-HSA-168256 → Reactome namespace
        KEGG:hsa04060 → KEGG namespace
    """
    if term_id.startswith("GO:"):
        # GO:0006955 → GO_0006955
        go_id = term_id.replace("GO:", "")
        return GO[go_id]

    if term_id.startswith("REAC:"):
        react_id = term_id.replace("REAC:", "")
        return REACTOME[react_id]

    if term_id.startswith("KEGG:"):
        kegg_id = term_id.replace("KEGG:", "")
        return KEGG[kegg_id]

    # Fallback
    safe_id = re.sub(r"[^a-zA-Z0-9._-]", "_", term_id)
    return OKN_WOBD[f"term/{safe_id}"]


def _term_type(source: str) -> str:
    """Map enrichment source to node type string."""
    source_map = {
        "GO:BP": "BiologicalProcess",
        "GO:CC": "CellularComponent",
        "GO:MF": "MolecularActivity",
        "KEGG": "KEGGPathway",
        "REAC": "Pathway",
    }
    return source_map.get(source, "Pathway")
