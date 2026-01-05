from __future__ import annotations

from typing import Dict, List

from wobd_web.config import load_config
from wobd_web.gene_expression.service import get_gene_expression_service
from wobd_web.models import AnswerBundle, ProvenanceItem, QueryPlan, SourceAction
from wobd_web.nl_to_sparql import TargetKind, generate_sparql
from wobd_web.sparql.client import SourceResult, execute_sparql
from wobd_web.sparql.endpoints import (
    Endpoint,
    get_default_frink_endpoint,
    get_default_nde_endpoint,
    get_gene_expr_endpoint_for_mode,
)


def _target_for_action(action: SourceAction) -> TargetKind:
    if action.kind == "gene_expression":
        return "gene_expression"
    return "nde"


def _run_single_action(action: SourceAction, max_rows: int) -> tuple[SourceResult, str, ProvenanceItem]:
    cfg = load_config()
    target = _target_for_action(action)

    # Generate SPARQL for this source.
    sparql = generate_sparql(
        question=action.query_text,
        target=target,
        interactive_limit=max_rows,
    )

    # Resolve endpoint and execute.
    endpoint: Endpoint | None
    if action.kind == "nde":
        endpoint = get_default_nde_endpoint()
        result = execute_sparql(endpoint.sparql_url, sparql)
    elif action.kind == "frink":
        endpoint = get_default_frink_endpoint()
        if endpoint is None:
            result = SourceResult(
                rows=[],
                variables=[],
                row_count=0,
                elapsed_ms=0.0,
                endpoint_url="",
                status="error",
                error="FRINK endpoint not configured.",
            )
        else:
            result = execute_sparql(endpoint.sparql_url, sparql)
    else:  # gene_expression
        # Gene expression may use a non-SPARQL adapter.
        endpoint = get_gene_expr_endpoint_for_mode("sparql")
        service = get_gene_expression_service("sparql")
        result = service.query_sparql(sparql)

    ep_url = endpoint.sparql_url if endpoint is not None else ""
    prov = ProvenanceItem(
        source_label=action.source_id,
        endpoint_url=ep_url,
        elapsed_ms=result.elapsed_ms,
        row_count=result.row_count,
        status=result.status,
    )

    return result, sparql, prov


def run_plan(plan: QueryPlan, question: str) -> AnswerBundle:
    """
    Execute all actions in the given QueryPlan and aggregate results.

    The NL question is passed into the NL→SPARQL generator for each action;
    in the future this could be customized per source.
    """

    cfg = load_config()
    max_rows = cfg.ui.max_rows

    tables: Dict[str, List[Dict[str, object]]] = {}
    sparql_texts: Dict[str, str] = {}
    provenance: List[ProvenanceItem] = []

    for action in plan.actions:
        # Use the original question as the prompt for each action.
        action.query_text = question
        result, sparql, prov = _run_single_action(action, max_rows=max_rows)
        tables[action.source_id] = result.rows
        sparql_texts[action.source_id] = sparql
        provenance.append(prov)

    # Simple heuristic answer text for MVP: summarise by counts.
    parts: List[str] = []
    for prov in provenance:
        parts.append(
            f"{prov.source_label}: {prov.row_count} rows (status={prov.status})"
        )
    final_text = " | ".join(parts) if parts else "No results."

    return AnswerBundle(
        final_text=final_text,
        tables=tables,
        sparql_texts=sparql_texts,
        provenance=provenance,
    )


__all__ = [
    "run_plan",
]

