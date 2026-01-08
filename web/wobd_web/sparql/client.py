from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


@dataclass
class SourceResult:
    rows: List[Dict[str, Any]]
    variables: List[str]
    row_count: int
    elapsed_ms: float
    endpoint_url: str
    status: str
    error: Optional[str] = None


def ensure_limit(query: str, max_rows: int) -> str:
    """
    Ensure that a SPARQL SELECT query has a LIMIT clause with the specified max_rows.

    This is a simple, case-insensitive heuristic and does not attempt to fully
    parse SPARQL. If a LIMIT is already present, it is replaced with the specified
    max_rows; otherwise a LIMIT is appended.
    """

    pattern = re.compile(r"\blimit\s+\d+\b", flags=re.IGNORECASE)
    if pattern.search(query):
        # Replace existing LIMIT clause
        return re.sub(r"\blimit\s+\d+\b", f"LIMIT {int(max_rows)}", query, flags=re.IGNORECASE)

    stripped = query.rstrip().rstrip(";")
    return f"{stripped}\nLIMIT {int(max_rows)}"


def execute_sparql(
    endpoint_url: str,
    query: str,
    timeout_s: float = 30.0,
    method_preference: str = "POST",
) -> SourceResult:
    """
    Execute a SPARQL query against the given endpoint and return a SourceResult.

    The client prefers HTTP POST with `application/sparql-query`, but will
    fall back to GET with the `query` parameter if POST fails with a method
    error.
    """

    headers = {
        "Accept": "application/sparql-results+json",
    }

    start = time.perf_counter()
    status = "ok"
    error: Optional[str] = None
    rows: List[Dict[str, Any]] = []
    variables: List[str] = []

    def _parse_json(payload: Dict[str, Any]) -> None:
        nonlocal rows, variables
        head = payload.get("head", {})
        vars_list = head.get("vars") or []
        if not isinstance(vars_list, list):
            vars_list = []
        variables = [str(v) for v in vars_list]

        results = payload.get("results", {})
        bindings = results.get("bindings") or []
        if not isinstance(bindings, list):
            bindings = []

        parsed_rows: List[Dict[str, Any]] = []
        for binding in bindings:
            if not isinstance(binding, dict):
                continue
            row: Dict[str, Any] = {}
            for var, value_obj in binding.items():
                if isinstance(value_obj, dict) and "value" in value_obj:
                    row[var] = value_obj["value"]
                else:
                    row[var] = value_obj
            parsed_rows.append(row)
        rows = parsed_rows

    try:
        resp: Optional[requests.Response] = None

        if method_preference.upper() == "POST":
            try:
                resp = requests.post(
                    endpoint_url,
                    data=query.encode("utf-8"),
                    headers={"Content-Type": "application/sparql-query", **headers},
                    timeout=timeout_s,
                )
            except requests.RequestException as exc:
                # Fall through to GET-based attempt below.
                error = str(exc)

        if resp is None or not resp.ok:
            # Attempt GET as a fallback.
            try:
                resp = requests.get(
                    endpoint_url,
                    params={"query": query},
                    headers=headers,
                    timeout=timeout_s,
                )
            except requests.RequestException as exc:
                status = "error"
                error = str(exc)
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                return SourceResult(
                    rows=[],
                    variables=[],
                    row_count=0,
                    elapsed_ms=elapsed_ms,
                    endpoint_url=endpoint_url,
                    status=status,
                    error=error,
                )

        if not resp.ok:
            status = "error"
            error = f"HTTP {resp.status_code}: {resp.text[:500]}"
        else:
            try:
                payload = resp.json()
                if isinstance(payload, dict):
                    _parse_json(payload)
                else:
                    status = "error"
                    error = "Unexpected JSON structure from SPARQL endpoint."
            except ValueError as exc:
                status = "error"
                error = f"Failed to decode JSON from SPARQL endpoint: {exc}"
    except Exception as exc:  # pragma: no cover - defensive catch
        status = "error"
        error = str(exc)

    elapsed_ms = (time.perf_counter() - start) * 1000.0
    row_count = len(rows)

    return SourceResult(
        rows=rows,
        variables=variables,
        row_count=row_count,
        elapsed_ms=elapsed_ms,
        endpoint_url=endpoint_url,
        status=status,
        error=error,
    )


__all__ = [
    "SourceResult",
    "ensure_limit",
    "execute_sparql",
]

