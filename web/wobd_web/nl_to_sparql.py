from __future__ import annotations

import json
import os
from typing import Literal

from openai import OpenAI

from wobd_web.config import LLMConfig, load_config
from wobd_web.sparql.client import ensure_limit
from wobd_web.context import load_nde_context


TargetKind = Literal["nde", "gene_expression"]


PREFIX_BLOCK = """PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
"""


def _get_client_and_model() -> tuple[OpenAI, LLMConfig]:
    cfg = load_config()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Please provide an API key to enable NL→SPARQL."
        )
    client = OpenAI(api_key=api_key)
    return client, cfg.llm


def _build_nde_context_hint() -> str:
    """
    Build a small textual hint from the NDE context JSON, if available.

    The NDE context file `nde_global.json` can be large; we include only a
    truncated pretty-printed snippet to give the LLM some idea of the schema
    without overwhelming the prompt. If the file is missing or cannot be
    parsed, this returns an empty string.
    """

    ctx = load_nde_context()
    if not ctx:
        return ""

    try:
        snippet = json.dumps(ctx, indent=2)
    except Exception:
        return ""

    # Truncate to keep prompts reasonably sized.
    max_len = 2000
    if len(snippet) > max_len:
        snippet = snippet[: max_len - 40] + "\n... (context truncated) ..."

    return (
        "\nHere is JSON context describing the NDE schema and common patterns. "
        "Use it to choose appropriate classes and properties:\n"
        f"{snippet}\n"
    )


def _build_system_prompt(target: TargetKind) -> str:
    base = (
        "You are an expert SPARQL query generator. "
        "Given a natural-language question, you produce a single SPARQL SELECT "
        "query that can be executed directly against the target endpoint. "
        "You MUST only output the SPARQL query, with no explanation or commentary. "
        "The query MUST NOT modify data (no INSERT, DELETE, UPDATE, LOAD, or DROP). "
        "ALWAYS include PREFIX declarations at the top of the query such as:\n"
        "PREFIX schema: <http://schema.org/>\n"
        "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n"
        "If you use any additional prefixes, declare them as well.\n"
        "Use explicit variable names."
    )
    if target == "nde":
        return (
            base
            + " The target is an NDE knowledge graph. In this graph, studies are "
            "represented as schema:Dataset resources (not schema:Study). Use "
            "schema:infectiousAgent to link datasets to pathogens or diseases, "
            "schema:includedInDataCatalog to see which catalog a dataset belongs to, "
            "and schema:name for human-readable labels."
            + _build_nde_context_hint()
        )
    if target == "gene_expression":
        return (
            base
            + " The target is a gene expression dataset. Focus on genes, samples, "
            "conditions, and expression values."
        )
    return base


def _add_prefixes_if_missing(query: str) -> str:
    """
    Ensure the standard schema/rdf prefixes are present.

    If the model already emitted them, avoid duplicating.
    """

    normalized = query.lower()
    if "prefix schema:" in normalized and "prefix rdf:" in normalized:
        return query
    return f"{PREFIX_BLOCK}\n{query.lstrip()}"


def generate_sparql(
    question: str,
    target: TargetKind,
    interactive_limit: int,
) -> str:
    """
    Use OpenAI to generate a SPARQL SELECT query for the given target.

    The generated query is post-processed to ensure a LIMIT clause is present
    for interactive usage.
    """

    client, llm_cfg = _get_client_and_model()
    system_prompt = _build_system_prompt(target)

    completion = client.responses.create(  # type: ignore[attr-defined]
        model=llm_cfg.model,
        input=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": question,
            },
        ],
        temperature=llm_cfg.temperature,
    )

    # The Responses API can return content in segments; this helper extracts text.
    text_chunks: list[str] = []
    for output in completion.output:  # type: ignore[union-attr]
        for item in getattr(output, "content", []) or []:
            if getattr(item, "type", None) == "output_text":
                text_chunks.append(getattr(item, "text", "") or "")

    query = "\n".join(chunk.strip() for chunk in text_chunks if chunk.strip())
    if not query:
        raise RuntimeError("LLM did not return a SPARQL query.")

    # Enforce SELECT-only by a simple guard; callers can choose how strict to be.
    lowered = query.lower()
    forbidden = ("insert", "delete", "update", "load", "drop")
    if any(f" {kw} " in lowered for kw in forbidden):
        raise RuntimeError("Generated query appears to contain forbidden SPARQL operations.")

    query_with_prefixes = _add_prefixes_if_missing(query)
    return ensure_limit(query_with_prefixes, interactive_limit)


__all__ = [
    "TargetKind",
    "generate_sparql",
]

