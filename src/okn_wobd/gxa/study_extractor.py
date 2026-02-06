"""
GXA Study extractor.

Extracts Study node data from GXA experiments.
"""

from typing import Dict, List

import pandas as pd

from .parser import GEAExperiment, get_organism_taxonomy


def extract_study_nodes(experiment: GEAExperiment) -> pd.DataFrame:
    """
    Extract Study node data from a GXA experiment.

    Args:
        experiment: Parsed GEAExperiment object

    Returns:
        DataFrame with Study node data
    """
    taxonomy = experiment.taxonomy_id
    if not taxonomy and experiment.organism:
        taxonomy = get_organism_taxonomy(experiment.organism)

    study = {
        "identifier": experiment.accession,
        "name": experiment.accession,
        "project_title": experiment.title,
        "project_type": "Gene Expression Atlas",
        "description": experiment.description,
        "organism": experiment.organism,
        "taxonomy": taxonomy,
        "source": "GEA",
        "submitter_name": experiment.submitter_name,
        "submitter_email": experiment.submitter_email,
        "submitter_affiliation": experiment.submitter_affiliation,
    }

    if experiment.secondary_accessions:
        study["secondary_accessions"] = experiment.secondary_accessions

    if experiment.experimental_factors:
        study["experimental_factors"] = experiment.experimental_factors

    if experiment.pubmed_id:
        study["pubmed_id"] = experiment.pubmed_id

    return pd.DataFrame([study])


def extract_study_from_experiments(experiments: List[GEAExperiment]) -> pd.DataFrame:
    """Extract Study nodes from multiple GXA experiments."""
    studies = []
    for exp in experiments:
        study_df = extract_study_nodes(exp)
        studies.append(study_df)

    if studies:
        return pd.concat(studies, ignore_index=True)
    return pd.DataFrame()


def get_study_summary(experiment: GEAExperiment) -> Dict:
    """Get a summary of study information for logging/reporting."""
    return {
        "accession": experiment.accession,
        "title": experiment.title[:100] + "..." if len(experiment.title) > 100 else experiment.title,
        "organism": experiment.organism,
        "num_samples": len(experiment.samples),
        "num_contrasts": len(experiment.contrasts),
        "num_array_designs": len(experiment.array_designs),
        "experimental_factors": experiment.experimental_factors,
    }
