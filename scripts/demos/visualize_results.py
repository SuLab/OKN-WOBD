#!/usr/bin/env python3
"""
Visualize GO Disease Analyzer results as ASCII provenance diagram.

Takes a JSON output file from go_disease_analyzer.py and creates a visual
summary showing data flow and provenance through all analysis layers.

Usage:
    python visualize_results.py demo_lupus_b-cell_blood.json
    python visualize_results.py demo_lupus_b-cell_blood.json --output summary.txt
"""

import json
import argparse
import sys
from pathlib import Path
from typing import Dict, Any, List

# Configuration for number of items to show
MAX_ITEMS = 10


def wrap_text(text: str, width: int, indent: str = "") -> List[str]:
    """Wrap text to specified width with indent."""
    words = text.split()
    lines = []
    current_line = indent

    for word in words:
        if len(current_line) + len(word) + 1 <= width:
            if current_line == indent:
                current_line += word
            else:
                current_line += " " + word
        else:
            if current_line != indent:
                lines.append(current_line)
            current_line = indent + word

    if current_line != indent:
        lines.append(current_line)

    return lines


def truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis if too long."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def generate_visualization(data: Dict[str, Any]) -> str:
    """Generate ASCII visualization of analysis results."""

    query = data.get("query", {})
    layer1 = data.get("layer1_knowledge", {})
    layer2 = data.get("layer2_singlecell", {})
    layer3 = data.get("layer3_validation", {})
    llm_summary = data.get("llm_summary", "")

    # Extract key data points
    go_term = query.get("go_term", "N/A")
    go_label = query.get("go_label", "N/A")
    disease = query.get("disease", "N/A")
    tissue = query.get("tissue", "N/A")

    n_genes = layer1.get("n_genes", 0)
    sample_genes = layer1.get("sample_genes", [])[:MAX_ITEMS]
    genes_with_terms = layer1.get("genes_with_go_terms", [])[:MAX_ITEMS]

    n_upregulated = layer2.get("n_upregulated", 0)
    n_downregulated = layer2.get("n_downregulated", 0)
    top_upregulated = layer2.get("top_upregulated", [])[:MAX_ITEMS]
    cell_type_drivers = layer2.get("cell_type_drivers", [])[:MAX_ITEMS]

    n_studies = layer3.get("n_studies", 0)
    # Support both old and new field names for backward compatibility
    n_disease_samples_metadata = layer3.get("n_disease_samples_in_metadata", layer3.get("n_disease_samples", 0))
    n_disease_samples_data = layer3.get("n_disease_samples_with_data", 0)
    n_control_samples_metadata = layer3.get("n_control_samples_in_metadata", layer3.get("n_control_samples", 0))
    n_control_samples_data = layer3.get("n_control_samples_with_data", 0)
    n_studies_examined = layer3.get("n_studies_examined", 0)
    n_studies_in_metadata = layer3.get("n_studies_in_metadata", 0)
    study_stats = layer3.get("study_search_stats", {})
    diff_expr = layer3.get("differential_expression", [])[:MAX_ITEMS]
    studies = layer3.get("studies", [])[:MAX_ITEMS]
    control_samples = layer3.get("control_samples", [])[:MAX_ITEMS]

    # Build visualization
    lines = []

    # Header
    lines.append("=" * 100)
    lines.append("                       GO DISEASE ANALYZER - PROVENANCE VISUALIZATION")
    lines.append("=" * 100)
    lines.append("")

    # Introduction / Overview
    lines.append("┌" + "─" * 98 + "┐")
    lines.append("│" + " ABOUT THIS ANALYSIS ".center(98) + "│")
    lines.append("├" + "─" * 98 + "┤")
    lines.append("│".ljust(99) + "│")
    lines.append("│  This analysis answers the question:".ljust(99) + "│")
    lines.append(f"│  \"Which genes involved in {truncate(go_label, 40)} are dysregulated in".ljust(99) + "│")
    lines.append(f"│   {truncate(disease, 50)}, and which cell types drive those changes?\"".ljust(99) + "│")
    lines.append("│".ljust(99) + "│")
    lines.append("│  The analysis proceeds through 4 layers:".ljust(99) + "│")
    lines.append("│    1. KNOWLEDGE GRAPH: Discover genes annotated to the GO term via Ubergraph + Wikidata".ljust(99) + "│")
    lines.append("│    2. SINGLE-CELL: Compare expression in disease vs normal cells (CellxGene Census)".ljust(99) + "│")
    lines.append("│    3. BULK VALIDATION: Validate findings in independent GEO studies (ARCHS4)".ljust(99) + "│")
    lines.append("│    4. INTEGRATION: Synthesize findings and assess cross-layer concordance".ljust(99) + "│")
    lines.append("│".ljust(99) + "│")
    lines.append("│  Each layer provides provenance: the specific data sources, sample IDs, and methods used.".ljust(99) + "│")
    lines.append("│".ljust(99) + "│")
    lines.append("└" + "─" * 98 + "┘")
    lines.append("")

    # Query Box
    lines.append("┌" + "─" * 98 + "┐")
    lines.append("│" + " QUERY ".center(98) + "│")
    lines.append("├" + "─" * 98 + "┤")
    lines.append(f"│  GO Term:  {go_term} ({go_label})".ljust(99) + "│")
    lines.append(f"│  Disease:  {disease}".ljust(99) + "│")
    lines.append(f"│  Tissue:   {tissue}".ljust(99) + "│")
    lines.append("└" + "─" * 98 + "┘")
    lines.append("                                             │")
    lines.append("                                             ▼")

    # Layer 1: Knowledge Graph
    lines.append("┌" + "─" * 98 + "┐")
    lines.append("│" + " LAYER 1: KNOWLEDGE GRAPH DISCOVERY ".center(98) + "│")
    lines.append("│" + " (Ubergraph + Wikidata) ".center(98) + "│")
    lines.append("├" + "─" * 98 + "┤")
    lines.append("│".ljust(99) + "│")
    lines.append("│  ┌───────────────────────────────────────┐    ┌───────────────────────────────────────┐  │")
    lines.append("│  │           UBERGRAPH                   │    │              WIKIDATA                 │  │")
    lines.append("│  │        (GO Ontology)                  │    │         (Gene Annotations)           │  │")
    lines.append("│  ├───────────────────────────────────────┤    ├───────────────────────────────────────┤  │")
    lines.append(f"│  │  {go_term}                         │───►│  Query: genes annotated to            │  │")
    lines.append(f"│  │  + subclass terms                    │    │  these GO terms in humans            │  │")
    lines.append("│  └───────────────────────────────────────┘    └───────────────────────────────────────┘  │")
    lines.append("│".ljust(99) + "│")
    lines.append(f"│  RESULT: {n_genes} genes discovered".ljust(99) + "│")
    lines.append("│".ljust(99) + "│")

    # Show sample genes with GO terms
    lines.append("│  Gene → GO term mappings:".ljust(99) + "│")
    lines.append("│  ┌────────────┬───────────────────────────────────────────────────────────────────────┐  │")
    lines.append("│  │   Gene     │  GO Terms                                                             │  │")
    lines.append("│  ├────────────┼───────────────────────────────────────────────────────────────────────┤  │")
    for g in genes_with_terms:
        symbol = g.get("symbol", "")[:10]
        terms = g.get("go_terms", [])[:2]
        term_str = truncate(", ".join(terms), 65)
        line = f"│  │ {symbol:10} │ {term_str:65} │  │"
        lines.append(line)
    lines.append("│  └────────────┴───────────────────────────────────────────────────────────────────────┘  │")

    lines.append("│".ljust(99) + "│")
    lines.append("└" + "─" * 98 + "┘")
    lines.append("                                             │")
    gene_list = ", ".join(sample_genes[:6])
    if len(sample_genes) > 6:
        gene_list += ", ..."
    lines.append(f"                    Genes: {gene_list}")
    lines.append("                                             │")
    lines.append("                                             ▼")

    # Layer 2: Single-Cell
    lines.append("┌" + "─" * 98 + "┐")
    lines.append("│" + " LAYER 2: SINGLE-CELL EXPRESSION ANALYSIS ".center(98) + "│")
    lines.append("│" + " (CellxGene Census) ".center(98) + "│")
    lines.append("├" + "─" * 98 + "┤")
    lines.append("│".ljust(99) + "│")
    lines.append("│  ┌────────────────────────────────────────────┐  ┌────────────────────────────────────┐  │")
    lines.append(f"│  │  NORMAL {tissue.upper()[:25]:25}        │  │  {truncate(disease.upper(), 30):30}  │  │")
    lines.append("│  │  (control cells)                           │  │  (disease cells)                   │  │")
    lines.append("│  └────────────────────────────────────────────┘  └────────────────────────────────────┘  │")
    lines.append("│                             │                           │                                │")
    lines.append("│                             └───────────┬───────────────┘                                │")
    lines.append("│                                         ▼                                                │")
    lines.append("│                             Compare expression per cell type                             │")
    lines.append("│".ljust(99) + "│")
    lines.append("│  ┌──────────────────────────────────────────────────────────────────────────────────────────┐  │")
    lines.append(f"│  │  TISSUE-LEVEL SUMMARY ({tissue}, normal vs {truncate(disease, 35)})".ljust(96) + "│  │")
    lines.append("│  ├──────────────────────────────────────────────────────────────────────────────────────────┤  │")
    n_analyzed = layer2.get("n_genes_analyzed", n_genes)
    lines.append(f"│  │  {n_upregulated} of {n_analyzed} genes UPREGULATED (max FC > 1.5 in at least one cell type)".ljust(96) + "│  │")
    lines.append(f"│  │  {n_downregulated} of {n_analyzed} genes DOWNREGULATED (max FC < 0.67 across all cell types)".ljust(96) + "│  │")
    lines.append("│  │".ljust(96) + "│  │")
    lines.append("│  │  (A gene is 'upregulated' if ANY cell type shows FC > 1.5)".ljust(96) + "│  │")
    lines.append("│  │  (A gene is 'downregulated' only if ALL cell types show FC < 0.67)".ljust(96) + "│  │")
    lines.append("│  └──────────────────────────────────────────────────────────────────────────────────────────┘  │")
    lines.append("│".ljust(99) + "│")

    # Top upregulated table
    lines.append("│  Top Upregulated Genes (ranked by max fold change across cell types):".ljust(99) + "│")
    lines.append("│  ┌────────────┬────────────┬─────────────────────────────────────────────────────────┐  │")
    lines.append("│  │   Gene     │ Fold Change│  Top Cell Type                                          │  │")
    lines.append("│  ├────────────┼────────────┼─────────────────────────────────────────────────────────┤  │")
    for g in top_upregulated:
        symbol = g.get("symbol", "")[:10]
        fc = g.get("fold_change", 0)
        ct = truncate(g.get("top_cell_type", ""), 50)
        line = f"│  │ {symbol:10} │ {fc:10.2f} │ {ct:55} │  │"
        lines.append(line)
    lines.append("│  └────────────┴────────────┴─────────────────────────────────────────────────────────┘  │")

    lines.append("│".ljust(99) + "│")

    # Cell type drivers table
    lines.append("│  ┌──────────────────────────────────────────────────────────────────────────────────────────┐  │")
    lines.append("│  │  CELL-TYPE LEVEL BREAKDOWN (drilling down within the tissue)".ljust(96) + "│  │")
    lines.append("│  ├──────────────────────────────────────────────────────────────────────────────────────────┤  │")
    lines.append("│  │  Shows expression changes within each specific cell population.".ljust(96) + "│  │")
    lines.append("│  │  Note: The SAME gene can be UP in one cell type and DOWN in another!".ljust(96) + "│  │")
    lines.append("│  │  (e.g., CD19 is UP 3x in lymphocytes but DOWN in NK cells and monocytes)".ljust(96) + "│  │")
    lines.append("│  └──────────────────────────────────────────────────────────────────────────────────────────┘  │")
    lines.append("│  ┌─────────────────────────────────┬─────┬─────┬───────────────────────────────────┐  │")
    lines.append("│  │  Cell Type                      │  ↑  │  ↓  │  Genes changed in this cell type  │  │")
    lines.append("│  ├─────────────────────────────────┼─────┼─────┼───────────────────────────────────┤  │")
    for ct in cell_type_drivers:
        ct_name = truncate(ct.get("cell_type", ""), 30)
        n_up = ct.get("n_upregulated", 0)
        n_down = ct.get("n_downregulated", 0)
        genes = ct.get("genes", [])[:5]
        genes_str = truncate(", ".join(genes), 33)
        line = f"│  │ {ct_name:31} │ {n_up:3} │ {n_down:3} │ {genes_str:33} │  │"
        lines.append(line)
    lines.append("│  └─────────────────────────────────┴─────┴─────┴───────────────────────────────────┘  │")

    lines.append("│".ljust(99) + "│")
    lines.append("└" + "─" * 98 + "┘")
    lines.append("                                             │")

    # Show genes flowing to Layer 3 with explanation
    # Use genes_queried from Layer 3 as source of truth (JSON may truncate top_upregulated)
    genes_to_layer3 = layer3.get("genes_queried", [g.get("symbol", "") for g in top_upregulated])
    n_genes_to_layer3 = len(genes_to_layer3)
    genes_display = genes_to_layer3[:5]
    genes_str = ", ".join(genes_display) + ("..." if n_genes_to_layer3 > 5 else "")

    lines.append(f"                    ┌─────────────────────────────────────────────────────────┐")
    lines.append(f"                    │ GENES PASSED TO LAYER 3: {n_genes_to_layer3} upregulated genes from above│")
    lines.append(f"                    │ (ranked by max fold change at tissue level)            │")
    padding = 52 - len(genes_str)
    lines.append(f"                    │ → {genes_str}" + " " * max(0, padding) + "│")
    lines.append(f"                    └─────────────────────────────────────────────────────────┘")
    lines.append("                                             │")
    lines.append("                                             ▼")

    # Layer 3: Bulk Validation
    lines.append("┌" + "─" * 98 + "┐")
    lines.append("│" + " LAYER 3: BULK RNA-SEQ VALIDATION ".center(98) + "│")
    lines.append("│" + " (ARCHS4 / GEO) ".center(98) + "│")
    lines.append("├" + "─" * 98 + "┤")
    lines.append("│".ljust(99) + "│")
    lines.append("│  ┌──────────────────────────────────────────────────────────────────────────────────────────┐  │")
    lines.append("│  │  VALIDATION HYPOTHESIS:                                                                  │  │")
    lines.append("│  │  Do the genes upregulated in single-cell (Layer 2) also show upregulation in             │  │")
    lines.append("│  │  independent bulk RNA-seq studies from GEO?                                              │  │")
    lines.append("│  │                                                                                          │  │")
    control_term = query.get("control_term", f"normal {tissue}")
    lines.append(f"│  │  Test: Compare expression in '{truncate(disease, 35)}' samples".ljust(96) + "│  │")
    lines.append(f"│  │        vs '{truncate(control_term, 35)}' samples from ARCHS4".ljust(96) + "│  │")
    lines.append("│  └──────────────────────────────────────────────────────────────────────────────────────────┘  │")
    lines.append("│".ljust(99) + "│")

    # Show detailed ARCHS4 statistics
    lines.append("│  ┌──────────────────────────────────────────────────────────────────────────────────────────┐  │")
    lines.append("│  │  ARCHS4 DATA AVAILABILITY:                                                              │  │")
    lines.append("│  ├──────────────────────────────────────────────────────────────────────────────────────────┤  │")

    # Studies line
    if n_studies_in_metadata > 0:
        lines.append(f"│  │  Studies:  {n_studies} with expression data (examined {n_studies_examined} of {n_studies_in_metadata} in metadata)".ljust(96) + "│  │")
    else:
        lines.append(f"│  │  Studies:  {n_studies} with expression data".ljust(96) + "│  │")

    # Disease samples line
    if n_disease_samples_data > 0 or n_disease_samples_metadata > 0:
        lines.append(f"│  │  Disease:  {n_disease_samples_data} samples with data (of {n_disease_samples_metadata} in metadata)".ljust(96) + "│  │")
    else:
        lines.append(f"│  │  Disease:  {n_disease_samples_metadata} samples in metadata".ljust(96) + "│  │")

    # Control samples line
    if n_control_samples_data > 0 or n_control_samples_metadata > 0:
        lines.append(f"│  │  Control:  {n_control_samples_data} samples with data (of {n_control_samples_metadata} in metadata)".ljust(96) + "│  │")
    else:
        lines.append(f"│  │  Control:  {n_control_samples_metadata} samples in metadata".ljust(96) + "│  │")

    # Show failure reasons if available
    if study_stats:
        no_expr = study_stats.get("no_expression_data", 0)
        empty_expr = study_stats.get("expression_empty", 0)
        if no_expr > 0 or empty_expr > 0:
            lines.append("│  │".ljust(96) + "│  │")
            lines.append(f"│  │  Note: {no_expr} studies had no expression data in HDF5, {empty_expr} had empty results".ljust(96) + "│  │")

    lines.append("│  └──────────────────────────────────────────────────────────────────────────────────────────┘  │")
    lines.append("│".ljust(99) + "│")

    # Disease Studies with sample details
    if studies:
        lines.append("│  ╔═══════════════════════════════════════════════════════════════════════════════════════════╗  │")
        lines.append("│  ║  DISEASE STUDIES                                                                          ║  │")
        lines.append("│  ╠═══════════════════════════════════════════════════════════════════════════════════════════╣  │")
        for s in studies:
            gse = s.get("gse", "")
            title = truncate(s.get("study_title", ""), 60)
            n_samp = s.get("n_samples", 0)
            n_genes_det = s.get("n_genes_detected", 0)
            lines.append(f"│  ║  {gse}: {title}".ljust(95) + "║  │")
            lines.append(f"│  ║    Samples: {n_samp}  |  Genes detected: {n_genes_det}".ljust(95) + "║  │")

            # Show sample info
            sample_info = s.get("sample_info", [])[:5]
            if sample_info:
                lines.append("│  ║    Sample Details:".ljust(95) + "║  │")
                for si in sample_info:
                    gsm = si.get("gsm", "")
                    stitle = truncate(si.get("title", ""), 60)
                    source = truncate(si.get("source", ""), 70)
                    lines.append(f"│  ║      • {gsm}: {stitle}".ljust(95) + "║  │")
                    lines.append(f"│  ║        Source: {source}".ljust(95) + "║  │")

            # Show detected genes
            genes_detected = s.get("genes_detected", [])[:10]
            if genes_detected:
                genes_str = ", ".join(genes_detected)
                lines.append(f"│  ║    Genes: {truncate(genes_str, 78)}".ljust(95) + "║  │")

        lines.append("│  ╚═══════════════════════════════════════════════════════════════════════════════════════════╝  │")

    lines.append("│".ljust(99) + "│")

    # Control Samples
    if control_samples:
        lines.append("│  ╔═══════════════════════════════════════════════════════════════════════════════════════════╗  │")
        lines.append("│  ║  CONTROL SAMPLES                                                                          ║  │")
        lines.append("│  ╠═══════════════════════════════════════════════════════════════════════════════════════════╣  │")
        for cs in control_samples:
            gsm = cs.get("gsm", "")
            series = cs.get("series", "")
            title = truncate(cs.get("title", ""), 60)
            source = truncate(cs.get("source", ""), 70)
            lines.append(f"│  ║  • {gsm} ({series}): {title}".ljust(95) + "║  │")
            lines.append(f"│  ║    Source: {source}".ljust(95) + "║  │")
        lines.append("│  ╚═══════════════════════════════════════════════════════════════════════════════════════════╝  │")

    lines.append("│".ljust(99) + "│")

    # Differential expression
    lines.append("│  Differential Expression (Disease vs Controls):".ljust(99) + "│")
    lines.append("│  ┌────────────┬────────────┬────────────┬────────────┬──────────┬─────────────────────────┐  │")
    lines.append("│  │   Gene     │  Disease   │  Control   │ Fold Change│ Log2 FC  │    Interpretation       │  │")
    lines.append("│  ├────────────┼────────────┼────────────┼────────────┼──────────┼─────────────────────────┤  │")

    for de in diff_expr:
        gene = de.get("gene", "")[:10]
        mean_d = de.get("mean_disease", 0)
        mean_c = de.get("mean_control", 0)
        fc = de.get("fold_change", 0)
        log2_fc = de.get("log2_fc", 0) or 0
        if fc > 2:
            interp = "STRONGLY UP"
        elif fc > 1.5:
            interp = "UP"
        elif fc < 0.5:
            interp = "STRONGLY DOWN"
        elif fc < 0.67:
            interp = "DOWN"
        else:
            interp = "UNCHANGED"
        line = f"│  │ {gene:10} │ {mean_d:10.1f} │ {mean_c:10.1f} │ {fc:10.2f} │ {log2_fc:8.2f} │ {interp:23} │  │"
        lines.append(line)

    lines.append("│  └────────────┴────────────┴────────────┴────────────┴──────────┴─────────────────────────┘  │")
    lines.append("│".ljust(99) + "│")
    lines.append("└" + "─" * 98 + "┘")
    lines.append("                                             │")
    lines.append("                                             ▼")

    # Layer 4: Summary
    lines.append("┌" + "─" * 98 + "┐")
    lines.append("│" + " LAYER 4: INTEGRATED CONCLUSIONS ".center(98) + "│")
    lines.append("├" + "─" * 98 + "┤")
    lines.append("│".ljust(99) + "│")

    # Key findings
    lines.append("│  KEY FINDINGS:".ljust(99) + "│")
    lines.append("│".ljust(99) + "│")

    # Finding 1: Top gene
    if diff_expr:
        top_de = diff_expr[0]
        finding1 = f"  1. {top_de.get('gene', 'N/A')} shows {top_de.get('fold_change', 0):.1f}x expression in {disease}"
        lines.append(f"│{finding1}".ljust(99) + "│")

    # Finding 2: Cell type
    if cell_type_drivers:
        top_ct = cell_type_drivers[0]
        finding2 = f"  2. {top_ct.get('cell_type', 'N/A')} is the primary driver ({top_ct.get('n_upregulated', 0)} genes upregulated)"
        lines.append(f"│{finding2}".ljust(99) + "│")

    # Finding 3: Validation
    if diff_expr and len(diff_expr) > 1:
        validated = [de for de in diff_expr if de.get("fold_change", 1) > 1.5]
        finding3 = f"  3. {len(validated)} of {len(diff_expr)} top genes validated in bulk RNA-seq (GEO)"
        lines.append(f"│{finding3}".ljust(99) + "│")

    # Finding 4: Top validated genes
    if diff_expr:
        top_validated = [de.get("gene", "") for de in diff_expr[:3] if de.get("fold_change", 1) > 1.5]
        if top_validated:
            finding4 = f"  4. Most strongly validated: {', '.join(top_validated)}"
            lines.append(f"│{finding4}".ljust(99) + "│")

    lines.append("│".ljust(99) + "│")

    # Provenance summary
    lines.append("│  DATA PROVENANCE:".ljust(99) + "│")
    lines.append(f"│    • GO terms: Ubergraph (subclasses of {go_term})".ljust(99) + "│")
    lines.append(f"│    • Gene annotations: Wikidata (human protein → GO term links)".ljust(99) + "│")
    lines.append(f"│    • Single-cell: CellxGene Census ({tissue}, normal vs {disease})".ljust(99) + "│")
    if studies:
        gse_ids = [s.get("gse", "") for s in studies]
        lines.append(f"│    • Bulk validation: ARCHS4/GEO ({', '.join(gse_ids)})".ljust(99) + "│")
        # List GSM numbers
        all_disease_gsms = []
        for s in studies:
            for si in s.get("sample_info", []):
                all_disease_gsms.append(si.get("gsm", ""))
        if all_disease_gsms:
            gsm_str = truncate(", ".join(all_disease_gsms[:10]), 70)
            lines.append(f"│      Disease samples: {gsm_str}".ljust(99) + "│")
        if control_samples:
            ctrl_gsms = [cs.get("gsm", "") for cs in control_samples[:10]]
            ctrl_str = truncate(", ".join(ctrl_gsms), 70)
            lines.append(f"│      Control samples: {ctrl_str}".ljust(99) + "│")

    lines.append("│".ljust(99) + "│")
    lines.append("└" + "─" * 98 + "┘")

    # LLM Summary section
    if llm_summary:
        lines.append("")
        lines.append("┌" + "─" * 98 + "┐")
        lines.append("│" + " LLM-GENERATED SUMMARY ".center(98) + "│")
        lines.append("├" + "─" * 98 + "┤")
        lines.append("│".ljust(99) + "│")

        # Wrap the LLM summary text to fit within the box
        for paragraph in llm_summary.split('\n\n'):
            if paragraph.strip():
                # Handle markdown headers
                if paragraph.startswith('##'):
                    header = paragraph.replace('##', '').strip()
                    lines.append(f"│  {header}".ljust(99) + "│")
                    lines.append("│  " + "-" * 60 + "".ljust(35) + "│")
                else:
                    # Wrap regular text
                    wrapped = wrap_text(paragraph.strip(), 94, "  ")
                    for wline in wrapped:
                        lines.append(f"│{wline}".ljust(99) + "│")
                lines.append("│".ljust(99) + "│")

        lines.append("└" + "─" * 98 + "┘")

    # Footer
    lines.append("")
    lines.append("=" * 100)
    lines.append(f"  Analysis timestamp: {data.get('timestamp', 'N/A')}")
    lines.append("=" * 100)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Visualize GO Disease Analyzer results as ASCII provenance diagram"
    )
    parser.add_argument("input_file", help="JSON results file from go_disease_analyzer.py")
    parser.add_argument("--output", "-o", help="Output file (default: print to stdout)")

    args = parser.parse_args()

    # Load input file
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    with open(input_path) as f:
        data = json.load(f)

    # Generate visualization
    viz = generate_visualization(data)

    # Output
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w") as f:
            f.write(viz)
        print(f"Visualization saved to: {output_path}")
    else:
        print(viz)


if __name__ == "__main__":
    main()
