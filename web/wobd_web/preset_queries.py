from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal, Optional


@dataclass
class QueryStep:
    """A single step in a multi-step query."""

    query: str
    source_kind: Literal["nde", "frink", "gene_expression"]
    step_name: str


@dataclass
class PresetQueryConfig:
    """Configuration for a preset query."""

    query_type: Literal["single", "multistep"]
    question_text: str
    # For single-step queries
    query: Optional[str] = None
    source_kind: Literal["nde", "frink", "gene_expression"] = "nde"
    # For multi-step queries
    steps: Optional[List[QueryStep]] = None


# Preset query for influenza vaccines
INFLUENZA_VACCINES_QUERY = """PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?dataset ?datasetName ?catalogName ?url ?description
WHERE {
    ?dataset rdf:type schema:Dataset ;
             schema:name ?datasetName .
    
    # Get catalog if available and extract name
    OPTIONAL { 
        ?dataset schema:includedInDataCatalog ?catalog .
        BIND(REPLACE(STR(?catalog), "https://okn.wobd.org/catalog/", "") AS ?catalogName)
    }
    
    # Get URL if available
    OPTIONAL {
        ?dataset schema:url ?url .
    }
    
    # Get description if available
    OPTIONAL {
        ?dataset schema:description ?description .
    }
    
    {
        # Match influenza via healthCondition (MONDO ontology)
        ?dataset schema:healthCondition ?disease .
        ?disease schema:name ?diseaseName .
        FILTER(
            ?disease = <http://purl.obolibrary.org/obo/MONDO_0005812> ||
            CONTAINS(LCASE(?diseaseName), "influenza")
        )
    }
    UNION
    {
        # Match influenza via infectiousAgent (UniProt taxonomy)
        ?dataset schema:infectiousAgent ?agent .
        ?agent schema:name ?agentName .
        FILTER(CONTAINS(LCASE(?agentName), "influenza"))
    }
    UNION
    {
        # Match "influenza" in dataset name
        FILTER(CONTAINS(LCASE(?datasetName), "influenza"))
    }
    UNION
    {
        # Match "influenza" in description
        ?dataset schema:description ?desc .
        FILTER(CONTAINS(LCASE(?desc), "influenza"))
    }
    
    # Filter for vaccine-related content
    FILTER(
        CONTAINS(LCASE(?datasetName), "vaccine") ||
        (BOUND(?description) && CONTAINS(LCASE(?description), "vaccine"))
    )
}
ORDER BY ?catalogName ?datasetName
"""

# Preset query for RNA-seq data for human blood samples
RNA_SEQ_HUMAN_BLOOD_QUERY = """PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?dataset ?datasetName ?catalogName ?url ?description ?measurementTechnique ?speciesName
WHERE {
    ?dataset rdf:type schema:Dataset ;
             schema:name ?datasetName .
    
    # Get catalog if available and extract name
    OPTIONAL { 
        ?dataset schema:includedInDataCatalog ?catalog .
        BIND(REPLACE(STR(?catalog), "https://okn.wobd.org/catalog/", "") AS ?catalogName)
    }
    
    # Get URL if available
    OPTIONAL {
        ?dataset schema:url ?url .
    }
    
    # Get description if available
    OPTIONAL {
        ?dataset schema:description ?description .
    }
    
    # Match RNA-seq measurement technique
    OPTIONAL {
        ?dataset schema:measurementTechnique ?measurementTechnique .
        FILTER(CONTAINS(LCASE(?measurementTechnique), "rna-seq") || 
               CONTAINS(LCASE(?measurementTechnique), "rna seq") ||
               CONTAINS(LCASE(?measurementTechnique), "rnaseq") ||
               CONTAINS(LCASE(?measurementTechnique), "transcriptome"))
    }
    
    # Match human species
    OPTIONAL {
        ?dataset schema:species ?species .
        ?species schema:name ?speciesName .
        FILTER(
            ?species = <https://www.uniprot.org/taxonomy/9606> ||
            REGEX(LCASE(?speciesName), "human|homo sapiens")
        )
    }
    
    # Filter for RNA-seq and human
    FILTER(
        (BOUND(?measurementTechnique) && (
            CONTAINS(LCASE(?measurementTechnique), "rna-seq") || 
            CONTAINS(LCASE(?measurementTechnique), "rna seq") ||
            CONTAINS(LCASE(?measurementTechnique), "rnaseq") ||
            CONTAINS(LCASE(?measurementTechnique), "transcriptome")
        )) ||
        CONTAINS(LCASE(?datasetName), "rna-seq") ||
        CONTAINS(LCASE(?datasetName), "rna seq") ||
        CONTAINS(LCASE(?datasetName), "rnaseq") ||
        (BOUND(?description) && (
            CONTAINS(LCASE(?description), "rna-seq") ||
            CONTAINS(LCASE(?description), "rna seq") ||
            CONTAINS(LCASE(?description), "rnaseq")
        ))
    )
    
    FILTER(
        (BOUND(?species) && (
            ?species = <https://www.uniprot.org/taxonomy/9606> ||
            REGEX(LCASE(?speciesName), "human|homo sapiens")
        )) ||
        CONTAINS(LCASE(?datasetName), "human") ||
        (BOUND(?description) && CONTAINS(LCASE(?description), "human"))
    )
    
    # Filter for blood-related content
    FILTER(
        CONTAINS(LCASE(?datasetName), "blood") ||
        (BOUND(?description) && CONTAINS(LCASE(?description), "blood"))
    )
}
ORDER BY ?catalogName ?datasetName
LIMIT 200
"""

# Step 1: Query Wikidata in FRINK for Tocilizumab → disease (MONDO) mappings
TOCILIZUMAB_STEP1_WIKIDATA = """PREFIX wd:   <http://www.wikidata.org/entity/>
PREFIX wdt:  <http://www.wikidata.org/prop/direct/>
PREFIX wdtn: <http://www.wikidata.org/prop/direct-normalized/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT
  ?disease
  ?diseaseLabel
  ?mondo_id
  ?mondo_uri
  ?how
WHERE {
  VALUES ?drug { wd:Q425154 }

  {
    ?drug wdtn:P2175 ?disease .
    BIND("wdtn:P2175" AS ?how)
  }
  UNION
  {
    ?drug wdt:P2175 ?disease .
    BIND("wdt:P2175" AS ?how)
  }

  OPTIONAL {
    ?disease rdfs:label ?diseaseLabel .
    FILTER(LANG(?diseaseLabel) = "en")
  }

  # MONDO as literal (most common)
  OPTIONAL { ?disease wdt:P5270 ?mondo_id . }

  # MONDO as normalized URI (sometimes present)
  OPTIONAL { ?disease wdtn:P5270 ?mondo_uri . }
}
LIMIT 200
"""

# Step 2: Query NDE with MONDO identifiers (will be parameterized)
TOCILIZUMAB_STEP2_NDE_TEMPLATE = """PREFIX schema: <http://schema.org/>

SELECT DISTINCT
  ?study
  ?studyName
  ?studyId
  ?doi
WHERE {
  VALUES ?mondo {
    {MONDO_VALUES}
  }

  ?study schema:healthCondition ?mondo .

  OPTIONAL { ?study schema:name ?studyName . }
  OPTIONAL { ?study schema:identifier ?studyId . }

  OPTIONAL {
    ?study schema:sameAs ?doi .
    # Optional: keep only DOI-style sameAs values
    FILTER(CONTAINS(LCASE(STR(?doi)), "doi.org/") || CONTAINS(STR(?doi), "10."))
  }
}
LIMIT 200
"""

# Step 3: Query sample metadata for datasets
TOCILIZUMAB_STEP3_METADATA_TEMPLATE = """PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?study ?studyName ?catalogName 
       (GROUP_CONCAT(DISTINCT ?healthConditionDisplay; SEPARATOR="; ") AS ?healthConditions)
       (GROUP_CONCAT(DISTINCT ?pathogenName; SEPARATOR="; ") AS ?pathogens)
       (GROUP_CONCAT(DISTINCT ?speciesName; SEPARATOR="; ") AS ?speciesList)
       (GROUP_CONCAT(DISTINCT ?variableMeasured; SEPARATOR="; ") AS ?variablesList)
       (GROUP_CONCAT(DISTINCT ?measurementTechnique; SEPARATOR="; ") AS ?measurementTechniques)
       (MIN(?description) AS ?descriptionText)
WHERE {
  VALUES ?study {
    {STUDY_VALUES}
  }
  
  ?study rdf:type schema:Dataset .
  OPTIONAL { ?study schema:name ?studyName . }
  OPTIONAL { 
    ?study schema:includedInDataCatalog ?catalog .
    BIND(REPLACE(STR(?catalog), "https://okn.wobd.org/catalog/", "") AS ?catalogName)
  }
  OPTIONAL { 
    ?study schema:healthCondition ?healthCondition .
    ?healthCondition schema:name ?healthConditionName .
    
    # Extract ID from URI (generic: everything after last / or #)
    # Works for MONDO: http://purl.obolibrary.org/obo/MONDO_0011849 -> MONDO_0011849
    # And other ontology terms like NCIT: http://purl.obolibrary.org/obo/NCIT_C173627 -> NCIT_C173627
    BIND(REPLACE(STR(?healthCondition), "^.*[/#]", "") AS ?termId)
    
    # Format health condition with appropriate CURIE format
    # MONDO: "name (MONDO:0011849)" - remove MONDO_ prefix, add colon
    # NCIT: "name (NCIT:C173627)" - replace NCIT_ with NCIT:
    # Other: "name (id)" - use extracted ID as-is
    BIND(IF(
      BOUND(?termId) && ?termId != "" && CONTAINS(STR(?healthCondition), "MONDO"),
      CONCAT(?healthConditionName, " (MONDO:", REPLACE(?termId, "MONDO_", ""), ")"),
      IF(
        BOUND(?termId) && ?termId != "" && CONTAINS(STR(?healthCondition), "NCIT"),
        CONCAT(?healthConditionName, " (", REPLACE(?termId, "NCIT_", "NCIT:"), ")"),
        IF(
          BOUND(?termId) && ?termId != "",
          CONCAT(?healthConditionName, " (", ?termId, ")"),
          ?healthConditionName
        )
      )
    ) AS ?healthConditionDisplay)
  }
  OPTIONAL { 
    ?study schema:infectiousAgent ?pathogen .
    ?pathogen schema:name ?pathogenName .
  }
  OPTIONAL { 
    ?study schema:species ?species .
    ?species schema:name ?speciesName .
  }
  OPTIONAL { ?study schema:variableMeasured ?variableMeasured . }
  OPTIONAL { ?study schema:measurementTechnique ?measurementTechnique . }
  OPTIONAL { ?study schema:description ?description . }
}
GROUP BY ?study ?studyName ?catalogName
ORDER BY ?healthConditions ?studyName
LIMIT 200
"""


# Registry of preset queries
PRESET_QUERIES: Dict[str, PresetQueryConfig] = {
    "Show datasets related to influenza vaccines.": PresetQueryConfig(
        query_type="single",
        question_text="Show datasets related to influenza vaccines.",
        query=INFLUENZA_VACCINES_QUERY,
        source_kind="nde",
    ),
    "Find datasets with RNA-seq data for human blood samples.": PresetQueryConfig(
        query_type="single",
        question_text="Find datasets with RNA-seq data for human blood samples.",
        query=RNA_SEQ_HUMAN_BLOOD_QUERY,
        source_kind="nde",
    ),
    "Find me datasets that use an experimental system (organism, what part of the immune system is measured, and experimental context (treatment, stimulation, disease state)) that might be useful for studying Drug Tocilizumab.": PresetQueryConfig(
        query_type="multistep",
        question_text="Find me datasets that use an experimental system (organism, what part of the immune system is measured, and experimental context (treatment, stimulation, disease state)) that might be useful for studying Drug Tocilizumab.",
        steps=[
            QueryStep(
                query=TOCILIZUMAB_STEP1_WIKIDATA,
                source_kind="frink",
                step_name="wikidata_drug_to_disease",
            ),
            QueryStep(
                query=TOCILIZUMAB_STEP2_NDE_TEMPLATE,
                source_kind="nde",
                step_name="nde_datasets_by_mondo",
            ),
            QueryStep(
                query=TOCILIZUMAB_STEP3_METADATA_TEMPLATE,
                source_kind="nde",
                step_name="sample_metadata",
            ),
        ],
    ),
}


def get_preset_query(question: str) -> Optional[PresetQueryConfig]:
    """
    Get preset query configuration for a given question, if it exists.
    
    Performs exact match on question text.
    """
    return PRESET_QUERIES.get(question.strip())


__all__ = [
    "QueryStep",
    "PresetQueryConfig",
    "PRESET_QUERIES",
    "get_preset_query",
    "TOCILIZUMAB_STEP2_NDE_TEMPLATE",
    "TOCILIZUMAB_STEP3_METADATA_TEMPLATE",
]

