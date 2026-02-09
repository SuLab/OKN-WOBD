"""Biolink Model class and predicate mappings for DE RDF export.

Maps internal node types and relationship types to their Biolink Model
equivalents. Determines which relationships require reification
(association nodes with additional properties).
"""

from rdflib import URIRef

from .config import BIOLINK, OKN_WOBD

# =============================================================================
# Node type → Biolink class
# =============================================================================

BIOLINK_NODE_CLASSES = {
    # Core DE types (ChatGEO names)
    "DEExperiment": BIOLINK.Study,
    "DEAssay": BIOLINK.Assay,
    "Gene": BIOLINK.Gene,
    # GXA aliases (map to same Biolink classes)
    "Study": BIOLINK.Study,
    "Assay": BIOLINK.Assay,
    "MGene": BIOLINK.Gene,
    # Ontology types
    "Disease": BIOLINK.Disease,
    "AnatomicalEntity": BIOLINK.AnatomicalEntity,
    "Anatomy": BIOLINK.AnatomicalEntity,
    "OrganismTaxon": BIOLINK.OrganismTaxon,
    "CellType": BIOLINK.Cell,
    # GO categories
    "BiologicalProcess": BIOLINK.BiologicalProcess,
    "MolecularActivity": BIOLINK.MolecularActivity,
    "CellularComponent": BIOLINK.CellularComponent,
    "GOTerm": BIOLINK.BiologicalProcess,
    # Pathways
    "Pathway": BIOLINK.Pathway,
    "KEGGPathway": BIOLINK.Pathway,
    "ReactomePathway": BIOLINK.Pathway,
    "InterProDomain": BIOLINK.ProteinDomain,
    # GXA characteristic types
    "Sex": BIOLINK.BiologicalSex,
    "DevelopmentalStage": BIOLINK.LifeStage,
    "EthnicGroup": BIOLINK.PopulationOfIndividualOrganisms,
    "OrganismStatus": BIOLINK.Attribute,
}

# GO source prefix → Biolink class
GO_CATEGORY_CLASSES = {
    "GO:BP": BIOLINK.BiologicalProcess,
    "GO:CC": BIOLINK.CellularComponent,
    "GO:MF": BIOLINK.MolecularActivity,
}


# =============================================================================
# Relationship type → Biolink predicate
# =============================================================================

BIOLINK_PREDICATES = {
    # Study relationships
    "STUDIES": BIOLINK.studies,
    "HAS_OUTPUT": BIOLINK.has_output,
    "IN_TAXON": BIOLINK.in_taxon,
    # Gene expression
    "MEASURED_DIFFERENTIAL_EXPRESSION": BIOLINK.affects_expression_of,
    # Enrichment
    "ENRICHED_IN": BIOLINK.associated_with,
    # Attribute
    "HAS_ATTRIBUTE": BIOLINK.has_attribute,
    # Generic
    "ASSOCIATED_WITH": BIOLINK.associated_with,
    "RELATED_TO": BIOLINK.related_to,
}

# =============================================================================
# Property predicates (for node/association attributes)
# =============================================================================

# Standard Biolink properties
_BIOLINK_PROPERTIES = {
    "name": BIOLINK.name,
    "symbol": BIOLINK.symbol,
    "id": BIOLINK.id,
    "description": BIOLINK.description,
    "category": BIOLINK.category,
    "in_taxon": BIOLINK.in_taxon,
    "subject": BIOLINK.subject,
    "predicate": BIOLINK.predicate,
    "object": BIOLINK["object"],
}

# Custom OKN-WOBD properties for DE data
_CUSTOM_PROPERTIES = {
    "log2fc": OKN_WOBD.log2fc,
    "adj_p_value": OKN_WOBD.adj_p_value,
    "p_value": OKN_WOBD.p_value,
    "direction": OKN_WOBD.direction,
    "mean_test": OKN_WOBD.mean_test,
    "mean_control": OKN_WOBD.mean_control,
    "test_method": OKN_WOBD.test_method,
    "platform": OKN_WOBD.platform,
    "n_test_samples": OKN_WOBD.n_test_samples,
    "n_control_samples": OKN_WOBD.n_control_samples,
    "fdr_threshold": OKN_WOBD.fdr_threshold,
    "log2fc_threshold": OKN_WOBD.log2fc_threshold,
    "intersection_size": OKN_WOBD.intersection_size,
    "term_size": OKN_WOBD.term_size,
    "query_size": OKN_WOBD.query_size,
    "precision": OKN_WOBD.precision,
    "recall": OKN_WOBD.recall,
    "enrichment_source": OKN_WOBD.enrichment_source,
    "test_condition": OKN_WOBD.test_condition,
    "control_condition": OKN_WOBD.control_condition,
    "test_samples": OKN_WOBD.test_samples,
    "control_samples": OKN_WOBD.control_samples,
    "test_studies": OKN_WOBD.test_studies,
    "control_studies": OKN_WOBD.control_studies,
    "search_pattern_test": OKN_WOBD.search_pattern_test,
    "search_pattern_control": OKN_WOBD.search_pattern_control,
    "disease_terms": OKN_WOBD.disease_terms,
    "tissue_include_terms": OKN_WOBD.tissue_include_terms,
    "tissue_exclude_terms": OKN_WOBD.tissue_exclude_terms,
    "timestamp": OKN_WOBD.timestamp,
    "summary": OKN_WOBD.summary,
    "interpretation": OKN_WOBD.interpretation,
    # GXA-specific properties
    "organism": OKN_WOBD.organism,
    "technology": OKN_WOBD.technology,
    "experimental_factors": OKN_WOBD.experimental_factors,
    "pubmed_id": OKN_WOBD.pubmed_id,
    "effect_size": OKN_WOBD.effect_size,
    "project_title": OKN_WOBD.project_title,
    "source": OKN_WOBD.source,
    "submitter_name": OKN_WOBD.submitter_name,
    "array_design": OKN_WOBD.array_design,
    "contrast_id": OKN_WOBD.contrast_id,
    "secondary_accessions": OKN_WOBD.secondary_accessions,
}


# =============================================================================
# Reified relationship types (associations with properties)
# =============================================================================

# Relationship types that are reified as association nodes
_REIFIED_RELATIONSHIPS = {
    "MEASURED_DIFFERENTIAL_EXPRESSION": BIOLINK.GeneExpressionMixin,
    "ENRICHED_IN": BIOLINK.Association,
}


# =============================================================================
# Public lookup functions
# =============================================================================


def get_biolink_class(node_type: str) -> URIRef:
    """Get the Biolink class URI for a node type.

    Args:
        node_type: Internal node type string (e.g., "Gene", "DEExperiment")

    Returns:
        Biolink class URIRef; falls back to biolink:NamedThing
    """
    return BIOLINK_NODE_CLASSES.get(node_type, BIOLINK.NamedThing)


def get_biolink_predicate(relationship_type: str) -> URIRef:
    """Get the Biolink predicate URI for a relationship type.

    Args:
        relationship_type: Internal relationship type string

    Returns:
        Biolink predicate URIRef; falls back to biolink:related_to
    """
    return BIOLINK_PREDICATES.get(relationship_type, BIOLINK.related_to)


def get_property_predicate(property_name: str) -> URIRef:
    """Get the predicate URI for a node or association property.

    Checks standard Biolink properties first, then custom OKN-WOBD properties.

    Args:
        property_name: Property name string

    Returns:
        Property predicate URIRef; falls back to OKN_WOBD custom property
    """
    if property_name in _BIOLINK_PROPERTIES:
        return _BIOLINK_PROPERTIES[property_name]
    if property_name in _CUSTOM_PROPERTIES:
        return _CUSTOM_PROPERTIES[property_name]
    # Fallback: create custom property in OKN-WOBD namespace
    return OKN_WOBD[property_name]


def is_reified_relationship(relationship_type: str) -> bool:
    """Check if a relationship type should be reified as an association node."""
    return relationship_type in _REIFIED_RELATIONSHIPS


def get_association_class(relationship_type: str) -> URIRef:
    """Get the Biolink association class for a reified relationship.

    Args:
        relationship_type: Internal relationship type string

    Returns:
        Association class URIRef; falls back to biolink:Association
    """
    return _REIFIED_RELATIONSHIPS.get(relationship_type, BIOLINK.Association)
