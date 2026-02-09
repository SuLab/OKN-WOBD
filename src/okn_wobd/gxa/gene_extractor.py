"""
GXA Gene extractor.

Extracts gene nodes from GXA differential expression analytics files.
Maps Ensembl IDs to NCBI gene IDs for human genes.
"""

from typing import Dict

import pandas as pd

from .parser import GEAExperiment, parse_analytics_file, get_organism_taxonomy
from .gene_id_mapper import get_ensembl_to_ncbi_map, add_ncbi_gene_ids


def extract_genes_from_analytics(
    analytics_file: str,
    organism: str = "",
    taxonomy: str = "",
) -> pd.DataFrame:
    """
    Extract gene information from a GXA analytics file.

    Args:
        analytics_file: Path to analytics TSV file
        organism: Organism name
        taxonomy: NCBI taxonomy ID

    Returns:
        DataFrame with gene information including NCBI and Ensembl IDs
    """
    df = parse_analytics_file(analytics_file)

    genes = df[["gene_id", "gene_name"]].drop_duplicates()
    genes = genes[genes["gene_id"].notna() & (genes["gene_id"] != "")]

    genes["organism"] = organism
    genes["taxonomy"] = taxonomy

    genes = genes.rename(columns={
        "gene_id": "ensembl_id",
        "gene_name": "symbol",
    })

    genes["name"] = ""

    # For human genes, map Ensembl IDs to NCBI gene IDs
    if taxonomy == "9606":
        genes = add_ncbi_gene_ids(genes, ensembl_col="ensembl_id", ncbi_col="ncbi_gene_id")
        genes["identifier"] = genes["ncbi_gene_id"].fillna(genes["ensembl_id"])
        genes["id_source"] = genes["ncbi_gene_id"].apply(
            lambda x: "NCBIGene" if pd.notna(x) else "Ensembl"
        )
    else:
        genes["identifier"] = genes["ensembl_id"]
        genes["ncbi_gene_id"] = None
        genes["id_source"] = "Ensembl"

    return genes[["identifier", "ensembl_id", "ncbi_gene_id", "symbol", "name", "organism", "taxonomy", "id_source"]]


def extract_genes_from_experiment(experiment: GEAExperiment) -> pd.DataFrame:
    """Extract all unique genes from a GXA experiment."""
    all_genes = []

    taxonomy = experiment.taxonomy_id
    if not taxonomy:
        taxonomy = get_organism_taxonomy(experiment.organism)

    for analytics_file in experiment.analytics_files:
        genes = extract_genes_from_analytics(
            analytics_file,
            organism=experiment.organism,
            taxonomy=taxonomy,
        )
        all_genes.append(genes)

    if all_genes:
        combined = pd.concat(all_genes, ignore_index=True)
        combined = combined.drop_duplicates(subset="identifier")
        return combined

    return pd.DataFrame(columns=["identifier", "ensembl_id", "ncbi_gene_id", "symbol", "name", "organism", "taxonomy", "id_source"])


def create_mgene_nodes(experiment: GEAExperiment) -> pd.DataFrame:
    """Create gene nodes from a GXA experiment."""
    return extract_genes_from_experiment(experiment)


def extract_differential_expression(
    experiment: GEAExperiment,
    p_value_threshold: float = 0.01,
    max_genes_per_assay: int = 200,
) -> pd.DataFrame:
    """
    Extract differential expression data for creating Assay-Gene relationships.

    Args:
        experiment: Parsed GEAExperiment object
        p_value_threshold: Adjusted p-value threshold for significance
        max_genes_per_assay: Maximum number of DE genes to include per assay

    Returns:
        DataFrame with columns: from, to, log2fc, adj_p_value
    """
    all_de = []

    taxonomy = experiment.taxonomy_id
    if not taxonomy:
        taxonomy = get_organism_taxonomy(experiment.organism)

    # Build Ensembl -> identifier mapping for human genes
    ensembl_to_identifier: Dict[str, str] = {}
    if taxonomy == "9606":
        ncbi_map = get_ensembl_to_ncbi_map()
        ensembl_to_identifier = {k: v if v else k for k, v in ncbi_map.items()}

    for analytics_file in experiment.analytics_files:
        df = parse_analytics_file(analytics_file)

        for contrast in experiment.contrasts:
            contrast_id = contrast.id

            pval_col = f"{contrast_id}.p-value"
            log2fc_col = f"{contrast_id}.log2foldchange"

            if pval_col not in df.columns or log2fc_col not in df.columns:
                continue

            de_data = df[["gene_id", pval_col, log2fc_col]].copy()
            de_data = de_data.rename(columns={
                pval_col: "p_value",
                log2fc_col: "log2fc",
            })

            de_data = de_data[de_data["p_value"].notna()]
            de_data = de_data[de_data["p_value"] <= p_value_threshold]

            if de_data.empty:
                continue

            de_data = de_data.sort_values("p_value").head(max_genes_per_assay)

            assay_id = f"{experiment.accession}-{contrast_id}"
            de_data["assay_id"] = assay_id

            if taxonomy == "9606" and ensembl_to_identifier:
                de_data["to"] = de_data["gene_id"].map(
                    lambda x: ensembl_to_identifier.get(x, x)
                )
            else:
                de_data["to"] = de_data["gene_id"]

            de_data["from"] = assay_id

            all_de.append(de_data[["from", "to", "log2fc", "p_value"]])

    if all_de:
        combined = pd.concat(all_de, ignore_index=True)
        combined = combined.rename(columns={"p_value": "adj_p_value"})
        return combined

    return pd.DataFrame(columns=["from", "to", "log2fc", "adj_p_value"])
