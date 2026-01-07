from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from wobd_web.config import EndpointConfig, AppConfig, load_config


@dataclass
class Endpoint:
    """Resolved endpoint with id, label and SPARQL URL."""

    id: str
    label: str
    sparql_url: str


def _to_endpoint(cfg: EndpointConfig) -> Endpoint:
    return Endpoint(id=cfg["id"], label=cfg["label"], sparql_url=cfg["sparql_url"])


def get_config() -> AppConfig:
    """Small wrapper for ease of import from other modules."""

    return load_config()


def get_nde_endpoints() -> List[Endpoint]:
    cfg = get_config()
    return [_to_endpoint(e) for e in cfg.nde_endpoints]


def get_default_nde_endpoint() -> Endpoint:
    endpoints = get_nde_endpoints()
    if not endpoints:
        raise RuntimeError("No NDE endpoints available from configuration.")
    return endpoints[0]


def get_frink_endpoints() -> List[Endpoint]:
    cfg = get_config()
    return [_to_endpoint(e) for e in cfg.frink_endpoints]


def get_default_frink_endpoint() -> Optional[Endpoint]:
    endpoints = get_frink_endpoints()
    return endpoints[0] if endpoints else None


def get_gene_expr_endpoint_for_mode(mode: str) -> Optional[Endpoint]:
    """
    Return the first configured gene-expression endpoint for the given mode.

    Modes are free-form strings for now (e.g., "sparql", "web_mcp", "local").
    Only "sparql" will actually resolve to an HTTP SPARQL endpoint; the others
    are handled by their respective adapters.
    """

    cfg = get_config()
    ge = cfg.gene_expr
    section = ge.get(mode) if isinstance(ge, dict) else None
    if not isinstance(section, dict):
        return None

    endpoints = section.get("endpoints") or []
    if not isinstance(endpoints, list) or not endpoints:
        return None

    first = endpoints[0]
    if not isinstance(first, dict):
        return None
    # Reuse Endpoint construction semantics; minimal validation for now.
    try:
        return Endpoint(
            id=str(first["id"]),
            label=str(first.get("label") or first["id"]),
            sparql_url=str(first["sparql_url"]),
        )
    except KeyError:
        return None


def get_wikidata_endpoints() -> List[Endpoint]:
    """Get all configured Wikidata endpoints."""
    from wobd_web.config import get_wikidata_endpoints_or_none
    
    endpoints = get_wikidata_endpoints_or_none()
    return [_to_endpoint(e) for e in endpoints]


def get_default_wikidata_endpoint() -> Optional[Endpoint]:
    """Return the first configured Wikidata endpoint, or None if not configured."""
    endpoints = get_wikidata_endpoints()
    return endpoints[0] if endpoints else None


__all__ = [
    "Endpoint",
    "get_config",
    "get_nde_endpoints",
    "get_default_nde_endpoint",
    "get_frink_endpoints",
    "get_default_frink_endpoint",
    "get_wikidata_endpoints",
    "get_default_wikidata_endpoint",
    "get_gene_expr_endpoint_for_mode",
]

