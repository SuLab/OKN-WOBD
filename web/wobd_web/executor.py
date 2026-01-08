from __future__ import annotations

from typing import Dict, List, Set

from wobd_web.config import load_config
from wobd_web.gene_expression.service import get_gene_expression_service
from wobd_web.models import AnswerBundle, ProvenanceItem, QueryPlan, SourceAction
from wobd_web.nl_to_sparql import TargetKind, generate_sparql
from wobd_web.preset_queries import (
    TOCILIZUMAB_STEP2_NDE_TEMPLATE,
    TOCILIZUMAB_STEP3_METADATA_TEMPLATE,
    get_preset_query,
)
from wobd_web.sparql.client import SourceResult, ensure_limit, execute_sparql
from wobd_web.sparql.endpoints import (
    Endpoint,
    get_default_frink_endpoint,
    get_default_nde_endpoint,
    get_default_wikidata_endpoint,
    get_default_spoke_endpoint,
    get_default_ubergraph_endpoint,
    get_gene_expr_endpoint_for_mode,
)


def _target_for_action(action: SourceAction) -> TargetKind:
    if action.kind == "gene_expression":
        return "gene_expression"
    return "nde"


def _is_preset_query(query_text: str) -> bool:
    """Check if query_text contains raw SPARQL (preset query) rather than NL question."""
    return "SELECT" in query_text.upper() or "PREFIX" in query_text.upper()


def _replace_endpoint_placeholders(sparql: str) -> str:
    """
    Replace endpoint placeholders in SPARQL queries with actual endpoint URLs.
    
    Placeholders:
    - SPOKE_ENDPOINT_PLACEHOLDER -> SPOKE endpoint URL
    - UBERGRAPH_ENDPOINT_PLACEHOLDER -> Ubergraph endpoint URL
    - GENE_EXPR_ENDPOINT_PLACEHOLDER -> Gene expression endpoint URL
    """
    from wobd_web.sparql.endpoints import get_default_ubergraph_endpoint
    
    query = sparql
    
    # Replace SPOKE endpoint placeholder
    spoke_endpoint = get_default_spoke_endpoint()
    if spoke_endpoint:
        query = query.replace(
            "<SPOKE_ENDPOINT_PLACEHOLDER>",
            f"<{spoke_endpoint.sparql_url}>"
        )
    
    # Replace Ubergraph endpoint placeholder
    ubergraph_endpoint = get_default_ubergraph_endpoint()
    if ubergraph_endpoint:
        query = query.replace(
            "<UBERGRAPH_ENDPOINT_PLACEHOLDER>",
            f"<{ubergraph_endpoint.sparql_url}>"
        )
    
    # Replace Gene Expression endpoint placeholder
    gene_expr_endpoint = get_gene_expr_endpoint_for_mode("sparql")
    if gene_expr_endpoint:
        query = query.replace(
            "<GENE_EXPR_ENDPOINT_PLACEHOLDER>",
            f"<{gene_expr_endpoint.sparql_url}>"
        )
    
    return query


def _run_single_action(action: SourceAction, max_rows: int, apply_limit: bool = True) -> tuple[SourceResult, str, ProvenanceItem]:
    cfg = load_config()
    
    # Check if this is a preset query (raw SPARQL) or needs NL→SPARQL generation
    if _is_preset_query(action.query_text):
        # Preset query - use SPARQL directly, but replace endpoint placeholders if present
        # Preset queries don't get LIMIT applied - they're trusted queries
        sparql = _replace_endpoint_placeholders(action.query_text)
    else:
        # Generate SPARQL from natural language
        target = _target_for_action(action)
        # Only apply limit if requested and not a preset query
        limit_for_llm = max_rows if apply_limit else None
        sparql = generate_sparql(
            question=action.query_text,
            target=target,
            interactive_limit=limit_for_llm,
        )
        # Also ensure LIMIT is in the generated query if needed
        if apply_limit:
            sparql = ensure_limit(sparql, max_rows)

    # Resolve endpoint and execute.
    endpoint: Endpoint | None
    # Check for Wikidata-specific source_id (for multi-step queries)
    if action.source_id == "wikidata_drug_to_disease":
        endpoint = get_default_wikidata_endpoint()
        if endpoint is None:
            result = SourceResult(
                rows=[],
                variables=[],
                row_count=0,
                elapsed_ms=0.0,
                endpoint_url="",
                status="error",
                error="Wikidata endpoint not configured.",
            )
        else:
            result = execute_sparql(endpoint.sparql_url, sparql)
    elif action.kind == "nde":
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


def _execute_multistep_query(plan: QueryPlan, question: str, apply_limit: bool = True) -> AnswerBundle:
    """
    Execute a multi-step query workflow (e.g., Tocilizumab).
    
    Steps:
    1. Query Wikidata in FRINK for drug → disease (MONDO) mappings
    2. Query NDE with MONDO identifiers to find datasets
    3. For each dataset, query sample metadata
    """
    cfg = load_config()
    max_rows = cfg.ui.max_rows
    
    tables: Dict[str, List[Dict[str, object]]] = {}
    sparql_texts: Dict[str, str] = {}
    provenance: List[ProvenanceItem] = []
    
    # Step 1: Query Wikidata for drug → disease mappings
    # Find the wikidata step action
    step1_action = next((a for a in plan.actions if a.source_id == "wikidata_drug_to_disease"), None)
    
    if not step1_action:
        # No step 1 action found - return empty result
        return AnswerBundle(
            final_text="Error: Multi-step query configuration not found.",
            tables={},
            sparql_texts={},
            provenance=[],
        )
    
    if step1_action:
        result1, sparql1, prov1 = _run_single_action(step1_action, max_rows=max_rows, apply_limit=apply_limit)
        tables["wikidata_drug_to_disease"] = result1.rows
        sparql_texts["wikidata_drug_to_disease"] = sparql1
        provenance.append(prov1)
        
        # Extract MONDO URIs from step 1 results
        mondo_uris: Set[str] = set()
        for row in result1.rows:
            if "mondo_uri" in row and row["mondo_uri"]:
                mondo_uris.add(row["mondo_uri"])
            elif "mondo_id" in row and row["mondo_id"]:
                # Convert MONDO ID to URI format
                mondo_id = str(row["mondo_id"]).strip()
                if mondo_id.startswith("MONDO:"):
                    mondo_id = mondo_id.replace("MONDO:", "")
                if mondo_id.startswith("http"):
                    mondo_uris.add(mondo_id)
                else:
                    mondo_uris.add(f"http://purl.obolibrary.org/obo/MONDO_{mondo_id}")
        
        # Step 2: Query NDE with MONDO identifiers
        if mondo_uris:
            mondo_values = "\n    ".join(f"<{uri}>" for uri in mondo_uris)
            step2_query = TOCILIZUMAB_STEP2_NDE_TEMPLATE.replace("{MONDO_VALUES}", mondo_values)
            
            step2_action = SourceAction(
                source_id="nde_datasets_by_mondo",
                kind="nde",
                query_text=step2_query,
                mode="interactive",
            )
            result2, sparql2, prov2 = _run_single_action(step2_action, max_rows=max_rows, apply_limit=apply_limit)
            tables["nde_datasets_by_mondo"] = result2.rows
            sparql_texts["nde_datasets_by_mondo"] = sparql2
            provenance.append(prov2)
            
            # Step 3: Query sample metadata for each dataset
            dataset_uris: Set[str] = set()
            for row in result2.rows:
                if "study" in row and row["study"]:
                    dataset_uris.add(str(row["study"]))
            
            if dataset_uris:
                study_values = "\n    ".join(f"<{uri}>" for uri in dataset_uris)
                step3_query = TOCILIZUMAB_STEP3_METADATA_TEMPLATE.replace("{STUDY_VALUES}", study_values)
                
                step3_action = SourceAction(
                    source_id="sample_metadata",
                    kind="nde",
                    query_text=step3_query,
                    mode="interactive",
                )
                result3, sparql3, prov3 = _run_single_action(step3_action, max_rows=max_rows, apply_limit=apply_limit)
                tables["sample_metadata"] = result3.rows
                sparql_texts["sample_metadata"] = sparql3
                provenance.append(prov3)
        else:
            # No MONDO IDs found - add empty result
            tables["nde_datasets_by_mondo"] = []
            sparql_texts["nde_datasets_by_mondo"] = "No MONDO identifiers found from Wikidata query."
            provenance.append(
                ProvenanceItem(
                    source_label="nde_datasets_by_mondo",
                    endpoint_url="",
                    elapsed_ms=0.0,
                    row_count=0,
                    status="skipped",
                )
            )
    
    # Aggregate results
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
        limit_applied=False,  # Multi-step queries use preset queries which don't get limits
        limit_value=None,
    )


def run_plan(plan: QueryPlan, question: str, apply_limit: bool = True) -> AnswerBundle:
    """
    Execute all actions in the given QueryPlan and aggregate results.

    Handles both single-step and multi-step queries.
    For preset queries, uses raw SPARQL. Otherwise, generates SPARQL from NL.
    """

    # Check if this is a multi-step query (Tocilizumab workflow)
    preset = get_preset_query(question)
    if preset and preset.query_type == "multistep":
        return _execute_multistep_query(plan, question, apply_limit=apply_limit)
    
    # Single-step execution (original behavior)
    cfg = load_config()
    max_rows = cfg.ui.max_rows
    
    # Check for keywords in question that indicate no limit should be applied
    question_lower = question.lower()
    no_limit_keywords = ["all results", "no limit", "remove limit", "unlimited", "show all"]
    if any(keyword in question_lower for keyword in no_limit_keywords):
        apply_limit = False

    tables: Dict[str, List[Dict[str, object]]] = {}
    sparql_texts: Dict[str, str] = {}
    provenance: List[ProvenanceItem] = []
    limit_was_applied = False

    for action in plan.actions:
        # Track if this is a preset query before processing
        is_preset = _is_preset_query(action.query_text)
        # For non-preset queries, use the original question as the prompt
        if not is_preset:
            action.query_text = question
        result, sparql, prov = _run_single_action(action, max_rows=max_rows, apply_limit=apply_limit)
        tables[action.source_id] = result.rows
        sparql_texts[action.source_id] = sparql
        provenance.append(prov)
        # Track if limit was applied (only for non-preset queries)
        if apply_limit and not is_preset:
            limit_was_applied = True

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
        limit_applied=limit_was_applied,
        limit_value=max_rows if limit_was_applied else None,
    )


__all__ = [
    "run_plan",
]

