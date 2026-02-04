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
"""


# Preset query for Dusp2 upregulation
DUSP2_UPREGULATION_QUERY = """PREFIX biolink: <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>
PREFIX ensembl: <http://identifiers.org/ensembl/>

SELECT DISTINCT 
    ?experiment 
    (REPLACE(STR(?experiment), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentId)
    ?experimentLabel
    ?gene 
    ?geneSymbol 
    ?log2fc 
    ?adjPValue
WHERE {
    # Find gene expression associations
    ?association a biolink:GeneExpressionMixin ;
        biolink:object ?gene ;
        biolink:subject ?experiment ;
        spokegenelab:log2fc ?log2fc ;
        spokegenelab:adj_p_value ?adjPValue .
    
    # Get gene symbol (filter for Dusp2)
    ?gene biolink:symbol ?geneSymbol .
    FILTER(LCASE(?geneSymbol) = "dusp2")
    
    # Filter for upregulated genes (log2fc > 0)
    FILTER(?log2fc > 0)
    
    # Get experiment label if available
    OPTIONAL {
        ?experiment biolink:name ?experimentLabel .
    }
}
ORDER BY DESC(?log2fc)
"""


# Query to find studies/experiments where SFRP2 is upregulated or downregulated
# Similar structure to DUSP2_UPREGULATION_QUERY but for SFRP2 and includes both up and down
# Key fields returned: studyId, gene, expressionDirection (upregulated/downregulated)
SFRP2_EXPRESSION_STUDIES_QUERY = """PREFIX biolink: <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>

SELECT DISTINCT 
    ?studyId
    ?gene 
    ?geneSymbol 
    ?expressionDirection
    ?experiment 
    (REPLACE(STR(?experiment), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentId)
    ?experimentLabel
    ?log2fc 
    ?adjPValue
WHERE {
    # Find gene expression associations
    ?association a biolink:GeneExpressionMixin ;
        biolink:object ?gene ;
        biolink:subject ?experiment ;
        spokegenelab:log2fc ?log2fc ;
        spokegenelab:adj_p_value ?adjPValue .
    
    # Get gene symbol (filter for SFRP2)
    ?gene biolink:symbol ?geneSymbol .
    FILTER(LCASE(?geneSymbol) = "sfrp2" || LCASE(?geneSymbol) = "sfrp-2")
    
    # Get study ID from experiment (key field for linking to other graphs)
    ?experiment spokegenelab:study_id ?studyId .
    
    # Determine if upregulated or downregulated
    BIND(IF(?log2fc > 0, "upregulated", "downregulated") AS ?expressionDirection)
    
    # Get experiment label if available
    OPTIONAL {
        ?experiment biolink:name ?experimentLabel .
    }
}
ORDER BY ?studyId DESC(?log2fc)
"""

# Query to find Doxycycline → SFRP2 → Disease connections (matching the visualization)
# This query spans three endpoints:
# 1. SPOKE-OKN: Drug-gene relationships (Doxycycline → SFRP2)
# 2. Ubergraph: Gene-disease relationships (SFRP2 → Diseases)
# 3. GXA (Gene Expression): Gene expression data (SFRP2 upregulated/downregulated in diseases)
DOXYCYCLINE_SFRP2_DISEASE_QUERY = """PREFIX biolink: <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT
    ?drug
    ?drugLabel
    ?gene
    ?geneSymbol
    ?disease
    ?diseaseLabel
    ?experiment
    (REPLACE(STR(?experiment), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentId)
    ?log2fc
    ?adjPValue
    ?experimentLabel
    ?drugGenePredicate
    ?geneDiseasePredicate
WHERE {
    # Step 1: Query SPOKE-OKN for Doxycycline → SFRP2 relationship
    SERVICE <SPOKE_ENDPOINT_PLACEHOLDER> {
        ?drug ?drugGenePredicate ?gene .
        
        # Filter for Doxycycline
        OPTIONAL {
            ?drug rdfs:label ?drugLabel .
            FILTER(LANG(?drugLabel) = "en")
        }
        FILTER(
            CONTAINS(LCASE(STR(?drugLabel)), "doxycycline") ||
            CONTAINS(LCASE(STR(?drug)), "doxycycline")
        )
        
        # Filter for SFRP2 gene
        ?gene biolink:symbol ?geneSymbol .
        FILTER(LCASE(?geneSymbol) = "sfrp2" || LCASE(?geneSymbol) = "sfrp-2")
    }
    
    # Step 2: Query Ubergraph for SFRP2 → Disease relationships
    SERVICE <UBERGRAPH_ENDPOINT_PLACEHOLDER> {
        ?gene ?geneDiseasePredicate ?disease .
        
        # Get disease label
        OPTIONAL {
            ?disease rdfs:label ?diseaseLabel .
            FILTER(LANG(?diseaseLabel) = "en")
        }
    }
    
    # Step 3: Query GXA (Gene Expression) for SFRP2 expression data
    SERVICE <GENE_EXPR_ENDPOINT_PLACEHOLDER> {
        ?association a biolink:GeneExpressionMixin ;
            biolink:object ?gene ;
            biolink:subject ?experiment ;
            spokegenelab:log2fc ?log2fc ;
            spokegenelab:adj_p_value ?adjPValue .
        
        # Get experiment label
        OPTIONAL {
            ?experiment biolink:name ?experimentLabel .
        }
    }
}
ORDER BY ?drugLabel ?geneSymbol ?diseaseLabel DESC(?log2fc)
"""

# Federated query for drug repurposing across multiple FRINK graph endpoints
# 
# This query uses SPARQL SERVICE clauses to query across separate endpoints:
# 1. SPOKE endpoint: Drug-gene relationships (drug downregulates gene)
# 2. Gene Expression endpoint: Gene expression data (gene upregulated in diseases)
#
# Structure: Drug → downregulates → Gene → upregulated in → Diseases/Experiments
#
# Note: Adjust endpoint URLs and predicates based on your FRINK setup
DRUG_REPURPOSE_FEDERATED_QUERY = """PREFIX biolink: <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>

SELECT DISTINCT
    ?drug
    ?drugLabel
    ?gene
    ?geneSymbol
    ?experiment
    (REPLACE(STR(?experiment), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentId)
    ?log2fc
    ?adjPValue
    ?experimentLabel
    ?predicate
WHERE {
    # Step 1: Query SPOKE endpoint for drug-gene relationships
    # Find drugs that downregulate genes (e.g., Doxycycline downregulates SFPR2)
    SERVICE <SPOKE_ENDPOINT_PLACEHOLDER> {
        ?drug ?predicate ?gene .
        
        # Filter for drug-gene relationships that indicate downregulation
        # Common predicates: biolink:decreases_expression_of, biolink:negatively_regulates
        # Adjust based on actual SPOKE/Ubergraph vocabulary
        FILTER(?predicate IN (biolink:decreases_expression_of, biolink:negatively_regulates, biolink:affects))
        
        # Get drug label from SPOKE
        OPTIONAL {
            ?drug rdfs:label ?drugLabel .
            FILTER(LANG(?drugLabel) = "en")
        }
        
        # Filter for specific drug (e.g., Doxycycline)
        # This can be by label or by URI/identifier
        FILTER(
            CONTAINS(LCASE(STR(?drugLabel)), "doxycycline") ||
            CONTAINS(LCASE(STR(?drug)), "doxycycline")
        )
        
        # Get gene symbol from SPOKE
        ?gene biolink:symbol ?geneSymbol .
    }
    
    # Step 2: Query Gene Expression endpoint for upregulated genes
    # Find where those same genes are upregulated in disease experiments
    SERVICE <GENE_EXPR_ENDPOINT_PLACEHOLDER> {
        ?association a biolink:GeneExpressionMixin ;
            biolink:object ?gene ;
            biolink:subject ?experiment ;
            spokegenelab:log2fc ?log2fc ;
            spokegenelab:adj_p_value ?adjPValue .
        
        # Filter for upregulated genes (log2fc > 0)
        # Drug downregulates, but disease shows upregulation - repurposing opportunity
        FILTER(?log2fc > 0)
        
        # Get experiment label
        OPTIONAL {
            ?experiment biolink:name ?experimentLabel .
        }
    }
}
ORDER BY ?drugLabel ?geneSymbol DESC(?log2fc)
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
    "Find datasets that use an experimental system that might be useful for studying the drug Tocilizumab.": PresetQueryConfig(
        query_type="multistep",
        question_text="Find datasets that use an experimental system that might be useful for studying the drug Tocilizumab.",
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
    "Find experiments where Dusp2 is upregulated.": PresetQueryConfig(
        query_type="single",
        question_text="Find experiments where Dusp2 is upregulated.",
        query=DUSP2_UPREGULATION_QUERY,
        source_kind="gene_expression",
    ),
    # Note: This query assumes FRINK has both drug-gene relationships (from SPOKE/Ubergraph)
    # and gene expression data (from GXA) in a unified graph or accessible via federated queries
    "Find disease experiments where genes downregulated by Doxycycline show upregulation.": PresetQueryConfig(
        query_type="single",
        question_text="Find disease experiments where genes downregulated by Doxycycline show upregulation.",
        query=DRUG_REPURPOSE_FEDERATED_QUERY,
        source_kind="frink",  # Use FRINK if it has unified access to both drug-gene and gene expression data
    ),
    # Query matching the Doxycycline → SFRP2 → Disease network visualization
    "Find diseases connected to SFRP2 that is affected by Doxycycline.": PresetQueryConfig(
        query_type="single",
        question_text="Find diseases connected to SFRP2 that is affected by Doxycycline.",
        query=DOXYCYCLINE_SFRP2_DISEASE_QUERY,
        source_kind="frink",  # Uses federated queries across SPOKE-OKN, Ubergraph, and GXA
    ),
    # Simple query to find studies where SFRP2 is up or downregulated
    "Find studies where SFRP2 is upregulated or downregulated.": PresetQueryConfig(
        query_type="single",
        question_text="Find studies where SFRP2 is upregulated or downregulated.",
        query=SFRP2_EXPRESSION_STUDIES_QUERY,
        source_kind="gene_expression",
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
    "DUSP2_UPREGULATION_QUERY",
    "TOCILIZUMAB_STEP2_NDE_TEMPLATE",
    "TOCILIZUMAB_STEP3_METADATA_TEMPLATE",
    "DRUG_REPURPOSE_FEDERATED_QUERY",
    "DOXYCYCLINE_SFRP2_DISEASE_QUERY",
    "SFRP2_EXPRESSION_STUDIES_QUERY",
]

