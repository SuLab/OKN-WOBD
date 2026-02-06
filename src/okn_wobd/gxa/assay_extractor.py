"""
GXA Assay extractor.

Extracts Assay nodes from GXA experiments based on contrasts defined
in the configuration.xml file. Also extracts characteristic and factor
nodes from SDRF sample metadata.
"""

from typing import Dict, List, Set

import pandas as pd

from .parser import GEAExperiment, AssayGroup, Contrast


def generate_assay_id(experiment_accession: str, contrast_id: str) -> str:
    """Generate a unique assay identifier."""
    return f"{experiment_accession}-{contrast_id}"


def extract_assay_nodes(experiment: GEAExperiment) -> pd.DataFrame:
    """
    Extract Assay nodes from a GXA experiment.

    Each contrast in the experiment becomes an Assay node.
    """
    assays = []

    for contrast in experiment.contrasts:
        ref_group = experiment.assay_groups.get(contrast.reference_group_id)
        test_group = experiment.assay_groups.get(contrast.test_group_id)

        ref_label = ref_group.label if ref_group else ""
        test_label = test_group.label if test_group else ""

        ref_factors = [f.strip() for f in ref_label.split(";")] if ref_label else []
        test_factors = [f.strip() for f in test_label.split(";")] if test_label else []

        assay = {
            "identifier": generate_assay_id(experiment.accession, contrast.id),
            "name": contrast.name,
            "study_id": experiment.accession,
            "contrast_id": contrast.id,
            "technology": "DNA microarray",
            "measurement": "transcription profiling",
            "array_design": contrast.array_design,
            "reference_group_id": contrast.reference_group_id,
            "reference_group_label": ref_label,
            "test_group_id": contrast.test_group_id,
            "test_group_label": test_label,
            "factors_1": ref_factors,
            "factors_2": test_factors,
        }

        assays.append(assay)

    return pd.DataFrame(assays)


# =============================================================================
# SDRF Characteristic/Factor Extraction Functions
# =============================================================================

CHARACTERISTIC_TYPE_MAPPING = {
    "disease": {"node_type": "Disease", "uri_prefixes": ["MONDO", "PATO"]},
    "sex": {"node_type": "Sex", "uri_prefixes": ["PATO"]},
    "developmental stage": {"node_type": "DevelopmentalStage", "uri_prefixes": ["EFO"]},
    "ethnic group": {"node_type": "EthnicGroup", "uri_prefixes": ["HANCESTRO"]},
    "organism status": {"node_type": "OrganismStatus", "uri_prefixes": ["PATO"]},
    "organism part": {"node_type": "Anatomy", "uri_prefixes": ["UBERON"]},
    "cell type": {"node_type": "CellType", "uri_prefixes": ["CL"]},
}

SKIP_CHARACTERISTICS = {"individual", "age", "organism"}


def extract_sdrf_characteristics(experiment: GEAExperiment) -> Dict[str, List[Dict]]:
    """
    Extract all characteristics and factors from SDRF data.

    Returns:
        Dictionary mapping characteristic names to lists of unique values with URIs.
    """
    characteristics: Dict[str, Set[tuple]] = {}

    for sample in experiment.samples:
        for key, value in sample.items():
            if not value or pd.isna(value):
                continue

            if ":" not in key or key.endswith("_URI"):
                continue

            parts = key.split(":", 1)
            if len(parts) != 2:
                continue

            annot_type, annot_name = parts
            annot_name = annot_name.strip()

            if annot_name.lower() in SKIP_CHARACTERISTICS:
                continue

            if annot_type not in ("characteristic", "factor"):
                continue

            uri_key = f"{annot_name}_URI"
            uri = sample.get(uri_key, "")
            if pd.isna(uri):
                uri = ""

            if annot_name not in characteristics:
                characteristics[annot_name] = set()
            characteristics[annot_name].add((str(value), str(uri), annot_type))

    result = {}
    for annot_name, values in characteristics.items():
        result[annot_name] = [
            {"value": v, "uri": u, "type": t}
            for v, u, t in values
        ]

    return result


def extract_factor_values_per_assay_group(
    experiment: GEAExperiment,
) -> Dict[str, Dict[str, List[Dict]]]:
    """Extract factor values for each assay group."""
    group_factors: Dict[str, Dict[str, Set[tuple]]] = {}

    sample_to_group = {}
    for group_id, group in experiment.assay_groups.items():
        for sample_id in group.samples:
            sample_to_group[sample_id] = group_id

    for sample in experiment.samples:
        sample_id = sample.get("Sample", "")
        group_id = sample_to_group.get(sample_id)
        if not group_id:
            continue

        if group_id not in group_factors:
            group_factors[group_id] = {}

        for key, value in sample.items():
            if not value or pd.isna(value):
                continue

            if not key.startswith("factor:") or key.endswith("_URI"):
                continue

            annot_name = key.split(":", 1)[1].strip()

            uri_key = f"{annot_name}_URI"
            uri = sample.get(uri_key, "")
            if pd.isna(uri):
                uri = ""

            if annot_name not in group_factors[group_id]:
                group_factors[group_id][annot_name] = set()
            group_factors[group_id][annot_name].add((str(value), str(uri)))

    result = {}
    for group_id, factors in group_factors.items():
        result[group_id] = {}
        for factor_name, values in factors.items():
            result[group_id][factor_name] = [
                {"value": v, "uri": u} for v, u in values
            ]

    return result


def extract_characteristics_per_assay_group(
    experiment: GEAExperiment,
) -> Dict[str, Dict[str, List[Dict]]]:
    """Extract characteristic values for each assay group."""
    group_characteristics: Dict[str, Dict[str, Set[tuple]]] = {}

    sample_to_group = {}
    for group_id, group in experiment.assay_groups.items():
        for sample_id in group.samples:
            sample_to_group[sample_id] = group_id

    for sample in experiment.samples:
        sample_id = sample.get("Sample", "")
        group_id = sample_to_group.get(sample_id)
        if not group_id:
            continue

        if group_id not in group_characteristics:
            group_characteristics[group_id] = {}

        for key, value in sample.items():
            if not value or pd.isna(value):
                continue

            if not key.startswith("characteristic:") or key.endswith("_URI"):
                continue

            annot_name = key.split(":", 1)[1].strip()

            if annot_name.lower() in SKIP_CHARACTERISTICS:
                continue

            uri_key = f"{annot_name}_URI"
            uri = sample.get(uri_key, "")
            if pd.isna(uri):
                uri = ""

            if annot_name not in group_characteristics[group_id]:
                group_characteristics[group_id][annot_name] = set()
            group_characteristics[group_id][annot_name].add((str(value), str(uri)))

    result = {}
    for group_id, chars in group_characteristics.items():
        result[group_id] = {}
        for char_name, values in chars.items():
            result[group_id][char_name] = [
                {"value": v, "uri": u} for v, u in values
            ]

    return result


def create_characteristic_nodes(
    characteristics: Dict[str, List[Dict]],
    node_type: str,
    characteristic_name: str,
) -> pd.DataFrame:
    """Create nodes for a specific characteristic type."""
    if characteristic_name not in characteristics:
        return pd.DataFrame(columns=["identifier", "name", "uri"])

    values = characteristics[characteristic_name]
    nodes = []

    for item in values:
        uri = item.get("uri", "")
        value = item.get("value", "")

        if uri and " " in uri and uri.startswith("http"):
            uris = uri.split()
            for single_uri in uris:
                if single_uri.startswith("http"):
                    nodes.append({
                        "identifier": single_uri,
                        "name": value,
                        "uri": single_uri,
                    })
        elif uri:
            nodes.append({
                "identifier": uri,
                "name": value,
                "uri": uri,
            })
        else:
            safe_value = value.replace(" ", "_").replace("'", "")
            identifier = f"http://purl.org/okn/wobd/{node_type}/{safe_value}"
            nodes.append({
                "identifier": identifier,
                "name": value,
                "uri": uri,
            })

    if nodes:
        df = pd.DataFrame(nodes).drop_duplicates(subset=["identifier"])
        return df
    return pd.DataFrame(columns=["identifier", "name", "uri"])


def create_disease_nodes(characteristics: Dict[str, List[Dict]]) -> pd.DataFrame:
    return create_characteristic_nodes(characteristics, "Disease", "disease")


def create_sex_nodes(characteristics: Dict[str, List[Dict]]) -> pd.DataFrame:
    return create_characteristic_nodes(characteristics, "Sex", "sex")


def create_developmental_stage_nodes(characteristics: Dict[str, List[Dict]]) -> pd.DataFrame:
    return create_characteristic_nodes(characteristics, "DevelopmentalStage", "developmental stage")


def create_ethnic_group_nodes(characteristics: Dict[str, List[Dict]]) -> pd.DataFrame:
    return create_characteristic_nodes(characteristics, "EthnicGroup", "ethnic group")


def create_organism_status_nodes(characteristics: Dict[str, List[Dict]]) -> pd.DataFrame:
    return create_characteristic_nodes(characteristics, "OrganismStatus", "organism status")


def create_anatomy_nodes_from_sdrf(characteristics: Dict[str, List[Dict]]) -> pd.DataFrame:
    return create_characteristic_nodes(characteristics, "Anatomy", "organism part")


def create_celltype_nodes_from_sdrf(characteristics: Dict[str, List[Dict]]) -> pd.DataFrame:
    return create_characteristic_nodes(characteristics, "CellType", "cell type")


def create_study_characteristic_relationships(
    study_id: str,
    characteristics: Dict[str, List[Dict]],
    characteristic_name: str,
    node_type: str,
) -> pd.DataFrame:
    """Create Study-HAS_ATTRIBUTE-* relationships for a characteristic type."""
    if characteristic_name not in characteristics:
        return pd.DataFrame(columns=["from", "to"])

    relationships = []
    for item in characteristics[characteristic_name]:
        uri = item.get("uri", "")
        value = item.get("value", "")

        if uri and " " in uri and uri.startswith("http"):
            uris = uri.split()
            for single_uri in uris:
                if single_uri.startswith("http"):
                    relationships.append({"from": study_id, "to": single_uri})
        elif uri:
            relationships.append({"from": study_id, "to": uri})
        else:
            safe_value = value.replace(" ", "_").replace("'", "")
            to_id = f"http://purl.org/okn/wobd/{node_type}/{safe_value}"
            relationships.append({"from": study_id, "to": to_id})

    if relationships:
        return pd.DataFrame(relationships).drop_duplicates()
    return pd.DataFrame(columns=["from", "to"])


def create_study_disease_relationships(study_id: str, characteristics: Dict[str, List[Dict]]) -> pd.DataFrame:
    return create_study_characteristic_relationships(study_id, characteristics, "disease", "Disease")


def create_study_sex_relationships(study_id: str, characteristics: Dict[str, List[Dict]]) -> pd.DataFrame:
    return create_study_characteristic_relationships(study_id, characteristics, "sex", "Sex")


def create_study_developmental_stage_relationships(study_id: str, characteristics: Dict[str, List[Dict]]) -> pd.DataFrame:
    return create_study_characteristic_relationships(study_id, characteristics, "developmental stage", "DevelopmentalStage")


def create_study_ethnic_group_relationships(study_id: str, characteristics: Dict[str, List[Dict]]) -> pd.DataFrame:
    return create_study_characteristic_relationships(study_id, characteristics, "ethnic group", "EthnicGroup")


def create_study_organism_status_relationships(study_id: str, characteristics: Dict[str, List[Dict]]) -> pd.DataFrame:
    return create_study_characteristic_relationships(study_id, characteristics, "organism status", "OrganismStatus")


def create_assay_factor_relationships(
    assays: pd.DataFrame,
    group_factors: Dict[str, Dict[str, List[Dict]]],
    factor_name: str,
    node_type: str,
) -> pd.DataFrame:
    """Create Assay-HAS_ATTRIBUTE-* relationships for factors."""
    relationships = []

    for _, assay in assays.iterrows():
        assay_id = assay["identifier"]

        for group_col in ["reference_group_id", "test_group_id"]:
            group_id = assay.get(group_col, "")
            if not group_id or group_id not in group_factors:
                continue

            factors = group_factors[group_id].get(factor_name, [])
            for item in factors:
                uri = item.get("uri", "")
                value = item.get("value", "")

                if uri and " " in uri and uri.startswith("http"):
                    uris = uri.split()
                    for single_uri in uris:
                        if single_uri.startswith("http"):
                            relationships.append({"from": assay_id, "to": single_uri})
                elif uri:
                    relationships.append({"from": assay_id, "to": uri})
                else:
                    safe_value = value.replace(" ", "_").replace("'", "")
                    to_id = f"http://purl.org/okn/wobd/{node_type}/{safe_value}"
                    relationships.append({"from": assay_id, "to": to_id})

    if relationships:
        return pd.DataFrame(relationships).drop_duplicates()
    return pd.DataFrame(columns=["from", "to"])


def create_assay_characteristic_relationships(
    assays: pd.DataFrame,
    group_characteristics: Dict[str, Dict[str, List[Dict]]],
    characteristic_name: str,
    node_type: str,
) -> pd.DataFrame:
    """Create Assay-HAS_ATTRIBUTE-* relationships for characteristics."""
    relationships = []

    for _, assay in assays.iterrows():
        assay_id = assay["identifier"]

        for group_col in ["reference_group_id", "test_group_id"]:
            group_id = assay.get(group_col, "")
            if not group_id or group_id not in group_characteristics:
                continue

            chars = group_characteristics[group_id].get(characteristic_name, [])
            for item in chars:
                uri = item.get("uri", "")
                value = item.get("value", "")

                if uri and " " in uri and uri.startswith("http"):
                    uris = uri.split()
                    for single_uri in uris:
                        if single_uri.startswith("http"):
                            relationships.append({"from": assay_id, "to": single_uri})
                elif uri:
                    relationships.append({"from": assay_id, "to": uri})
                else:
                    safe_value = value.replace(" ", "_").replace("'", "")
                    to_id = f"http://purl.org/okn/wobd/{node_type}/{safe_value}"
                    relationships.append({"from": assay_id, "to": to_id})

    if relationships:
        return pd.DataFrame(relationships).drop_duplicates()
    return pd.DataFrame(columns=["from", "to"])
