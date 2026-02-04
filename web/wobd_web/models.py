from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


@dataclass
class SourceAction:
    """A single query action against a configured source."""

    source_id: str
    kind: Literal["nde", "frink", "gene_expression"]
    query_text: str
    mode: Literal["interactive", "batch"] = "interactive"


@dataclass
class QueryPlan:
    """A collection of source actions to execute for one user question."""

    actions: List[SourceAction] = field(default_factory=list)


@dataclass
class ProvenanceItem:
    """Lightweight provenance for a single source query."""

    source_label: str
    endpoint_url: str
    elapsed_ms: float
    row_count: int
    status: str


@dataclass
class AnswerBundle:
    """
    Aggregated answer returned to the UI.

    - final_text: high-level natural-language answer.
    - tables: mapping from source_id to list of row dicts.
    - sparql_texts: mapping from source_id to generated SPARQL.
    - provenance: list of per-source provenance records.
    - limit_applied: whether a LIMIT clause was applied to non-preset queries.
    - limit_value: the LIMIT value that was applied (if any).
    """

    final_text: str
    tables: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    sparql_texts: Dict[str, str] = field(default_factory=dict)
    provenance: List[ProvenanceItem] = field(default_factory=list)
    limit_applied: bool = False
    limit_value: Optional[int] = None


__all__ = [
    "SourceAction",
    "QueryPlan",
    "ProvenanceItem",
    "AnswerBundle",
]

