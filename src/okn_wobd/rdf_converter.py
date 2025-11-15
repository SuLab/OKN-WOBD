"""Convert JSONL dataset records to RDF N-Triples format."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, OWL, XSD

logger = logging.getLogger(__name__)

# Base namespace for OKN-WOBD entities
OKN_BASE = "https://okn.wobd.org/"
OKN = Namespace(OKN_BASE)

# Schema.org namespace
SCHEMA = Namespace("http://schema.org/")

# Fields to skip during conversion (Elasticsearch/Solr metadata)
SKIP_FIELDS = {"_score", "_ignored", "@version", "@context"}


def slugify(value: str) -> str:
    """Convert a string to a URL-safe slug."""
    clean = "".join(ch if ch.isalnum() else "_" for ch in value)
    while "__" in clean:
        clean = clean.replace("__", "_")
    return clean.strip("_").lower() or "resource"


def dataset_uri(resource: str, dataset_id: str) -> URIRef:
    """Generate a URI for a dataset."""
    resource_slug = slugify(resource)
    safe_id = quote(dataset_id, safe="")
    return URIRef(f"{OKN_BASE}dataset/{resource_slug}/{safe_id}")


def get_entity_uri(entity: Dict[str, Any], entity_type: str) -> Optional[URIRef]:
    """Get URI for an entity, preferring external URIs when available.
    
    Returns None if the entity doesn't have sufficient information to create a URI.
    """
    # For diseases, species, infectious agents - use 'url' field if it's an ontology URI
    if entity.get("url"):
        url = entity["url"]
        # Check if it's a recognized ontology URI
        if any(prefix in url for prefix in [
            "purl.obolibrary.org",
            "uniprot.org",
            "ror.org",
            "doi.org",
            "http://purl.obolibrary.org/",
            "https://www.uniprot.org/",
        ]):
            return URIRef(url)
    
    # For organizations - use ROR identifier if available
    if entity_type == "Organization" and entity.get("identifier"):
        identifier = entity["identifier"]
        if isinstance(identifier, str) and identifier.startswith("https://ror.org/"):
            return URIRef(identifier)
    
    # For DOIs - convert to https://doi.org/ URI
    if entity.get("doi"):
        doi = entity["doi"] if isinstance(entity["doi"], str) else str(entity["doi"])
        if not doi.startswith("http"):
            return URIRef(f"https://doi.org/{doi}")
        return URIRef(doi)
    
    # For identifiers that are already URIs
    if entity.get("identifier"):
        identifier = entity["identifier"]
        if isinstance(identifier, str) and identifier.startswith("http"):
            return URIRef(identifier)
    
    # Fall back to constructed URI in our namespace
    if entity.get("name"):
        name = entity["name"]
        if entity_type == "Organization":
            return URIRef(f"{OKN_BASE}organization/{slugify(name)}")
        elif entity_type == "Person":
            return URIRef(f"{OKN_BASE}person/{slugify(name)}")
        elif entity_type == "MonetaryGrant":
            # Use identifier if available, otherwise construct from name
            grant_id = entity.get("identifier")
            if grant_id:
                safe_id = quote(str(grant_id), safe="")
                return URIRef(f"{OKN_BASE}grant/{safe_id}")
            return URIRef(f"{OKN_BASE}grant/{slugify(name)}")
        elif entity_type == "DataCatalog":
            return URIRef(f"{OKN_BASE}catalog/{slugify(name)}")
    
    return None


def convert_literal(value: Any) -> Literal:
    """Convert a Python value to an RDF Literal."""
    if isinstance(value, bool):
        return Literal(value, datatype=XSD.boolean)
    elif isinstance(value, int):
        return Literal(value, datatype=XSD.integer)
    elif isinstance(value, float):
        return Literal(value, datatype=XSD.double)
    elif isinstance(value, str):
        # Check if it looks like a date/datetime
        if "T" in value and ":" in value:
            # Try datetime
            try:
                from datetime import datetime
                datetime.fromisoformat(value.replace("Z", "+00:00"))
                return Literal(value, datatype=XSD.dateTime)
            except (ValueError, AttributeError):
                pass
        # Check if it's a date (YYYY-MM-DD)
        if len(value) == 10 and value.count("-") == 2:
            try:
                from datetime import datetime
                datetime.strptime(value, "%Y-%m-%d")
                return Literal(value, datatype=XSD.date)
            except (ValueError, AttributeError):
                pass
        return Literal(value)
    return Literal(str(value))


def add_simple_property(graph: Graph, subject: URIRef, predicate: URIRef, value: Any) -> None:
    """Add a simple property (string, number, boolean, date) to the graph."""
    if value is None or value == "":
        return
    
    if isinstance(value, (str, int, float, bool)):
        graph.add((subject, predicate, convert_literal(value)))
    elif isinstance(value, list) and value and isinstance(value[0], (str, int, float, bool)):
        # Handle arrays of simple values
        for item in value:
            graph.add((subject, predicate, convert_literal(item)))


def add_entity_property(
    graph: Graph,
    subject: URIRef,
    predicate: URIRef,
    entity: Dict[str, Any],
    entity_type: Optional[str] = None,
) -> Optional[URIRef]:
    """Add an entity property to the graph and return its URI."""
    entity_type = entity_type or entity.get("@type", "Thing")
    
    entity_uri = get_entity_uri(entity, entity_type)
    if not entity_uri:
        return None
    
    # Add the relationship
    graph.add((subject, predicate, entity_uri))
    
    # Add type for the entity
    schema_type = SCHEMA[entity_type]
    graph.add((entity_uri, RDF.type, schema_type))
    
    # Add owl:sameAs if entity_uri is an external URI (MONDO, UniProt, ROR, etc.)
    if entity_uri and not str(entity_uri).startswith(OKN_BASE):
        # External URI - add owl:sameAs for interoperability
        # Also check if we have an internal URI we should map to
        internal_uri = None
        if entity_type == "Organization" and entity.get("identifier"):
            # We might have created an internal URI for organizations
            pass  # For now, we use external URIs directly
    
    # Add properties of the entity
    add_entity_properties(graph, entity_uri, entity, entity_type)
    
    return entity_uri


def add_entity_properties(graph: Graph, subject: URIRef, entity: Dict[str, Any], entity_type: str) -> None:
    """Add properties to an entity node."""
    # Map of Schema.org property names to RDF predicates
    property_map = {
        "name": SCHEMA.name,
        "description": SCHEMA.description,
        "url": SCHEMA.url,
        "identifier": SCHEMA.identifier,
        "alternateName": SCHEMA.alternateName,
        "startDate": SCHEMA.startDate,
        "endDate": SCHEMA.endDate,
        "datePublished": SCHEMA.datePublished,
        "dateModified": SCHEMA.dateModified,
        "dateCreated": SCHEMA.dateCreated,
        "date": SCHEMA.date,
        "contentUrl": SCHEMA.contentUrl,
        "encodingFormat": SCHEMA.encodingFormat,
        "archivedAt": SCHEMA.archivedAt,
        "versionDate": SCHEMA.versionDate,
        "parentOrganization": SCHEMA.parentOrganization,
        "affiliation": SCHEMA.affiliation,
        "familyName": SCHEMA.familyName,
        "givenName": SCHEMA.givenName,
        "abstract": SCHEMA.abstract,
        "doi": SCHEMA.sameAs,  # DOI can be represented as sameAs
        "pmid": None,  # Skip - not a standard Schema.org property
        "displayName": None,  # Skip - internal field
        "originalName": None,  # Skip - internal field
        "fromPMID": None,  # Skip - internal field
        "fromGPT": None,  # Skip - internal field
        "curatedBy": None,  # Skip for now - could be expanded later
        "inDefinedTermSet": None,  # Skip - internal metadata
        "isCurated": None,  # Skip - internal metadata
        "classification": None,  # Skip - internal metadata
        "commonName": None,  # Skip - redundant with name
        "projectNumSplit": None,  # Skip - internal structure
    }
    
    for key, value in entity.items():
        if key in SKIP_FIELDS or key.startswith("_"):
            continue
        
        predicate = property_map.get(key)
        if predicate is None:
            continue  # Skip unmapped or explicitly None properties
        
        if value is None:
            continue
        
        if isinstance(value, str) and not value:
            continue  # Skip empty strings
        
        if isinstance(value, list):
            if not value:
                continue
            for item in value:
                if isinstance(item, dict):
                    # Recursive entity
                    add_entity_property(graph, subject, predicate, item)
                else:
                    add_simple_property(graph, subject, predicate, item)
        elif isinstance(value, dict):
            # Nested entity
            add_entity_property(graph, subject, predicate, value)
        else:
            add_simple_property(graph, subject, predicate, value)


def convert_dataset(graph: Graph, dataset: Dict[str, Any], resource: str) -> URIRef:
    """Convert a dataset record to RDF and add it to the graph."""
    dataset_id = dataset.get("_id")
    if not dataset_id:
        raise ValueError("Dataset missing required '_id' field")
    
    dataset_uri_ref = dataset_uri(resource, dataset_id)
    
    # Add type
    graph.add((dataset_uri_ref, RDF.type, SCHEMA.Dataset))
    
    # Add properties
    add_entity_properties(graph, dataset_uri_ref, dataset, "Dataset")
    
    # Handle special relationships
    handle_author(graph, dataset_uri_ref, dataset.get("author", []))
    handle_funding(graph, dataset_uri_ref, dataset.get("funding", []))
    handle_health_condition(graph, dataset_uri_ref, dataset.get("healthCondition", []))
    handle_species(graph, dataset_uri_ref, dataset.get("species", []))
    handle_infectious_agent(graph, dataset_uri_ref, dataset.get("infectiousAgent", []))
    handle_distribution(graph, dataset_uri_ref, dataset.get("distribution", []))
    handle_included_in_catalog(graph, dataset_uri_ref, dataset.get("includedInDataCatalog"))
    handle_doi(graph, dataset_uri_ref, dataset.get("doi"))
    handle_identifier(graph, dataset_uri_ref, dataset.get("identifier", []))
    
    return dataset_uri_ref


def handle_author(graph: Graph, subject: URIRef, authors: List[Dict[str, Any]]) -> None:
    """Handle author(s) of a dataset."""
    if not authors:
        return
    
    for author in authors:
        if isinstance(author, dict):
            author_uri = add_entity_property(graph, subject, SCHEMA.author, author, "Person")
            if author_uri:
                # Handle affiliation
                affiliation = author.get("affiliation")
                if affiliation:
                    if isinstance(affiliation, dict):
                        add_entity_property(graph, author_uri, SCHEMA.affiliation, affiliation, "Organization")
                    elif isinstance(affiliation, str):
                        org_uri = URIRef(f"{OKN_BASE}organization/{slugify(affiliation)}")
                        graph.add((author_uri, SCHEMA.affiliation, org_uri))
                        graph.add((org_uri, RDF.type, SCHEMA.Organization))
                        graph.add((org_uri, SCHEMA.name, Literal(affiliation)))
        elif isinstance(author, str):
            # Simple string author
            graph.add((subject, SCHEMA.author, Literal(author)))


def handle_funding(graph: Graph, subject: URIRef, funding: List[Dict[str, Any]] | Dict[str, Any] | None) -> None:
    """Handle funding information."""
    if not funding:
        return
    
    # Handle both list and single object
    if isinstance(funding, dict):
        funding = [funding]
    
    for grant in funding:
        if isinstance(grant, dict):
            grant_uri = add_entity_property(graph, subject, SCHEMA.funding, grant, "MonetaryGrant")
            if grant_uri:
                # Handle funder(s)
                funder = grant.get("funder")
                if funder:
                    if isinstance(funder, list):
                        for f in funder:
                            if isinstance(f, dict):
                                add_entity_property(graph, grant_uri, SCHEMA.funder, f, "Organization")
                    elif isinstance(funder, dict):
                        add_entity_property(graph, grant_uri, SCHEMA.funder, funder, "Organization")


def handle_health_condition(graph: Graph, subject: URIRef, conditions: List[Dict[str, Any]]) -> None:
    """Handle health condition(s)."""
    if not conditions:
        return
    
    for condition in conditions:
        if isinstance(condition, dict):
            # Use the URL field if available (MONDO URI)
            condition_uri = get_entity_uri(condition, "DefinedTerm")
            if condition_uri:
                graph.add((subject, SCHEMA.healthCondition, condition_uri))
                graph.add((condition_uri, RDF.type, SCHEMA.DefinedTerm))
                # Add name if available
                if condition.get("name"):
                    graph.add((condition_uri, SCHEMA.name, Literal(condition["name"])))
                # If it's an external URI (MONDO), we could add owl:sameAs if we had internal URIs
                # For now, we use external URIs directly, so owl:sameAs isn't needed here


def handle_species(graph: Graph, subject: URIRef, species_list: List[Dict[str, Any]]) -> None:
    """Handle species information."""
    if not species_list:
        return
    
    for species in species_list:
        if isinstance(species, dict):
            # Use the URL field if available (UniProt taxonomy URI)
            species_uri = get_entity_uri(species, "DefinedTerm")
            if species_uri:
                graph.add((subject, SCHEMA.species, species_uri))
                graph.add((species_uri, RDF.type, SCHEMA.DefinedTerm))
                # Add name if available
                if species.get("name"):
                    graph.add((species_uri, SCHEMA.name, Literal(species["name"])))


def handle_infectious_agent(graph: Graph, subject: URIRef, agents: List[Dict[str, Any]]) -> None:
    """Handle infectious agent(s)."""
    if not agents:
        return
    
    for agent in agents:
        if isinstance(agent, dict):
            # Use the URL field if available (UniProt taxonomy URI)
            agent_uri = get_entity_uri(agent, "DefinedTerm")
            if agent_uri:
                graph.add((subject, SCHEMA.infectiousAgent, agent_uri))
                graph.add((agent_uri, RDF.type, SCHEMA.DefinedTerm))
                # Add name if available
                if agent.get("name"):
                    graph.add((agent_uri, SCHEMA.name, Literal(agent["name"])))


def handle_distribution(graph: Graph, subject: URIRef, distributions: List[Dict[str, Any]]) -> None:
    """Handle distribution(s) of the dataset."""
    if not distributions:
        return
    
    for dist in distributions:
        if isinstance(dist, dict):
            add_entity_property(graph, subject, SCHEMA.distribution, dist, "DataDownload")


def handle_included_in_catalog(graph: Graph, subject: URIRef, catalog: Dict[str, Any] | List[Dict[str, Any]] | None) -> None:
    """Handle includedInDataCatalog."""
    if not catalog:
        return
    
    # Handle both list and single object
    if isinstance(catalog, list):
        catalogs = catalog
    else:
        catalogs = [catalog]
    
    for cat in catalogs:
        if isinstance(cat, dict):
            add_entity_property(graph, subject, SCHEMA.includedInDataCatalog, cat, "DataCatalog")


def handle_doi(graph: Graph, subject: URIRef, doi: str | List[str] | None) -> None:
    """Handle DOI - convert to https://doi.org/ URI and add as sameAs and owl:sameAs."""
    if not doi:
        return
    
    if isinstance(doi, list):
        dois = doi
    else:
        dois = [doi]
    
    for d in dois:
        if d and isinstance(d, str) and d.lower() != "none":
            if not d.startswith("http"):
                doi_uri = URIRef(f"https://doi.org/{d}")
            else:
                doi_uri = URIRef(d)
            # Add both schema:sameAs and owl:sameAs for interoperability
            graph.add((subject, SCHEMA.sameAs, doi_uri))
            graph.add((subject, OWL.sameAs, doi_uri))


def handle_identifier(graph: Graph, subject: URIRef, identifiers: List[str] | str | None) -> None:
    """Handle identifier(s) - add as schema:identifier if not already a URI."""
    if not identifiers:
        return
    
    if isinstance(identifiers, str):
        identifiers = [identifiers]
    
    for ident in identifiers:
        if ident and isinstance(ident, str):
            if ident.startswith("http"):
                # It's already a URI, add as sameAs and owl:sameAs
                ident_uri = URIRef(ident)
                graph.add((subject, SCHEMA.sameAs, ident_uri))
                graph.add((subject, OWL.sameAs, ident_uri))
            else:
                # Add as literal identifier
                graph.add((subject, SCHEMA.identifier, Literal(ident)))


def add_rdfs_axioms(graph: Graph) -> None:
    """Add RDFS axioms for classes and properties per Proto-OKN best practices."""
    # Classes we use from Schema.org
    classes = [
        "Dataset",
        "Person",
        "Organization",
        "MonetaryGrant",
        "DefinedTerm",
        "DataCatalog",
        "DataDownload",
        "ScholarlyArticle",
        "ResearchProject",
    ]
    
    for class_name in classes:
        class_uri = SCHEMA[class_name]
        # Declare as rdfs:Class
        graph.add((class_uri, RDF.type, RDFS.Class))
    
    # Property domain and range assertions
    # These are simplified - Schema.org has more complex hierarchies
    properties = [
        # (property_name, domain, range)
        ("name", "Thing", "Text"),
        ("description", "Thing", "Text"),
        ("url", "Thing", "URL"),
        ("identifier", "Thing", "Text"),
        ("date", "Thing", "Date"),
        ("dateModified", "Thing", "DateTime"),
        ("dateCreated", "Thing", "Date"),
        ("datePublished", "Thing", "Date"),
        ("author", "CreativeWork", "Person"),
        ("author", "Dataset", "Person"),  # Dataset is CreativeWork
        ("funding", "Thing", "MonetaryGrant"),
        ("funder", "MonetaryGrant", "Organization"),
        ("healthCondition", "MedicalEntity", "DefinedTerm"),
        ("healthCondition", "Dataset", "DefinedTerm"),  # Dataset may have healthCondition
        ("species", "Dataset", "DefinedTerm"),
        ("infectiousAgent", "Dataset", "DefinedTerm"),
        ("distribution", "Dataset", "DataDownload"),
        ("includedInDataCatalog", "Dataset", "DataCatalog"),
        ("sameAs", "Thing", "URL"),
        ("alternateName", "Thing", "Text"),
        ("startDate", "MonetaryGrant", "Date"),
        ("endDate", "MonetaryGrant", "Date"),
        ("affiliation", "Person", "Organization"),
        ("parentOrganization", "Organization", "Organization"),
    ]
    
    for prop_name, domain, range_name in properties:
        prop_uri = SCHEMA[prop_name]
        domain_uri = SCHEMA[domain]
        
        # Add domain
        graph.add((prop_uri, RDFS.domain, domain_uri))
        
        # Add range (simplified - Text/URL might be literals)
        if range_name in ("Text", "URL", "Date", "DateTime"):
            # For literals, we'll use rdfs:Literal or XSD types
            if range_name == "Date":
                graph.add((prop_uri, RDFS.range, XSD.date))
            elif range_name == "DateTime":
                graph.add((prop_uri, RDFS.range, XSD.dateTime))
            else:
                graph.add((prop_uri, RDFS.range, RDFS.Literal))
        else:
            range_uri = SCHEMA[range_name]
            graph.add((prop_uri, RDFS.range, range_uri))


def convert_jsonl_to_rdf(
    input_path: Path,
    output_path: Path,
    resource: str,
) -> int:
    """Convert a JSONL file to RDF N-Triples format.
    
    Args:
        input_path: Path to input JSONL file
        output_path: Path to output N-Triples file
        resource: Name of the resource (for URI generation)
    
    Returns:
        Number of datasets converted
    """
    graph = Graph()
    
    # Bind namespaces for cleaner output
    graph.bind("schema", SCHEMA)
    graph.bind("okn", OKN)
    graph.bind("rdf", RDF)
    graph.bind("rdfs", RDFS)
    graph.bind("owl", OWL)
    graph.bind("xsd", XSD)
    
    # Add RDFS axioms per Proto-OKN best practices
    add_rdfs_axioms(graph)
    
    count = 0
    
    with input_path.open("r", encoding="utf-8") as fh:
        for line_num, line in enumerate(fh, 1):
            if not line.strip():
                continue
            
            try:
                dataset = json.loads(line)
                convert_dataset(graph, dataset, resource)
                count += 1
                
                if count % 100 == 0:
                    logger.info(f"Converted {count} datasets from {input_path.name}")
            
            except json.JSONDecodeError as e:
                logger.warning(f"Skipping invalid JSON at line {line_num} in {input_path}: {e}")
                continue
            except Exception as e:
                logger.error(f"Error converting dataset at line {line_num} in {input_path}: {e}")
                continue
    
    # Write to N-Triples format
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as fh:
        graph.serialize(fh, format="nt", encoding="utf-8")
    
    logger.info(f"Converted {count} datasets from {input_path.name} to {output_path}")
    
    return count

