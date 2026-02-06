"""
GXA GSEA extractor.

Extracts pathway enrichment results from GXA Gene Set Enrichment Analysis files.
Creates flat enrichment DataFrames for the rdf_builder's 1-hop ENRICHED_IN pattern.
"""

from pathlib import Path
from typing import Dict, List

import pandas as pd

from .parser import (
    GEAExperiment,
    parse_gsea_file,
    get_gsea_enrichment_type,
    get_contrast_from_gsea_filename,
)


def extract_gsea_results(
    experiment: GEAExperiment,
    p_value_threshold: float = 0.01,
    max_terms_per_type: int = 20,
) -> pd.DataFrame:
    """
    Extract all GSEA enrichment results from a GXA experiment.

    Returns a flat DataFrame with one row per enrichment result,
    suitable for the rdf_builder's 1-hop ENRICHED_IN pattern.

    Args:
        experiment: Parsed GEAExperiment object
        p_value_threshold: Adjusted p-value threshold for significance
        max_terms_per_type: Maximum enriched terms per type per contrast

    Returns:
        DataFrame with columns: term_id, term_name, enrichment_type,
        contrast_id, experiment_accession, adj_p_value, effect_size, etc.
    """
    all_results = []

    for gsea_file in experiment.gsea_files:
        filename = Path(gsea_file).name
        enrichment_type = get_gsea_enrichment_type(filename)
        contrast_id = get_contrast_from_gsea_filename(filename)

        if enrichment_type == "unknown" or not contrast_id:
            continue

        try:
            df = parse_gsea_file(gsea_file)

            df["enrichment_type"] = enrichment_type
            df["contrast_id"] = contrast_id
            df["experiment_accession"] = experiment.accession
            df["source_file"] = filename

            if "adj_p_value" in df.columns:
                df = df[df["adj_p_value"] <= p_value_threshold]
                df = df.sort_values("adj_p_value").head(max_terms_per_type)

            if not df.empty:
                all_results.append(df)

        except Exception as e:
            print(f"Warning: Failed to parse {gsea_file}: {e}")

    if all_results:
        return pd.concat(all_results, ignore_index=True)

    return pd.DataFrame()


def create_go_term_nodes(gsea_results: pd.DataFrame) -> pd.DataFrame:
    """Create GOTerm proxy nodes from GO enrichment results."""
    go_results = gsea_results[gsea_results["enrichment_type"] == "go"]

    if go_results.empty:
        return pd.DataFrame(columns=["identifier", "name"])

    go_terms = []
    seen = set()

    for _, row in go_results.iterrows():
        term_id = row.get("term_id", row.get("Accession", ""))
        if term_id and term_id not in seen:
            seen.add(term_id)
            term_name = row.get("term_name", row.get("Term", ""))
            go_terms.append({
                "identifier": term_id,
                "name": term_name,
            })

    return pd.DataFrame(go_terms)


def create_reactome_pathway_nodes(gsea_results: pd.DataFrame) -> pd.DataFrame:
    """Create ReactomePathway proxy nodes from Reactome enrichment results."""
    reactome_results = gsea_results[gsea_results["enrichment_type"] == "reactome"]

    if reactome_results.empty:
        return pd.DataFrame(columns=["identifier", "name"])

    pathways = []
    seen = set()

    for _, row in reactome_results.iterrows():
        term_id = row.get("term_id", row.get("Accession", ""))
        if term_id and term_id not in seen:
            seen.add(term_id)
            pathways.append({
                "identifier": term_id,
                "name": row.get("term_name", row.get("Term", "")),
            })

    return pd.DataFrame(pathways)


def create_interpro_domain_nodes(gsea_results: pd.DataFrame) -> pd.DataFrame:
    """Create InterProDomain proxy nodes from InterPro enrichment results."""
    interpro_results = gsea_results[gsea_results["enrichment_type"] == "interpro"]

    if interpro_results.empty:
        return pd.DataFrame(columns=["identifier", "name"])

    domains = []
    seen = set()

    for _, row in interpro_results.iterrows():
        term_id = row.get("term_id", row.get("Accession", ""))
        if term_id and term_id not in seen:
            seen.add(term_id)
            domains.append({
                "identifier": term_id,
                "name": row.get("term_name", row.get("Term", "")),
            })

    return pd.DataFrame(domains)
