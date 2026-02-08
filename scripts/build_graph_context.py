#!/usr/bin/env python3
"""
Build graph context JSON files for FRINK knowledge graphs and ontologies.

Subcommands:
  build-one    Introspect one graph (knowledge_graph or ontology) and write *_global.json
  build-frink  Discover from FRINK registry, resolve YAML, run build-one (default: nde only)
  build-obo    Per-OBO ontology views over Ubergraph (IRI prefix filter)

Usage:

  python scripts/build_graph_context.py build-one --graph nde --endpoint https://frink.apps.renci.org/nde/sparql --type knowledge_graph
  python scripts/build_graph_context.py build-one --graph ubergraph --endpoint https://frink.apps.renci.org/ubergraph/sparql --type ontology
  python scripts/build_graph_context.py build-frink
  python scripts/build_graph_context.py build-obo
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests
import yaml


# ---------------------------------------------------------------------------
# Prefixes
# ---------------------------------------------------------------------------

PREFIXES_RDF = """PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX schema: <http://schema.org/>
"""

PREFIXES_OWL = """PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>
"""


# ---------------------------------------------------------------------------
# SPARQL
# ---------------------------------------------------------------------------

SPARQL_RETRIES = 3
SPARQL_RETRY_DELAYS = (2, 4, 8)


def run_sparql(endpoint: str, query: str, timeout: int = 60) -> Dict[str, Any]:
    last_exc = None
    for attempt in range(SPARQL_RETRIES + 1):
        try:
            resp = requests.post(
                endpoint,
                data=query.encode("utf-8"),
                headers={
                    "Content-Type": "application/sparql-query",
                    "Accept": "application/sparql-results+json",
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            last_exc = e
            status = e.response.status_code
            if attempt < SPARQL_RETRIES and (status == 429 or status >= 500):
                delay = SPARQL_RETRY_DELAYS[attempt]
                print(
                    f"SPARQL {status} from {endpoint}, retrying in {delay}s ({attempt + 1}/{SPARQL_RETRIES})...",
                    file=sys.stderr,
                )
                time.sleep(delay)
                continue
            raise
        except requests.exceptions.Timeout as e:
            last_exc = e
            if attempt < SPARQL_RETRIES:
                delay = SPARQL_RETRY_DELAYS[attempt]
                print(
                    f"SPARQL timeout from {endpoint}, retrying in {delay}s ({attempt + 1}/{SPARQL_RETRIES})...",
                    file=sys.stderr,
                )
                time.sleep(delay)
                continue
            raise
    raise last_exc  # unreachable if SPARQL_RETRIES >= 0


def get_bindings(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    return data.get("results", {}).get("bindings", [])


# ---------------------------------------------------------------------------
# Introspection budget (fast vs full mode, caps for timeout avoidance)
# ---------------------------------------------------------------------------

DEFAULT_SAMPLE_TRIPLES = 200_000
DEFAULT_MAX_OBJECT_PROPS = 100
DEFAULT_MAX_RESTRICTIONS = 50_000
DEFAULT_MAX_SUBPROPERTY = 50_000


@dataclass
class IntrospectBudget:
    """Caps and mode for introspection to avoid timeouts. fast = sampled + capped; full = no caps."""

    mode: str = "fast"  # "fast" | "full"
    sample_triples: int = DEFAULT_SAMPLE_TRIPLES
    max_object_props: int = DEFAULT_MAX_OBJECT_PROPS
    max_restrictions: int = DEFAULT_MAX_RESTRICTIONS
    max_subproperty: int = DEFAULT_MAX_SUBPROPERTY

    def use_sampling(self) -> bool:
        return self.mode == "fast" and self.sample_triples > 0

    def use_caps(self) -> bool:
        return self.mode == "fast"


# ---------------------------------------------------------------------------
# Graph-derived metadata (uses_ontologies, description)
# ---------------------------------------------------------------------------

# IRI prefixes that map to ontology IDs (non-OBO). OBO: we parse .../obo/PREFIX_num.
_KNOWN_ONTOLOGY_PREFIXES: List[tuple[str, str]] = [
    ("https://www.uniprot.org/taxonomy/", "UniProt"),
]


def _iri_to_ontology(iri: str) -> Optional[str]:
    """Extract an ontology ID from an IRI, or None if not a known ontology IRI."""
    if not iri or not isinstance(iri, str) or not iri.startswith("http"):
        return None
    for prefix, ont in _KNOWN_ONTOLOGY_PREFIXES:
        if iri.startswith(prefix):
            return ont
    obo = "http://purl.obolibrary.org/obo/"
    if iri.startswith(obo):
        # e.g. .../obo/MONDO_0000001 or .../obo/NCBITaxon_562
        rest = iri[len(obo) :].lstrip("/#")
        if "_" in rest:
            prefix = rest.split("_")[0]
            if prefix and prefix[0].isalpha():
                return prefix
    return None


def _collect_iris(
    classes: List[Dict[str, Any]],
    dataset_properties: Optional[Dict[str, Any]] = None,
    properties: Optional[Dict[str, Any]] = None,
    object_properties: Optional[Dict[str, Any]] = None,
) -> List[str]:
    out: List[str] = []
    for c in classes or []:
        i = c.get("iri")
        if i:
            out.append(i)
    for name, data in (dataset_properties or {}).items():
        if name.startswith("http"):
            out.append(name)
        if isinstance(data, dict):
            if data.get("iri"):
                out.append(data["iri"])
            for ex in data.get("examples") or []:
                for k in ("subject", "object"):
                    v = ex.get(k)
                    if v and isinstance(v, str) and v.startswith("http"):
                        out.append(v)
    for name, data in (properties or {}).items():
        if name.startswith("http"):
            out.append(name)
        if isinstance(data, dict):
            if data.get("iri"):
                out.append(data["iri"])
            for ex in data.get("examples") or []:
                for k in ("subject", "object"):
                    v = ex.get(k)
                    if v and isinstance(v, str) and v.startswith("http"):
                        out.append(v)
    for name, data in (object_properties or {}).items():
        if name.startswith("http"):
            out.append(name)
        if isinstance(data, dict):
            if data.get("iri"):
                out.append(data["iri"])
            for ex in data.get("examples") or []:
                for k in ("subject", "object"):
                    v = ex.get(k)
                    if v and isinstance(v, str) and v.startswith("http"):
                        out.append(v)
            for r in data.get("in_restriction") or []:
                for k in ("class_iri", "filler_iri"):
                    v = r.get(k)
                    if v and isinstance(v, str) and v.startswith("http"):
                        out.append(v)
    return out


def derive_uses_ontologies(
    classes: List[Dict[str, Any]],
    dataset_properties: Optional[Dict[str, Any]] = None,
    properties: Optional[Dict[str, Any]] = None,
    object_properties: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Infer ontology IDs from class/property/example IRIs (OBO, UniProt taxonomy, etc.)."""
    seen: set = set()
    for iri in _collect_iris(classes, dataset_properties, properties, object_properties):
        ont = _iri_to_ontology(iri)
        if ont:
            seen.add(ont)
    return sorted(seen)


def _shorten_iri(iri: str) -> str:
    """Local name: part after # or last /."""
    if not iri or not isinstance(iri, str):
        return ""
    return (iri.split("#")[-1].split("/")[-1]) or iri


def derive_description(
    is_kg: bool,
    classes: List[Dict[str, Any]],
    dataset_properties: Optional[Dict[str, Any]] = None,
    properties: Optional[Dict[str, Any]] = None,
    object_properties: Optional[Dict[str, Any]] = None,
) -> str:
    """Build a short overview from top classes and key predicates for NL→SPARQL context."""
    if is_kg and dataset_properties:
        top = (classes or [])[:5]
        types_str = ", ".join(f"{_shorten_iri(c.get('iri', ''))} ({c.get('count', 0)})" for c in top)
        preds = list(dataset_properties.items())[:8]
        pred_str = ", ".join(
            (v.get("curie") or _shorten_iri(k)) for k, v in preds if isinstance(v, dict)
        )
        return f"Dataset graph. Top types: {types_str or '—'}. Key predicates: {pred_str or '—'}."
    # ontology
    top = (classes or [])[:5]
    types_str = ", ".join(f"{_shorten_iri(c.get('iri', ''))} ({c.get('count', 0)})" for c in top)
    obj = (object_properties or {}).items()
    obj_str = ", ".join(
        (v.get("label") or _shorten_iri(k)) for k, v in list(obj)[:6] if isinstance(v, dict)
    )
    return f"Ontology. Top classes: {types_str or '—'}. Object properties: {obj_str or '—'}."


# Preferred key order: metadata first, then structural (prefixes, classes, properties).
_CONTEXT_KEY_ORDER = [
    "endpoint",
    "description",
    "uses_ontologies",
    "good_for",
    "notable_relationships",
    "example_predicates",
    "queryable_by",
    "prefixes",
    "classes",
    "dataset_properties",
    "properties",
    "object_properties",
    "identifier_info",
    "query_patterns",
]


def reorder_context(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Place metadata (description, uses_ontologies, etc.) at the top of the context dict."""
    out: Dict[str, Any] = {}
    for k in _CONTEXT_KEY_ORDER:
        if k in ctx:
            out[k] = ctx[k]
    for k in ctx:
        if k not in out:
            out[k] = ctx[k]
    return out


def load_yaml_metadata(yaml_path: Path) -> Dict[str, Any]:
    """Load {graph}.yaml and return metadata to merge into context JSON.
    Does not include uses_ontologies (that is derived from the graph).
    YAML description can override the graph-derived description.
    """
    if not yaml_path.exists():
        return {}
    with open(yaml_path, encoding="utf-8") as f:
        meta = yaml.safe_load(f) or {}
    out: Dict[str, Any] = {}
    if meta.get("description") is not None:
        out["description"] = meta["description"]
    if meta.get("good_for") is not None:
        out["good_for"] = meta["good_for"]
    if meta.get("notable_relationships") is not None:
        out["notable_relationships"] = meta["notable_relationships"]
    if meta.get("example_predicates") is not None:
        out["example_predicates"] = meta["example_predicates"]
    if meta.get("queryable_by") is not None:
        out["queryable_by"] = meta["queryable_by"]
    return out


def get_primary_class_from_yaml(yaml_path: Path, default: str) -> str:
    """Read primary_class from graph YAML if present; otherwise return default.
    Used for introspection: graphs like gene-expression-atlas-okn use Study, not schema:Dataset.
    """
    if not yaml_path.exists():
        return default
    with open(yaml_path, encoding="utf-8") as f:
        meta = yaml.safe_load(f) or {}
    return meta.get("primary_class") or default


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

def get_top_classes(
    endpoint: str,
    timeout: int,
    limit: int = 50,
    iri_prefix: Optional[str] = None,
    sample_triples: Optional[int] = None,
) -> List[Dict[str, Any]]:
    extra = f'\n  FILTER(STRSTARTS(STR(?s), "{iri_prefix}"))' if iri_prefix else ""
    if sample_triples and sample_triples > 0:
        inner = f"SELECT ?s ?class WHERE {{\n  ?s rdf:type ?class .{extra}\n}}\nLIMIT {sample_triples}"
        query = f"""{PREFIXES_RDF}
SELECT ?class (COUNT(DISTINCT ?s) AS ?count)
WHERE {{
  {{ {inner} }}
}}
GROUP BY ?class
ORDER BY DESC(?count)
LIMIT {limit}
"""
    else:
        query = f"""{PREFIXES_RDF}
SELECT ?class (COUNT(DISTINCT ?s) AS ?count)
WHERE {{
  ?s rdf:type ?class .{extra}
}}
GROUP BY ?class
ORDER BY DESC(?count)
LIMIT {limit}
"""
    data = run_sparql(endpoint, query, timeout)
    rows: List[Dict[str, Any]] = []
    for b in get_bindings(data):
        iri = b.get("class", {}).get("value")
        cnt = b.get("count", {}).get("value")
        if not iri or cnt is None:
            continue
        try:
            rows.append({"iri": iri, "count": int(cnt)})
        except ValueError:
            continue
    return rows


def derive_prefixes(namespaces: Dict[str, int]) -> Dict[str, str]:
    base: Dict[str, str] = {
        "schema": "http://schema.org/",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "owl": "http://www.w3.org/2002/07/owl#",
        "xsd": "http://www.w3.org/2001/XMLSchema#",
        "skos": "http://www.w3.org/2004/02/skos/core#",
        "dcterms": "http://purl.org/dc/terms/",
        "oboInOwl": "http://www.geneontology.org/formats/oboInOwl#",
        "obo": "http://purl.obolibrary.org/obo/",
    }
    remaining = dict(namespaces)
    out: Dict[str, str] = {}
    for p, ns in base.items():
        if ns in remaining:
            out[p] = ns
            del remaining[ns]
    for i, (ns, _) in enumerate(sorted(remaining.items(), key=lambda kv: (-kv[1], kv[0])), 1):
        out[f"ns{i}"] = ns
    return out


# ---------------------------------------------------------------------------
# Knowledge graph
# ---------------------------------------------------------------------------

# Relationship predicates (objects are entity IRIs) and key literal predicates.
KEY_PROPS_KG = {
    "http://schema.org/healthCondition": "schema:healthCondition",
    "http://schema.org/species": "schema:species",
    "http://schema.org/infectiousAgent": "schema:infectiousAgent",
    "http://schema.org/includedInDataCatalog": "schema:includedInDataCatalog",
    "http://schema.org/name": "schema:name",
    "http://schema.org/identifier": "schema:identifier",
    "http://schema.org/description": "schema:description",
}


def get_dataset_properties(
    endpoint: str,
    primary_class_iri: str,
    timeout: int,
    limit: int = 50,
    sample_triples: Optional[int] = None,
) -> List[Dict[str, Any]]:
    if sample_triples and sample_triples > 0:
        inner = f"SELECT ?s ?p ?o WHERE {{\n  ?s rdf:type <{primary_class_iri}> ;\n     ?p ?o .\n}}\nLIMIT {sample_triples}"
        query = f"""{PREFIXES_RDF}
SELECT ?p (COUNT(*) AS ?count)
WHERE {{
  {{ {inner} }}
}}
GROUP BY ?p
ORDER BY DESC(?count)
LIMIT {limit}
"""
    else:
        query = f"""{PREFIXES_RDF}
SELECT ?p (COUNT(*) AS ?count)
WHERE {{
  ?s rdf:type <{primary_class_iri}> ;
     ?p ?o .
}}
GROUP BY ?p
ORDER BY DESC(?count)
LIMIT {limit}
"""
    data = run_sparql(endpoint, query, timeout)
    out: List[Dict[str, Any]] = []
    for b in get_bindings(data):
        iri = b.get("p", {}).get("value")
        cnt = b.get("count", {}).get("value")
        if not iri or cnt is None:
            continue
        try:
            out.append({"iri": iri, "count": int(cnt)})
        except ValueError:
            continue
    return out


def _object_pattern(obj: str) -> str:
    """Pattern for object value: IRI namespace (before id) or 'literal'."""
    if not obj or not isinstance(obj, str):
        return "literal"
    s = obj.strip()
    if not (s.startswith("http://") or s.startswith("https://")):
        return "literal"
    if "#" in s:
        return s.split("#", 1)[0] + "#"
    if "/" in s:
        return s.rsplit("/", 1)[0] + "/"
    return "literal"


def _trim_examples(
    examples: List[Dict[str, str]], max_same: int = 3, max_mixed: int = 5
) -> List[Dict[str, str]]:
    """If all object values follow the same pattern and we have >= max_same, keep max_same; else keep up to max_mixed."""
    if not examples:
        return examples
    patterns = {_object_pattern(ex.get("object") or "") for ex in examples}
    if len(examples) >= max_same and len(patterns) == 1:
        return examples[:max_same]
    return examples[:max_mixed]


def get_example_triples(
    endpoint: str,
    primary_class_iri: str,
    predicate_iri: str,
    timeout: int,
    limit: int = 5,
) -> List[Dict[str, str]]:
    query = f"""{PREFIXES_RDF}
SELECT ?s ?o
WHERE {{
  ?s rdf:type <{primary_class_iri}> ;
     <{predicate_iri}> ?o .
}}
LIMIT {limit}
"""
    data = run_sparql(endpoint, query, timeout)
    out: List[Dict[str, str]] = []
    for b in get_bindings(data):
        s = b.get("s", {}).get("value")
        o = b.get("o", {}).get("value")
        if not s or o is None:
            continue
        out.append({"subject": s, "object": o})
    return _trim_examples(out)


def build_context_kg(
    endpoint: str,
    graph: str,
    primary_class_iri: str,
    timeout: int,
    budget: Optional[IntrospectBudget] = None,
) -> Dict[str, Any]:
    b = budget or IntrospectBudget()
    sample = b.sample_triples if b.use_sampling() else None
    classes = get_top_classes(endpoint, timeout, limit=50, sample_triples=sample)
    props = get_dataset_properties(
        endpoint, primary_class_iri, timeout, limit=50, sample_triples=sample
    )

    namespaces: Dict[str, int] = defaultdict(int)
    props_with_examples: Dict[str, Any] = {}

    for p in props:
        iri = p["iri"]
        entry: Dict[str, Any] = {"iri": iri, "count": p["count"]}
        sep = max(iri.rfind("#"), iri.rfind("/"))
        if sep != -1:
            ns = iri[: sep + 1]
            namespaces[ns] += 1
        curie = KEY_PROPS_KG.get(iri)
        if curie:
            entry["curie"] = curie
            entry["examples"] = get_example_triples(endpoint, primary_class_iri, iri, timeout)
        props_with_examples[iri] = entry

    prefixes = derive_prefixes(namespaces)
    uses_ontologies = derive_uses_ontologies(classes, dataset_properties=props_with_examples)
    description = derive_description(True, classes, dataset_properties=props_with_examples)
    return {
        "endpoint": endpoint,
        "description": description,
        "uses_ontologies": uses_ontologies,
        "prefixes": prefixes,
        "classes": classes,
        "dataset_properties": props_with_examples,
    }


# ---------------------------------------------------------------------------
# Ontology
# ---------------------------------------------------------------------------

def get_top_predicates(
    endpoint: str,
    timeout: int,
    limit: int = 100,
    iri_prefix: Optional[str] = None,
    sample_triples: Optional[int] = None,
) -> List[Dict[str, Any]]:
    extra = f'\n  FILTER(STRSTARTS(STR(?s), "{iri_prefix}"))' if iri_prefix else ""
    if sample_triples and sample_triples > 0:
        inner = f"SELECT ?s ?p ?o WHERE {{\n  ?s ?p ?o .{extra}\n}}\nLIMIT {sample_triples}"
        query = f"""{PREFIXES_RDF}
SELECT ?p (COUNT(*) AS ?count)
WHERE {{
  {{ {inner} }}
}}
GROUP BY ?p
ORDER BY DESC(?count)
LIMIT {limit}
"""
    else:
        query = f"""{PREFIXES_RDF}
SELECT ?p (COUNT(*) AS ?count)
WHERE {{
  ?s ?p ?o .{extra}
}}
GROUP BY ?p
ORDER BY DESC(?count)
LIMIT {limit}
"""
    data = run_sparql(endpoint, query, timeout)
    out: List[Dict[str, Any]] = []
    for b in get_bindings(data):
        iri = b.get("p", {}).get("value")
        cnt = b.get("count", {}).get("value")
        if not iri or cnt is None:
            continue
        try:
            out.append({"iri": iri, "count": int(cnt)})
        except ValueError:
            continue
    return out


def get_examples_for_predicate(
    endpoint: str,
    predicate_iri: str,
    timeout: int,
    limit: int = 5,
    iri_prefix: Optional[str] = None,
) -> List[Dict[str, str]]:
    extra = f'\n  FILTER(STRSTARTS(STR(?s), "{iri_prefix}"))' if iri_prefix else ""
    query = f"""{PREFIXES_RDF}
SELECT ?s ?o
WHERE {{ ?s <{predicate_iri}> ?o .{extra} }}
LIMIT {limit}
"""
    data = run_sparql(endpoint, query, timeout)
    out: List[Dict[str, str]] = []
    for b in get_bindings(data):
        s = b.get("s", {}).get("value")
        o = b.get("o", {}).get("value")
        if not s or o is None:
            continue
        out.append({"subject": s, "object": o})
    return _trim_examples(out)


def get_object_properties_and_restrictions(
    endpoint: str,
    timeout: int,
    iri_prefix: Optional[str] = None,
    max_restrictions: Optional[int] = None,
    max_subproperty: Optional[int] = None,
) -> tuple[
    List[str],
    List[tuple[str, str, str]],
    Dict[str, str],
]:
    """Returns (list of property IRIs, list of (class_iri, prop_iri, filler_iri), prop_iri -> rdfs:label)."""
    seen: set = set()
    in_restriction: List[tuple[str, str, str]] = []
    prop_labels: Dict[str, str] = {}
    class_filter = f'\n  FILTER(STRSTARTS(STR(?class), "{iri_prefix}"))' if iri_prefix else ""
    cap_r = max_restrictions
    cap_s = max_subproperty
    lim_r = f"\nLIMIT {cap_r // 4}" if cap_r and cap_r > 0 else ""
    lim_s = f"\nLIMIT {cap_s}" if cap_s and cap_s > 0 else ""

    # 1) owl:ObjectProperty
    q1 = f"""{PREFIXES_OWL}
SELECT ?p ?l
WHERE {{
  ?p rdf:type owl:ObjectProperty .
  OPTIONAL {{ ?p rdfs:label ?l . }}
}}
"""
    for b in get_bindings(run_sparql(endpoint, q1, timeout)):
        iri = b.get("p", {}).get("value")
        if iri:
            seen.add(iri)
        label = b.get("l", {}).get("value") if b.get("l") else None
        if iri and label:
            prop_labels[iri] = label

    # 2) owl:onProperty in rdfs:subClassOf [ owl:someValuesFrom / owl:allValuesFrom ]
    q2 = f"""{PREFIXES_OWL}
SELECT ?class ?p ?filler
WHERE {{
  ?class rdfs:subClassOf [ owl:onProperty ?p ; owl:someValuesFrom ?filler ] .{class_filter}
}}{lim_r}"""
    for b in get_bindings(run_sparql(endpoint, q2, timeout)):
        c = b.get("class", {}).get("value")
        p = b.get("p", {}).get("value")
        f = b.get("filler", {}).get("value")
        if c and p and f:
            seen.add(p)
            in_restriction.append((c, p, f))

    q2b = f"""{PREFIXES_OWL}
SELECT ?class ?p ?filler
WHERE {{
  ?class rdfs:subClassOf [ owl:onProperty ?p ; owl:allValuesFrom ?filler ] .{class_filter}
}}{lim_r}"""
    for b in get_bindings(run_sparql(endpoint, q2b, timeout)):
        c = b.get("class", {}).get("value")
        p = b.get("p", {}).get("value")
        f = b.get("filler", {}).get("value")
        if c and p and f:
            seen.add(p)
            in_restriction.append((c, p, f))

    # 3) owl:equivalentClass [ owl:onProperty ; owl:someValuesFrom / owl:allValuesFrom ]
    q3 = f"""{PREFIXES_OWL}
SELECT ?class ?p ?filler
WHERE {{
  ?class owl:equivalentClass [ owl:onProperty ?p ; owl:someValuesFrom ?filler ] .{class_filter}
}}{lim_r}"""
    for b in get_bindings(run_sparql(endpoint, q3, timeout)):
        c = b.get("class", {}).get("value")
        p = b.get("p", {}).get("value")
        f = b.get("filler", {}).get("value")
        if c and p and f:
            seen.add(p)
            in_restriction.append((c, p, f))

    q3b = f"""{PREFIXES_OWL}
SELECT ?class ?p ?filler
WHERE {{
  ?class owl:equivalentClass [ owl:onProperty ?p ; owl:allValuesFrom ?filler ] .{class_filter}
}}{lim_r}"""
    for b in get_bindings(run_sparql(endpoint, q3b, timeout)):
        c = b.get("class", {}).get("value")
        p = b.get("p", {}).get("value")
        f = b.get("filler", {}).get("value")
        if c and p and f:
            seen.add(p)
            in_restriction.append((c, p, f))

    # 4) rdfs:subPropertyOf (property hierarchy)
    q4 = f"""{PREFIXES_OWL}
SELECT ?sub ?super
WHERE {{ ?sub rdfs:subPropertyOf ?super . }}{lim_s}
"""
    for b in get_bindings(run_sparql(endpoint, q4, timeout)):
        sub = b.get("sub", {}).get("value")
        super_ = b.get("super", {}).get("value")
        if sub:
            seen.add(sub)
        if super_:
            seen.add(super_)

    return (list(seen), in_restriction, prop_labels)


def build_context_ontology(
    endpoint: str,
    graph: str,
    timeout: int,
    iri_prefix: Optional[str] = None,
    budget: Optional[IntrospectBudget] = None,
) -> Dict[str, Any]:
    b = budget or IntrospectBudget()
    sample = b.sample_triples if b.use_sampling() else None
    max_r = b.max_restrictions if b.use_caps() else None
    max_s = b.max_subproperty if b.use_caps() else None
    max_op = b.max_object_props if b.use_caps() else None

    classes = get_top_classes(
        endpoint, timeout, limit=50, iri_prefix=iri_prefix, sample_triples=sample
    )
    top_preds = get_top_predicates(
        endpoint, timeout, limit=100, iri_prefix=iri_prefix, sample_triples=sample
    )
    obj_iris, in_restriction, prop_labels = get_object_properties_and_restrictions(
        endpoint, timeout, iri_prefix=iri_prefix,
        max_restrictions=max_r, max_subproperty=max_s,
    )

    namespaces: Dict[str, int] = defaultdict(int)
    for p in top_preds:
        iri = p["iri"]
        sep = max(iri.rfind("#"), iri.rfind("/"))
        if sep != -1:
            namespaces[iri[: sep + 1]] += 1
    for iri in obj_iris:
        sep = max(iri.rfind("#"), iri.rfind("/"))
        if sep != -1:
            namespaces[iri[: sep + 1]] += 1

    prefixes = derive_prefixes(namespaces)

    # properties: top predicates; examples for rdfs:label, oboInOwl:hasExactSynonym
    LABEL_IRI = "http://www.w3.org/2000/01/rdf-schema#label"
    HAS_EXACT_SYN = "http://www.geneontology.org/formats/oboInOwl#hasExactSynonym"

    properties: Dict[str, Any] = {}
    for p in top_preds:
        iri = p["iri"]
        entry: Dict[str, Any] = {"iri": iri, "count": p["count"]}
        if iri == LABEL_IRI or iri == HAS_EXACT_SYN:
            entry["examples"] = get_examples_for_predicate(
                endpoint, iri, timeout, iri_prefix=iri_prefix
            )
        properties[iri] = entry

    # object_properties: in_restriction (class, filler) and examples (s, o)
    # Rank props by restriction count; enrich with examples only for top max_object_props
    object_properties: Dict[str, Any] = {}
    by_prop: Dict[str, List[tuple[str, str]]] = defaultdict(list)
    for (c, prop, f) in in_restriction:
        by_prop[prop].append((c, f))

    if max_op and max_op > 0:
        prop_order = sorted(
            obj_iris,
            key=lambda p: len(by_prop.get(p, [])),
            reverse=True,
        )[:max_op]
        props_to_enrich: set = set(prop_order)
    else:
        props_to_enrich = set(obj_iris)

    for prop_iri in obj_iris:
        rec: Dict[str, Any] = {
            "iri": prop_iri,
            "label": prop_labels.get(prop_iri),
        }
        restr = by_prop.get(prop_iri, [])
        if restr:
            rec["in_restriction"] = [{"class_iri": c, "filler_iri": f} for c, f in restr[:50]]
        if prop_iri in props_to_enrich:
            ex = get_examples_for_predicate(
                endpoint, prop_iri, timeout, iri_prefix=iri_prefix
            )
            if ex:
                rec["examples"] = ex
        object_properties[prop_iri] = rec

    obj = object_properties if object_properties else None
    uses_ontologies = derive_uses_ontologies(classes, properties=properties, object_properties=obj)
    description = derive_description(False, classes, properties=properties, object_properties=obj)
    return {
        "endpoint": endpoint,
        "description": description,
        "uses_ontologies": uses_ontologies,
        "prefixes": prefixes,
        "classes": classes,
        "properties": properties,
        "object_properties": obj,
        "identifier_info": {"predicates": [LABEL_IRI, "http://www.geneontology.org/formats/oboInOwl#id", "http://purl.obolibrary.org/obo/IAO_0000118"]},
        "query_patterns": [
            {"pattern": "Find by identifier", "description": "Look up entity by OBO id or IAO_0000118."},
            {"pattern": "Resolve by label", "description": "Find entity by rdfs:label or synonym."},
        ],
    }


# ---------------------------------------------------------------------------
# build-one
# ---------------------------------------------------------------------------

DEFAULT_PRIMARY_CLASS = "http://schema.org/Dataset"
DEFAULT_OUTPUT_DIR = Path("web-v2/context/graphs")


def cmd_build_one(
    graph: str,
    endpoint: str,
    build_type: str,
    output: Path,
    primary_class: str,
    timeout: int,
    iri_prefix: Optional[str] = None,
    budget: Optional[IntrospectBudget] = None,
) -> int:
    # Override primary_class from graph YAML if present (e.g. gene-expression-atlas-okn uses Study)
    yaml_path = output.parent / f"{graph}.yaml"
    effective_primary = get_primary_class_from_yaml(yaml_path, primary_class)
    if effective_primary != primary_class:
        print(f"Using primary_class from {graph}.yaml: {effective_primary}", file=sys.stderr)

    effective_timeout = max(HEAVY_GRAPH_MIN_TIMEOUT, timeout) if graph in HEAVY_GRAPHS else timeout
    if build_type == "knowledge_graph":
        ctx = build_context_kg(
            endpoint, graph, effective_primary, effective_timeout, budget=budget
        )
    elif build_type == "ontology":
        ctx = build_context_ontology(
            endpoint, graph, effective_timeout, iri_prefix=iri_prefix, budget=budget
        )
    else:
        raise SystemExit(f"Unknown --type: {build_type}")

    # Merge metadata from co-located {graph}.yaml when present (description, good_for, etc.).
    # uses_ontologies is not merged from YAML; it is derived from the graph.
    yaml_path = output.parent / f"{graph}.yaml"
    for k, v in load_yaml_metadata(yaml_path).items():
        ctx[k] = v

    ctx = reorder_context(ctx)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(ctx, indent=2), encoding="utf-8")
    print(f"Context written to {output.resolve()}")
    return 0


# ---------------------------------------------------------------------------
# build-frink (discover from FRINK registry, run build-one)
# ---------------------------------------------------------------------------

REGISTRY_URL = "https://frink.renci.org/registry/"
# SPARQL endpoints follow https://frink.apps.renci.org/{shortname}/sparql (from registry kgs pages)
FRINK_SPARQL_BASE = "https://frink.apps.renci.org"
# Shortnames treated as ontology (build_type=ontology); others as knowledge_graph
ONTOLOGY_GRAPHS: frozenset = frozenset({"ubergraph"})
# Graphs that need longer SPARQL timeouts (e.g. very large or slow endpoints)
HEAVY_GRAPHS: frozenset = frozenset({"ubergraph", "wikidata"})
HEAVY_GRAPH_MIN_TIMEOUT: int = 300
# build-frink excludes these by default (heavy/slow; ubergraph/wikidata have hand-maintained or separate handling)
EXCLUDED_GRAPHS: frozenset = frozenset({"ubergraph", "wikidata"})


def fetch_registry(registry_url: str, timeout: int) -> List[tuple[str, str]]:
    """Fetch FRINK registry HTML and return [(shortname, endpoint), ...].
    Endpoint is https://frink.apps.renci.org/{shortname}/sparql per
    https://frink.renci.org/registry/kgs/{shortname}/.
    """
    resp = requests.get(registry_url, timeout=timeout)
    resp.raise_for_status()
    html = resp.text
    # Extract shortnames from links like href="kgs/nde/" or href='kgs/ubergraph/'
    # Also match markdown-style links like ](kgs/gene-expression-atlas-okn/)
    # Use more permissive pattern: match any path segment after kgs/
    seen: set = set()
    out: List[tuple[str, str]] = []
    # Pattern 1: href="kgs/..." or href='kgs/...' - more permissive character class
    for m in re.finditer(r'href=["\']kgs/([^/"\'\\s]+)/', html, re.IGNORECASE):
        s = m.group(1).strip()
        if s and s not in seen:
            seen.add(s)
            out.append((s, f"{FRINK_SPARQL_BASE}/{s}/sparql"))
    # Pattern 2: markdown-style ](kgs/.../) links (for rendered markdown tables)
    for m in re.finditer(r'\]\(kgs/([^/)]+)/', html):
        s = m.group(1).strip()
        if s and s not in seen:
            seen.add(s)
            out.append((s, f"{FRINK_SPARQL_BASE}/{s}/sparql"))
    # Pattern 3: More permissive - any occurrence of kgs/SHORTNAME/ where SHORTNAME can have hyphens
    # This catches cases where the HTML structure might be different
    for m in re.finditer(r'kgs/([a-zA-Z0-9_-]+)/', html):
        s = m.group(1).strip()
        if s and s not in seen and len(s) > 1:  # Filter out single char matches
            seen.add(s)
            out.append((s, f"{FRINK_SPARQL_BASE}/{s}/sparql"))
    return out


def _fallback_from_yaml(yaml_dir: Path) -> List[tuple[str, str, str]]:
    """Fallback: read nde.yaml, ubergraph.yaml, gene-expression-atlas-okn.yaml for (id, endpoint, type) when registry is unavailable."""
    graphs: List[tuple[str, str, str]] = []
    for p in [yaml_dir / "nde.yaml", yaml_dir / "ubergraph.yaml", yaml_dir / "gene-expression-atlas-okn.yaml"]:
        if not p.exists():
            continue
        with open(p, encoding="utf-8") as f:
            meta = yaml.safe_load(f) or {}
        gid = meta.get("id")
        ep = meta.get("endpoint")
        gtype = meta.get("graph_type") or ("ontology" if gid == "ubergraph" else "knowledge_graph")
        if gid and ep:
            graphs.append((gid, ep, gtype))
    return graphs


def cmd_build_frink(
    output_dir: Path,
    timeout: int,
    graphs_allowlist: List[str],
    registry_url: str,
    budget: Optional[IntrospectBudget] = None,
) -> int:
    # Discover from FRINK registry (https://frink.renci.org/registry/)
    try:
        registry_list = fetch_registry(registry_url, timeout)
    except Exception as e:
        # Fallback to YAML when registry is unavailable
        yaml_dir = Path("web-v2/context/graphs")
        if yaml_dir.is_dir():
            graphs = _fallback_from_yaml(yaml_dir)
            if graphs:
                graphs = [(g, ep, gt) for g, ep, gt in graphs if g.lower() not in EXCLUDED_GRAPHS]
                print(f"Registry unavailable ({e}), using YAML fallback (nde, ubergraph, gene-expression-atlas-okn)", file=sys.stderr)
                for gid, ep, gtype in graphs:
                    out = output_dir / f"{gid}_global.json"
                    try:
                        cmd_build_one(
                            gid, ep, gtype, out, DEFAULT_PRIMARY_CLASS, timeout,
                            budget=budget,
                        )
                    except requests.exceptions.HTTPError as he:
                        status = he.response.status_code
                        others = [g for g, _, _ in graphs if g != gid]
                        hint = f" Omit it with: --graphs {' '.join(others)}." if others else ""
                        print(
                            f"Warning: Skipping {gid}: {ep} returned {status}.{hint}",
                            file=sys.stderr,
                        )
                        continue
                    except requests.exceptions.Timeout:
                        others = [g for g, _, _ in graphs if g != gid]
                        hint = f" Omit it with: --graphs {' '.join(others)}." if others else ""
                        print(
                            f"Warning: Skipping {gid}: {ep} SPARQL read timed out.{hint}",
                            file=sys.stderr,
                        )
                        continue
                return 0
        raise SystemExit(f"Registry unavailable: {e}") from e

    # Filter to allowlist when --graphs is non-empty; empty means all from registry
    allow = {g.strip().lower() for g in graphs_allowlist if g.strip()}
    if allow:
        registry_list = [(s, ep) for s, ep in registry_list if s.lower() in allow]
    # Always exclude ubergraph and wikidata (heavy/slow; use build-one or hand-maintained for those)
    registry_list = [(s, ep) for s, ep in registry_list if s.lower() not in EXCLUDED_GRAPHS]
    if not registry_list:
        raise SystemExit("No graphs to build (registry returned none, none matched --graphs, or all excluded)")

    for shortname, endpoint in registry_list:
        gtype = "ontology" if shortname in ONTOLOGY_GRAPHS else "knowledge_graph"
        out = output_dir / f"{shortname}_global.json"
        try:
            cmd_build_one(
                shortname, endpoint, gtype, out, DEFAULT_PRIMARY_CLASS, timeout,
                budget=budget,
            )
        except requests.exceptions.HTTPError as he:
            status = he.response.status_code
            others = [g for g, _ in registry_list if g != shortname]
            hint = f" Omit it with: --graphs {' '.join(others)}." if others else ""
            print(
                f"Warning: Skipping {shortname}: {endpoint} returned {status}.{hint}",
                file=sys.stderr,
            )
            continue
        except requests.exceptions.Timeout:
            others = [g for g, _ in registry_list if g != shortname]
            hint = f" Omit it with: --graphs {' '.join(others)}." if others else ""
            print(
                f"Warning: Skipping {shortname}: {endpoint} SPARQL read timed out.{hint}",
                file=sys.stderr,
            )
            continue
    return 0


# ---------------------------------------------------------------------------
# build-obo (stub: Ubergraph + IRI prefix filter; write obo-{id}_global.json)
# ---------------------------------------------------------------------------

def cmd_build_obo(
    obo_ids: List[str],
    endpoint: str,
    output_dir: Path,
    timeout: int,
    budget: Optional[IntrospectBudget] = None,
) -> int:
    """Per-OBO ontology views over Ubergraph: IRI prefix filter per OBO, write obo-{id}_global.json."""
    obo_base = "http://purl.obolibrary.org/obo/"
    for obo_id in obo_ids:
        iri_prefix = f"{obo_base}{obo_id}_"
        graph = f"obo-{obo_id}"
        out = output_dir / f"{graph}_global.json"
        cmd_build_one(
            graph=graph,
            endpoint=endpoint,
            build_type="ontology",
            output=out,
            primary_class="http://schema.org/Dataset",
            timeout=timeout,
            iri_prefix=iri_prefix,
            budget=budget,
        )
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="build_graph_context", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)

    # build-one
    p1 = sp.add_parser("build-one", help="Introspect one graph and write context JSON")
    p1.add_argument("--graph", required=True, help="Graph shortname (e.g. nde, ubergraph)")
    p1.add_argument("--endpoint", required=True, help="SPARQL endpoint URL")
    p1.add_argument("--type", choices=("knowledge_graph", "ontology"), required=True, help="Graph type")
    p1.add_argument("--output", type=Path, default=None, help=f"Output path (default: {{web-v2/context/graphs,{{graph}}_global.json}})")
    p1.add_argument("--primary-class", default=DEFAULT_PRIMARY_CLASS, help=f"Primary class IRI for knowledge_graph (default: {DEFAULT_PRIMARY_CLASS})")
    p1.add_argument("--iri-prefix", default=None, help="For ontology: restrict to entities with IRIs starting with this (e.g. http://purl.obolibrary.org/obo/MONDO_)")
    p1.add_argument("--timeout", type=int, default=60)
    p1.add_argument("--mode", choices=("fast", "full"), default="fast", help="fast: sampled queries + caps (default). full: no caps.")
    p1.add_argument("--sample-triples", type=int, default=DEFAULT_SAMPLE_TRIPLES, metavar="N", help="Cap triples scanned when sampling (fast mode). Default: %(default)s")
    p1.add_argument("--max-object-props", type=int, default=DEFAULT_MAX_OBJECT_PROPS, metavar="N", help="Max object properties to enrich with examples (fast mode). Default: %(default)s")
    p1.add_argument("--max-restrictions", type=int, default=DEFAULT_MAX_RESTRICTIONS, metavar="N", help="Cap restriction rows per ontology query (fast mode). Default: %(default)s")
    p1.add_argument("--max-subproperty", type=int, default=DEFAULT_MAX_SUBPROPERTY, metavar="N", help="Cap subproperty rows (fast mode). Default: %(default)s")

    # build-frink
    p2 = sp.add_parser("build-frink", help="Discover from FRINK registry, run build-one for each graph")
    p2.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for *_global.json")
    p2.add_argument("--graphs", nargs="*", default=[], metavar="SHORTNAME", help="Graph shortnames to build. Default: all from registry except ubergraph and wikidata. e.g. --graphs nde to build only nde.")
    p2.add_argument("--registry-url", default=REGISTRY_URL, help="FRINK registry URL (default: %(default)s)")
    p2.add_argument("--timeout", type=int, default=60)
    p2.add_argument("--mode", choices=("fast", "full"), default="fast", help="fast: sampled + caps (default). full: no caps.")
    p2.add_argument("--sample-triples", type=int, default=DEFAULT_SAMPLE_TRIPLES, metavar="N")
    p2.add_argument("--max-object-props", type=int, default=DEFAULT_MAX_OBJECT_PROPS, metavar="N")
    p2.add_argument("--max-restrictions", type=int, default=DEFAULT_MAX_RESTRICTIONS, metavar="N")
    p2.add_argument("--max-subproperty", type=int, default=DEFAULT_MAX_SUBPROPERTY, metavar="N")

    # build-obo
    p3 = sp.add_parser("build-obo", help="Per-OBO ontology views over Ubergraph")
    p3.add_argument("--obo", nargs="+", default=["MONDO", "GO", "HP"], help="OBO ids from provides_ontologies")
    p3.add_argument("--endpoint", default="https://frink.apps.renci.org/ubergraph/sparql")
    p3.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p3.add_argument("--timeout", type=int, default=60)
    p3.add_argument("--mode", choices=("fast", "full"), default="fast")
    p3.add_argument("--sample-triples", type=int, default=DEFAULT_SAMPLE_TRIPLES, metavar="N")
    p3.add_argument("--max-object-props", type=int, default=DEFAULT_MAX_OBJECT_PROPS, metavar="N")
    p3.add_argument("--max-restrictions", type=int, default=DEFAULT_MAX_RESTRICTIONS, metavar="N")
    p3.add_argument("--max-subproperty", type=int, default=DEFAULT_MAX_SUBPROPERTY, metavar="N")

    ns = ap.parse_args(argv)

    if ns.cmd == "build-one":
        out = ns.output
        if out is None:
            out = DEFAULT_OUTPUT_DIR / f"{ns.graph}_global.json"
        budget = IntrospectBudget(
            mode=ns.mode,
            sample_triples=ns.sample_triples,
            max_object_props=ns.max_object_props,
            max_restrictions=ns.max_restrictions,
            max_subproperty=ns.max_subproperty,
        )
        return cmd_build_one(
            ns.graph, ns.endpoint, ns.type, out, ns.primary_class, ns.timeout,
            iri_prefix=ns.iri_prefix,
            budget=budget,
        )
    if ns.cmd == "build-frink":
        return cmd_build_frink(
            ns.output_dir, ns.timeout, ns.graphs, ns.registry_url,
            budget=_budget_from_ns(ns),
        )
    if ns.cmd == "build-obo":
        return cmd_build_obo(
            ns.obo, ns.endpoint, ns.output_dir, ns.timeout,
            budget=_budget_from_ns(ns),
        )
    return 1


def _budget_from_ns(ns: argparse.Namespace) -> IntrospectBudget:
    return IntrospectBudget(
        mode=getattr(ns, "mode", "fast"),
        sample_triples=getattr(ns, "sample_triples", DEFAULT_SAMPLE_TRIPLES),
        max_object_props=getattr(ns, "max_object_props", DEFAULT_MAX_OBJECT_PROPS),
        max_restrictions=getattr(ns, "max_restrictions", DEFAULT_MAX_RESTRICTIONS),
        max_subproperty=getattr(ns, "max_subproperty", DEFAULT_MAX_SUBPROPERTY),
    )


if __name__ == "__main__":
    raise SystemExit(main())
