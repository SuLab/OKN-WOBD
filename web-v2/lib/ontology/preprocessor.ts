// Ontology-grounded query preprocessor
// Detects ontology intent and enriches intent with ontology data before template generation

import type { Intent } from "@/types";
import type { ContextPack } from "@/lib/context-packs/types";
import type {
  OntologyQueryState,
  MONDOGroundingResult,
  MONDOSynonymResult,
  SPARQLResult,
} from "@/types";
import { identifyEntities, generateAlternativeNames, type IdentifiedEntity } from "./entity-identifier";
import { getOntologyForDomain } from "./ontology-mapping";
import { detectNDEEncoding } from "./nde-encoding";
import { executeSPARQL } from "@/lib/sparql/executor";
import {
  buildMONDOSynonymQuery,
  buildNDEDatasetQueryIRI,
  buildNDEDatasetQueryCURIE,
  buildNDEFallbackQuery,
} from "./templates";
import {
  groundTermToMONDO,
  groundTermToNCBITaxon,
  type OLSSearchResult,
} from "./ols-client";
import {
  groundDrugToWikidata,
  type WikidataSearchResult,
} from "./wikidata-client";

/**
 * Map entity type to corresponding Schema.org property for NDE queries
 */
export function getSchemaPropertyForEntityType(entityType: string): string {
  const normalizedType = entityType.toLowerCase();
  switch (normalizedType) {
    case "disease":
    case "condition":
    case "disorder":
      return "schema:healthCondition";
    case "species":
    case "organism":
      return "schema:species";
    case "drug":
    case "medication":
      // TODO: Add support for drugs when needed
      return "schema:healthCondition"; // Fallback for now
    case "gene":
      // Gene queries may use different properties depending on the graph
      return "schema:healthCondition"; // Fallback for now
    default:
      return "schema:healthCondition"; // Default fallback
  }
}

/**
 * Select appropriate graphs for gene expression queries
 * Returns list of graph shortnames that should be included for gene expression queries
 */
export function selectGraphsForGeneExpression(
  entityType: string,
  hasGeneExpression: boolean,
  identifiedEntities?: IdentifiedEntity[]
): string[] {
  // Check if this is a gene-related query
  const isGeneQuery = entityType === "gene" ||
    identifiedEntities?.some(e => e.domain === "gene");
  const hasExpression = hasGeneExpression ||
    identifiedEntities?.some(e => e.domain === "gene_expression");

  if (isGeneQuery || hasExpression) {
    // For gene expression queries, prioritize gene expression graphs
    return [
      "spoke-genelab",
      "spoke-okn",
      "gene-expression-atlas-okn"
    ];
  }
  return []; // Empty means use default graphs
}

/**
 * Convert NCBITaxon identifier to UniProt taxonomy format
 * Both systems use the same NCBI taxonomy database, so the numeric ID is the same
 * Examples:
 *   NCBITaxon:9606 -> https://www.uniprot.org/taxonomy/9606
 *   http://purl.obolibrary.org/obo/NCBITaxon_9606 -> https://www.uniprot.org/taxonomy/9606
 */
function convertNCBITaxonToUniProt(ncbitaxonIRI: string): string | null {
  try {
    // Extract numeric ID from various NCBITaxon formats
    let numericId: string | null = null;

    // Try CURIE format: NCBITaxon:9606
    const curieMatch = ncbitaxonIRI.match(/NCBITaxon:(\d+)/i);
    if (curieMatch) {
      numericId = curieMatch[1];
    }

    // Try OBO IRI format: http://purl.obolibrary.org/obo/NCBITaxon_9606
    if (!numericId) {
      const iriMatch = ncbitaxonIRI.match(/NCBITaxon[:_](\d+)/i);
      if (iriMatch) {
        numericId = iriMatch[1];
      }
    }

    // Try short form: NCBITaxon_9606
    if (!numericId) {
      const shortMatch = ncbitaxonIRI.match(/NCBITaxon[:_](\d+)/i);
      if (shortMatch) {
        numericId = shortMatch[1];
      }
    }

    if (!numericId) {
      console.warn(`[Ontology] Could not extract numeric ID from NCBITaxon identifier: ${ncbitaxonIRI}`);
      return null;
    }

    // Convert to UniProt taxonomy format
    return `https://www.uniprot.org/taxonomy/${numericId}`;
  } catch (error: any) {
    console.error(`[Ontology] Error converting NCBITaxon to UniProt: ${error.message}`);
    return null;
  }
}

/**
 * Detect if user query explicitly mentions animal/veterinary diseases
 * Returns true if animal intent is detected, false otherwise (defaults to human)
 * 
 * Given NIAID Data Ecosystem and proto-OKN focus on human health research,
 * we default to human diseases unless explicitly indicated otherwise.
 */
export function detectAnimalDiseaseIntent(text: string): boolean {
  const lowerText = text.toLowerCase();

  // Keywords that indicate animal/veterinary disease interest
  const animalKeywords = [
    // Explicit animal mentions
    "animal disease",
    "animal model",
    "veterinary",
    "veterinarian",
    "non-human",
    "nonhuman",

    // Specific animal species (in disease context)
    "dog disease",
    "canine disease",
    "cat disease",
    "feline disease",
    "mouse disease",
    "murine disease",
    "rat disease",
    "pig disease",
    "porcine disease",
    "swine disease",
    "cow disease",
    "bovine disease",
    "sheep disease",
    "ovine disease",
    "horse disease",
    "equine disease",
    "chicken disease",
    "poultry disease",

    // Veterinary contexts
    "veterinary medicine",
    "animal health",
    "livestock disease",
    "zoonotic", // Though zoonotic could be human too, it's often animal-focused

    // Research contexts that suggest animal models
    "animal model of",
    "murine model",
    "rodent model",
  ];

  // Check for animal keywords
  const hasAnimalKeyword = animalKeywords.some(keyword => lowerText.includes(keyword));

  // Also check for patterns like "disease in [animal]" or "[animal] disease"
  const animalSpeciesPattern = /\b(dog|cat|mouse|rat|pig|cow|sheep|horse|chicken|canine|feline|murine|porcine|bovine|ovine|equine|poultry|rodent)\s+(disease|disorder|condition|syndrome)/i;
  const diseaseInAnimalPattern = /\b(disease|disorder|condition|syndrome)\s+(in|of|affecting)\s+(dog|cat|mouse|rat|pig|cow|sheep|horse|chicken|animal|non-human)/i;

  const hasAnimalPattern = animalSpeciesPattern.test(text) || diseaseInAnimalPattern.test(text);

  const isAnimalIntent = hasAnimalKeyword || hasAnimalPattern;

  if (isAnimalIntent) {
    console.log(`[Ontology] Animal/veterinary disease intent detected in query: "${text}"`);
  }

  return isAnimalIntent;
}

/**
 * Detect if query should use ontology-grounded workflow.
 *
 * For now, we assume the primary entity type we care about is a
 * disease / health condition. The trigger rule is:
 *
 * - Task is `dataset_search`, AND
 * - We can extract a non-empty entity phrase (treated as a disease-like term), OR
 * - The user explicitly provides a MONDO ID/IRI.
 *
 * Importantly, this does NOT require the user to say "MONDO", "Ubergraph",
 * or "synonym expansion" – ontology grounding should happen by default
 * whenever there's a disease-like entity phrase.
 */
export function detectOntologyIntent(text: string, intent: Intent): boolean {
  // Only consider ontology workflow for dataset_search tasks
  if (intent.task !== "dataset_search") {
    return false;
  }

  // Explicit MONDO ID/IRI always triggers ontology workflow
  const hasMONDOID =
    /MONDO[:_]\d+/i.test(text) ||
    /http:\/\/purl\.obolibrary\.org\/obo\/MONDO_/i.test(text);
  if (hasMONDOID) {
    return true;
  }

  // Otherwise, look for a core entity phrase and treat it as a disease term.
  // extractEntityPhrase is currently disease-focused and will be generalized
  // to other entity types (species, drugs, etc.) over time.
  const entityPhrase = extractEntityPhrase(text).trim();

  // If we can extract a reasonably non-trivial phrase, trigger ontology workflow.
  // This makes ontology grounding the default for disease-like queries.
  if (entityPhrase.length >= 3) {
    return true;
  }

  return false;
}

/**
 * Extract explicit MONDO IDs/IRIs from text if present
 */
function extractMONDOIDs(text: string): string[] {
  const mondoIRIs: string[] = [];

  // Match MONDO:12345 format
  const curieMatches = text.match(/MONDO[:_](\d+)/gi);
  if (curieMatches) {
    for (const match of curieMatches) {
      const id = match.replace(/MONDO[:_]/i, "");
      mondoIRIs.push(`http://purl.obolibrary.org/obo/MONDO_${id}`);
    }
  }

  // Match full MONDO IRIs
  const iriMatches = text.match(/http:\/\/purl\.obolibrary\.org\/obo\/MONDO_\d+/gi);
  if (iriMatches) {
    mondoIRIs.push(...iriMatches);
  }

  return [...new Set(mondoIRIs)]; // Remove duplicates
}

/**
 * Extract the core disease/entity phrase from query text
 * Removes ontology-related instructions and common query patterns
 */
function extractEntityPhrase(text: string): string {
  let phrase = text.trim();

  // Remove common query prefixes
  phrase = phrase.replace(/^(find|show|get|list|search for|what are).*?(datasets?|data|information).*?(about|related to|for|on|regarding)\s*/i, "");

  // Remove ontology-related instructions (case-insensitive)
  const ontologyPatterns = [
    /\s*using\s+synonym\s+expansion.*$/i,
    /\s*from\s+MONDO.*$/i,
    /\s*in\s+Ubergraph.*$/i,
    /\s*using\s+ontology.*$/i,
    /\s*with\s+MONDO.*$/i,
    /\s*grounded\s+to\s+MONDO.*$/i,
    /\s*via\s+MONDO.*$/i,
  ];

  for (const pattern of ontologyPatterns) {
    phrase = phrase.replace(pattern, "");
  }

  // Clean up extra whitespace
  phrase = phrase.trim();

  // If we removed everything, fall back to original text
  if (phrase.length === 0) {
    return text.trim();
  }

  return phrase;
}

/**
 * Ground a single entity term to ontology
 * Returns ranked results with the best match first
 * Supports MONDO (disease entities), NCBITaxon (organism/species entities), and Wikidata (drugs)
 */
async function groundEntityToOntology(
  entity: IdentifiedEntity,
  topN: number = 3,
  userQuery?: string  // Original user query for animal intent detection
): Promise<MONDOGroundingResult[]> {
  const ontology = entity.ontology.toLowerCase();
  const term = entity.term.trim();

  console.log(`[Ontology] Grounding "${term}" to ${ontology}`);

  try {
    let olsResults: Array<OLSSearchResult & { matchScore: number; matchType: string; matchedText: string }>;

    if (ontology === "mondo") {
      // Detect if user explicitly wants animal diseases
      // Default to human diseases (appropriate for NIAID/NDE context)
      const humanOnly = userQuery ? !detectAnimalDiseaseIntent(userQuery) : true;

      if (humanOnly) {
        console.log(`[Ontology] Filtering to human diseases only (NIAID/NDE default)`);
      } else {
        console.log(`[Ontology] Animal/veterinary disease intent detected - including all MONDO terms`);
      }

      olsResults = await groundTermToMONDO(term, topN, humanOnly);
    } else if (ontology === "ncbitaxon") {
      // Ground to NCBITaxon for organism/species entities
      console.log(`[Ontology] Grounding organism/species term to NCBITaxon`);
      olsResults = await groundTermToNCBITaxon(term, topN);
    } else if (ontology.includes("wikidata") || ontology.includes("chebi") || ontology === "wikidata") {
      // Ground drugs to Wikidata (CHEBI support can be added later)
      console.log(`[Ontology] Grounding drug/medication term "${term}" to Wikidata (ontology: ${ontology})`);

      // Try Wikidata
      const wikidataResults = await groundDrugToWikidata(term);

      // Convert Wikidata results to OLS-like format
      olsResults = wikidataResults.map((wd) => ({
        iri: wd.wikidata_iri,
        id: wd.wikidata_iri,
        label: wd.label,
        description: wd.description != null ? [wd.description] : undefined,
        obo_id: wd.wikidata_id, // e.g., "Q421094"
        short_form: wd.wikidata_id,
        is_obsolete: false,
        matchScore: wd.matchScore,
        matchType: wd.matchType,
        matchedText: wd.matchedText,
      }));

      // Sort by match score and limit
      olsResults.sort((a, b) => b.matchScore - a.matchScore);
      olsResults = olsResults.slice(0, topN);
    } else {
      console.warn(`[Ontology] Ontology ${ontology} not yet supported`);
      return [];
    }

    const groundingResults = olsResults
      .map(olsResult => {
        // Get IRI - try multiple possible fields, handle both MONDO and NCBITaxon
        let termIRI = olsResult.iri || olsResult.id;

        if (!termIRI && olsResult.obo_id) {
          // Convert CURIE to IRI (e.g., "MONDO:0006664" -> "http://purl.obolibrary.org/obo/MONDO_0006664")
          // or "NCBITaxon:9606" -> "http://purl.obolibrary.org/obo/NCBITaxon_9606"
          const curie = olsResult.obo_id;
          if (curie.includes(":")) {
            const [prefix, id] = curie.split(":");
            termIRI = `http://purl.obolibrary.org/obo/${prefix}_${id}`;
          }
        }

        if (!termIRI) {
          console.warn(`[Ontology] Skipping OLS result with no IRI:`, olsResult);
          return null;
        }

        // For NCBITaxon (species/organism), convert to UniProt taxonomy format
        // NDE data uses UniProt taxonomy URIs, but the numeric ID is the same
        if (ontology === "ncbitaxon") {
          const uniprotIRI = convertNCBITaxonToUniProt(termIRI);
          if (uniprotIRI) {
            console.log(`[Ontology] Converted NCBITaxon ${termIRI} to UniProt format: ${uniprotIRI}`);
            termIRI = uniprotIRI;
          } else {
            console.warn(`[Ontology] Failed to convert NCBITaxon to UniProt, using original: ${termIRI}`);
          }
        }

        // Convert OLS result to our format
        // Note: For now, we use MONDOGroundingResult format even for NCBITaxon
        // This may need to be generalized in the future
        const result: MONDOGroundingResult = {
          mondo: termIRI, // For MONDO: MONDO IRI, For NCBITaxon: UniProt taxonomy IRI
          label: olsResult.label || "",
          matchedText: olsResult.matchedText || olsResult.label || "",
          matchedPred: olsResult.matchType === "label" ? "rdfs:label" : "synonym",
          matchScore: olsResult.matchScore,
          matchType: olsResult.matchType,
          obo_id: olsResult.obo_id || olsResult.short_form,
          is_obsolete: olsResult.is_obsolete,
        };
        return result;
      })
      .filter((r): r is MONDOGroundingResult => r !== null);

    console.log(`[Ontology] Grounded "${term}" to ${groundingResults.length} ${ontology} terms`);
    if (groundingResults.length > 0) {
      console.log(`[Ontology] Top match: ${groundingResults[0].obo_id || groundingResults[0].mondo} (${groundingResults[0].label}, score: ${groundingResults[0].matchScore})`);
    }

    return groundingResults;
  } catch (error: any) {
    console.error(`[Ontology] Failed to ground "${term}" to ${ontology}:`, error);
    return [];
  }
}

/**
 * Ground multiple search terms to MONDO (for fallback alternative names)
 * Returns ranked results with the best match first
 */
async function groundTermsToMONDO(
  searchTerms: string[],
  humanOnly: boolean = true  // Default to human diseases (NIAID/NDE context)
): Promise<MONDOGroundingResult[]> {
  console.log("[Ontology] Grounding multiple terms to MONDO using OLS, search terms:", searchTerms);

  const allResults: Map<string, MONDOGroundingResult> = new Map();

  // Ground each term
  for (const term of searchTerms) {
    try {
      const olsResults = await groundTermToMONDO(term, 3, humanOnly); // Get top 3 for each term

      for (const olsResult of olsResults) {
        // Get MONDO IRI - try multiple possible fields
        const mondoIRI = olsResult.iri || olsResult.id ||
          (olsResult.obo_id ? `http://purl.obolibrary.org/obo/${olsResult.obo_id.replace(":", "_")}` : null);

        if (!mondoIRI) {
          console.warn(`[Ontology] Skipping OLS result with no IRI:`, olsResult);
          continue;
        }

        // Skip if we already have this MONDO term with a better score
        const existing = allResults.get(mondoIRI);
        if (existing && (existing.matchScore || 0) >= olsResult.matchScore) {
          continue;
        }

        // Convert OLS result to our format
        const groundingResult: MONDOGroundingResult = {
          mondo: mondoIRI,
          label: olsResult.label || "",
          matchedText: olsResult.matchedText || olsResult.label || "",
          matchedPred: olsResult.matchType === "label" ? "rdfs:label" : "synonym",
          matchScore: olsResult.matchScore,
          matchType: olsResult.matchType,
          obo_id: olsResult.obo_id || olsResult.short_form,
          is_obsolete: olsResult.is_obsolete,
        };

        allResults.set(mondoIRI, groundingResult);
      }
    } catch (error: any) {
      console.error(`[Ontology] Failed to ground "${term}" to MONDO:`, error);
      // Continue with other terms
    }
  }

  // Convert to array and sort by match score (highest first)
  const results = Array.from(allResults.values());
  results.sort((a, b) => (b.matchScore || 0) - (a.matchScore || 0));

  console.log("[Ontology] OLS grounding returned", results.length, "unique MONDO terms");
  if (results.length > 0) {
    console.log("[Ontology] Top matches:", results.slice(0, 3).map(r =>
      `${r.obo_id || r.mondo}: ${r.label} (score: ${r.matchScore})`
    ));
  }

  return results;
}

/**
 * Expand MONDO synonyms in Ubergraph
 */
async function expandMONDOSynonyms(
  mondoIRIs: string[]
): Promise<MONDOSynonymResult[]> {
  if (mondoIRIs.length === 0) {
    return [];
  }

  try {
    const query = buildMONDOSynonymQuery(mondoIRIs);
    const result = await executeSPARQL(query);

    const bindings = result.result.results.bindings;
    const synonymMap = new Map<string, MONDOSynonymResult>();

    for (const binding of bindings) {
      const mondo = binding.mondo?.value;
      if (!mondo) continue;

      if (!synonymMap.has(mondo)) {
        synonymMap.set(mondo, {
          mondo,
          label: binding.label?.value,
          synonyms: [],
        });
      }

      const synResult = synonymMap.get(mondo)!;
      const syn = binding.syn?.value;
      if (syn && !synResult.synonyms.includes(syn)) {
        synResult.synonyms.push(syn);
      }
    }

    return Array.from(synonymMap.values());
  } catch (error: any) {
    throw new Error(`MONDO synonym expansion failed: ${error.message}`);
  }
}

/**
 * Query NDE datasets using MONDO terms
 */
async function queryNDEDatasets(
  mondoIRIs: string[],
  encoding: "iri" | "curie"
): Promise<SPARQLResult> {
  try {
    const query =
      encoding === "iri"
        ? buildNDEDatasetQueryIRI(mondoIRIs)
        : buildNDEDatasetQueryCURIE(mondoIRIs);

    const result = await executeSPARQL(query);
    return result.result;
  } catch (error: any) {
    throw new Error(`NDE dataset query failed: ${error.message}`);
  }
}

/**
 * Fallback text search in NDE
 */
async function fallbackTextSearch(
  rawPhrase: string,
  candidateLabels: string[]
): Promise<SPARQLResult> {
  try {
    const query = buildNDEFallbackQuery(rawPhrase, candidateLabels);
    const result = await executeSPARQL(query);
    return result.result;
  } catch (error: any) {
    throw new Error(`Fallback text search failed: ${error.message}`);
  }
}

/**
 * Main workflow orchestrator for ontology-grounded queries
 */
export async function processOntologyQuery(
  text: string,
  intent: Intent,
  pack: ContextPack,
  llmUrl?: string
): Promise<OntologyQueryState> {
  // Extract the core entity phrase (remove ontology instructions)
  const entityPhrase = extractEntityPhrase(text);

  // Initialize state - entity_type will be set from identified entities
  const state: OntologyQueryState = {
    entity_type: "disease", // Default, will be updated from identified entities
    raw_phrase: entityPhrase, // Use extracted phrase, not full query text
    candidate_labels: [],
    grounded_mondo_terms: [],
    synonyms: [],
    fallback_used: false,
    stage_errors: {},
    debug_info: {},
  };

  // Check for explicit MONDO IDs
  const explicitMONDOIDs = extractMONDOIDs(text);
  let mondoIRIs: string[] = [];
  let identifiedEntities: IdentifiedEntity[] = [];

  try {
    // Stage 1: Identify entities from user phrase (skip if MONDO IDs provided)
    if (explicitMONDOIDs.length === 0) {
      try {
        console.log(`[Ontology] User query: "${text}"`);
        console.log("[Ontology] Stage 1: Identifying entities from phrase:", entityPhrase);
        const entityResult = await identifyEntities(entityPhrase, llmUrl);
        identifiedEntities = entityResult.entities;
        state.debug_info!.identified_entities = identifiedEntities;

        console.log(`[Ontology] Identified ${identifiedEntities.length} entities:`,
          identifiedEntities.map(e => `${e.term} (${e.domain} → ${e.ontology})`).join(", "));

        // Update entity_type from identified entities
        // Priority: disease > species > gene > drug > other
        // This ensures disease entities are prioritized when multiple types are present
        // (e.g., "influenza vaccines" should prioritize disease over drug)
        const hasDisease = identifiedEntities.some(e =>
          e.domain.toLowerCase() === "disease" ||
          e.domain.toLowerCase() === "condition" ||
          e.domain.toLowerCase() === "disorder"
        );
        const hasSpecies = identifiedEntities.some(e =>
          e.domain.toLowerCase() === "species" ||
          e.domain.toLowerCase() === "organism"
        );
        const hasGene = identifiedEntities.some(e =>
          e.domain.toLowerCase() === "gene"
        );
        const hasGeneExpression = identifiedEntities.some(e =>
          e.domain.toLowerCase() === "gene_expression"
        );
        const hasDrug = identifiedEntities.some(e =>
          e.domain.toLowerCase() === "drug" ||
          e.domain.toLowerCase() === "medication"
        );

        if (hasDisease) {
          state.entity_type = "disease";
        } else if (hasSpecies) {
          state.entity_type = "species";
        } else if (hasDrug) {
          state.entity_type = "drug";
        } else if (hasGene) {
          state.entity_type = "gene";
        } else if (entityResult.primary_entity) {
          // Fallback to primary entity's domain
          const domain = entityResult.primary_entity.domain.toLowerCase();
          if (domain === "disease" || domain === "condition" || domain === "disorder") {
            state.entity_type = "disease";
          } else if (domain === "species" || domain === "organism") {
            state.entity_type = "species";
          } else if (domain === "drug" || domain === "medication") {
            state.entity_type = "drug";
          } else if (domain === "gene") {
            state.entity_type = "gene";
          } else {
            state.entity_type = "other";
          }
        }

        console.log(`[Ontology] Entity type set to: ${state.entity_type} (prioritized from ${identifiedEntities.length} entities)`);
      } catch (error: any) {
        state.stage_errors!.entity_identification = error.message;
        console.error("[Ontology] Entity identification failed:", error);
        // Fallback: assume disease entity with the raw phrase
        identifiedEntities = [{
          term: entityPhrase,
          domain: "disease",
          ontology: "MONDO",
        }];
      }
    } else {
      // Skip entity identification, use explicit MONDO IDs
      mondoIRIs = explicitMONDOIDs;
      identifiedEntities = [];
    }

    // Stage 2: Ground identified entities to ontology via OLS
    // Ground ALL entity types found (disease, species, drug, etc.)
    // This allows queries like "influenza" to be grounded as BOTH disease AND organism
    const isGeneEntity = state.entity_type === "gene";
    if (mondoIRIs.length === 0 && identifiedEntities.length > 0 && !isGeneEntity) {
      try {
        // Group entities by ontology type
        const diseaseEntities = identifiedEntities.filter(e =>
          e.ontology.toUpperCase() === "MONDO" ||
          e.domain.toLowerCase() === "disease" ||
          e.domain.toLowerCase() === "condition" ||
          e.domain.toLowerCase() === "disorder"
        );
        const speciesEntities = identifiedEntities.filter(e =>
          e.ontology.toUpperCase() === "NCBITAXON" ||
          e.domain.toLowerCase() === "species" ||
          e.domain.toLowerCase() === "organism"
        );
        const drugEntities = identifiedEntities.filter(e =>
          e.ontology.toUpperCase() === "WIKIDATA" ||
          e.domain.toLowerCase() === "drug" ||
          e.domain.toLowerCase() === "medication"
        );

        console.log(`[Ontology] Stage 2: Grounding entities by type - Disease: ${diseaseEntities.length}, Species: ${speciesEntities.length}, Drug: ${drugEntities.length}`);

        // Determine primary ontology based on entity_type for backward compatibility
        let targetOntology: string | null = null;
        if (state.entity_type === "disease") {
          targetOntology = "MONDO";
        } else if (state.entity_type === "species") {
          targetOntology = "NCBITaxon";
        } else if (state.entity_type === "drug" || (state.entity_type as string) === "medication") {
          targetOntology = "Wikidata";
        } else if (isGeneEntity) {
          // Gene entities don't need ontology grounding - gene symbols are used directly in queries
          targetOntology = null;
          console.log(`[Ontology] Gene entity detected - skipping ontology grounding, will use gene symbol directly`);
        } else {
          // Default to MONDO for backward compatibility
          targetOntology = "MONDO";
        }

        // For gene entities, use gene entities directly (no ontology grounding needed)
        if (state.entity_type === "gene" && targetOntology === null) {
          const geneEntities = identifiedEntities.filter(e =>
            e.domain.toLowerCase() === "gene"
          );
          console.log(`[Ontology] Stage 2: Using ${geneEntities.length} gene entities directly (no ontology grounding needed)`);
          // Store gene entities for use in queries
          state.debug_info!.identified_entities = geneEntities;
          // Skip grounding and proceed to next stage
          return state;
        }

        // Ground ALL entity types (disease, species, drug) - not just the primary type
        // This allows queries like "influenza" to be grounded as BOTH disease AND organism
        let allGroundingResults: MONDOGroundingResult[] = [];

        // Ground disease entities to MONDO
        if (diseaseEntities.length > 0) {
          console.log(`[Ontology] Grounding ${diseaseEntities.length} disease entities to MONDO`);
          for (const entity of diseaseEntities) {
            const groundingResults = await groundEntityToOntology(entity, 3, text);
            for (const result of groundingResults) {
              if (!allGroundingResults.find(r => r.mondo === result.mondo)) {
                allGroundingResults.push(result);
              }
            }
          }
        }

        // Ground species entities to NCBITaxon
        if (speciesEntities.length > 0) {
          console.log(`[Ontology] Grounding ${speciesEntities.length} species entities to NCBITaxon`);
          for (const entity of speciesEntities) {
            const groundingResults = await groundEntityToOntology(entity, 3, text);
            for (const result of groundingResults) {
              if (!allGroundingResults.find(r => r.mondo === result.mondo)) {
                allGroundingResults.push(result);
              }
            }
          }
        }

        // Ground drug entities to Wikidata
        if (drugEntities.length > 0) {
          console.log(`[Ontology] Grounding ${drugEntities.length} drug entities to Wikidata`);
          for (const entity of drugEntities) {
            const groundingResults = await groundEntityToOntology(entity, 3, text);
            for (const result of groundingResults) {
              if (!allGroundingResults.find(r => r.mondo === result.mondo)) {
                allGroundingResults.push(result);
              }
            }
          }
        }

        // Set targetEntities to all entities we're grounding (for compatibility with existing code)
        const targetEntities = [...diseaseEntities, ...speciesEntities, ...drugEntities];

        console.log(`[Ontology] Grounded ${targetEntities.length} entities to ${allGroundingResults.length} total unique terms`);

        let groundingResults = allGroundingResults;

        // Check if we have multiple entity types (disease, species, drug)
        const hasMultipleEntityTypes = diseaseEntities.length > 0 && (speciesEntities.length > 0 || drugEntities.length > 0) ||
          speciesEntities.length > 0 && drugEntities.length > 0;

        // Filter results based on target ontology (MONDO, NCBITaxon, or Wikidata)
        // BUT: if we have multiple entity types, keep ALL results (don't filter by ontology)
        let filteredResults = groundingResults;

        if (hasMultipleEntityTypes) {
          // Keep all results from all ontologies
          console.log(`[Ontology] Multiple entity types detected - keeping all ${filteredResults.length} terms across ontologies`);
          console.log(`[Ontology] - Disease (MONDO): ${filteredResults.filter(r => r.mondo?.includes("/MONDO_")).length} terms`);
          console.log(`[Ontology] - Species (UniProt): ${filteredResults.filter(r => r.mondo?.includes("/taxonomy/")).length} terms`);
          console.log(`[Ontology] - Drug (Wikidata): ${filteredResults.filter(r => r.mondo?.includes("wikidata.org/entity/")).length} terms`);
        } else if (targetOntology === "MONDO") {
          // Filter to only MONDO terms (remove any HP or other ontologies that slipped through)
          filteredResults = groundingResults.filter(r => {
            const iri = r.mondo || "";
            return iri.includes("/MONDO_") && !iri.includes("/HP_");
          });
          console.log(`[Ontology] Initial grounding returned ${filteredResults.length} MONDO terms from ${targetEntities.length} entities`);
        } else if (targetOntology === "NCBITaxon") {
          // Filter to only NCBITaxon terms
          filteredResults = groundingResults.filter(r => {
            const iri = r.mondo || "";
            return iri.includes("/NCBITaxon_") || iri.includes("/taxonomy/");
          });
          console.log(`[Ontology] Initial grounding returned ${filteredResults.length} NCBITaxon terms from ${targetEntities.length} entities`);
        } else if (targetOntology === "Wikidata") {
          // Filter to only Wikidata terms
          filteredResults = groundingResults.filter(r => {
            const iri = r.mondo || "";
            return iri.includes("wikidata.org/entity/");
          });
          console.log(`[Ontology] Initial grounding returned ${filteredResults.length} Wikidata terms from ${targetEntities.length} entities`);
          if (filteredResults.length === 0 && groundingResults.length > 0) {
            console.warn(`[Ontology] Wikidata filtering removed all ${groundingResults.length} results - check IRIs:`,
              groundingResults.map(r => r.mondo).slice(0, 3));
          }
          if (filteredResults.length === 0 && groundingResults.length === 0) {
            console.warn(`[Ontology] Wikidata grounding returned 0 results for entities:`,
              targetEntities.map(e => `${e.term} (${e.domain} → ${e.ontology})`));
          }
        } else {
          // For other ontologies, keep all results
          console.log(`[Ontology] Initial grounding returned ${filteredResults.length} terms from ${targetEntities.length} entities`);
        }

        // Set generic field names
        state.debug_info!.ontology_query_executed = true;
        state.debug_info!.ontology_query_result_count = filteredResults.length;

        // Stage 2.5: If no results found for any entity, try alternative names for entities that failed
        // Only do this for disease/MONDO entities for now (alternative names for organisms less critical)
        if (filteredResults.length === 0 && targetOntology === "MONDO" && targetEntities.length > 0) {
          // Try alternative names for each entity that didn't get results
          for (const targetEntity of targetEntities) {
            // Check if this entity already has results
            const entityHasResults = filteredResults.some(r =>
              r.label?.toLowerCase().includes(targetEntity.term.toLowerCase()) ||
              targetEntity.term.toLowerCase().includes(r.label?.toLowerCase() || "")
            );

            if (!entityHasResults) {
              console.log(`[Ontology] No OLS results for "${targetEntity.term}", generating alternative names...`);
              try {
                const alternatives = await generateAlternativeNames(targetEntity, llmUrl);
                console.log(`[Ontology] Generated ${alternatives.length} alternative names for "${targetEntity.term}":`, alternatives);

                // Add to candidate labels
                if (!state.candidate_labels) {
                  state.candidate_labels = [];
                }
                state.candidate_labels.push(...alternatives);

                // Search alternatives in OLS (use same human-only filter as initial search)
                const humanOnly = !detectAnimalDiseaseIntent(text);
                const alternativeResults = await groundTermsToMONDO(alternatives, humanOnly);
                const newResults = alternativeResults.filter(r => {
                  const iri = r.mondo || "";
                  return iri.includes("/MONDO_") && !iri.includes("/HP_");
                });

                // Add new results, avoiding duplicates
                for (const result of newResults) {
                  if (!filteredResults.find(r => r.mondo === result.mondo)) {
                    filteredResults.push(result);
                  }
                }

                console.log(`[Ontology] Alternative search for "${targetEntity.term}" returned ${newResults.length} MONDO terms`);
                state.debug_info!.alternatives_used = true;
              } catch (error: any) {
                state.stage_errors!.alternative_generation = error.message;
                console.error(`[Ontology] Alternative name generation failed for "${targetEntity.term}":`, error);
              }
            }
          }

          state.debug_info!.ontology_query_result_count = filteredResults.length;
        }

        state.grounded_mondo_terms = filteredResults;

        // Ranking priority:
        // Score 4 = exact match to preferred label (highest priority - use automatically)
        // Score 3 = exact match to exact synonym (EXACT scope) (high priority - use automatically)
        // Score 2 = exact match to other synonym types (NARROW, BROAD, RELATED) (medium priority - use automatically)
        // Score 1 = partial/substring match (low priority - requires user confirmation)
        const topScore = filteredResults.length > 0 ? (filteredResults[0].matchScore || 0) : 0;

        // Separate partial matches (score 1) that need user confirmation
        let partialMatches = filteredResults.filter(r => (r.matchScore || 0) === 1);
        let highConfidenceMatches = filteredResults.filter(r => (r.matchScore || 0) >= 2);

        // If we only have partial matches, try to get synonyms from Ubergraph and re-score
        // This helps when OLS doesn't return synonyms in the search response
        if (partialMatches.length > 0 && highConfidenceMatches.length === 0) {
          console.log(`[Ontology] Only partial matches found. Checking Ubergraph synonyms to re-score...`);
          try {
            const partialIRIs = partialMatches.map(r => r.mondo).slice(0, 5); // Check top 5 partial matches
            const synonymResults = await expandMONDOSynonyms(partialIRIs);

            // Re-score partial matches against their synonyms
            const queryLower = entityPhrase.toLowerCase().trim();
            for (const partialMatch of partialMatches) {
              const synonymData = synonymResults.find(s => s.mondo === partialMatch.mondo);
              if (synonymData && synonymData.synonyms) {
                // Check if query exactly matches any synonym
                for (const synonym of synonymData.synonyms) {
                  if (synonym.toLowerCase().trim() === queryLower) {
                    // Upgrade from partial (score 1) to exact synonym (score 3)
                    console.log(`[Ontology] Upgraded ${partialMatch.obo_id || partialMatch.mondo} from partial to exact synonym match via Ubergraph`);
                    partialMatch.matchScore = 3;
                    partialMatch.matchType = "synonym";
                    partialMatch.matchedText = synonym;
                    // Move to high confidence
                    highConfidenceMatches.push(partialMatch);
                    partialMatches = partialMatches.filter(r => r.mondo !== partialMatch.mondo);
                    break;
                  }
                }
              }
            }
          } catch (error: any) {
            console.warn(`[Ontology] Failed to check Ubergraph synonyms for re-scoring:`, error);
          }
        }

        // Store remaining partial matches for user confirmation
        if (partialMatches.length > 0) {
          state.debug_info = state.debug_info || {};
          state.debug_info.partial_matches_need_confirmation = partialMatches.map(r => ({
            mondo: r.mondo,
            label: r.label,
            obo_id: r.obo_id,
            matchScore: r.matchScore || 1,
            matchType: r.matchType || "partial",
            matchedText: r.matchedText,
          }));
          console.log(`[Ontology] Found ${partialMatches.length} partial matches that need user confirmation:`,
            partialMatches.map(r => `${r.obo_id || r.mondo} (${r.label})`).join(", "));
        }

        // Use high-confidence matches (score 4, 3, or 2) automatically
        if (highConfidenceMatches.length > 0) {
          // Score 4: Exact label matches (highest priority)
          const score4Matches = highConfidenceMatches.filter(r => (r.matchScore || 0) === 4 && r.matchType === "label");
          if (score4Matches.length > 0) {
            const nonObsoleteScore4 = score4Matches.filter(r => !r.is_obsolete);
            const selectedMatches = (nonObsoleteScore4.length > 0 ? nonObsoleteScore4 : score4Matches).slice(0, 3);
            mondoIRIs = selectedMatches.map(r => r.mondo);
            console.log(`[Ontology] Selected ${mondoIRIs.length} MONDO terms with score 4 (exact label) for querying:`,
              selectedMatches.map(r => `${r.obo_id || r.mondo} (${r.label}, match: ${r.matchType})`).join(", "));
          } else {
            // Score 3: Exact synonym matches (EXACT scope)
            const score3Matches = highConfidenceMatches.filter(r => (r.matchScore || 0) === 3 && r.matchType === "synonym");
            if (score3Matches.length > 0) {
              const nonObsoleteScore3 = score3Matches.filter(r => !r.is_obsolete);
              const selectedMatches = (nonObsoleteScore3.length > 0 ? nonObsoleteScore3 : score3Matches).slice(0, 3);
              mondoIRIs = selectedMatches.map(r => r.mondo);
              console.log(`[Ontology] Selected ${mondoIRIs.length} MONDO terms with score 3 (exact synonym) for querying:`,
                selectedMatches.map(r => `${r.obo_id || r.mondo} (${r.label}, match: ${r.matchType})`).join(", "));
            } else {
              // Score 2: Other synonym types (NARROW, BROAD, RELATED)
              const score2Matches = highConfidenceMatches.filter(r => (r.matchScore || 0) === 2);
              if (score2Matches.length > 0) {
                const nonObsoleteScore2 = score2Matches.filter(r => !r.is_obsolete);
                const selectedMatches = (nonObsoleteScore2.length > 0 ? nonObsoleteScore2 : score2Matches).slice(0, 3);
                mondoIRIs = selectedMatches.map(r => r.mondo);
                console.log(`[Ontology] Selected ${mondoIRIs.length} MONDO terms with score 2 (other synonym types) for querying:`,
                  selectedMatches.map(r => `${r.obo_id || r.mondo} (${r.label}, match: ${r.matchType})`).join(", "));
              }
            }
          }
        } else if (partialMatches.length > 0) {
          // Only partial matches available - don't use them automatically
          // They will be shown to the user for confirmation
          console.log(`[Ontology] Only partial matches found - waiting for user confirmation before querying`);
          mondoIRIs = []; // Don't query with partial matches automatically
        } else {
          // No matches at all
          const ontologyName = targetOntology === "MONDO" ? "MONDO" : targetOntology;
          console.log(`[Ontology] No ${ontologyName} terms found for querying`);
          mondoIRIs = [];
        }
      } catch (error: any) {
        console.error("[Ontology] MONDO grounding error:", error);
        state.stage_errors!.mondo_grounding = error.message;
      }
    } else {
      // Use explicit MONDO IDs - create grounding results
      state.grounded_mondo_terms = mondoIRIs.map(iri => ({
        mondo: iri,
        label: "",
        matchedText: "",
        matchedPred: "",
      }));
    }

    // Stage 3: Expand synonyms (if MONDO terms found)
    if (mondoIRIs.length > 0) {
      try {
        state.synonyms = await expandMONDOSynonyms(mondoIRIs);
      } catch (error: any) {
        state.stage_errors!.synonym_expansion = error.message;
      }
    }

    // Stage 4: Detect NDE encoding (for template to use)
    let ndeEncoding: "iri" | "curie" = "iri";
    try {
      ndeEncoding = await detectNDEEncoding();
      state.nde_encoding = ndeEncoding;
    } catch (error: any) {
      state.stage_errors!.nde_encoding = error.message;
      // Default to IRI
    }

    // Mark fallback if no MONDO terms found
    if (mondoIRIs.length === 0) {
      state.fallback_used = true;
    }

    // Note: Stage 5 (Dataset Query) is handled by the template generator
    // The template will use the MONDO terms from state.grounded_mondo_terms
    // Stage 6 (Fallback) is also handled by the template if no MONDO terms found

    // Store gene expression information for graph selection
    const hasGeneExpression = state.debug_info?.identified_entities?.some(
      (e: IdentifiedEntity) => e.domain.toLowerCase() === "gene_expression"
    ) || false;
    state.debug_info!.has_gene_expression = hasGeneExpression;

    // Store recommended graphs for gene expression queries
    if (state.entity_type === "gene" || hasGeneExpression) {
      const geneGraphs = selectGraphsForGeneExpression(
        state.entity_type,
        hasGeneExpression,
        state.debug_info?.identified_entities
      );
      state.debug_info!.recommended_graphs = geneGraphs;
      console.log(`[Ontology] Gene expression query detected, recommended graphs: ${geneGraphs.join(", ")}`);
    }
  } catch (error: any) {
    // Overall workflow error
    console.error("Ontology query processing failed:", error);
  }

  return state;
}

