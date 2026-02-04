// Ontology mapping: domain/topic → ontology
// Used to determine which ontology to query for each entity type

export interface OntologyMapping {
  domain: string;
  ontology: string;
  description?: string;
}

/**
 * Mapping of entity domains/topics to their corresponding ontologies
 * This is used by the LLM to know which ontology to use for grounding
 */
export const ONTOLOGY_MAPPING: Record<string, OntologyMapping> = {
  disease: {
    domain: "disease",
    ontology: "MONDO",
    description: "Diseases, disorders, syndromes, and medical conditions",
  },
  condition: {
    domain: "condition",
    ontology: "MONDO",
    description: "Health conditions and medical conditions",
  },
  disorder: {
    domain: "disorder",
    ontology: "MONDO",
    description: "Medical disorders",
  },
  species: {
    domain: "species",
    ontology: "NCBITaxon",
    description: "Biological species and organisms",
  },
  organism: {
    domain: "organism",
    ontology: "NCBITaxon",
    description: "Living organisms",
  },
  drug: {
    domain: "drug",
    ontology: "Wikidata",
    description: "Drugs, medications, and chemical compounds",
  },
  medication: {
    domain: "medication",
    ontology: "Wikidata",
    description: "Medications and pharmaceutical compounds",
  },
  gene: {
    domain: "gene",
    ontology: "HGNC",
    description: "Human genes",
  },
  gene_expression: {
    domain: "gene_expression",
    ontology: "NONE",
    description: "Gene expression concepts (upregulation, downregulation, differential expression)",
  },
  protein: {
    domain: "protein",
    ontology: "PR",
    description: "Proteins",
  },
};

/**
 * Get ontology for a given domain/topic
 */
export function getOntologyForDomain(domain: string): string | null {
  const normalized = domain.toLowerCase().trim();
  return ONTOLOGY_MAPPING[normalized]?.ontology || null;
}

/**
 * Get all available domains
 */
export function getAvailableDomains(): string[] {
  return Object.keys(ONTOLOGY_MAPPING);
}

/**
 * Format ontology mapping for LLM prompt
 */
export function formatOntologyMappingForLLM(): string {
  const mappings = Object.values(ONTOLOGY_MAPPING);
  return mappings
    .map((m) => `- ${m.domain} → ${m.ontology} (${m.description || ""})`)
    .join("\n");
}




