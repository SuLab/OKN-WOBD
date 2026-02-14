// Ontology Lookup Service (OLS) client for MONDO grounding
// https://www.ebi.ac.uk/ols4/

import { executeSPARQL } from "@/lib/sparql/executor";

export interface OLSSearchResult {
  id?: string; // MONDO IRI
  iri?: string;
  short_form?: string; // e.g., "MONDO_0006664"
  obo_id?: string; // e.g., "MONDO:0006664"
  label?: string;
  description?: string[];
  synonyms?: string[] | Array<{ value: string; scope?: string }>; // Can be strings or objects with scope
  is_obsolete?: boolean;
  score?: number; // OLS relevance score
  match_type?: string; // "label", "synonym", etc.
  // OLS4 might return different field names
  ontology_name?: string;
  ontology_prefix?: string;
}

// Synonym scope types from MONDO ontology
export type SynonymScope = "EXACT" | "NARROW" | "BROAD" | "RELATED";

export interface OLSSearchResponse {
  response?: {
    docs: OLSSearchResult[];
    numFound: number;
    start: number;
  };
  // Fallback for different API versions
  num_found?: number;
  page?: number;
  docs?: OLSSearchResult[];
}

/**
 * Search OLS for MONDO terms matching a query string
 */
export async function searchOLS(
  query: string,
  ontology: string = "mondo",
  size: number = 20
): Promise<OLSSearchResult[]> {
  try {
    const url = `https://www.ebi.ac.uk/ols4/api/search?q=${encodeURIComponent(query)}&ontology=${ontology}&size=${size}&exact=false`;
    console.log(`[OLS] Calling OLS API: ${url}`);

    const response = await fetch(url, {
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`[OLS] API error ${response.status}:`, errorText);
      throw new Error(`OLS API error: ${response.status} ${response.statusText}`);
    }

    const data: OLSSearchResponse = await response.json();

    // Handle OLS4 response structure: {response: {docs: [...], numFound: X}}
    const docs = data.response?.docs || data.docs || [];
    const numFound = data.response?.numFound || data.num_found || 0;

    console.log(`[OLS] API returned ${numFound} total results, ${docs.length} in this page`);
    console.log(`[OLS] Response structure:`, data.response ? "wrapped in 'response'" : "direct 'docs'");

    if (docs.length > 0) {
      const firstDoc = docs[0];
      console.log(`[OLS] Sample result (summary):`, {
        iri: firstDoc.iri,
        label: firstDoc.label,
        obo_id: firstDoc.obo_id,
        short_form: firstDoc.short_form,
        type: (firstDoc as { type?: string }).type,
        synonyms: firstDoc.synonyms ? (Array.isArray(firstDoc.synonyms) ? firstDoc.synonyms.length : 'not array') : 'none',
        synonyms_sample: firstDoc.synonyms && Array.isArray(firstDoc.synonyms) ? firstDoc.synonyms.slice(0, 3) : undefined,
      });
      // Log full structure for debugging
      console.log(`[OLS] Full first result structure:`, JSON.stringify(firstDoc, null, 2));
    } else {
      console.warn(`[OLS] No docs in response. Response keys:`, Object.keys(data));
      if (data.response) {
        console.warn(`[OLS] Response object keys:`, Object.keys(data.response));
      }
    }

    return docs;
  } catch (error: any) {
    console.error(`[OLS] Search failed for "${query}":`, error);
    throw new Error(`OLS search failed: ${error.message}`);
  }
}

/**
 * Score a MONDO term match based on match quality
 * Returns: 4 = exact label, 3 = exact synonym, 2 = other synonym types, 1 = partial (needs confirmation), 0 = no hit
 */
export function scoreMatch(
  result: OLSSearchResult,
  query: string
): { score: number; matchType: string; matchedText: string; synonymScope?: SynonymScope } {
  const queryLower = query.toLowerCase().trim();
  const label = result.label || "";
  const labelLower = label.toLowerCase().trim();

  // Score 4: Exact match to preferred label (case-insensitive)
  if (labelLower === queryLower) {
    return { score: 4, matchType: "label", matchedText: label };
  }

  // Score 3: Exact match to exact synonym (case-insensitive)
  // Score 2: Exact match to other synonym types (narrow, broad, related)
  if (result.synonyms && Array.isArray(result.synonyms)) {
    for (const synonym of result.synonyms) {
      let synStr: string;
      let synScope: SynonymScope | undefined;

      if (typeof synonym === "string") {
        synStr = synonym;
      } else if (typeof synonym === "object" && synonym !== null) {
        synStr = synonym.value || synonym.toString();
        // OLS might return scope as "EXACT", "NARROW", "BROAD", "RELATED"
        const scope = (synonym as any).scope || (synonym as any).type;
        if (scope) {
          synScope = scope.toUpperCase() as SynonymScope;
        }
      } else {
        synStr = String(synonym);
      }

      const synLower = synStr.toLowerCase().trim();
      if (synLower === queryLower) {
        // Exact synonym match - check if we know the scope
        if (synScope === "EXACT") {
          return { score: 3, matchType: "synonym", matchedText: synStr, synonymScope: "EXACT" };
        } else if (synScope && ["NARROW", "BROAD", "RELATED"].includes(synScope)) {
          return { score: 2, matchType: "synonym", matchedText: synStr, synonymScope: synScope as SynonymScope };
        } else {
          // If we don't know the scope, assume it's an exact synonym (most common case)
          // We'll refine this later when we query Ubergraph for full synonym details
          return { score: 3, matchType: "synonym", matchedText: synStr, synonymScope: "EXACT" };
        }
      }
    }
  }

  // Score 1: Partial/substring match (needs user confirmation)
  if (labelLower && (labelLower.includes(queryLower) || queryLower.includes(labelLower))) {
    return { score: 1, matchType: "label", matchedText: label };
  }

  if (result.synonyms && Array.isArray(result.synonyms)) {
    for (const synonym of result.synonyms) {
      const synStr = typeof synonym === "string" ? synonym :
        (typeof synonym === "object" && synonym !== null ? (synonym as { value?: string }).value || String(synonym) : String(synonym));
      const synLower = synStr.toLowerCase().trim();
      if (synLower.includes(queryLower) || queryLower.includes(synLower)) {
        return { score: 1, matchType: "synonym", matchedText: synStr };
      }
    }
  }

  // Score 0: No match (shouldn't happen if OLS returned it, but handle it)
  // But if OLS returned it, give it at least score 1 for being a match
  if (label) {
    return { score: 1, matchType: "label", matchedText: label };
  }

  return { score: 0, matchType: "none", matchedText: "" };
}

/**
 * Rank MONDO terms by match quality and other factors
 */
export function rankMONDOCTerms(
  results: OLSSearchResult[],
  query: string
): Array<OLSSearchResult & { matchScore: number; matchType: string; matchedText: string; synonymScope?: SynonymScope }> {
  const scored = results.map((result) => {
    const match = scoreMatch(result, query);
    return {
      ...result,
      matchScore: match.score,
      matchType: match.matchType,
      matchedText: match.matchedText,
      synonymScope: match.synonymScope,
    };
  });

  // Sort by:
  // 1. Match score (highest first) - exact matches always win
  // 2. Exact label match over synonym match (even if same score)
  // 3. Prefer canonical terms (no numbers, no "type X" patterns) over numbered variants
  // 4. OLS relevance score (if provided, highest first)
  // 5. Non-obsolete first
  // 6. Label length closer to query length (more specific match)
  const queryLength = query.length;
  const queryLower = query.toLowerCase().trim();

  // Helper: Check if a label looks like a numbered variant (e.g., "dermatitis, atopic, 4" or "disease type 2")
  const isNumberedVariant = (label: string): boolean => {
    const labelLower = label.toLowerCase().trim();
    // Patterns that indicate numbered variants:
    // - Ends with ", X" or ", X" where X is a number
    // - Contains "type X" or "type-X" where X is a number
    // - Contains "X" at the end where X is a single digit
    return (
      /,\s*\d+\s*$/.test(labelLower) || // Ends with ", 4" or ", 2"
      /\btype\s+\d+\b/i.test(labelLower) || // Contains "type 4" or "type-4"
      /^\d+\s*$/.test(labelLower.split(',').pop()?.trim() || '') // Last comma-separated part is just a number
    );
  };

  scored.sort((a, b) => {
    // Primary: match score (exact label = 4, exact synonym = 3, other synonyms = 2, partial = 1)
    if (b.matchScore !== a.matchScore) {
      return b.matchScore - a.matchScore;
    }

    // Secondary: Prefer exact label matches over synonym matches
    // Even if both have same score, exact label match should win
    const aIsExactLabel = (a.label || "").toLowerCase().trim() === queryLower && a.matchType === "label";
    const bIsExactLabel = (b.label || "").toLowerCase().trim() === queryLower && b.matchType === "label";
    if (aIsExactLabel !== bIsExactLabel) {
      return bIsExactLabel ? 1 : -1; // b wins if exact label, a wins if not
    }

    // Tertiary: Prefer canonical terms (no numbered variants) over numbered variants
    // This ensures "atopic dermatitis" is preferred over "dermatitis, atopic, 4"
    const aIsVariant = isNumberedVariant(a.label || "");
    const bIsVariant = isNumberedVariant(b.label || "");
    if (aIsVariant !== bIsVariant) {
      return aIsVariant ? 1 : -1; // a loses if variant, b loses if variant (non-variant wins)
    }

    // Quaternary: OLS relevance score (if provided, highest first)
    const aScore = a.score || 0;
    const bScore = b.score || 0;
    if (bScore !== aScore) {
      return bScore - aScore;
    }

    // Quinary: non-obsolete first
    const aObsolete = a.is_obsolete ? 1 : 0;
    const bObsolete = b.is_obsolete ? 1 : 0;
    if (aObsolete !== bObsolete) {
      return aObsolete - bObsolete;
    }

    // Senary: Label length closer to query length (more specific match)
    // Prefer terms whose label length is closer to the query length
    const aLabelLength = (a.label?.length || 0);
    const bLabelLength = (b.label?.length || 0);
    const aDistance = Math.abs(aLabelLength - queryLength);
    const bDistance = Math.abs(bLabelLength - queryLength);
    if (aDistance !== bDistance) {
      return aDistance - bDistance; // Closer to query length wins
    }

    // If still tied, prefer longer (more specific) label
    return bLabelLength - aLabelLength;
  });

  return scored;
}

/**
 * Ground a single candidate term to MONDO using OLS
 * Returns the best matching MONDO term(s)
 */
/**
 * Check if a result is from MONDO ontology
 * 
 * NOTE: This is disease-specific. For other entity types, we'll need different filters:
 * - Species: NCBITaxon, etc.
 * - Drugs: CHEBI, DRUGBANK, etc.
 * - Genes: HGNC, etc.
 * 
 * The entity type should be determined from the query context, and the appropriate
 * ontology filter applied based on that type.
 */
function isMONDOTerm(result: OLSSearchResult): boolean {
  // Check obo_id first (e.g., "MONDO:0006664")
  if (result.obo_id && result.obo_id.startsWith("MONDO:")) {
    return true;
  }

  // Check ontology_prefix
  if (result.ontology_prefix === "MONDO") {
    return true;
  }

  // Check ontology_name
  if (result.ontology_name === "mondo") {
    return true;
  }

  // Check IRI pattern
  if (result.iri && result.iri.includes("/MONDO_")) {
    return true;
  }

  // Check short_form
  if (result.short_form && result.short_form.startsWith("MONDO_")) {
    return true;
  }

  return false;
}

/**
 * Check if a result is from NCBITaxon ontology
 */
function isNCBITaxonTerm(result: OLSSearchResult): boolean {
  // Check obo_id first (e.g., "NCBITaxon:9606")
  if (result.obo_id && result.obo_id.startsWith("NCBITaxon:")) {
    return true;
  }

  // Check ontology_prefix
  if (result.ontology_prefix === "NCBITaxon") {
    return true;
  }

  // Check ontology_name
  if (result.ontology_name === "ncbitaxon" || result.ontology_name === "ncbi_taxonomy") {
    return true;
  }

  // Check IRI pattern
  if (result.iri && (result.iri.includes("/NCBITaxon_") || result.iri.includes("/taxonomy/"))) {
    return true;
  }

  // Check short_form
  if (result.short_form && result.short_form.startsWith("NCBITaxon_")) {
    return true;
  }

  return false;
}

/**
 * Check if a result is from UBERON ontology (anatomy/tissue)
 */
function isUBERONTerm(result: OLSSearchResult): boolean {
  if (result.obo_id && result.obo_id.startsWith("UBERON:")) {
    return true;
  }
  if (result.ontology_prefix === "UBERON") {
    return true;
  }
  if (result.ontology_name === "uberon") {
    return true;
  }
  if (result.iri && result.iri.includes("/UBERON_")) {
    return true;
  }
  if (result.short_form && result.short_form.startsWith("UBERON_")) {
    return true;
  }
  return false;
}

/**
 * Ground a single candidate term to UBERON using OLS.
 * Returns the best matching UBERON term(s); each result includes uberonId (numeric part, e.g. "0000948").
 */
export async function groundTermToUBERON(
  candidateTerm: string,
  topN: number = 3
): Promise<Array<OLSSearchResult & { matchScore: number; matchType: string; matchedText: string; uberonId?: string }>> {
  try {
    console.log(`[OLS] Searching for "${candidateTerm}" in UBERON...`);
    const results = await searchOLS(candidateTerm, "uberon", 20);
    console.log(`[OLS] Found ${results.length} total results for "${candidateTerm}"`);

    if (results.length === 0) {
      console.warn(`[OLS] No results from OLS API for "${candidateTerm}"`);
      return [];
    }

    const uberonResults = results.filter(isUBERONTerm);
    console.log(`[OLS] Filtered to ${uberonResults.length} UBERON terms (removed ${results.length - uberonResults.length} non-UBERON terms)`);

    if (uberonResults.length === 0) {
      console.warn(`[OLS] No UBERON terms found for "${candidateTerm}"`);
      return [];
    }

    const ranked = rankMONDOCTerms(uberonResults, candidateTerm);

    const filtered = ranked.filter((r) => r.matchScore > 0);
    console.log(`[OLS] ${filtered.length} UBERON results with score > 0 for "${candidateTerm}"`);

    if (filtered.length > 0) {
      console.log(`[OLS] Top UBERON match for "${candidateTerm}":`, filtered[0].label, `(${filtered[0].obo_id}, score: ${filtered[0].matchScore})`);
    }

    const withIds = filtered.slice(0, topN).map((r) => {
      const shortForm = r.short_form || r.obo_id?.replace(":", "_") || "";
      const match = shortForm.match(/UBERON[_\s:]*(\d+)/i);
      return { ...r, uberonId: match ? match[1] : undefined };
    });

    return withIds;
  } catch (error: unknown) {
    const err = error as Error;
    console.error(`[OLS] Failed to ground "${candidateTerm}" to UBERON:`, err);
    return [];
  }
}

/** Regex for an existing UBERON numeric ID (from CURIE, IRI, or bare digits). */
const UBERON_ID_REGEX = /^(?:UBERON[_\s:]*)?(\d+)$/i;
const UBERON_IRI_REGEX = /UBERON_(\d+)/i;

/**
 * Resolve tissue names or UBERON IDs to numeric UBERON IDs for SPARQL filters.
 * Values that already look like UBERON (e.g. "0000948", "UBERON:0000948") are normalized;
 * other values (e.g. "heart") are grounded via OLS and the best match's ID is used.
 */
export async function resolveTissueToUberonIds(rawTissue: string[]): Promise<string[]> {
  if (!rawTissue?.length) return [];

  const out: string[] = [];
  for (const t of rawTissue) {
    const trimmed = t.replace(/^http:\/\/purl\.obolibrary\.org\/obo\/UBERON_/i, "").trim();
    const fromCurieOrBare = trimmed.match(UBERON_ID_REGEX)?.[1];
    const fromIri = trimmed.match(UBERON_IRI_REGEX)?.[1];
    const numericId = fromCurieOrBare ?? fromIri;
    if (numericId) {
      out.push(numericId);
      continue;
    }
    const grounded = await groundTermToUBERON(trimmed, 1);
    const id = grounded[0]?.uberonId;
    if (id) out.push(id);
    else console.warn(`[OLS] No UBERON match for tissue "${t}", skipping`);
  }
  return [...new Set(out)];
}

/**
 * Check if a MONDO term is a descendant of "human disease" (MONDO:0700096)
 * Uses SPARQL query against FRINK Federated SPARQL (Ubergraph) for reliable hierarchy checks
 * 
 * Given NIAID Data Ecosystem and proto-OKN focus on human health research,
 * we default to human diseases unless explicitly indicated otherwise.
 */
export async function isHumanDiseaseTerm(
  mondoIRI: string
): Promise<boolean> {
  const HUMAN_DISEASE_IRI = "http://purl.obolibrary.org/obo/MONDO_0700096";

  // Check if the term itself is MONDO:0700096
  if (mondoIRI === HUMAN_DISEASE_IRI || mondoIRI?.includes("MONDO_0700096")) {
    console.log(`[OLS] ${mondoIRI} IS the human disease term itself`);
    return true;
  }

  try {
    console.log(`[OLS] Checking if ${mondoIRI} is a human disease (descendant of MONDO:0700096) via SPARQL`);

    // SPARQL query to check if term is a subclass of human disease
    // Uses rdfs:subClassOf* (transitive closure) to check all ancestors
    const query = `
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?term
FROM <https://purl.org/okn/frink/kg/ubergraph>
WHERE {
  # Check if the term is directly or transitively a subclass of human disease
  <${mondoIRI}> rdfs:subClassOf* <${HUMAN_DISEASE_IRI}> .
  BIND(<${mondoIRI}> AS ?term)
}
LIMIT 1
`.trim();

    const result = await executeSPARQL(query, undefined, { timeout_s: 5 });

    if (result.error) {
      console.warn(`[OLS] SPARQL query failed for ${mondoIRI}: ${result.error}, defaulting to human disease`);
      return true; // Default to human disease on error (fail open)
    }

    const bindings = result.result.results?.bindings || [];
    const isHuman = bindings.length > 0;

    console.log(`[OLS] ${mondoIRI} is ${isHuman ? "a human disease" : "NOT a human disease"} (via SPARQL check)`);

    return isHuman;
  } catch (error: any) {
    console.error(`[OLS] Error checking human disease status for ${mondoIRI} via SPARQL:`, error.message);
    // Default to human disease on error (fail open - better to include than exclude)
    return true;
  }
}

export async function groundTermToMONDO(
  candidateTerm: string,
  topN: number = 3,
  humanOnly: boolean = true  // Default to human diseases (NIAID/NDE context)
): Promise<Array<OLSSearchResult & { matchScore: number; matchType: string; matchedText: string }>> {
  try {
    console.log(`[OLS] Searching for "${candidateTerm}" in MONDO${humanOnly ? " (human diseases only)" : ""}...`);
    const results = await searchOLS(candidateTerm, "mondo", 20);
    console.log(`[OLS] Found ${results.length} total results for "${candidateTerm}"`);

    if (results.length === 0) {
      console.warn(`[OLS] No results from OLS API for "${candidateTerm}"`);
      return [];
    }

    // Filter to only MONDO terms
    const mondoResults = results.filter(isMONDOTerm);
    console.log(`[OLS] Filtered to ${mondoResults.length} MONDO terms (removed ${results.length - mondoResults.length} non-MONDO terms)`);

    if (mondoResults.length === 0) {
      console.warn(`[OLS] No MONDO terms found for "${candidateTerm}"`);
      return [];
    }

    // Rank first to get best matches, then filter if needed
    const ranked = rankMONDOCTerms(mondoResults, candidateTerm);

    // Filter to human diseases only (if requested) - do this AFTER ranking to preserve best matches
    let humanDiseaseResults = ranked;
    if (humanOnly) {
      console.log(`[OLS] Filtering ranked results to human diseases (descendants of MONDO:0700096)...`);

      // Check each term's ancestors in parallel (limit to top 10 to avoid too many API calls)
      const topResultsToCheck = ranked.slice(0, 10);
      const humanChecks = await Promise.all(
        topResultsToCheck.map(async (result) => {
          const iri = result.iri || result.id;
          if (!iri) {
            console.warn(`[OLS] No IRI found for result:`, result.label);
            return { result, isHuman: true }; // Default to human if no IRI
          }

          const isHuman = await isHumanDiseaseTerm(iri);
          return { result, isHuman };
        })
      );

      // Separate human and non-human results
      const humanResults = humanChecks
        .filter(({ isHuman }) => isHuman)
        .map(({ result }) => result);

      const nonHumanResults = humanChecks
        .filter(({ isHuman }) => !isHuman)
        .map(({ result }) => result);

      // Combine: human results first (already ranked), then remaining ranked results we didn't check
      const remainingResults = ranked.slice(10);
      humanDiseaseResults = [...humanResults, ...remainingResults];

      console.log(`[OLS] Filtered to ${humanResults.length} human disease terms in top 10 (removed ${nonHumanResults.length} non-human terms)`);
      if (nonHumanResults.length > 0) {
        console.log(`[OLS] Non-human terms filtered out:`, nonHumanResults.map(r => `${r.obo_id} (${r.label})`).join(", "));
      }

      // If we filtered everything out from top results, warn but use all results
      if (humanResults.length === 0 && topResultsToCheck.length > 0) {
        console.warn(`[OLS] No human disease terms found in top results for "${candidateTerm}", using all ranked results`);
        humanDiseaseResults = ranked;
      }
    }

    console.log(`[OLS] Final result set: ${humanDiseaseResults.length} MONDO results for "${candidateTerm}"`);

    const filtered = humanDiseaseResults.filter((r) => r.matchScore > 0);
    console.log(`[OLS] ${filtered.length} MONDO results with score > 0 for "${candidateTerm}"`);

    if (filtered.length > 0) {
      console.log(`[OLS] Top MONDO match for "${candidateTerm}":`, filtered[0].label, `(${filtered[0].obo_id}, score: ${filtered[0].matchScore})`);
    }

    // Return top N
    return filtered.slice(0, topN);
  } catch (error: any) {
    console.error(`[OLS] Failed to ground "${candidateTerm}" to MONDO:`, error);
    console.error(`[OLS] Error details:`, error.stack);
    return [];
  }
}

/**
 * Ground a single candidate term to NCBITaxon using OLS
 * Returns the best matching NCBITaxon term(s)
 */
export async function groundTermToNCBITaxon(
  candidateTerm: string,
  topN: number = 3
): Promise<Array<OLSSearchResult & { matchScore: number; matchType: string; matchedText: string }>> {
  try {
    console.log(`[OLS] Searching for "${candidateTerm}" in NCBITaxon...`);
    const results = await searchOLS(candidateTerm, "ncbitaxon", 20);
    console.log(`[OLS] Found ${results.length} total results for "${candidateTerm}"`);

    if (results.length === 0) {
      console.warn(`[OLS] No results from OLS API for "${candidateTerm}"`);
      return [];
    }

    // Filter to only NCBITaxon terms
    const ncbitaxonResults = results.filter(isNCBITaxonTerm);
    console.log(`[OLS] Filtered to ${ncbitaxonResults.length} NCBITaxon terms (removed ${results.length - ncbitaxonResults.length} non-NCBITaxon terms)`);

    if (ncbitaxonResults.length === 0) {
      console.warn(`[OLS] No NCBITaxon terms found for "${candidateTerm}"`);
      return [];
    }

    // Rank first to get best matches
    const ranked = rankMONDOCTerms(ncbitaxonResults, candidateTerm);

    console.log(`[OLS] Final result set: ${ranked.length} NCBITaxon results for "${candidateTerm}"`);

    const filtered = ranked.filter((r) => r.matchScore > 0);
    console.log(`[OLS] ${filtered.length} NCBITaxon results with score > 0 for "${candidateTerm}"`);

    if (filtered.length > 0) {
      console.log(`[OLS] Top NCBITaxon match for "${candidateTerm}":`, filtered[0].label, `(${filtered[0].obo_id}, score: ${filtered[0].matchScore})`);
    }

    // Return top N
    return filtered.slice(0, topN);
  } catch (error: any) {
    console.error(`[OLS] Failed to ground "${candidateTerm}" to NCBITaxon:`, error);
    console.error(`[OLS] Error details:`, error.stack);
    return [];
  }
}
