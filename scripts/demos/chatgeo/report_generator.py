"""
Report generation for differential expression analysis results.

Supports multiple output formats:
- JSON: Full provenance and results for programmatic use
- TSV: Gene tables for spreadsheet analysis
- Console: Human-readable summary
"""

import csv
import json
from io import StringIO
from pathlib import Path
from typing import Optional, Union

from .de_result import (
    DEResult,
    EnrichmentResult,
    GeneResult,
    MetaAnalysisResult,
)


class ReportGenerator:
    """
    Generates reports from differential expression results.

    Supports JSON (full provenance), TSV (gene tables), and console
    (human-readable summary) output formats.

    Example:
        generator = ReportGenerator()
        generator.to_json(result, "results.json")
        generator.to_console_summary(result)
    """

    def to_json(
        self,
        result: Union[DEResult, MetaAnalysisResult],
        path: Union[str, Path],
        indent: int = 2,
    ) -> None:
        """
        Write full results to JSON file.

        Args:
            result: DE or meta-analysis result
            path: Output file path
            indent: JSON indentation level
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(result.to_dict(), f, indent=indent)

    def to_json_string(
        self,
        result: Union[DEResult, MetaAnalysisResult],
        indent: int = 2,
    ) -> str:
        """
        Convert results to JSON string.

        Args:
            result: DE or meta-analysis result
            indent: JSON indentation level

        Returns:
            JSON string
        """
        return json.dumps(result.to_dict(), indent=indent)

    def to_tsv(
        self,
        result: DEResult,
        path: Union[str, Path],
        include_all: bool = False,
    ) -> None:
        """
        Write gene results to TSV file.

        Args:
            result: DE result
            path: Output file path
            include_all: If True, include all tested genes (not just significant)
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if include_all and result.all_genes:
            genes = result.all_genes
        else:
            genes = result.upregulated + result.downregulated

        with open(path, "w", newline="") as f:
            writer = csv.writer(f, delimiter="\t")

            # Header
            writer.writerow([
                "gene_symbol",
                "log2_fold_change",
                "mean_test",
                "mean_control",
                "pvalue",
                "pvalue_adjusted",
                "direction",
                "significant",
            ])

            # Data rows
            for gene in genes:
                is_significant = gene in result.upregulated or gene in result.downregulated
                writer.writerow([
                    gene.gene_symbol,
                    f"{gene.log2_fold_change:.4f}",
                    f"{gene.mean_test:.4f}",
                    f"{gene.mean_control:.4f}",
                    f"{gene.pvalue:.2e}" if gene.pvalue else "NA",
                    f"{gene.pvalue_adjusted:.2e}" if gene.pvalue_adjusted else "NA",
                    gene.direction,
                    "yes" if is_significant else "no",
                ])

    def to_tsv_string(
        self,
        result: DEResult,
        include_all: bool = False,
    ) -> str:
        """
        Convert gene results to TSV string.

        Args:
            result: DE result
            include_all: If True, include all tested genes

        Returns:
            TSV string
        """
        output = StringIO()

        if include_all and result.all_genes:
            genes = result.all_genes
        else:
            genes = result.upregulated + result.downregulated

        writer = csv.writer(output, delimiter="\t")

        writer.writerow([
            "gene_symbol",
            "log2_fold_change",
            "mean_test",
            "mean_control",
            "pvalue",
            "pvalue_adjusted",
            "direction",
            "significant",
        ])

        for gene in genes:
            is_significant = gene in result.upregulated or gene in result.downregulated
            writer.writerow([
                gene.gene_symbol,
                f"{gene.log2_fold_change:.4f}",
                f"{gene.mean_test:.4f}",
                f"{gene.mean_control:.4f}",
                f"{gene.pvalue:.2e}" if gene.pvalue else "NA",
                f"{gene.pvalue_adjusted:.2e}" if gene.pvalue_adjusted else "NA",
                gene.direction,
                "yes" if is_significant else "no",
            ])

        return output.getvalue()

    def to_console_summary(
        self,
        result: DEResult,
        top_n: int = 10,
        show_provenance: bool = True,
    ) -> str:
        """
        Generate human-readable console summary.

        Args:
            result: DE result
            top_n: Number of top genes to show per direction
            show_provenance: Whether to include provenance details

        Returns:
            Formatted string report
        """
        lines = []

        # Header
        lines.append("=" * 70)
        lines.append("DIFFERENTIAL EXPRESSION ANALYSIS RESULTS")
        lines.append("=" * 70)

        # Provenance section
        if show_provenance:
            prov = result.provenance
            lines.append("")
            lines.append("QUERY")
            lines.append(f"  Disease: {prov.query_disease}")
            if prov.query_tissue:
                lines.append(f"  Tissue: {prov.query_tissue}")
            lines.append(f"  Timestamp: {prov.timestamp}")
            lines.append("")
            lines.append("SAMPLES")
            lines.append(f"  Test: {prov.n_test_samples} samples from {len(prov.test_studies)} studies")
            lines.append(f"  Control: {prov.n_control_samples} samples from {len(prov.control_studies)} studies")
            lines.append(f"  Organisms: {', '.join(prov.organisms)}")
            lines.append("")
            lines.append("METHODS")
            lines.append(f"  Normalization: {prov.normalization_method}")
            lines.append(f"  Statistical test: {prov.test_method}")
            lines.append(f"  FDR correction: {prov.fdr_method}")
            lines.append("")
            lines.append("THRESHOLDS")
            lines.append(f"  FDR: {prov.thresholds.get('fdr', 0.05)}")
            lines.append(f"  Log2 FC: {prov.thresholds.get('log2fc', 1.0)}")

        # Summary section
        lines.append("")
        lines.append("-" * 70)
        lines.append("SUMMARY")
        lines.append("-" * 70)
        lines.append(f"  Genes tested: {result.genes_tested:,}")
        lines.append(f"  Genes significant: {result.genes_significant:,}")
        lines.append(f"  Upregulated: {result.n_upregulated:,}")
        lines.append(f"  Downregulated: {result.n_downregulated:,}")

        # Top upregulated genes
        if result.upregulated:
            lines.append("")
            lines.append("-" * 70)
            lines.append(f"TOP {min(top_n, len(result.upregulated))} UPREGULATED GENES")
            lines.append("-" * 70)
            lines.append(f"  {'Gene':<12} {'Log2FC':>10} {'P-adj':>12} {'Mean Test':>12} {'Mean Ctrl':>12}")
            lines.append("  " + "-" * 58)

            for gene in result.upregulated[:top_n]:
                p_adj = f"{gene.pvalue_adjusted:.2e}" if gene.pvalue_adjusted else "N/A"
                lines.append(
                    f"  {gene.gene_symbol:<12} {gene.log2_fold_change:>10.2f} "
                    f"{p_adj:>12} {gene.mean_test:>12.2f} {gene.mean_control:>12.2f}"
                )

        # Top downregulated genes
        if result.downregulated:
            lines.append("")
            lines.append("-" * 70)
            lines.append(f"TOP {min(top_n, len(result.downregulated))} DOWNREGULATED GENES")
            lines.append("-" * 70)
            lines.append(f"  {'Gene':<12} {'Log2FC':>10} {'P-adj':>12} {'Mean Test':>12} {'Mean Ctrl':>12}")
            lines.append("  " + "-" * 58)

            for gene in result.downregulated[:top_n]:
                p_adj = f"{gene.pvalue_adjusted:.2e}" if gene.pvalue_adjusted else "N/A"
                lines.append(
                    f"  {gene.gene_symbol:<12} {gene.log2_fold_change:>10.2f} "
                    f"{p_adj:>12} {gene.mean_test:>12.2f} {gene.mean_control:>12.2f}"
                )

        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)

    def print_summary(
        self,
        result: DEResult,
        top_n: int = 10,
        show_provenance: bool = True,
    ) -> None:
        """
        Print human-readable summary to stdout.

        Args:
            result: DE result
            top_n: Number of top genes to show
            show_provenance: Whether to include provenance details
        """
        print(self.to_console_summary(result, top_n, show_provenance))

    # =========================================================================
    # Enrichment Analysis Output Methods
    # =========================================================================

    def to_json_with_enrichment(
        self,
        de_result: DEResult,
        enrichment_result: EnrichmentResult,
        path: Union[str, Path],
        indent: int = 2,
    ) -> None:
        """
        Write DE results with enrichment to JSON file.

        Args:
            de_result: Differential expression result
            enrichment_result: Enrichment analysis result
            path: Output file path
            indent: JSON indentation level
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        combined = de_result.to_dict()
        combined["enrichment"] = enrichment_result.to_dict()

        with open(path, "w") as f:
            json.dump(combined, f, indent=indent)

    def enrichment_to_tsv(
        self,
        enrichment_result: EnrichmentResult,
        path: Union[str, Path],
        direction: Optional[str] = None,
    ) -> None:
        """
        Write enrichment results to TSV file.

        Args:
            enrichment_result: Enrichment analysis result
            path: Output file path
            direction: "up", "down", or None for both
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Collect terms based on direction
        terms = []
        if direction is None or direction == "up":
            for t in enrichment_result.upregulated.terms:
                terms.append(("up", t))
        if direction is None or direction == "down":
            for t in enrichment_result.downregulated.terms:
                terms.append(("down", t))

        with open(path, "w", newline="") as f:
            writer = csv.writer(f, delimiter="\t")

            # Header
            writer.writerow([
                "direction",
                "term_id",
                "term_name",
                "source",
                "pvalue_adjusted",
                "intersection_size",
                "term_size",
                "precision",
                "recall",
                "genes",
            ])

            # Data rows sorted by p-value
            for dir_label, term in sorted(terms, key=lambda x: x[1].pvalue_adjusted):
                writer.writerow([
                    dir_label,
                    term.term_id,
                    term.term_name,
                    term.source,
                    f"{term.pvalue_adjusted:.2e}",
                    term.intersection_size,
                    term.term_size,
                    f"{term.precision:.4f}",
                    f"{term.recall:.4f}",
                    ",".join(term.genes),
                ])

    def format_enrichment_summary(
        self,
        enrichment_result: EnrichmentResult,
        top_n: int = 10,
    ) -> str:
        """
        Generate human-readable enrichment summary.

        Args:
            enrichment_result: Enrichment analysis result
            top_n: Number of top terms to show per category

        Returns:
            Formatted string report
        """
        lines = []

        lines.append("")
        lines.append("-" * 70)
        lines.append("ENRICHMENT ANALYSIS")
        lines.append("-" * 70)

        prov = enrichment_result.provenance
        lines.append(f"  Backend: {prov.backend}")
        lines.append(f"  Organism: {prov.organism}")
        lines.append(f"  Sources: {', '.join(prov.sources)}")
        lines.append(f"  Threshold: {prov.significance_threshold}")

        lines.append("")
        lines.append(f"  Total significant terms: {enrichment_result.total_terms}")
        lines.append(f"  Upregulated: {enrichment_result.upregulated.n_terms} terms")
        lines.append(f"  Downregulated: {enrichment_result.downregulated.n_terms} terms")

        # Top terms for upregulated genes
        if enrichment_result.upregulated.terms:
            lines.append("")
            lines.append("-" * 70)
            up_terms = enrichment_result.upregulated.get_top_terms(top_n)
            lines.append(f"TOP {len(up_terms)} ENRICHED TERMS (UPREGULATED GENES)")
            lines.append("-" * 70)
            lines.append(
                f"  {'Source':<8} {'Term ID':<14} {'P-adj':>10} {'Genes':>6}  Term Name"
            )
            lines.append("  " + "-" * 66)

            for term in up_terms:
                name = term.term_name[:35] + "..." if len(term.term_name) > 35 else term.term_name
                lines.append(
                    f"  {term.source:<8} {term.term_id:<14} "
                    f"{term.pvalue_adjusted:>10.2e} {term.intersection_size:>6}  {name}"
                )

        # Top terms for downregulated genes
        if enrichment_result.downregulated.terms:
            lines.append("")
            lines.append("-" * 70)
            down_terms = enrichment_result.downregulated.get_top_terms(top_n)
            lines.append(f"TOP {len(down_terms)} ENRICHED TERMS (DOWNREGULATED GENES)")
            lines.append("-" * 70)
            lines.append(
                f"  {'Source':<8} {'Term ID':<14} {'P-adj':>10} {'Genes':>6}  Term Name"
            )
            lines.append("  " + "-" * 66)

            for term in down_terms:
                name = term.term_name[:35] + "..." if len(term.term_name) > 35 else term.term_name
                lines.append(
                    f"  {term.source:<8} {term.term_id:<14} "
                    f"{term.pvalue_adjusted:>10.2e} {term.intersection_size:>6}  {name}"
                )

        return "\n".join(lines)


def format_gene_table(genes: list[GeneResult], max_genes: int = 20) -> str:
    """
    Format a list of genes as a simple table.

    Args:
        genes: List of GeneResult objects
        max_genes: Maximum genes to show

    Returns:
        Formatted table string
    """
    if not genes:
        return "  No genes found."

    lines = []
    lines.append(f"  {'Gene':<12} {'Log2FC':>8} {'P-adj':>12} {'Direction':>10}")
    lines.append("  " + "-" * 44)

    for gene in genes[:max_genes]:
        p_adj = f"{gene.pvalue_adjusted:.2e}" if gene.pvalue_adjusted else "N/A"
        lines.append(
            f"  {gene.gene_symbol:<12} {gene.log2_fold_change:>8.2f} "
            f"{p_adj:>12} {gene.direction:>10}"
        )

    if len(genes) > max_genes:
        lines.append(f"  ... and {len(genes) - max_genes} more genes")

    return "\n".join(lines)


def format_provenance_brief(result: DEResult) -> str:
    """
    Format brief provenance summary.

    Args:
        result: DE result

    Returns:
        One-line provenance summary
    """
    prov = result.provenance
    tissue = f" in {prov.query_tissue}" if prov.query_tissue else ""
    return (
        f"{prov.query_disease}{tissue} | "
        f"{prov.n_test_samples} test vs {prov.n_control_samples} control | "
        f"{result.n_upregulated} up, {result.n_downregulated} down"
    )
