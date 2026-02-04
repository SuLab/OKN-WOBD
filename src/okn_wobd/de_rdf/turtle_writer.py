"""RDF graph writer for differential expression data.

Provides a high-level API for building an RDF graph from typed nodes
and relationships, with support for reified associations (relationship
nodes that carry additional properties like p-values and fold changes).
"""

import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS, XSD

from .biolink_mapping import (
    get_association_class,
    get_biolink_class,
    get_biolink_predicate,
    get_property_predicate,
    is_reified_relationship,
)
from .config import BIOLINK, NAMESPACES, OKN_WOBD


class TurtleWriter:
    """Builds an RDF graph from typed nodes and relationships.

    Usage::

        writer = TurtleWriter()
        writer.add_node(gene_uri, "Gene", {"symbol": "IDO1", "id": "NCBIGene:3620"})
        writer.add_relationship(assay_uri, "MEASURED_DIFFERENTIAL_EXPRESSION", gene_uri,
                                properties={"log2fc": 6.96, "adj_p_value": 4.16e-61})
        writer.write(Path("output.ttl"))
    """

    def __init__(self) -> None:
        self._graph = Graph()
        for prefix, ns in NAMESPACES.items():
            self._graph.bind(prefix, ns)
        # Also bind standard namespaces
        self._graph.bind("rdf", RDF)
        self._graph.bind("rdfs", RDFS)
        self._graph.bind("xsd", XSD)

    @property
    def graph(self) -> Graph:
        """Access the underlying rdflib Graph."""
        return self._graph

    # -----------------------------------------------------------------
    # Nodes
    # -----------------------------------------------------------------

    def add_node(
        self,
        uri: URIRef,
        node_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> URIRef:
        """Add a typed node to the graph.

        Args:
            uri: The node URI
            node_type: Internal type string (mapped to Biolink class)
            properties: Optional dict of property name → value

        Returns:
            The node URI
        """
        biolink_class = get_biolink_class(node_type)
        self._graph.add((uri, RDF.type, biolink_class))

        if properties:
            for prop_name, value in properties.items():
                if value is None:
                    continue
                pred = get_property_predicate(prop_name)
                self._graph.add((uri, pred, _to_literal(value)))

        return uri

    # -----------------------------------------------------------------
    # Relationships
    # -----------------------------------------------------------------

    def add_relationship(
        self,
        subject_uri: URIRef,
        relationship_type: str,
        object_uri: URIRef,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Optional[URIRef]:
        """Add a relationship between two nodes.

        If the relationship type is reified (e.g., differential expression),
        an association node is created with the given properties.

        Args:
            subject_uri: Subject node URI
            relationship_type: Internal relationship type string
            object_uri: Object node URI
            properties: Optional properties for reified associations

        Returns:
            The association node URI if reified, else None
        """
        if is_reified_relationship(relationship_type) and properties:
            return self._add_reified_relationship(
                subject_uri, relationship_type, object_uri, properties
            )

        # Simple edge
        predicate = get_biolink_predicate(relationship_type)
        self._graph.add((subject_uri, predicate, object_uri))
        return None

    def _add_reified_relationship(
        self,
        subject_uri: URIRef,
        relationship_type: str,
        object_uri: URIRef,
        properties: Dict[str, Any],
    ) -> URIRef:
        """Create a reified association node for a relationship.

        The association node follows the Biolink association pattern:
        - rdf:type → association class
        - biolink:subject → subject_uri
        - biolink:predicate → the predicate URI
        - biolink:object → object_uri
        - additional properties attached to the association node

        Args:
            subject_uri: Subject node URI
            relationship_type: Internal relationship type string
            object_uri: Object node URI
            properties: Properties to attach to the association node

        Returns:
            The association node URI
        """
        assoc_class = get_association_class(relationship_type)
        predicate = get_biolink_predicate(relationship_type)

        # Generate a unique association URI
        assoc_id = uuid.uuid4().hex[:12]
        # Choose path segment based on relationship type
        if relationship_type == "ENRICHED_IN":
            assoc_uri = OKN_WOBD[f"enrichment/{assoc_id}"]
        else:
            assoc_uri = OKN_WOBD[f"Association/{assoc_id}"]

        self._graph.add((assoc_uri, RDF.type, assoc_class))
        self._graph.add((assoc_uri, BIOLINK.subject, subject_uri))
        self._graph.add((assoc_uri, BIOLINK.predicate, predicate))
        self._graph.add((assoc_uri, BIOLINK["object"], object_uri))

        # Attach properties to the association
        for prop_name, value in properties.items():
            if value is None:
                continue
            pred = get_property_predicate(prop_name)
            self._graph.add((assoc_uri, pred, _to_literal(value)))

        return assoc_uri

    # -----------------------------------------------------------------
    # Serialization
    # -----------------------------------------------------------------

    def serialize(self, fmt: Optional[str] = None) -> str:
        """Serialize the graph to a string.

        Args:
            fmt: RDF serialization format (default: "turtle").
                 Common values: "turtle", "nt", "xml", "json-ld"

        Returns:
            Serialized RDF string
        """
        fmt = fmt or "turtle"
        return self._graph.serialize(format=fmt)

    def write(self, path: Union[str, Path], fmt: Optional[str] = None) -> Path:
        """Write the graph to a file.

        Args:
            path: Output file path
            fmt: RDF format (inferred from extension if not given)

        Returns:
            The output path
        """
        path = Path(path)
        if fmt is None:
            ext_map = {".ttl": "turtle", ".nt": "nt", ".xml": "xml", ".jsonld": "json-ld"}
            fmt = ext_map.get(path.suffix.lower(), "turtle")

        path.parent.mkdir(parents=True, exist_ok=True)
        self._graph.serialize(destination=str(path), format=fmt)
        return path

    def query(self, sparql: str) -> List[Dict[str, Any]]:
        """Run a SPARQL query against the graph.

        Args:
            sparql: SPARQL SELECT query string

        Returns:
            List of result rows as dicts
        """
        results = self._graph.query(sparql)
        rows = []
        for row in results:
            row_dict = {}
            for var in results.vars:
                val = getattr(row, str(var), None)
                row_dict[str(var)] = val
            rows.append(row_dict)
        return rows

    def get_triple_count(self) -> int:
        """Return the number of triples in the graph."""
        return len(self._graph)


# =============================================================================
# Helpers
# =============================================================================


def _to_literal(value: Any) -> Literal:
    """Convert a Python value to an rdflib Literal with appropriate datatype."""
    if isinstance(value, bool):
        return Literal(value, datatype=XSD.boolean)
    if isinstance(value, int):
        return Literal(value, datatype=XSD.integer)
    if isinstance(value, float):
        return Literal(value, datatype=XSD.double)
    return Literal(str(value))
