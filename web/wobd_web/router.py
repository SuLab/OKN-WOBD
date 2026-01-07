from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from wobd_web.config import AppConfig, load_config
from wobd_web.models import QueryPlan, SourceAction
from wobd_web.preset_queries import PresetQueryConfig, get_preset_query


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

    First checks for preset queries. If found, uses the preset SPARQL.
    Otherwise, falls back to NL→SPARQL generation.

    - NDE is always included by default.
    - FRINK is optionally included if both toggled on and configured.
    - Gene expression is optionally included depending on the selected / default mode.
    """

    # Check for preset query first
    preset = get_preset_query(question)
    if preset is not None:
        actions: list[SourceAction] = []
        
        if preset.query_type == "single":
            # Single-step preset query
            actions.append(
                SourceAction(
                    source_id=preset.source_kind,
                    kind=preset.source_kind,
                    query_text=preset.query or "",  # Contains raw SPARQL
                    mode="interactive",
                )
            )
        else:
            # Multi-step preset query - create actions for each step
            # The executor will handle the multi-step logic
            if preset.steps:
                for step in preset.steps:
                    actions.append(
                        SourceAction(
                            source_id=step.step_name,
                            kind=step.source_kind,
                            query_text=step.query,  # Contains raw SPARQL or template
                            mode="interactive",
                        )
                    )
        
        return QueryPlan(actions=actions)

    # No preset found - use NL→SPARQL generation (original behavior)
    cfg = load_config()
    actions = []

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

