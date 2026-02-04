"""RDF namespace definitions and configuration for DE result export.

Defines standard biomedical ontology namespaces and a configuration
dataclass controlling RDF output options.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, Optional

from rdflib import Namespace, URIRef

# =============================================================================
# Namespace definitions
# =============================================================================

# Core project namespace
OKN_WOBD = Namespace("https://okn.wobd.org/")

# Biolink Model
BIOLINK = Namespace("https://w3id.org/biolink/vocab/")

# Gene / protein identifiers
NCBIGENE = Namespace("https://www.ncbi.nlm.nih.gov/gene/")
UNIPROT = Namespace("https://www.uniprot.org/uniprot/")
HGNC = Namespace("https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/")

# Ontologies
GO = Namespace("http://purl.obolibrary.org/obo/GO_")
MONDO = Namespace("http://purl.obolibrary.org/obo/MONDO_")
UBERON = Namespace("http://purl.obolibrary.org/obo/UBERON_")
NCBITAXON = Namespace("http://purl.obolibrary.org/obo/NCBITaxon_")
HP = Namespace("http://purl.obolibrary.org/obo/HP_")
CHEBI = Namespace("http://purl.obolibrary.org/obo/CHEBI_")
DOID = Namespace("http://purl.obolibrary.org/obo/DOID_")

# Pathway databases
REACTOME = Namespace("https://reactome.org/content/detail/")
KEGG = Namespace("https://www.genome.jp/entry/")

# Standard namespaces (rdflib provides RDF, RDFS, OWL, XSD)

# All namespaces for graph binding
NAMESPACES: Dict[str, Namespace] = {
    "okn-wobd": OKN_WOBD,
    "biolink": BIOLINK,
    "ncbigene": NCBIGENE,
    "uniprot": UNIPROT,
    "hgnc": HGNC,
    "GO": GO,
    "MONDO": MONDO,
    "UBERON": UBERON,
    "NCBITaxon": NCBITAXON,
    "HP": HP,
    "CHEBI": CHEBI,
    "DOID": DOID,
    "REACT": REACTOME,
    "KEGG": KEGG,
}


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class RdfConfig:
    """Configuration for DE RDF export."""

    base_uri: str = "https://okn.wobd.org/"
    output_format: str = "turtle"  # "turtle" or "nt"
    include_all_genes: bool = False  # include non-significant genes
    include_enrichment: bool = True
    include_provenance: bool = True


# =============================================================================
# URI utilities
# =============================================================================

# Characters that are invalid in URI path segments
_INVALID_URI_CHARS = re.compile(r"[^a-zA-Z0-9._~:@!$&'()*+,;=/-]")


def sanitize_uri_identifier(identifier: str) -> str:
    """Sanitize a string for use as a URI path segment.

    Replaces spaces with underscores and removes other invalid characters.
    """
    result = identifier.strip()
    result = result.replace(" ", "_")
    result = _INVALID_URI_CHARS.sub("", result)
    return result


def create_node_uri(
    node_type: str, identifier: str, base_ns: Optional[Namespace] = None
) -> URIRef:
    """Create a URI for a typed node.

    Args:
        node_type: The type of node (e.g., "experiment", "gene", "assay")
        identifier: The node identifier
        base_ns: Base namespace (defaults to OKN_WOBD)

    Returns:
        URIRef like ``okn-wobd:experiment/psoriasis_skin_20260202``
    """
    ns = base_ns or OKN_WOBD
    safe_id = sanitize_uri_identifier(identifier)
    return URIRef(f"{ns}{node_type}/{safe_id}")


def create_uri(identifier: str, base_ns: Optional[Namespace] = None) -> URIRef:
    """Create a URI from an identifier string.

    Args:
        identifier: Identifier (may contain path separators)
        base_ns: Base namespace (defaults to OKN_WOBD)

    Returns:
        URIRef under the given namespace
    """
    ns = base_ns or OKN_WOBD
    safe_id = sanitize_uri_identifier(identifier)
    return URIRef(f"{ns}{safe_id}")


def get_namespace_for_node_type(node_type: str) -> Namespace:
    """Return the appropriate namespace for a node type.

    Args:
        node_type: A Biolink-style node type string

    Returns:
        The namespace to use for URI construction
    """
    mapping = {
        "Gene": NCBIGENE,
        "BiologicalProcess": GO,
        "MolecularActivity": GO,
        "CellularComponent": GO,
        "Disease": MONDO,
        "AnatomicalEntity": UBERON,
        "OrganismTaxon": NCBITAXON,
        "Pathway": REACTOME,
        "KEGGPathway": KEGG,
    }
    return mapping.get(node_type, OKN_WOBD)
