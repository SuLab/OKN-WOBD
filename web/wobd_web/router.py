from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from wobd_web.config import AppConfig, load_config
from wobd_web.models import QueryPlan, SourceAction
from wobd_web.preset_queries import PresetQueryConfig, get_preset_query


GeneExprMode = Literal["off", "sparql", "web_mcp", "local"]


@dataclass
class RouterOptions:
    include_gene_expr: bool
    gene_expr_mode: GeneExprMode


def _default_gene_expr_mode(cfg: AppConfig) -> GeneExprMode:
    ge = cfg.gene_expr
    if isinstance(ge, dict):
        mode = ge.get("default_mode", "sparql")
        if mode in {"sparql", "web_mcp", "local"}:
            return mode  # type: ignore[return-value]
    return "sparql"


def build_query_plan(question: str) -> QueryPlan:
    """
    Build a QueryPlan for the given natural-language question.

    First checks for preset queries. If found, uses the preset SPARQL.
    Otherwise, falls back to NL→SPARQL generation.

    - NDE is always included by default (queries NDE data in FRINK).
    - Gene expression is automatically included if configured (via FRINK SPARQL endpoint).
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

    # Gene expression is automatically included if configured (via FRINK SPARQL endpoint)
    gene_expr_cfg = cfg.gene_expr
    if isinstance(gene_expr_cfg, dict):
        sparql_cfg = gene_expr_cfg.get("sparql", {})
        if sparql_cfg.get("endpoints"):
            actions.append(
                SourceAction(
                    source_id="gene_expression",
                    kind="gene_expression",
                    query_text="",  # to be filled by NL→SPARQL
                    mode="interactive",
                )
            )

    return QueryPlan(actions=actions)


__all__ = [
    "RouterOptions",
    "GeneExprMode",
    "build_query_plan",
]

