from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

import yaml


CONFIG_ENV_VAR = "WOBD_CONFIG_PATH"


class EndpointConfig(TypedDict):
    id: str
    label: str
    sparql_url: str


@dataclass
class UIConfig:
    show_generated_sparql: bool = True
    show_provenance: bool = True
    max_rows: int = 200


@dataclass
class LLMConfig:
    provider: str = "openai"
    model: str = "gpt-4.1"
    temperature: float = 0.1


@dataclass
class AppConfig:
    raw: Dict[str, Any]
    nde_endpoints: List[EndpointConfig]
    frink_endpoints: List[EndpointConfig]
    gene_expr: Dict[str, Any]
    ui: UIConfig
    llm: LLMConfig


class ConfigError(RuntimeError):
    """Raised when the WOBD web configuration is missing or invalid."""


def _default_config_path() -> Path:
    """
    Determine the default local config path.

    This is resolved relative to the `web/` directory so it works both when run
    via `streamlit run web/app.py` and when imported as a package.
    """

    here = Path(__file__).resolve()
    web_root = here.parents[1]  # .../web
    return web_root / "configs" / "demo.local.yaml"


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ConfigError(
            f"WOBD config file not found at '{path}'. "
            "Set WOBD_CONFIG_PATH to a valid YAML config."
        )
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Failed to parse config YAML at '{path}': {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"Config at '{path}' must be a YAML mapping/object.")
    return data


def _coerce_endpoints(section: Any, key: str) -> List[EndpointConfig]:
    if not section:
        return []

    endpoints = section.get("endpoints")
    if endpoints is None:
        return []
    if not isinstance(endpoints, list):
        raise ConfigError(f"'{key}.endpoints' must be a list.")

    coerced: List[EndpointConfig] = []
    for idx, item in enumerate(endpoints):
        if not isinstance(item, dict):
            raise ConfigError(f"Endpoint #{idx} in '{key}.endpoints' must be a mapping.")
        try:
            eid = str(item["id"])
            label = str(item.get("label") or eid)
            url = str(item["sparql_url"])
        except KeyError as exc:
            raise ConfigError(
                f"Endpoint #{idx} in '{key}.endpoints' is missing required key: {exc}."
            ) from exc
        if not url:
            raise ConfigError(f"Endpoint '{eid}' in '{key}.endpoints' has empty sparql_url.")
        coerced.append(EndpointConfig(id=eid, label=label, sparql_url=url))
    return coerced


def _coerce_ui(section: Any) -> UIConfig:
    if not isinstance(section, dict):
        return UIConfig()
    return UIConfig(
        show_generated_sparql=bool(section.get("show_generated_sparql", True)),
        show_provenance=bool(section.get("show_provenance", True)),
        max_rows=int(section.get("max_rows", 200)),
    )


def _coerce_llm(section: Any) -> LLMConfig:
    if not isinstance(section, dict):
        return LLMConfig()
    return LLMConfig(
        provider=str(section.get("provider", "openai")),
        model=str(section.get("model", "gpt-4.1")),
        temperature=float(section.get("temperature", 0.1)),
    )


_CACHED_CONFIG: Optional[AppConfig] = None


def load_config(force_reload: bool = False) -> AppConfig:
    """
    Load and validate the WOBD web configuration.

    Precedence:
    1. Use path from WOBD_CONFIG_PATH if set.
    2. Otherwise fall back to `web/configs/demo.local.yaml`.
    """

    global _CACHED_CONFIG
    if _CACHED_CONFIG is not None and not force_reload:
        return _CACHED_CONFIG

    env_path = os.environ.get(CONFIG_ENV_VAR)
    path = Path(env_path).expanduser() if env_path else _default_config_path()

    raw = _load_yaml(path)
    sources = raw.get("sources") or {}
    if not isinstance(sources, dict):
        raise ConfigError("'sources' section must be a mapping/object.")

    nde = sources.get("nde") or {}
    nde_endpoints = _coerce_endpoints(nde, "sources.nde")
    if not nde_endpoints:
        raise ConfigError(
            "No NDE endpoints configured. "
            "Please define 'sources.nde.endpoints[*].sparql_url' in the config."
        )

    frink = sources.get("frink") or {}
    frink_endpoints = _coerce_endpoints(frink, "sources.frink")

    gene_expr = sources.get("gene_expression") or {}
    if not isinstance(gene_expr, dict):
        raise ConfigError("'sources.gene_expression' must be a mapping/object if present.")

    ui_cfg = _coerce_ui(raw.get("ui") or {})
    llm_cfg = _coerce_llm(raw.get("llm") or {})

    _CACHED_CONFIG = AppConfig(
        raw=raw,
        nde_endpoints=nde_endpoints,
        frink_endpoints=frink_endpoints,
        gene_expr=gene_expr,
        ui=ui_cfg,
        llm=llm_cfg,
    )
    return _CACHED_CONFIG


def get_nde_endpoints() -> List[EndpointConfig]:
    """Convenience accessor for NDE endpoints."""

    return load_config().nde_endpoints


def get_frink_endpoints_or_none() -> List[EndpointConfig]:
    """Convenience accessor for FRINK endpoints (may be empty)."""

    return load_config().frink_endpoints


def get_gene_expr_config() -> Dict[str, Any]:
    """Return the raw gene expression configuration mapping (may be empty)."""

    return load_config().gene_expr


__all__ = [
    "AppConfig",
    "UIConfig",
    "LLMConfig",
    "EndpointConfig",
    "ConfigError",
    "load_config",
    "get_nde_endpoints",
    "get_frink_endpoints_or_none",
    "get_gene_expr_config",
]

