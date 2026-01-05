from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from wobd_web.config import AppConfig, load_config
from wobd_web.models import QueryPlan, SourceAction


GeneExprMode = Literal["off", "sparql", "web_mcp", "local"]


@dataclass
class RouterOptions:
    include_frink: bool
    include_gene_expr: bool
    gene_expr_mode: GeneExprMode


def _default_gene_expr_mode(cfg: AppConfig) -> GeneExprMode:
    ge = cfg.gene_expr
    if isinstance(ge, dict):
        mode = ge.get("default_mode", "sparql")
        if mode in {"sparql", "web_mcp", "local"}:
            return mode  # type: ignore[return-value]
    return "sparql"


def build_query_plan(
    question: str,
    include_frink: bool,
    include_gene_expr: bool,
    gene_expr_mode: GeneExprMode | None = None,
) -> QueryPlan:
    """
    Build a QueryPlan for the given natural-language question and UI toggles.

    - NDE is always included by default.
    - FRINK is optionally included if both toggled on and configured.
    - Gene expression is optionally included depending on the selected / default mode.
    """

    cfg = load_config()
    actions: list[SourceAction] = []

    # NDE is always on for now.
    actions.append(
        SourceAction(
            source_id="nde",
            kind="nde",
            query_text="",  # to be filled by NL→SPARQL
            mode="interactive",
        )
    )

    # FRINK optional, only if endpoints are configured.
    if include_frink and cfg.frink_endpoints:
        actions.append(
            SourceAction(
                source_id="frink",
                kind="frink",
                query_text="",
                mode="interactive",
            )
        )

    # Gene expression optional.
    if include_gene_expr:
        mode = gene_expr_mode or _default_gene_expr_mode(cfg)
        if mode != "off":
            actions.append(
                SourceAction(
                    source_id="gene_expression",
                    kind="gene_expression",
                    query_text="",
                    mode="interactive",
                )
            )

    return QueryPlan(actions=actions)


__all__ = [
    "RouterOptions",
    "GeneExprMode",
    "build_query_plan",
]

