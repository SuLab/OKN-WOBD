"""
AI-powered interpretation of differential expression results.

Uses the Anthropic API to generate biological interpretations of DE and
enrichment analysis results.

Requires:
    - anthropic package: pip install anthropic
    - ANTHROPIC_API_KEY environment variable

Example:
    from chatgeo.interpretation import interpret_results
    interpretation = interpret_results(de_result, enrichment_result)
"""

import os
from pathlib import Path
from typing import Optional

from .de_result import DEResult, EnrichmentResult


def build_prompt(
    de_result: DEResult,
    enrichment_result: Optional[EnrichmentResult] = None,
    top_genes: int = 30,
    top_terms: int = 15,
) -> str:
    """
    Build a structured prompt summarizing DE and enrichment results.

    Args:
        de_result: Differential expression result
        enrichment_result: Optional enrichment result
        top_genes: Number of top genes to include per direction
        top_terms: Number of top enrichment terms per direction

    Returns:
        Formatted prompt string
    """
    prov = de_result.provenance
    tissue_str = f" in {prov.query_tissue}" if prov.query_tissue else ""

    sections = []

    # Header context
    sections.append(
        f"I performed a differential expression analysis comparing "
        f"{prov.query_disease}{tissue_str} samples versus healthy controls "
        f"using bulk RNA-seq data from the ARCHS4 compendium.\n"
    )

    # Study design
    sections.append("## Study Design\n")
    sections.append(f"- Test samples: {prov.n_test_samples} ({prov.query_disease})")
    sections.append(f"- Control samples: {prov.n_control_samples} (healthy)")
    sections.append(f"- Test studies: {len(prov.test_studies)}")
    sections.append(f"- Control studies: {len(prov.control_studies)}")
    sections.append(f"- Method: {prov.test_method}")
    sections.append(f"- FDR threshold: {prov.thresholds.get('fdr', 0.01)}")
    sections.append(f"- Log2FC threshold: {prov.thresholds.get('log2fc', 2.0)}")

    # Summary statistics
    sections.append(f"\n## Summary\n")
    sections.append(f"- Genes tested: {de_result.genes_tested:,}")
    sections.append(f"- Significant genes: {de_result.genes_significant:,}")
    sections.append(f"- Upregulated: {de_result.n_upregulated:,}")
    sections.append(f"- Downregulated: {de_result.n_downregulated:,}")

    # Top upregulated genes
    if de_result.upregulated:
        n_show = min(top_genes, len(de_result.upregulated))
        sections.append(f"\n## Top {n_show} Upregulated Genes\n")
        sections.append("Gene | Log2FC | P-adj | Mean Disease | Mean Control")
        sections.append("--- | --- | --- | --- | ---")
        for g in de_result.upregulated[:n_show]:
            padj = f"{g.pvalue_adjusted:.2e}" if g.pvalue_adjusted else "NA"
            sections.append(
                f"{g.gene_symbol} | {g.log2_fold_change:.2f} | {padj} | "
                f"{g.mean_test:.1f} | {g.mean_control:.1f}"
            )

    # Top downregulated genes
    if de_result.downregulated:
        n_show = min(top_genes, len(de_result.downregulated))
        sections.append(f"\n## Top {n_show} Downregulated Genes\n")
        sections.append("Gene | Log2FC | P-adj | Mean Disease | Mean Control")
        sections.append("--- | --- | --- | --- | ---")
        for g in de_result.downregulated[:n_show]:
            padj = f"{g.pvalue_adjusted:.2e}" if g.pvalue_adjusted else "NA"
            sections.append(
                f"{g.gene_symbol} | {g.log2_fold_change:.2f} | {padj} | "
                f"{g.mean_test:.1f} | {g.mean_control:.1f}"
            )

    # Enrichment results
    if enrichment_result is not None:
        sections.append(f"\n## Enrichment Analysis\n")
        sections.append(
            f"- Total enriched terms: {enrichment_result.total_terms}"
        )

        if enrichment_result.upregulated.terms:
            up_terms = enrichment_result.upregulated.get_top_terms(top_terms)
            sections.append(f"\n### Enriched in Upregulated Genes ({enrichment_result.upregulated.n_terms} total)\n")
            sections.append("Source | Term | P-adj | Genes")
            sections.append("--- | --- | --- | ---")
            for t in up_terms:
                sections.append(
                    f"{t.source} | {t.term_name} | {t.pvalue_adjusted:.2e} | "
                    f"{t.intersection_size}"
                )

        if enrichment_result.downregulated.terms:
            down_terms = enrichment_result.downregulated.get_top_terms(top_terms)
            sections.append(f"\n### Enriched in Downregulated Genes ({enrichment_result.downregulated.n_terms} total)\n")
            sections.append("Source | Term | P-adj | Genes")
            sections.append("--- | --- | --- | ---")
            for t in down_terms:
                sections.append(
                    f"{t.source} | {t.term_name} | {t.pvalue_adjusted:.2e} | "
                    f"{t.intersection_size}"
                )

    return "\n".join(sections)


SYSTEM_PROMPT = """\
You are a molecular biology expert interpreting differential expression \
analysis results from bulk RNA-seq data. Provide a concise, rigorous \
biological interpretation.

Structure your response as markdown with these sections:

## Key Findings
A 2-3 sentence summary of the most important biological signals.

## Upregulated Pathways
Describe the major biological themes among upregulated genes. Group genes \
into functional categories (e.g., immune signaling, cell cycle, metabolism). \
Name specific genes that are well-known markers for the condition.

## Downregulated Pathways
Same analysis for downregulated genes.

## Biological Interpretation
Synthesize the up and downregulated signals into a coherent narrative about \
disease mechanism. Reference established literature where the findings \
confirm known biology. Note any unexpected or novel findings.

## Caveats
Briefly note methodological limitations (pooled samples across studies, \
bulk RNA-seq averaging over cell types, potential confounders).

Be specific about gene names and pathways. Avoid vague generalizations. \
If the gene signature matches a well-known disease mechanism, state that \
explicitly. Keep the total response under 800 words."""


def interpret_results(
    de_result: DEResult,
    enrichment_result: Optional[EnrichmentResult] = None,
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 2048,
) -> str:
    """
    Generate an AI interpretation of DE and enrichment results.

    Args:
        de_result: Differential expression result
        enrichment_result: Optional enrichment result
        model: Anthropic model to use
        max_tokens: Maximum tokens in response

    Returns:
        Markdown-formatted interpretation string

    Raises:
        ImportError: If anthropic package not installed
        ValueError: If ANTHROPIC_API_KEY not set
    """
    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "anthropic package required for interpretation. "
            "Install with: pip install anthropic"
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Set it to your Anthropic API key."
        )

    user_prompt = build_prompt(de_result, enrichment_result)

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": user_prompt},
        ],
    )

    return message.content[0].text


def save_interpretation(
    interpretation: str,
    output_dir: Path,
    de_result: DEResult,
    filename: str = "interpretation.md",
) -> Path:
    """
    Save interpretation to a markdown file with header metadata.

    Args:
        interpretation: The AI-generated interpretation text
        output_dir: Directory to save the file
        de_result: DE result for metadata
        filename: Output filename

    Returns:
        Path to the saved file
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename

    prov = de_result.provenance
    tissue_str = f" in {prov.query_tissue}" if prov.query_tissue else ""

    header = (
        f"# Interpretation: {prov.query_disease}{tissue_str}\n\n"
        f"*Auto-generated from ChatGEO differential expression analysis*\n"
        f"*{prov.n_test_samples} disease vs {prov.n_control_samples} control samples | "
        f"FDR < {prov.thresholds.get('fdr', 0.01)} | "
        f"|log2FC| >= {prov.thresholds.get('log2fc', 2.0)}*\n\n"
        f"---\n\n"
    )

    path.write_text(header + interpretation)
    return path
