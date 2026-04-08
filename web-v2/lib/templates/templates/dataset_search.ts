import type { ContextPack, TemplateDefinition } from "@/lib/context-packs/types";
import type { Intent } from "@/types";
import {
  buildNDEDatasetQueryIRI,
  buildNDEDatasetQueryCURIE,
  buildNDESpeciesQueryIRI,
  buildNDESpeciesQueryCURIE,
  buildNDEFallbackQuery,
  buildNDEDatasetKeywordAndFacetQuery,
  buildGXAExperimentsForGenesQuery,
  buildWikidataDrugQuery,
  buildNDEDiseaseAndOrganismQuery,
} from "@/lib/ontology/templates";
import type { MondoExpansionStats } from "@/lib/ontology/mondo-descendants-ols";
import { expandHealthConditionInputsWithMondoDescendants } from "@/lib/ontology/mondo-descendants-ols";
import {
  convertGeneNameToSymbol,
  isGeneName,
} from "@/lib/ontology/hgnc-client";
import type { TemplateGenerateResult } from "@/lib/templates/generate-types";

export const DATASET_SEARCH_TEMPLATE_ID = "dataset_search";

function dsResult(
  query: string,
  expansionLabels?: string[],
  expansionStats?: MondoExpansionStats
): TemplateGenerateResult {
  const out: TemplateGenerateResult = { query };
  if (expansionLabels && expansionLabels.length > 0) {
    out.mondoExpansionHighlightLabels = expansionLabels;
  }
  if (expansionStats) {
    out.mondoExpansionStats = expansionStats;
  }
  return out;
}

function withLimit(
  query: string,
  limit: number | undefined,
  pack: ContextPack,
  expansionLabels?: string[],
  expansionStats?: MondoExpansionStats
): TemplateGenerateResult {
  if (!limit) {
    return dsResult(query, expansionLabels, expansionStats);
  }
  const maxLimit = Math.min(limit, pack.guardrails.max_limit);
  const withoutLimit = query.replace(/\s*LIMIT\s+\d+\s*$/i, "").trim();
  return dsResult(`${withoutLimit}\nLIMIT ${maxLimit}`, expansionLabels, expansionStats);
}

function withSparqlFilterContext(
  stats: MondoExpansionStats | undefined,
  appliedToSparqlFilter: boolean
): MondoExpansionStats | undefined {
  if (!stats) return undefined;
  return { ...stats, appliedToSparqlFilter };
}

export const datasetSearchTemplate: TemplateDefinition = {
  id: DATASET_SEARCH_TEMPLATE_ID,
  description: "Find datasets by keywords with optional health condition, host species, and pathogen species filters",
  required_slots: [],
  optional_slots: [
    "health_condition",
    "mondo_expand_descendants",
    "infectious_agent",
    "species",
    "only_gene_expression",
  ],
};

/** Opt-in: MONDO subclass expansion when `mondo_expand_descendants` is truthy (form checkbox / JSON). */
function isMondoExpandDescendantsEnabled(slot: unknown): boolean {
  if (slot === true) return true;
  const raw = Array.isArray(slot) ? slot[0] : slot;
  if (raw === undefined || raw === null || raw === false) return false;
  if (typeof raw === "number" && raw === 1) return true;
  if (typeof raw === "string") {
    const t = raw.trim().toLowerCase();
    return t === "true" || t === "1" || t === "yes" || t === "on";
  }
  return false;
}

async function maybeExpandMondoIrisForNDE(
  mondoIRIs: string[],
  mondoExpandSlot: unknown
): Promise<{ iris: string[]; highlightLabels: string[]; stats?: MondoExpansionStats }> {
  if (mondoIRIs.length === 0 || !isMondoExpandDescendantsEnabled(mondoExpandSlot)) {
    return { iris: mondoIRIs, highlightLabels: [] };
  }
  try {
    const r = await expandHealthConditionInputsWithMondoDescendants(mondoIRIs);
    return {
      iris: r.expandedInputs,
      highlightLabels: r.highlightLabels,
      stats: r.stats,
    };
  } catch (e) {
    console.warn(
      "[Template] MONDO descendant expansion failed; using selected IRIs only:",
      e
    );
    return { iris: mondoIRIs, highlightLabels: [] };
  }
}

/** Keyword/facet `health_condition` slot: MONDO values expanded; free text and other IRIs unchanged. */
async function maybeExpandHealthConditionFacetInputs(
  inputs: string[],
  mondoExpandSlot: unknown
): Promise<{ inputs: string[]; highlightLabels: string[]; stats?: MondoExpansionStats }> {
  if (inputs.length === 0 || !isMondoExpandDescendantsEnabled(mondoExpandSlot)) {
    return { inputs, highlightLabels: [] };
  }
  try {
    const r = await expandHealthConditionInputsWithMondoDescendants(inputs);
    return {
      inputs: r.expandedInputs,
      highlightLabels: r.highlightLabels,
      stats: r.stats,
    };
  } catch (e) {
    console.warn(
      "[Template] MONDO descendant expansion failed; using selected terms only:",
      e
    );
    return { inputs, highlightLabels: [] };
  }
}

export interface DatasetSearchOptions {
  /** Restrict results to NCBI GEO datasets in NDE (identifier GSE* or url/sameAs containing geo/ncbi). */
  geoOnly?: boolean;
}

export async function buildDatasetSearchQuery(
  intent: Intent,
  pack: ContextPack,
  options?: DatasetSearchOptions
): Promise<TemplateGenerateResult> {
  const slots = intent.slots || {};
  const geoOnly = options?.geoOnly ?? false;

  // Check if ontology-grounded workflow was used
  const healthConditions = slots.health_conditions as string[] | undefined;
  const species = slots.species as string[] | undefined;
  const drugs = slots.drugs as string[] | undefined;
  const ndeEncoding = (slots.nde_encoding as "iri" | "curie") || "iri";
  const ontologyState = slots.ontology_state as any;
  const entityType = ontologyState?.entity_type || "disease";

  // Debug logging
  if (intent.ontology_workflow) {
    console.log(`[Template] buildDatasetSearchQuery - entityType: ${entityType}, ontology_workflow: ${intent.ontology_workflow}, has ontologyState: ${!!ontologyState}`);
  }

  // Handle queries with BOTH disease AND organism entities (e.g., "influenza" as both disease and pathogen)
  // This should be checked FIRST before individual disease/species handlers
  if (
    intent.ontology_workflow &&
    Array.isArray(healthConditions) && healthConditions.length > 0 &&
    Array.isArray(species) && species.length > 0
  ) {
    const mondoIRIs = healthConditions.filter(iri =>
      typeof iri === "string" && iri.startsWith("http://purl.obolibrary.org/obo/MONDO_")
    );
    const speciesIRIs = species.filter(iri =>
      typeof iri === "string" && iri.startsWith("https://www.uniprot.org/taxonomy/")
    );

    if (mondoIRIs.length > 0 && speciesIRIs.length > 0) {
      console.log(`[Template] Building combined disease+organism query with ${mondoIRIs.length} diseases and ${speciesIRIs.length} organisms`);

      // Extract labels for both diseases and organisms
      const selectedMondoIRISet = new Set(mondoIRIs);
      const selectedSpeciesIRISet = new Set(speciesIRIs);

      const diseaseTerms = (ontologyState?.grounded_mondo_terms || [])
        .filter((term: any) => selectedMondoIRISet.has(term.mondo))
        .slice(0, 3);
      const diseaseLabels = diseaseTerms.map((term: any) => term.label).filter(Boolean);

      const organismTerms = (ontologyState?.grounded_mondo_terms || [])
        .filter((term: any) => selectedSpeciesIRISet.has(term.mondo))
        .slice(0, 3);
      const organismLabels = organismTerms.map((term: any) => term.label).filter(Boolean);

      // Determine if we should use text matching
      const hasHighConfidence =
        diseaseTerms.some((term: any) => (term.matchScore || 0) >= 3) ||
        organismTerms.some((term: any) => (term.matchScore || 0) >= 3);
      const useTextMatching = hasHighConfidence && (diseaseLabels.length > 0 || organismLabels.length > 0);

      // Keyword fallback: match name/description so we get results when ontology IRIs are not in the graph
      const keywordFallbackTerms = [...new Set([...diseaseLabels, ...organismLabels])]
        .filter(Boolean)
        .slice(0, 5);

      const { iris: mondoIRIsForQuery, highlightLabels: mondoExpandHl, stats: mondoExpandStats } =
        await maybeExpandMondoIrisForNDE(mondoIRIs, slots.mondo_expand_descendants);

      // When we have keyword fallback, use the simple REGEX-only query so NDE returns results (the full
      // disease+organism query with OPTIONALs returns 0 on the NDE endpoint even with FROM stripped)
      const combinedQuery =
        keywordFallbackTerms.length > 0
          ? buildNDEFallbackQuery(
            keywordFallbackTerms[0],
            keywordFallbackTerms.slice(1),
            geoOnly
          )
          : buildNDEDiseaseAndOrganismQuery(
            mondoIRIsForQuery,
            speciesIRIs,
            diseaseLabels,
            organismLabels,
            useTextMatching,
            keywordFallbackTerms,
            500,
            geoOnly
          );

      return withLimit(
        combinedQuery,
        intent.slots?.limit as number | undefined,
        pack,
        mondoExpandHl,
        withSparqlFilterContext(mondoExpandStats, keywordFallbackTerms.length === 0)
      );
    }
  }

  // Handle species/organism entities with schema:species
  if (
    intent.ontology_workflow &&
    (entityType === "species" || entityType === "organism") &&
    Array.isArray(species) &&
    species.length > 0
  ) {
    // All species should be UniProt taxonomy IRIs at this point
    const speciesIRIs = species.filter(iri =>
      typeof iri === "string" && iri.startsWith("https://www.uniprot.org/taxonomy/")
    );

    if (speciesIRIs.length > 0) {
      // Extract labels from ontology state for text search
      const selectedIRISet = new Set(speciesIRIs);
      const selectedTerms = (ontologyState?.grounded_mondo_terms || [])
        .filter((term: any) => selectedIRISet.has(term.mondo))
        .slice(0, 3);

      // Only use preferred names (labels) for text search
      const labels = selectedTerms
        .map((term: any) => term.label)
        .filter(Boolean);

      // Determine if we should use text matching based on confidence scores
      // Only use text matching for high-confidence matches (score 4 or 3) to reduce noise
      const hasHighConfidence = selectedTerms.some((term: any) =>
        (term.matchScore || 0) >= 3
      );
      const useTextMatching = hasHighConfidence && labels.length > 0;

      // Use species query template with optional text search
      const speciesQuery = ndeEncoding === "iri"
        ? buildNDESpeciesQueryIRI(speciesIRIs, labels, [], useTextMatching)
        : buildNDESpeciesQueryCURIE(speciesIRIs, labels, [], useTextMatching);

      return withLimit(speciesQuery, intent.slots?.limit as number | undefined, pack);
    }
  }

  // Handle drug/medication entities with Wikidata IRIs
  if (
    intent.ontology_workflow &&
    (entityType === "drug" || entityType === "medication") &&
    Array.isArray(drugs) &&
    drugs.length > 0
  ) {
    // All drugs should be Wikidata IRIs at this point
    const wikidataIRIs = drugs.filter(iri =>
      typeof iri === "string" && iri.startsWith("http://www.wikidata.org/entity/")
    );

    if (wikidataIRIs.length > 0) {
      // Extract labels from ontology state for text search
      const selectedIRISet = new Set(wikidataIRIs);
      const selectedTerms = (ontologyState?.grounded_mondo_terms || [])
        .filter((term: any) => selectedIRISet.has(term.mondo))
        .slice(0, 3);

      // Only use preferred names (labels) for text search
      const labels = selectedTerms
        .map((term: any) => term.label)
        .filter(Boolean);

      // Determine if we should use text matching based on confidence scores
      // Only use text matching for high-confidence matches (score 4 or 3) to reduce noise
      const hasHighConfidence = selectedTerms.some((term: any) =>
        (term.matchScore || 0) >= 3
      );
      const useTextMatching = hasHighConfidence && labels.length > 0;

      // Use Wikidata drug query template
      const drugQuery = buildWikidataDrugQuery(wikidataIRIs, labels, useTextMatching);

      return withLimit(drugQuery, intent.slots?.limit as number | undefined, pack);
    }
  }

  // Handle disease entities with schema:healthCondition (existing logic)
  if (
    intent.ontology_workflow &&
    Array.isArray(healthConditions) &&
    healthConditions.length > 0
  ) {
    console.log(`[Template] Entering ontology workflow block for health_conditions`);
    console.log(`[Template] healthConditions:`, healthConditions);
    console.log(`[Template] ontologyState:`, ontologyState);

    // Separate MONDO IRIs from Wikidata IRIs
    const mondoIRIs = healthConditions.filter(iri =>
      typeof iri === "string" && iri.startsWith("http://purl.obolibrary.org/obo/MONDO_")
    );

    const wikidataIRIs = healthConditions.filter(iri =>
      typeof iri === "string" && iri.startsWith("http://www.wikidata.org/entity/")
    );

    console.log(`[Template] Found ${mondoIRIs.length} MONDO IRIs and ${wikidataIRIs.length} Wikidata IRIs`);

    if (mondoIRIs.length > 0) {
      console.log(`[Template] Building query for ${mondoIRIs.length} MONDO IRIs`);

      // Extract labels and synonyms from ontology state for text search
      // Filter to only include terms that match the selected mondoIRIs
      const selectedIRISet = new Set(mondoIRIs);
      const selectedTerms = (ontologyState?.grounded_mondo_terms || [])
        .filter((term: any) => selectedIRISet.has(term.mondo))
        .slice(0, 3);

      // Only use preferred names (labels) for text search - no synonyms to reduce ambiguity
      const diseaseLabels = selectedTerms
        .map((term: any) => term.label)
        .filter(Boolean);

      // Determine if we should use text matching based on confidence scores
      const hasHighConfidence = selectedTerms.some((term: any) =>
        (term.matchScore || 0) >= 3
      );
      const useTextMatching = hasHighConfidence && diseaseLabels.length > 0;

      // Keyword fallback for disease-only: match dataset name/description so we get results
      // when NDE has datasets that mention the disease in name/description but lack schema:healthCondition
      const keywordFallbackTerms = [...new Set(diseaseLabels)].filter(Boolean).slice(0, 5);

      console.log(`[Template] useTextMatching: ${useTextMatching}, diseaseLabels: ${diseaseLabels.length}, keywordFallback: ${keywordFallbackTerms.length}`);
      console.log(`[Template] ndeEncoding: ${ndeEncoding}`);

      const { iris: mondoIRIsForQuery, highlightLabels: mondoExpandHl, stats: mondoExpandStats } =
        await maybeExpandMondoIrisForNDE(mondoIRIs, slots.mondo_expand_descendants);

      // When we have keyword fallback, use the simple REGEX-only query so NDE returns results
      const ontologyQuery =
        keywordFallbackTerms.length > 0
          ? buildNDEFallbackQuery(String(keywordFallbackTerms[0]), keywordFallbackTerms.slice(1) as string[], geoOnly)
          : buildNDEDiseaseAndOrganismQuery(
            mondoIRIsForQuery,
            [],
            diseaseLabels,
            [],
            useTextMatching,
            keywordFallbackTerms as string[],
            500,
            geoOnly
          );

      console.log(`[Template] Generated query, length: ${ontologyQuery?.length || 0} chars`);
      console.log(`[Template] Query is truthy: ${!!ontologyQuery}, type: ${typeof ontologyQuery}`);

      return withLimit(
        ontologyQuery,
        intent.slots?.limit as number | undefined,
        pack,
        mondoExpandHl,
        withSparqlFilterContext(mondoExpandStats, keywordFallbackTerms.length === 0)
      );
    }

    // If no MONDO IRIs but we have Wikidata IRIs, this is handled by fallback logic in the executor
    console.warn(`[Template] No MONDO IRIs found, but have ${wikidataIRIs.length} Wikidata IRIs. Executor should fallback to text search.`);
  } // End of: if (intent.ontology_workflow && Array.isArray(healthConditions) && healthConditions.length > 0)

  // Handle gene entities - extract gene symbols from identified entities
  // This should run before the fallback to ensure gene queries use the proper gene expression query
  // Also check for gene names even if entityType isn't explicitly "gene" (LLM might miss it)
  if (
    intent.ontology_workflow &&
    ontologyState
  ) {
    // Check if we have gene entities or if we should detect gene names from the query
    const hasGeneEntity = entityType === "gene" ||
      (ontologyState.debug_info?.identified_entities || []).some(
        (e: any) => e.domain?.toLowerCase() === "gene"
      );

    console.log(`[Template] Checking for gene entities. Entity type: ${entityType}, Has gene entity: ${hasGeneEntity}, Raw phrase: ${ontologyState.raw_phrase}`);

    // Extract gene terms from identified entities
    // Try to get from identified_entities first, fallback to raw_phrase if needed
    let geneTerms: string[] = [];
    if (ontologyState.debug_info?.identified_entities) {
      const geneEntities = ontologyState.debug_info.identified_entities.filter(
        (e: any) => e.domain?.toLowerCase() === "gene"
      );
      geneTerms = geneEntities.map((e: any) => e.term).filter(Boolean);
    }

    // If no gene terms found in identified_entities, try to extract from raw_phrase
    // This is important for cases where the LLM didn't classify a gene name as "gene"
    if (geneTerms.length === 0 && ontologyState.raw_phrase) {
      const words = ontologyState.raw_phrase.split(/\s+/);
      // Gene symbols are typically 2-10 characters, capitalized, may include numbers
      const potentialGeneSymbols = words.filter((word: string) => {
        const cleaned = word.replace(/[.,;:!?]/g, '');
        return cleaned.length >= 2 &&
          cleaned.length <= 10 &&
          /^[A-Z][A-Za-z0-9]*$/.test(cleaned) &&
          cleaned.toLowerCase() !== 'find' &&
          cleaned.toLowerCase() !== 'where' &&
          cleaned.toLowerCase() !== 'experiments' &&
          cleaned.toLowerCase() !== 'upregulated' &&
          cleaned.toLowerCase() !== 'downregulated' &&
          cleaned.toLowerCase() !== 'is';
      });
      if (potentialGeneSymbols.length > 0) {
        geneTerms = [potentialGeneSymbols[0]]; // Use first potential gene symbol
        console.log(`[Template] Extracted gene term from raw_phrase: ${geneTerms[0]}`);
      } else {
        // If no short symbols found, check if the raw phrase itself might be a gene name
        // Remove common query words and check if what remains looks like a gene name
        const cleanedPhrase = ontologyState.raw_phrase
          .replace(/\b(find|experiments|where|is|upregulated|downregulated|show|all|datasets|related|to|experiments|where)\b/gi, '')
          .trim();

        // Try the cleaned phrase first
        if (cleanedPhrase.length > 0 && isGeneName(cleanedPhrase)) {
          geneTerms = [cleanedPhrase];
          console.log(`[Template] Detected gene name in cleaned phrase: ${geneTerms[0]}`);
        } else {
          // If cleaned phrase doesn't work, try to extract multi-word phrases that might be gene names
          // Look for phrases that are 3+ words and contain gene-related keywords
          const words = ontologyState.raw_phrase.split(/\s+/);
          for (let i = 0; i < words.length - 2; i++) {
            // Try 3-word, 4-word, and 5-word phrases
            for (let len = 3; len <= 5 && i + len <= words.length; len++) {
              const phrase = words.slice(i, i + len).join(' ').replace(/[.,;:!?]/g, '');
              if (phrase.length > 15 && isGeneName(phrase)) {
                geneTerms = [phrase];
                console.log(`[Template] Detected gene name in phrase: ${geneTerms[0]}`);
                break;
              }
            }
            if (geneTerms.length > 0) break;
          }
        }
      }
    }

    // Also check raw_phrase directly for common gene symbol patterns if still not found
    if (geneTerms.length === 0 && ontologyState.raw_phrase) {
      // Try to match gene symbols directly in the phrase (e.g., "Dusp2", "TP53")
      const geneSymbolMatch = ontologyState.raw_phrase.match(/\b([A-Z][A-Za-z0-9]{1,9})\b/);
      if (geneSymbolMatch && geneSymbolMatch[1]) {
        const symbol = geneSymbolMatch[1];
        // Exclude common words
        if (!['Find', 'Where', 'Experiments', 'Is', 'Upregulated', 'Downregulated', 'Show', 'All', 'Datasets', 'Related', 'To'].includes(symbol)) {
          geneTerms = [symbol];
          console.log(`[Template] Extracted gene symbol via regex: ${geneTerms[0]}`);
        }
      }
    }

    // Only proceed with gene query if we found gene terms OR if we have a gene entity
    // This ensures we don't accidentally trigger gene queries for non-gene queries
    if (geneTerms.length === 0 && !hasGeneEntity) {
      // No gene terms found and no gene entity detected, skip gene handler
      console.log(`[Template] No gene terms found, skipping gene handler`);
    } else {
      // Detect organism from identified entities or ontology state
      // Default to human if no organism is detected
      let organism: string | undefined = undefined;

      // Check for species/organism entities in identified entities
      const identifiedEntities = ontologyState.debug_info?.identified_entities || [];
      const speciesEntities = identifiedEntities.filter(
        (e: any) => e.domain?.toLowerCase() === "species" || e.domain?.toLowerCase() === "organism"
      );

      if (speciesEntities.length > 0) {
        // Use the first species entity term as organism name
        organism = speciesEntities[0].term;
        console.log(`[Template] Detected organism from entities: ${organism}`);
      } else {
        // Check if species slot is populated (from ontology grounding)
        const speciesSlot = slots.species as string[] | undefined;
        if (speciesSlot && speciesSlot.length > 0) {
          // Extract organism name from grounded terms
          const groundedTerms = ontologyState.grounded_mondo_terms || [];
          const speciesTerms = groundedTerms.filter((term: any) =>
            speciesSlot.some((iri: string) => term.mondo === iri || term.mondo?.includes(iri))
          );

          if (speciesTerms.length > 0) {
            organism = speciesTerms[0].label;
            console.log(`[Template] Detected organism from grounded terms: ${organism}`);
          }
        }
      }

      // Default to human if no organism detected
      if (!organism) {
        organism = "homo_sapiens";
        console.log(`[Template] No organism detected, defaulting to human (homo_sapiens)`);
      }

      // Convert gene names to symbols using HGNC API (for human) or Ensembl API (for other organisms)
      // This is important for spokegenelab which uses gene symbols
      let geneSymbols: string[] = [];
      for (const term of geneTerms) {
        if (isGeneName(term)) {
          // It's a gene name, convert to symbol
          console.log(`[Template] Converting gene name to symbol: "${term}" for organism: ${organism}`);
          const symbol = await convertGeneNameToSymbol(term, organism);
          if (symbol) {
            geneSymbols.push(symbol);
            console.log(`[Template] Converted "${term}" to symbol: ${symbol}`);
          } else {
            // If conversion fails, try using the term as-is (might still work)
            console.warn(`[Template] Failed to convert gene name "${term}" to symbol, using as-is`);
            geneSymbols.push(term);
          }
        } else {
          // It's already a symbol, use it directly
          geneSymbols.push(term);
        }
      }

      // Check for gene expression concepts (upregulated, downregulated)
      const hasGeneExpression = ontologyState.debug_info?.has_gene_expression || false;
      let hasUpregulated = identifiedEntities.some((e: any) =>
        e.domain === "gene_expression" &&
        (e.term.toLowerCase().includes("upregulated") ||
          e.term.toLowerCase().includes("up-regulation") ||
          e.term.toLowerCase().includes("increased expression") ||
          e.term.toLowerCase().includes("overexpressed"))
      );
      let hasDownregulated = identifiedEntities.some((e: any) =>
        e.domain === "gene_expression" &&
        (e.term.toLowerCase().includes("downregulated") ||
          e.term.toLowerCase().includes("down-regulation") ||
          e.term.toLowerCase().includes("decreased expression") ||
          e.term.toLowerCase().includes("underexpressed"))
      );

      // Check raw_phrase for upregulated/downregulated if not found in identified entities
      if (!hasUpregulated && !hasDownregulated && ontologyState.raw_phrase) {
        const lowerPhrase = ontologyState.raw_phrase.toLowerCase();
        if (lowerPhrase.includes("upregulated") ||
          lowerPhrase.includes("up-regulation") ||
          lowerPhrase.includes("increased expression") ||
          lowerPhrase.includes("overexpressed")) {
          hasUpregulated = true;
        } else if (lowerPhrase.includes("downregulated") ||
          lowerPhrase.includes("down-regulation") ||
          lowerPhrase.includes("decreased expression") ||
          lowerPhrase.includes("underexpressed")) {
          hasDownregulated = true;
        }
      }

      if (geneSymbols.length > 0) {
        // Determine if we should filter by up/down regulation
        let upregulated: boolean | undefined = undefined;
        if (hasUpregulated) {
          upregulated = true;
        } else if (hasDownregulated) {
          upregulated = false;
        }

        console.log(`[Template] Building gene expression query for symbols: ${geneSymbols.join(", ")}, upregulated: ${upregulated}`);

        // Use GXA experiments-for-genes query template
        const limit = Math.min(
          (intent.slots?.limit as number) || pack.guardrails?.max_limit || 100,
          pack.guardrails?.max_limit || 500
        );
        const geneQuery = buildGXAExperimentsForGenesQuery(geneSymbols, limit, upregulated);

        return dsResult(geneQuery);
      } else {
        console.warn(`[Template] Gene entity detected but no gene symbols extracted. Raw phrase: ${ontologyState.raw_phrase}`);
      }
    }
  }

  // If ontology workflow was used but no MONDO terms found, use fallback text search
  // Skip fallback for gene queries (they should have been handled above)
  if (intent.ontology_workflow && ontologyState &&
    entityType !== "gene" &&
    (!healthConditions || healthConditions.length === 0)) {
    const rawPhrase = ontologyState.raw_phrase || (slots.keywords as string) || "";
    const candidateLabels = ontologyState.candidate_labels || [];

    // Use fallback text search template
    const fallbackQuery = buildNDEFallbackQuery(rawPhrase, candidateLabels, geoOnly);

    return withLimit(fallbackQuery, intent.slots?.limit as number | undefined, pack);
  }

  // Keyword-based search with optional facet slots (form / chat)
  const prefixes = pack.prefixes;
  const keywordsList: string[] | undefined = (slots as any).keywords_list;
  const keywords: string = Array.isArray(slots.keywords)
    ? (slots.keywords as string[]).join(" ")
    : (slots.keywords ?? "").toString();

  const keywordRegexTerms: string[] =
    Array.isArray(keywordsList) && keywordsList.length > 0
      ? keywordsList.map((k) => String(k).trim()).filter(Boolean)
      : [keywords.trim()].filter(Boolean);

  const healthConditionRaw = slots.health_condition;
  const healthConditionInputs: string[] = Array.isArray(healthConditionRaw)
    ? healthConditionRaw.map((s) => String(s).trim()).filter(Boolean)
    : typeof healthConditionRaw === "string" && healthConditionRaw.trim()
      ? healthConditionRaw
          .split(/[,\s]+/)
          .map((s) => s.trim())
          .filter(Boolean)
      : [];

  const infectiousAgentRaw = slots.infectious_agent;
  const infectiousAgentInputs: string[] = Array.isArray(infectiousAgentRaw)
    ? infectiousAgentRaw.map((s) => String(s).trim()).filter(Boolean)
    : typeof infectiousAgentRaw === "string" && infectiousAgentRaw.trim()
      ? infectiousAgentRaw
          .split(/[,\s]+/)
          .map((s) => s.trim())
          .filter(Boolean)
      : [];

  const speciesRaw = slots.species;
  const speciesInputs: string[] = Array.isArray(speciesRaw)
    ? speciesRaw.map((s) => String(s).trim()).filter(Boolean)
    : typeof speciesRaw === "string" && speciesRaw.trim()
      ? speciesRaw
          .split(/[,\s]+/)
          .map((s) => s.trim())
          .filter(Boolean)
      : [];

  let healthForFacet = healthConditionInputs;
  let mondoFacetExpandHl: string[] = [];
  let mondoFacetExpandStats: MondoExpansionStats | undefined;
  if (healthConditionInputs.length > 0) {
    const expanded = await maybeExpandHealthConditionFacetInputs(
      healthConditionInputs,
      slots.mondo_expand_descendants
    );
    healthForFacet = expanded.inputs;
    mondoFacetExpandHl = expanded.highlightLabels;
    mondoFacetExpandStats = expanded.stats;
  }

  let body = buildNDEDatasetKeywordAndFacetQuery(keywordRegexTerms, {
    healthConditionInputs:
      healthForFacet.length > 0 ? healthForFacet : undefined,
    speciesInputs: speciesInputs.length > 0 ? speciesInputs : undefined,
    infectiousAgentInputs:
      infectiousAgentInputs.length > 0 ? infectiousAgentInputs : undefined,
    geoOnly,
  });

  let query = "";
  for (const [prefix, uri] of Object.entries(prefixes)) {
    query += `PREFIX ${prefix}: <${uri}>\n`;
  }
  query += body;

  const limit = intent.slots?.limit as number | undefined;
  if (limit) {
    const maxLimit = Math.min(limit, pack.guardrails.max_limit);
    const withoutLimit = query.replace(/\s*LIMIT\s+\d+\s*$/i, "").trim();
    query = `${withoutLimit}\nLIMIT ${maxLimit}`;
  }

  return dsResult(query, mondoFacetExpandHl, withSparqlFilterContext(mondoFacetExpandStats, true));
}


