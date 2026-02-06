"""
GXA (Gene Expression Atlas) file parser.

Parses the various file formats used in GXA experiment archives:
- IDF (Investigation Description Format) - experiment metadata
- SDRF (Sample and Data Relationship Format) - sample metadata
- configuration.xml - assay groups and contrasts
- analytics.tsv - differential expression results
- GSEA .tsv files - pathway enrichment results
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


@dataclass
class AssayGroup:
    """Represents an assay group (set of samples with same condition)."""

    id: str
    label: str
    samples: List[str] = field(default_factory=list)


@dataclass
class Contrast:
    """Represents a contrast (comparison between two assay groups)."""

    id: str
    name: str
    reference_group_id: str
    test_group_id: str
    array_design: str = ""


@dataclass
class GEAExperiment:
    """
    Data class representing a complete GXA experiment.

    Contains all parsed metadata and references to data files.
    """

    accession: str
    title: str = ""
    description: str = ""
    organism: str = ""
    taxonomy_id: str = ""

    # Submitter information
    submitter_name: str = ""
    submitter_email: str = ""
    submitter_affiliation: str = ""

    # Experimental factors
    experimental_factors: List[str] = field(default_factory=list)

    # Array designs used
    array_designs: List[str] = field(default_factory=list)

    # Assay groups and contrasts
    assay_groups: Dict[str, AssayGroup] = field(default_factory=dict)
    contrasts: List[Contrast] = field(default_factory=list)

    # Sample information
    samples: List[Dict[str, Any]] = field(default_factory=list)

    # File paths
    experiment_dir: str = ""
    analytics_files: List[str] = field(default_factory=list)
    gsea_files: List[str] = field(default_factory=list)

    # Cross-references
    secondary_accessions: List[str] = field(default_factory=list)
    pubmed_id: str = ""
    publication_title: str = ""


def parse_idf_file(idf_path: str) -> Dict[str, Any]:
    """
    Parse an IDF (Investigation Description Format) file.

    The IDF file contains experiment-level metadata in tab-delimited format
    with keys in the first column and values in subsequent columns.

    Args:
        idf_path: Path to the IDF file (e.g., E-GEOD-5305.idf.txt)

    Returns:
        Dictionary with parsed metadata
    """
    metadata = {
        "title": "",
        "description": "",
        "submitter_last_name": "",
        "submitter_first_name": "",
        "submitter_email": "",
        "submitter_affiliation": "",
        "experimental_factors": [],
        "secondary_accessions": [],
        "pubmed_id": "",
        "publication_title": "",
        "release_date": "",
    }

    with open(idf_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 2:
                continue

            key = parts[0].strip()
            values = [p.strip() for p in parts[1:] if p.strip()]

            if key == "Investigation Title":
                metadata["title"] = values[0] if values else ""
            elif key == "Experiment Description":
                metadata["description"] = values[0] if values else ""
            elif key == "Person Last Name":
                metadata["submitter_last_name"] = values[0] if values else ""
            elif key == "Person First Name":
                metadata["submitter_first_name"] = values[0] if values else ""
            elif key == "Person Email":
                metadata["submitter_email"] = values[0] if values else ""
            elif key == "Person Affiliation":
                metadata["submitter_affiliation"] = values[0] if values else ""
            elif key == "Experimental Factor Name":
                metadata["experimental_factors"] = values
            elif key == "Comment[SecondaryAccession]":
                metadata["secondary_accessions"].extend(values)
            elif key == "PubMed ID":
                metadata["pubmed_id"] = values[0] if values else ""
            elif key == "Publication Title":
                metadata["publication_title"] = values[0] if values else ""
            elif key == "Public Release Date":
                metadata["release_date"] = values[0] if values else ""

    return metadata


def parse_sdrf_file(sdrf_path: str, include_uris: bool = True) -> pd.DataFrame:
    """
    Parse a condensed SDRF (Sample and Data Relationship Format) file.

    The condensed SDRF has columns:
    - ExperimentID (accession)
    - ArrayDesign
    - SampleID
    - PropertyType (characteristic/factor)
    - PropertyName
    - PropertyValue
    - OntologyURI (optional)

    Args:
        sdrf_path: Path to condensed SDRF file
        include_uris: Whether to include ontology URIs

    Returns:
        DataFrame with sample metadata in wide format
    """
    # Standard column names for condensed SDRF
    sdrf_headers = [
        "Accession", "Array", "Sample", "Annot_type",
        "Annot", "Annot_value", "Annot_ont_URI"
    ]

    df = pd.read_csv(sdrf_path, sep="\t", names=sdrf_headers, na_values=[""])

    # Get unique samples
    samples = df["Sample"].unique()

    # Get all annotation types
    characteristics = sorted(df[df["Annot_type"] == "characteristic"]["Annot"].unique())
    factors = sorted(df[df["Annot_type"] == "factor"]["Annot"].unique())

    # Build wide format
    rows = []
    for sample in samples:
        sample_df = df[df["Sample"] == sample]
        row = {"Sample": sample}

        # Get characteristics
        for char in characteristics:
            char_values = sample_df[
                (sample_df["Annot_type"] == "characteristic") &
                (sample_df["Annot"] == char)
            ]
            if not char_values.empty:
                row[f"characteristic:{char}"] = char_values["Annot_value"].iloc[0]
                if include_uris:
                    uri = char_values["Annot_ont_URI"].iloc[0]
                    row[f"{char}_URI"] = uri if pd.notna(uri) else ""

        # Get factors
        for fac in factors:
            fac_values = sample_df[
                (sample_df["Annot_type"] == "factor") &
                (sample_df["Annot"] == fac)
            ]
            if not fac_values.empty:
                row[f"factor:{fac}"] = fac_values["Annot_value"].iloc[0]
                if include_uris:
                    uri = fac_values["Annot_ont_URI"].iloc[0]
                    row[f"{fac}_URI"] = uri if pd.notna(uri) else ""

        rows.append(row)

    return pd.DataFrame(rows)


def parse_configuration_xml(config_path: str) -> Tuple[Dict[str, AssayGroup], List[Contrast]]:
    """
    Parse the GXA configuration.xml file.

    This file defines:
    - Array designs used in the experiment
    - Assay groups (sets of samples with same experimental condition)
    - Contrasts (comparisons between assay groups)

    Args:
        config_path: Path to configuration.xml

    Returns:
        Tuple of (assay_groups dict, contrasts list)
    """
    tree = ET.parse(config_path)
    root = tree.getroot()

    all_assay_groups = {}
    all_contrasts = []

    # Process each analytics section (one per array design)
    for analytics in root.findall("analytics"):
        array_design = ""
        array_elem = analytics.find("array_design")
        if array_elem is not None and array_elem.text:
            array_design = array_elem.text.strip()

        # Parse assay groups
        assay_groups_elem = analytics.find("assay_groups")
        if assay_groups_elem is not None:
            for group_elem in assay_groups_elem.findall("assay_group"):
                group_id = group_elem.get("id", "")
                label = group_elem.get("label", "")

                samples = []
                for assay_elem in group_elem.findall("assay"):
                    if assay_elem.text:
                        samples.append(assay_elem.text.strip())

                all_assay_groups[group_id] = AssayGroup(
                    id=group_id,
                    label=label,
                    samples=samples,
                )

        # Parse contrasts
        contrasts_elem = analytics.find("contrasts")
        if contrasts_elem is not None:
            for contrast_elem in contrasts_elem.findall("contrast"):
                contrast_id = contrast_elem.get("id", "")

                name_elem = contrast_elem.find("name")
                name = name_elem.text.strip() if name_elem is not None and name_elem.text else ""

                ref_elem = contrast_elem.find("reference_assay_group")
                ref_group = ref_elem.text.strip() if ref_elem is not None and ref_elem.text else ""

                test_elem = contrast_elem.find("test_assay_group")
                test_group = test_elem.text.strip() if test_elem is not None and test_elem.text else ""

                all_contrasts.append(Contrast(
                    id=contrast_id,
                    name=name,
                    reference_group_id=ref_group,
                    test_group_id=test_group,
                    array_design=array_design,
                ))

    return all_assay_groups, all_contrasts


def parse_analytics_file(analytics_path: str) -> pd.DataFrame:
    """
    Parse a GXA analytics TSV file containing differential expression results.

    The file has columns:
    - Gene ID (Ensembl ID)
    - Gene Name (symbol)
    - Design Element (probe set ID)
    - For each contrast: {contrast_id}.p-value, {contrast_id}.t-statistic, {contrast_id}.log2foldchange

    Args:
        analytics_path: Path to analytics TSV file

    Returns:
        DataFrame with differential expression data
    """
    df = pd.read_csv(analytics_path, sep="\t", low_memory=False)

    # Standardize column names
    df = df.rename(columns={
        "Gene ID": "gene_id",
        "Gene Name": "gene_name",
        "Design Element": "design_element",
    })

    return df


def parse_gsea_file(gsea_path: str) -> pd.DataFrame:
    """
    Parse a GXA GSEA (Gene Set Enrichment Analysis) results file.

    Args:
        gsea_path: Path to GSEA TSV file

    Returns:
        DataFrame with GSEA results
    """
    df = pd.read_csv(gsea_path, sep="\t", low_memory=False)

    # In GXA GSEA files:
    #   "Term" column = ontology ID (e.g. GO:0000002, R-HSA-12345, IPR000001)
    #   "Accession" column = term name/description
    if "Term" in df.columns:
        df["term_id"] = df["Term"].astype(str)

    if "Accession" in df.columns:
        df["term_name"] = df["Accession"].astype(str)
    elif "Term" in df.columns:
        df["term_name"] = df["Term"].astype(str)

    # Standardize column names
    rename_map = {
        "Genes (tot)": "genes_total",
        "Stat (non-dir.) p": "p_value",
        "p adj (non-dir.)": "adj_p_value",
        "effect.size": "effect_size",
        "Significant..in.gene.set.": "significant_in_set",
        "Non.significant..in.gene.set.": "nonsignificant_in_set",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    return df


def get_gsea_enrichment_type(filename: str) -> str:
    """
    Determine the enrichment type from a GSEA filename.

    Args:
        filename: Filename like "E-GEOD-5305.g1_g3.go.gsea.tsv"

    Returns:
        Enrichment type: "go", "reactome", or "interpro"
    """
    filename_lower = filename.lower()
    if ".go.gsea" in filename_lower:
        return "go"
    elif ".reactome.gsea" in filename_lower:
        return "reactome"
    elif ".interpro.gsea" in filename_lower:
        return "interpro"
    return "unknown"


def get_contrast_from_gsea_filename(filename: str) -> str:
    """
    Extract contrast ID from a GSEA filename.

    Args:
        filename: Filename like "E-GEOD-5305.g1_g3.go.gsea.tsv"

    Returns:
        Contrast ID like "g1_g3"
    """
    match = re.search(r"\.(g\d+_g\d+)\.", filename)
    if match:
        return match.group(1)
    return ""


def find_gea_files(experiment_dir: str) -> Dict[str, List[str]]:
    """
    Find all GXA files in an experiment directory.

    Args:
        experiment_dir: Path to experiment directory

    Returns:
        Dictionary with file types as keys and lists of paths as values
    """
    exp_dir = Path(experiment_dir)
    accession = exp_dir.name.replace("-gea", "")

    files = {
        "idf": [],
        "sdrf": [],
        "config": [],
        "analytics": [],
        "gsea_go": [],
        "gsea_reactome": [],
        "gsea_interpro": [],
        "normalized_expressions": [],
    }

    for f in exp_dir.iterdir():
        if not f.is_file():
            continue

        name = f.name.lower()

        if name.endswith(".idf.txt"):
            files["idf"].append(str(f))
        elif name.endswith(".condensed-sdrf.tsv") or name.endswith(".sdrf.tsv"):
            files["sdrf"].append(str(f))
        elif name.endswith("-configuration.xml"):
            files["config"].append(str(f))
        elif name.endswith("-analytics.tsv") and ".undecorated" not in name:
            files["analytics"].append(str(f))
        elif ".go.gsea.tsv" in name and ".undecorated" not in name:
            files["gsea_go"].append(str(f))
        elif ".reactome.gsea.tsv" in name and ".undecorated" not in name:
            files["gsea_reactome"].append(str(f))
        elif ".interpro.gsea.tsv" in name and ".undecorated" not in name:
            files["gsea_interpro"].append(str(f))
        elif "normalized-expressions.tsv" in name and ".undecorated" not in name:
            files["normalized_expressions"].append(str(f))

    return files


def load_gea_experiment(experiment_dir: str) -> GEAExperiment:
    """
    Load all GXA files for an experiment into a structured GEAExperiment object.

    Args:
        experiment_dir: Path to experiment directory (e.g., "./E-GEOD-5305-gea/")

    Returns:
        GEAExperiment object with all parsed metadata
    """
    exp_dir = Path(experiment_dir)

    # Extract accession from directory name
    dir_name = exp_dir.name
    accession = dir_name.replace("-gea", "")

    # Find all files
    files = find_gea_files(experiment_dir)

    # Initialize experiment
    experiment = GEAExperiment(
        accession=accession,
        experiment_dir=str(exp_dir),
    )

    # Parse IDF file
    if files["idf"]:
        idf_data = parse_idf_file(files["idf"][0])
        experiment.title = idf_data["title"]
        experiment.description = idf_data["description"]
        experiment.submitter_name = f"{idf_data['submitter_first_name']} {idf_data['submitter_last_name']}".strip()
        experiment.submitter_email = idf_data["submitter_email"]
        experiment.submitter_affiliation = idf_data["submitter_affiliation"]
        experiment.experimental_factors = idf_data["experimental_factors"]
        experiment.secondary_accessions = idf_data["secondary_accessions"]
        experiment.pubmed_id = idf_data["pubmed_id"]

    # Parse SDRF file
    if files["sdrf"]:
        samples_df = parse_sdrf_file(files["sdrf"][0])
        experiment.samples = samples_df.to_dict("records")

        # Extract organism from samples
        for col in samples_df.columns:
            if "organism" in col.lower():
                organisms = samples_df[col].dropna().unique()
                if len(organisms) > 0:
                    experiment.organism = organisms[0]
                break

    # Parse configuration file
    if files["config"]:
        assay_groups, contrasts = parse_configuration_xml(files["config"][0])
        experiment.assay_groups = assay_groups
        experiment.contrasts = contrasts

        # Extract array designs
        experiment.array_designs = list(set(c.array_design for c in contrasts if c.array_design))

    # Store file paths
    experiment.analytics_files = files["analytics"]
    experiment.gsea_files = (
        files["gsea_go"] +
        files["gsea_reactome"] +
        files["gsea_interpro"]
    )

    return experiment


def get_organism_taxonomy(organism: str) -> str:
    """
    Get NCBI taxonomy ID for a given organism name.

    Args:
        organism: Organism name (e.g., "Mus musculus")

    Returns:
        NCBI taxonomy ID (e.g., "10090")
    """
    organism_map = {
        "mus musculus": "10090",
        "homo sapiens": "9606",
        "rattus norvegicus": "10116",
        "danio rerio": "7955",
        "drosophila melanogaster": "7227",
        "caenorhabditis elegans": "6239",
        "saccharomyces cerevisiae": "4932",
        "arabidopsis thaliana": "3702",
    }
    return organism_map.get(organism.lower(), "")
