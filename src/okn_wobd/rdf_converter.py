"""Convert JSONL dataset records to RDF N-Triples format."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlparse

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


def clean_uri(uri_string: str) -> Optional[str]:
    """
    Clean and validate a URI string.
    
    Extracts just the URI portion if there's extra text (e.g., "https://orcid.org/123  extra text"),
    and validates it's a proper URI. Returns None if the string doesn't contain a valid URI.
    """
    if not isinstance(uri_string, str):
        return None
    
    uri_string = uri_string.strip()
    if not uri_string:
        return None
    
    # If it starts with http/https, try to extract just the URI part
    if uri_string.startswith("http://") or uri_string.startswith("https://"):
        # Find where the URI ends (first whitespace or invalid character)
        match = re.match(r"(https?://[^\s<>\"{}|\\^`\[\]]+)", uri_string)
        if match:
            cleaned = match.group(1)
            # Basic validation: should be a valid-looking URI
            try:
                parsed = urlparse(cleaned)
                if parsed.scheme and parsed.netloc:
                    return cleaned
            except Exception:
                pass
    
    return None


def safe_uriref(uri_string: str, context: Optional[str] = None) -> Optional[URIRef]:
    """
    Safely create a URIRef, logging warnings for invalid URIs.
    
    Args:
        uri_string: The URI string to convert
        context: Optional context string for logging (e.g., "dataset_id=123, field=identifier")
    
    Returns:
        URIRef if valid, None otherwise
    """
    if not uri_string:
        return None
    
    cleaned = clean_uri(uri_string)
    if not cleaned:
        if context:
            logger.warning(
                f"Invalid URI format (no valid URI found): {uri_string!r} "
                f"[Context: {context}]"
            )
        return None
    
    try:
        return URIRef(cleaned)
    except Exception as e:
        if context:
            logger.warning(
                f"Failed to create URIRef from {uri_string!r} (cleaned: {cleaned!r}): {e} "
                f"[Context: {context}]"
            )
        return None


def dataset_uri(resource: str, dataset_id: str) -> URIRef:
    """Generate a URI for a dataset."""
    resource_slug = slugify(resource)
    safe_id = quote(dataset_id, safe="")
    return URIRef(f"{OKN_BASE}dataset/{resource_slug}/{safe_id}")


def get_entity_uri(
    entity: Dict[str, Any],
    entity_type: str,
    context: Optional[str] = None,
) -> Optional[URIRef]:
    """Get URI for an entity, preferring external URIs when available.
    
    Args:
        entity: Entity dictionary
        entity_type: Type of entity (e.g., "Person", "Organization")
        context: Optional context string for error logging (e.g., "dataset_id=123")
    
    Returns:
        URIRef if valid URI found, None otherwise
    """
    # For diseases, species, infectious agents - use 'url' field if it's an ontology URI
    if entity.get("url"):
        url = entity["url"]
        if isinstance(url, str):
            # Check if it's a recognized ontology URI
            if any(prefix in url for prefix in [
                "purl.obolibrary.org",
                "uniprot.org",
                "ror.org",
                "doi.org",
                "orcid.org",
                "http://purl.obolibrary.org/",
                "https://www.uniprot.org/",
            ]):
                ctx = f"{context}, entity_type={entity_type}, field=url" if context else f"entity_type={entity_type}, field=url"
                return safe_uriref(url, context=ctx)
    
    # For organizations - use ROR identifier if available
    if entity_type == "Organization" and entity.get("identifier"):
        identifier = entity["identifier"]
        if isinstance(identifier, str):
            ctx = f"{context}, entity_type={entity_type}, field=identifier" if context else f"entity_type={entity_type}, field=identifier"
            uri = safe_uriref(identifier, context=ctx)
            if uri and str(uri).startswith("https://ror.org/"):
                return uri
    
    # For DOIs - convert to https://doi.org/ URI
    if entity.get("doi"):
        doi = entity["doi"] if isinstance(entity["doi"], str) else str(entity["doi"])
        ctx = f"{context}, entity_type={entity_type}, field=doi" if context else f"entity_type={entity_type}, field=doi"
        if not doi.startswith("http"):
            cleaned_doi = clean_uri(doi)
            if cleaned_doi:
                return safe_uriref(f"https://doi.org/{cleaned_doi}", context=ctx)
            return safe_uriref(f"https://doi.org/{doi}", context=ctx)
        return safe_uriref(doi, context=ctx)
    
    # For identifiers that are already URIs (including ORCID)
    if entity.get("identifier"):
        identifier = entity["identifier"]
        if isinstance(identifier, str):
            ctx = f"{context}, entity_type={entity_type}, field=identifier" if context else f"entity_type={entity_type}, field=identifier"
            return safe_uriref(identifier, context=ctx)
    
    # For DataDownload - use contentUrl if available, otherwise construct from name or contentUrl hash
    if entity_type == "DataDownload":
        if entity.get("contentUrl"):
            # Use contentUrl as the URI for DataDownload
            content_url = entity["contentUrl"]
            if isinstance(content_url, str):
                ctx = f"{context}, entity_type={entity_type}, field=contentUrl" if context else f"entity_type={entity_type}, field=contentUrl"
                uri = safe_uriref(content_url, context=ctx)
                if uri:
                    return uri
        # Fall back to constructed URI if no valid contentUrl
        if entity.get("name"):
            return URIRef(f"{OKN_BASE}datadownload/{slugify(entity['name'])}")
        # Last resort: use a hash of the entity dict to create a unique URI
        entity_str = json.dumps(entity, sort_keys=True)
        entity_hash = hashlib.md5(entity_str.encode()).hexdigest()[:8]
        return URIRef(f"{OKN_BASE}datadownload/{entity_hash}")
    
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
    context: Optional[str] = None,
) -> Optional[URIRef]:
    """Add an entity property to the graph and return its URI."""
    entity_type = entity_type or entity.get("@type", "Thing")
    
    entity_uri = get_entity_uri(entity, entity_type, context=context)
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
    add_entity_properties(graph, entity_uri, entity, entity_type, context=context)
    
    return entity_uri


def add_entity_properties(graph: Graph, subject: URIRef, entity: Dict[str, Any], entity_type: str, context: Optional[str] = None) -> None:
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
                    add_entity_property(graph, subject, predicate, item, context=context)
                else:
                    add_simple_property(graph, subject, predicate, item)
        elif isinstance(value, dict):
            # Nested entity
            add_entity_property(graph, subject, predicate, value, context=context)
        else:
            add_simple_property(graph, subject, predicate, value)


def convert_dataset(graph: Graph, dataset: Dict[str, Any], resource: str) -> URIRef:
    """Convert a dataset record to RDF and add it to the graph."""
    dataset_id = dataset.get("_id")
    if not dataset_id:
        raise ValueError("Dataset missing required '_id' field")
    
    dataset_uri_ref = dataset_uri(resource, dataset_id)
    context = f"dataset_id={dataset_id}"
    
    # Add type
    graph.add((dataset_uri_ref, RDF.type, SCHEMA.Dataset))
    
    # Add properties
    add_entity_properties(graph, dataset_uri_ref, dataset, "Dataset", context=context)
    
    # Handle special relationships
    handle_author(graph, dataset_uri_ref, dataset.get("author", []), context=context)
    handle_funding(graph, dataset_uri_ref, dataset.get("funding", []), context=context)
    handle_health_condition(graph, dataset_uri_ref, dataset.get("healthCondition", []), context=context)
    handle_species(graph, dataset_uri_ref, dataset.get("species", []), context=context)
    handle_infectious_agent(graph, dataset_uri_ref, dataset.get("infectiousAgent", []), context=context)
    handle_distribution(graph, dataset_uri_ref, dataset.get("distribution"), context=context)
    handle_included_in_catalog(graph, dataset_uri_ref, dataset.get("includedInDataCatalog"), context=context)
    handle_doi(graph, dataset_uri_ref, dataset.get("doi"), context=context)
    handle_identifier(graph, dataset_uri_ref, dataset.get("identifier", []), context=context)
    
    return dataset_uri_ref


def handle_author(graph: Graph, subject: URIRef, authors: List[Dict[str, Any]], context: Optional[str] = None) -> None:
    """Handle author(s) of a dataset."""
    if not authors:
        return
    
    for author in authors:
        if isinstance(author, dict):
            author_uri = add_entity_property(graph, subject, SCHEMA.author, author, "Person", context=context)
            if author_uri:
                # Handle affiliation
                affiliation = author.get("affiliation")
                if affiliation:
                    if isinstance(affiliation, dict):
                        add_entity_property(graph, author_uri, SCHEMA.affiliation, affiliation, "Organization", context=context)
                    elif isinstance(affiliation, str):
                        org_uri = URIRef(f"{OKN_BASE}organization/{slugify(affiliation)}")
                        graph.add((author_uri, SCHEMA.affiliation, org_uri))
                        graph.add((org_uri, RDF.type, SCHEMA.Organization))
                        graph.add((org_uri, SCHEMA.name, Literal(affiliation)))
        elif isinstance(author, str):
            # Simple string author
            graph.add((subject, SCHEMA.author, Literal(author)))


def handle_funding(graph: Graph, subject: URIRef, funding: List[Dict[str, Any]] | Dict[str, Any] | None, context: Optional[str] = None) -> None:
    """Handle funding information."""
    if not funding:
        return
    
    # Handle both list and single object
    if isinstance(funding, dict):
        funding = [funding]
    
    for grant in funding:
        if isinstance(grant, dict):
            grant_uri = add_entity_property(graph, subject, SCHEMA.funding, grant, "MonetaryGrant", context=context)
            if grant_uri:
                # Handle funder(s)
                funder = grant.get("funder")
                if funder:
                    if isinstance(funder, list):
                        for f in funder:
                            if isinstance(f, dict):
                                add_entity_property(graph, grant_uri, SCHEMA.funder, f, "Organization", context=context)
                    elif isinstance(funder, dict):
                        add_entity_property(graph, grant_uri, SCHEMA.funder, funder, "Organization", context=context)


def handle_health_condition(graph: Graph, subject: URIRef, conditions: List[Dict[str, Any]], context: Optional[str] = None) -> None:
    """Handle health condition(s)."""
    if not conditions:
        return
    
    for condition in conditions:
        if isinstance(condition, dict):
            # Use the URL field if available (MONDO URI)
            condition_uri = get_entity_uri(condition, "DefinedTerm", context=context)
            if condition_uri:
                graph.add((subject, SCHEMA.healthCondition, condition_uri))
                graph.add((condition_uri, RDF.type, SCHEMA.DefinedTerm))
                # Add name if available
                if condition.get("name"):
                    graph.add((condition_uri, SCHEMA.name, Literal(condition["name"])))
                # If it's an external URI (MONDO), we could add owl:sameAs if we had internal URIs
                # For now, we use external URIs directly, so owl:sameAs isn't needed here


def handle_species(graph: Graph, subject: URIRef, species_list: List[Dict[str, Any]], context: Optional[str] = None) -> None:
    """Handle species information."""
    if not species_list:
        return
    
    for species in species_list:
        if isinstance(species, dict):
            # Use the URL field if available (UniProt taxonomy URI)
            species_uri = get_entity_uri(species, "DefinedTerm", context=context)
            if species_uri:
                graph.add((subject, SCHEMA.species, species_uri))
                graph.add((species_uri, RDF.type, SCHEMA.DefinedTerm))
                # Add name if available
                if species.get("name"):
                    graph.add((species_uri, SCHEMA.name, Literal(species["name"])))


def handle_infectious_agent(graph: Graph, subject: URIRef, agents: List[Dict[str, Any]], context: Optional[str] = None) -> None:
    """Handle infectious agent(s)."""
    if not agents:
        return
    
    for agent in agents:
        if isinstance(agent, dict):
            # Use the URL field if available (UniProt taxonomy URI)
            agent_uri = get_entity_uri(agent, "DefinedTerm", context=context)
            if agent_uri:
                graph.add((subject, SCHEMA.infectiousAgent, agent_uri))
                graph.add((agent_uri, RDF.type, SCHEMA.DefinedTerm))
                # Add name if available
                if agent.get("name"):
                    graph.add((agent_uri, SCHEMA.name, Literal(agent["name"])))


def handle_distribution(
    graph: Graph,
    subject: URIRef,
    distributions: List[Dict[str, Any]] | Dict[str, Any] | None,
    context: Optional[str] = None,
) -> None:
    """Handle distribution(s) of the dataset.
    
    Preserves the original contentUrl values from the JSONL (e.g., ImmPort browser URLs,
    NCBI GEO URLs, OmicsDI API URLs) as they represent the actual source-specific
    download/browser locations for accessing the data.
    """
    if not distributions:
        return
    
    # Handle both list and single object
    if isinstance(distributions, dict):
        distributions = [distributions]
    
    for dist in distributions:
        if isinstance(dist, dict):
            # Preserve the original contentUrl from the JSONL - don't modify it
            # This keeps source-specific URLs like:
            # - ImmPort: https://browser.immport.org/browser?path=SDY2740
            # - NCBI GEO: https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE211378
            # - OmicsDI: https://www.omicsdi.org/ws/dataset/...
            add_entity_property(graph, subject, SCHEMA.distribution, dist, "DataDownload", context=context)


def handle_included_in_catalog(graph: Graph, subject: URIRef, catalog: Dict[str, Any] | List[Dict[str, Any]] | None, context: Optional[str] = None) -> None:
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
            add_entity_property(graph, subject, SCHEMA.includedInDataCatalog, cat, "DataCatalog", context=context)


def handle_doi(graph: Graph, subject: URIRef, doi: str | List[str] | None, context: Optional[str] = None) -> None:
    """Handle DOI - convert to https://doi.org/ URI and add as sameAs and owl:sameAs."""
    if not doi:
        return
    
    if isinstance(doi, list):
        dois = doi
    else:
        dois = [doi]
    
    for d in dois:
        if d and isinstance(d, str) and d.lower() != "none":
            ctx = f"{context}, field=doi" if context else "field=doi"
            if not d.startswith("http"):
                uri = safe_uriref(f"https://doi.org/{d}", context=ctx)
            else:
                uri = safe_uriref(d, context=ctx)
            if uri:
                # Add both schema:sameAs and owl:sameAs for interoperability
                graph.add((subject, SCHEMA.sameAs, uri))
                graph.add((subject, OWL.sameAs, uri))


def handle_identifier(graph: Graph, subject: URIRef, identifiers: List[str] | str | None, context: Optional[str] = None) -> None:
    """Handle identifier(s) - add as schema:identifier if not already a URI."""
    if not identifiers:
        return
    
    if isinstance(identifiers, str):
        identifiers = [identifiers]
    
    for ident in identifiers:
        if ident and isinstance(ident, str):
            if ident.startswith("http"):
                # It's already a URI, add as sameAs and owl:sameAs
                ctx = f"{context}, field=identifier" if context else "field=identifier"
                ident_uri = safe_uriref(ident, context=ctx)
                if ident_uri:
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
    unique_ids = set()  # Track unique dataset IDs to avoid double-counting duplicates
    skipped_duplicates = 0
    conversion_errors = 0
    json_errors = 0
    
    with input_path.open("r", encoding="utf-8") as fh:
        for line_num, line in enumerate(fh, 1):
            if not line.strip():
                continue
            
            try:
                dataset = json.loads(line)
                dataset_id = dataset.get("_id")
                
                # Skip if we've already processed this ID (duplicate in JSONL)
                if dataset_id in unique_ids:
                    skipped_duplicates += 1
                    if skipped_duplicates % 1000 == 0:
                        logger.debug(f"Skipped {skipped_duplicates} duplicate dataset IDs so far")
                    continue
                
                unique_ids.add(dataset_id)
                convert_dataset(graph, dataset, resource)
                count += 1
                
                if count % 100 == 0:
                    logger.info(f"Converted {count} unique datasets from {input_path.name}")
            
            except json.JSONDecodeError as e:
                json_errors += 1
                logger.warning(f"Skipping invalid JSON at line {line_num} in {input_path}: {e}")
                continue
            except ValueError as e:
                # Missing required fields (e.g., _id) - log and skip
                conversion_errors += 1
                logger.warning(f"Skipping dataset at line {line_num} in {input_path}: {e}")
                continue
            except Exception as e:
                # Other errors (e.g., invalid URIs) - log and skip, don't fail entire conversion
                conversion_errors += 1
                dataset_id = "unknown"
                try:
                    dataset = json.loads(line)
                    dataset_id = dataset.get("_id", "unknown")
                except Exception:
                    pass
                logger.warning(
                    f"Error converting dataset at line {line_num} (dataset_id={dataset_id}) "
                    f"in {input_path}: {e}. Skipping this dataset and continuing."
                )
                continue
    
    # Summary logging
    if skipped_duplicates > 0:
        logger.info(
            f"Skipped {skipped_duplicates} duplicate dataset ID(s) in {input_path.name}."
        )
    if json_errors > 0:
        logger.warning(f"Encountered {json_errors} JSON decode error(s) in {input_path.name}.")
    if conversion_errors > 0:
        logger.warning(
            f"Encountered {conversion_errors} conversion error(s) in {input_path.name}. "
            f"Check logs above for details (dataset IDs and field names)."
        )
    logger.info(f"Successfully converted {count} unique datasets from {input_path.name}.")
    
    # Write to N-Triples format
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as fh:
        graph.serialize(fh, format="nt", encoding="utf-8")
    
    logger.info(f"Converted {count} datasets from {input_path.name} to {output_path}")
    
    return count

