#!/usr/bin/env python3
"""
Client for fetching FRINK registry and schema statistics.

Scrapes the FRINK registry (https://frink.renci.org/registry/) and
kg-stats pages to extract knowledge graph metadata, classes, properties,
and prefix mappings for use in NL-to-SPARQL query generation.

Usage:
    from frink import FrinkRegistryClient

    client = FrinkRegistryClient()
    graphs = client.fetch_all_graphs()

    # Or fetch a single graph's schema
    schema = client.fetch_schema_stats("ubergraph")
"""

import re
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from urllib.parse import urljoin

import requests
from clients.http_utils import create_session

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


@dataclass
class GraphClass:
    """A class/type in a knowledge graph schema."""
    uri: str
    label: str
    count: int
    description: str = ""


@dataclass
class GraphProperty:
    """A property/slot in a knowledge graph schema."""
    uri: str
    label: str
    usage_count: int
    domain: str = ""
    range: str = ""
    description: str = ""


@dataclass
class GraphSchema:
    """Schema information for a knowledge graph."""
    classes: List[GraphClass] = field(default_factory=list)
    properties: List[GraphProperty] = field(default_factory=list)
    prefixes: Dict[str, str] = field(default_factory=dict)


@dataclass
class KnowledgeGraphMetadata:
    """Metadata for a FRINK knowledge graph."""
    shortname: str
    title: str
    description: str
    sparql_endpoint: str
    stats_url: str
    registry_url: str
    domain: str = "general"
    typical_use_cases: List[str] = field(default_factory=list)


@dataclass
class KnowledgeGraph:
    """Complete metadata and schema for a FRINK knowledge graph."""
    metadata: KnowledgeGraphMetadata
    schema: Optional[GraphSchema] = None

    @property
    def shortname(self) -> str:
        return self.metadata.shortname


class FrinkRegistryClient:
    """
    Client for fetching FRINK registry and knowledge graph schema data.

    Scrapes:
    - Registry page for list of knowledge graphs
    - Individual kg-stats pages for schema information (classes, properties, prefixes)

    Usage:
        client = FrinkRegistryClient()

        # Fetch all graphs with schemas
        graphs = client.fetch_all_graphs()

        # Fetch registry only (faster)
        registry = client.fetch_registry()

        # Fetch single graph schema
        schema = client.fetch_schema_stats("ubergraph")
    """

    REGISTRY_URL = "https://frink.renci.org/registry/"
    SPARQL_ENDPOINT_TEMPLATE = "https://frink.apps.renci.org/{shortname}/sparql"
    STATS_URL_TEMPLATE = "https://frink.renci.org/kg-stats/{shortname}-kg"
    GRAPH_DETAIL_TEMPLATE = "https://frink.renci.org/registry/kgs/{shortname}/"
    FEDERATED_ENDPOINT = "https://frink.apps.renci.org/?query="

    # Domain classification based on graph name patterns
    DOMAIN_HINTS = {
        "biobricks": "toxicology",
        "spoke": "biomedical",
        "ubergraph": "ontology",
        "wikidata": "general",
        "nde": "biomedical_datasets",
        "geoconnex": "geospatial",
        "sawgraph": "environmental",
        "climate": "climate",
        "health": "health",
        "semopenalex": "scholarly",
        "ufokn": "flooding",
        "mesh": "ontology",
        "kg-microbe": "microbiology",
        "kg-ichange": "climate",
        "biolink": "biomedical",
    }

    # Use cases by domain
    DOMAIN_USE_CASES = {
        "ontology": ["term lookup", "hierarchy traversal", "semantic reasoning", "cross-ontology mapping"],
        "biomedical": ["disease-gene relationships", "drug-target interactions", "phenotype associations"],
        "biomedical_datasets": ["dataset discovery", "study metadata", "data availability"],
        "toxicology": ["adverse outcome pathways", "chemical toxicity", "key event relationships"],
        "geospatial": ["location queries", "spatial relationships", "geographic features"],
        "environmental": ["environmental monitoring", "pollution data", "ecological relationships"],
        "climate": ["climate data", "weather patterns", "environmental indicators"],
        "scholarly": ["publication search", "author networks", "citation analysis"],
        "general": ["entity lookup", "relationship queries", "data exploration"],
    }

    def __init__(self, timeout: int = 30, max_retries: int = 3):
        """
        Initialize the FRINK registry client.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
        """
        if not HAS_BS4:
            raise ImportError(
                "beautifulsoup4 is required. Install with: pip install beautifulsoup4"
            )

        self.timeout = timeout
        self.max_retries = max_retries
        self._session = None

    @property
    def session(self) -> requests.Session:
        """Get or create the requests session with retry logic."""
        if self._session is None:
            self._session = create_session(
                max_retries=self.max_retries,
                backoff_factor=1.0,
                user_agent="FrinkContextBuilder/1.0 (+https://github.com/SuLab/OKN-WOBD)",
            )
        return self._session

    def fetch_registry(self) -> List[Dict[str, str]]:
        """
        Fetch the list of knowledge graphs from the FRINK registry.

        Returns:
            List of dicts with shortname, title, description for each graph
        """
        response = self.session.get(self.REGISTRY_URL, timeout=self.timeout)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        graphs = []

        # Find the table containing knowledge graphs
        # The registry page has a table with columns: Shortname, Title, Description, Links
        tables = soup.find_all('table')

        for table in tables:
            rows = table.find_all('tr')
            for row in rows[1:]:  # Skip header row
                cols = row.find_all(['td', 'th'])
                if len(cols) >= 3:
                    # Extract shortname (may be in a link)
                    shortname_cell = cols[0]
                    link = shortname_cell.find('a')
                    if link:
                        shortname = link.get_text(strip=True)
                        # Extract shortname from href if needed
                        href = link.get('href', '')
                        if '/kgs/' in href:
                            # Extract from URL like /registry/kgs/ubergraph/
                            match = re.search(r'/kgs/([^/]+)/?', href)
                            if match:
                                shortname = match.group(1)
                    else:
                        shortname = shortname_cell.get_text(strip=True)

                    title = cols[1].get_text(strip=True) if len(cols) > 1 else shortname
                    description = cols[2].get_text(strip=True) if len(cols) > 2 else ""

                    if shortname and shortname.lower() not in ('shortname', 'name'):
                        graphs.append({
                            "shortname": shortname,
                            "title": title,
                            "description": description
                        })

        # Deduplicate by shortname
        seen = set()
        unique_graphs = []
        for g in graphs:
            if g["shortname"] not in seen:
                seen.add(g["shortname"])
                unique_graphs.append(g)

        return unique_graphs

    def fetch_schema_via_sparql(self, shortname: str, timeout: int = 30) -> Optional[GraphSchema]:
        """
        Discover schema by querying the SPARQL endpoint directly.

        This is more reliable than scraping kg-stats pages.

        Args:
            shortname: The graph's shortname (e.g., "ubergraph")
            timeout: Query timeout in seconds

        Returns:
            GraphSchema with discovered predicates and prefixes
        """
        try:
            from clients.sparql import SPARQLClient
        except ImportError:
            return None

        endpoint = self.SPARQL_ENDPOINT_TEMPLATE.format(shortname=shortname)
        client = SPARQLClient(default_endpoint=endpoint, timeout=timeout)

        properties = []
        prefixes = {}

        # Query for distinct predicates (fast query)
        predicate_query = """
        SELECT DISTINCT ?p WHERE {
            ?s ?p ?o .
        }
        LIMIT 200
        """

        try:
            result = client.query(predicate_query, include_prefixes=False)
            seen_prefixes = set()

            for row in result.bindings:
                pred_uri = row.get('p', {}).get('value', '')
                if pred_uri:
                    # Extract label from URI
                    label = pred_uri.split('/')[-1].split('#')[-1]
                    properties.append(GraphProperty(
                        uri=pred_uri,
                        label=label,
                        usage_count=0,  # We don't count for speed
                    ))

                    # Extract prefix from URI
                    if '#' in pred_uri:
                        prefix_uri = pred_uri.rsplit('#', 1)[0] + '#'
                    elif '/' in pred_uri:
                        prefix_uri = pred_uri.rsplit('/', 1)[0] + '/'
                    else:
                        continue

                    if prefix_uri not in seen_prefixes:
                        seen_prefixes.add(prefix_uri)
                        # Generate prefix name from URI
                        prefix_name = self._guess_prefix_name(prefix_uri)
                        if prefix_name:
                            prefixes[prefix_name] = prefix_uri

        except Exception as e:
            print(f"  SPARQL schema query failed for {shortname}: {e}")

        if properties or prefixes:
            return GraphSchema(classes=[], properties=properties, prefixes=prefixes)
        return None

    def _guess_prefix_name(self, uri: str) -> Optional[str]:
        """Guess a reasonable prefix name from a URI."""
        # Common mappings
        known = {
            "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf",
            "http://www.w3.org/2000/01/rdf-schema#": "rdfs",
            "http://www.w3.org/2002/07/owl#": "owl",
            "http://www.w3.org/2001/XMLSchema#": "xsd",
            "http://purl.obolibrary.org/obo/": "obo",
            "http://www.wikidata.org/prop/direct/": "wdt",
            "http://www.wikidata.org/entity/": "wd",
            "http://schema.org/": "schema",
            "http://purl.org/dc/terms/": "dcterms",
            "http://xmlns.com/foaf/0.1/": "foaf",
        }
        if uri in known:
            return known[uri]

        # Extract from URI pattern
        if '#' in uri:
            part = uri.split('/')[-1].rstrip('#').lower()
        else:
            part = uri.rstrip('/').split('/')[-1].lower()

        # Clean up
        part = re.sub(r'[^a-z0-9]', '', part)
        if part and len(part) <= 15:
            return part
        return None

    def fetch_schema_stats(self, shortname: str) -> Optional[GraphSchema]:
        """
        Fetch schema statistics, trying kg-stats page first, then SPARQL.

        Args:
            shortname: The graph's shortname (e.g., "ubergraph")

        Returns:
            GraphSchema with classes, properties, and prefixes, or None if unavailable
        """
        # First try SPARQL-based discovery (more reliable)
        schema = self.fetch_schema_via_sparql(shortname)
        if schema and (schema.properties or schema.prefixes):
            return schema

        # Fall back to kg-stats page scraping
        url = self.STATS_URL_TEMPLATE.format(shortname=shortname)

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as e:
            # Already tried SPARQL, so just note the failure
            return schema  # May have partial data from SPARQL

        soup = BeautifulSoup(response.text, 'html.parser')

        classes = []
        properties = []
        prefixes = {}

        # Parse the page content - kg-stats pages typically have sections for
        # Classes, Slots (properties), and Prefixes

        # Find all tables on the page
        tables = soup.find_all('table')

        for table in tables:
            # Try to identify table type by headers or preceding text
            caption = table.find('caption')
            prev_header = table.find_previous(['h2', 'h3', 'h4'])

            table_type = None
            if caption:
                caption_text = caption.get_text(strip=True).lower()
                if 'class' in caption_text:
                    table_type = 'classes'
                elif 'slot' in caption_text or 'propert' in caption_text:
                    table_type = 'properties'
                elif 'prefix' in caption_text:
                    table_type = 'prefixes'
            elif prev_header:
                header_text = prev_header.get_text(strip=True).lower()
                if 'class' in header_text:
                    table_type = 'classes'
                elif 'slot' in header_text or 'propert' in header_text:
                    table_type = 'properties'
                elif 'prefix' in header_text:
                    table_type = 'prefixes'

            # Parse table rows
            rows = table.find_all('tr')
            if len(rows) < 2:
                continue

            # Get header to understand columns
            header_row = rows[0]
            headers = [th.get_text(strip=True).lower() for th in header_row.find_all(['th', 'td'])]

            for row in rows[1:]:
                cols = row.find_all(['td', 'th'])
                if len(cols) < 2:
                    continue

                col_texts = [col.get_text(strip=True) for col in cols]

                # Try to parse as class/property entry
                if table_type == 'classes' or (not table_type and self._looks_like_class_row(headers, col_texts)):
                    class_entry = self._parse_class_row(headers, col_texts)
                    if class_entry:
                        classes.append(class_entry)

                elif table_type == 'properties' or (not table_type and self._looks_like_property_row(headers, col_texts)):
                    prop_entry = self._parse_property_row(headers, col_texts)
                    if prop_entry:
                        properties.append(prop_entry)

                elif table_type == 'prefixes':
                    if len(col_texts) >= 2:
                        prefix_name = col_texts[0].rstrip(':')
                        prefix_uri = col_texts[1]
                        if prefix_uri.startswith('http'):
                            prefixes[prefix_name] = prefix_uri

        # Also try to extract prefixes from any code blocks or definition lists
        prefixes.update(self._extract_prefixes_from_text(soup))

        return GraphSchema(classes=classes, properties=properties, prefixes=prefixes)

    def _looks_like_class_row(self, headers: List[str], values: List[str]) -> bool:
        """Check if a row looks like a class definition."""
        # Look for patterns like URI/name + count
        if any('class' in h or 'type' in h for h in headers):
            return True
        if len(values) >= 2:
            # Check if second column looks like a count
            try:
                int(re.sub(r'[^\d]', '', values[1]) or '0')
                return 'http' in values[0] or ':' in values[0]
            except (ValueError, IndexError):
                pass
        return False

    def _looks_like_property_row(self, headers: List[str], values: List[str]) -> bool:
        """Check if a row looks like a property definition."""
        if any('slot' in h or 'propert' in h or 'predicate' in h for h in headers):
            return True
        return False

    def _parse_class_row(self, headers: List[str], values: List[str]) -> Optional[GraphClass]:
        """Parse a table row as a class entry."""
        if len(values) < 1:
            return None

        uri = values[0]
        label = uri.split('#')[-1].split('/')[-1]
        count = 0

        # Find count column
        for i, h in enumerate(headers):
            if 'count' in h or 'instance' in h or 'occurrence' in h:
                if i < len(values):
                    try:
                        count = int(re.sub(r'[^\d]', '', values[i]) or '0')
                    except ValueError:
                        pass
                break
        else:
            # Default: try second column as count
            if len(values) >= 2:
                try:
                    count = int(re.sub(r'[^\d]', '', values[1]) or '0')
                except ValueError:
                    pass

        if uri and (uri.startswith('http') or ':' in uri):
            return GraphClass(uri=uri, label=label, count=count)
        return None

    def _parse_property_row(self, headers: List[str], values: List[str]) -> Optional[GraphProperty]:
        """Parse a table row as a property entry."""
        if len(values) < 1:
            return None

        uri = values[0]
        label = uri.split('#')[-1].split('/')[-1]
        usage_count = 0

        # Find usage count column
        for i, h in enumerate(headers):
            if 'count' in h or 'usage' in h or 'occurrence' in h:
                if i < len(values):
                    try:
                        usage_count = int(re.sub(r'[^\d]', '', values[i]) or '0')
                    except ValueError:
                        pass
                break
        else:
            # Default: try second column as count
            if len(values) >= 2:
                try:
                    usage_count = int(re.sub(r'[^\d]', '', values[1]) or '0')
                except ValueError:
                    pass

        if uri and (uri.startswith('http') or ':' in uri):
            return GraphProperty(uri=uri, label=label, usage_count=usage_count)
        return None

    def _extract_prefixes_from_text(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract prefix mappings from code blocks or definition lists."""
        prefixes = {}

        # Look for prefix definitions in code blocks
        for code in soup.find_all(['code', 'pre']):
            text = code.get_text()
            # Match patterns like "prefix: http://..."
            matches = re.findall(r'(\w+):\s*(https?://[^\s<>"]+)', text)
            for name, uri in matches:
                if name.lower() not in ('http', 'https'):
                    prefixes[name] = uri

        # Look for definition lists
        for dl in soup.find_all('dl'):
            dts = dl.find_all('dt')
            dds = dl.find_all('dd')
            for dt, dd in zip(dts, dds):
                name = dt.get_text(strip=True).rstrip(':')
                uri = dd.get_text(strip=True)
                if uri.startswith('http'):
                    prefixes[name] = uri

        return prefixes

    def _classify_domain(self, shortname: str, title: str, description: str) -> str:
        """Classify a graph's domain based on name, title, and description."""
        text = f"{shortname} {title} {description}".lower()

        for hint, domain in self.DOMAIN_HINTS.items():
            if hint in text:
                return domain

        # Additional keyword matching
        if any(kw in text for kw in ['ontology', 'obo', 'taxonomy']):
            return 'ontology'
        if any(kw in text for kw in ['disease', 'gene', 'drug', 'protein', 'clinical']):
            return 'biomedical'
        if any(kw in text for kw in ['geo', 'spatial', 'location', 'map']):
            return 'geospatial'

        return "general"

    def _get_use_cases(self, domain: str) -> List[str]:
        """Get typical use cases for a domain."""
        return self.DOMAIN_USE_CASES.get(domain, self.DOMAIN_USE_CASES["general"])

    def build_knowledge_graph(self, registry_entry: Dict[str, str], fetch_schema: bool = True) -> KnowledgeGraph:
        """
        Build a complete KnowledgeGraph object from registry data.

        Args:
            registry_entry: Dict with shortname, title, description
            fetch_schema: Whether to fetch schema stats (slower)

        Returns:
            KnowledgeGraph with metadata and optionally schema
        """
        shortname = registry_entry["shortname"]
        title = registry_entry.get("title", shortname)
        description = registry_entry.get("description", "")

        domain = self._classify_domain(shortname, title, description)

        metadata = KnowledgeGraphMetadata(
            shortname=shortname,
            title=title,
            description=description,
            sparql_endpoint=self.SPARQL_ENDPOINT_TEMPLATE.format(shortname=shortname),
            stats_url=self.STATS_URL_TEMPLATE.format(shortname=shortname),
            registry_url=self.GRAPH_DETAIL_TEMPLATE.format(shortname=shortname),
            domain=domain,
            typical_use_cases=self._get_use_cases(domain),
        )

        schema = None
        if fetch_schema:
            schema = self.fetch_schema_stats(shortname)

        return KnowledgeGraph(metadata=metadata, schema=schema)

    def fetch_all_graphs(self, fetch_schemas: bool = True, verbose: bool = True) -> List[KnowledgeGraph]:
        """
        Fetch all knowledge graphs from registry with their schemas.

        Args:
            fetch_schemas: Whether to fetch schema stats for each graph
            verbose: Print progress messages

        Returns:
            List of KnowledgeGraph objects
        """
        if verbose:
            print("Fetching registry...")

        registry = self.fetch_registry()

        if verbose:
            print(f"Found {len(registry)} knowledge graphs")

        graphs = []
        for i, entry in enumerate(registry):
            if verbose:
                print(f"  [{i+1}/{len(registry)}] {entry['shortname']}...", end=" ")

            graph = self.build_knowledge_graph(entry, fetch_schema=fetch_schemas)
            graphs.append(graph)

            if verbose:
                if graph.schema:
                    print(f"({len(graph.schema.classes)} classes, {len(graph.schema.properties)} properties)")
                else:
                    print("(no schema)")

        return graphs
