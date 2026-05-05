// Wikidata client for grounding drug/medication entities to Wikidata identifiers
// Uses the FRINK Wikidata graph to search for drugs by name

export interface WikidataSearchResult {
    wikidata_id: string; // e.g., "Q421094" for aspirin
    wikidata_iri: string; // e.g., "http://www.wikidata.org/entity/Q421094"
    label: string;
    description?: string;
    matchScore: number; // 1-4 scale (4 = exact match, 3 = exact alias, 2 = partial, 1 = weak)
    matchType: string; // "exact_label", "exact_alias", "partial", etc.
    matchedText: string; // The text that matched
    aliases?: string[];
}

// Use FRINK's federated endpoint with the Wikidata graph (for drug→disease queries in the pipeline)
const FRINK_FEDERATION_ENDPOINT =
    process.env.NEXT_PUBLIC_FRINK_FEDERATION_URL ||
    "https://frink.apps.renci.org/federation/sparql";

// Public Wikidata Query Service — used for drug search (autocomplete + resolution) for reliability
const PUBLIC_WIKIDATA_SPARQL =
    "https://query.wikidata.org/sparql";

/** User-Agent for public Wikidata (required by their policy). */
const WIKIDATA_USER_AGENT =
    "OKN-WOBD/1.0 (drug autocomplete; https://github.com/SuLab/OKN-WOBD)";

/** Timeout per SPARQL request (ms). Public Wikidata is typically fast. */
const WIKIDATA_SEARCH_TIMEOUT_MS = 15000;

/**
 * Search Wikidata for drugs/medications by name
 * Returns results ranked by match quality
 */
export async function searchWikidataDrugs(
    searchTerm: string
): Promise<WikidataSearchResult[]> {
    console.log(`[Wikidata] Searching for drug: "${searchTerm}"`);

    const results: WikidataSearchResult[] = [];

    try {
        // Run brand and exact in parallel; brand is fast and finds Lipitor/Synthroid
        const [brandResults, exactResults] = await Promise.all([
            searchWikidataBrands(searchTerm),
            searchWikidataExact(searchTerm),
        ]);
        results.push(...exactResults);
        results.push(...brandResults);

        // If still no results, try alias (label/alias substring match)
        if (results.length === 0) {
            const aliasResults = await searchWikidataAliases(searchTerm);
            results.push(...aliasResults);
        }

        // Deduplicate by wikidata_id
        const seen = new Set<string>();
        const deduped = results.filter((r) => {
            if (seen.has(r.wikidata_id)) return false;
            seen.add(r.wikidata_id);
            return true;
        });

        // Sort by match score (highest first)
        deduped.sort((a, b) => b.matchScore - a.matchScore);

        console.log(
            `[Wikidata] Found ${deduped.length} results for "${searchTerm}"`
        );

        return deduped;
    } catch (error: any) {
        console.error(`[Wikidata] Search failed for "${searchTerm}":`, error);
        throw error;
    }
}

/**
 * Search for exact label matches in Wikidata for drugs
 */
async function searchWikidataExact(
    searchTerm: string
): Promise<WikidataSearchResult[]> {
    const query = `
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX schema: <http://schema.org/>

SELECT DISTINCT ?item ?itemLabel ?itemDescription
WHERE {
  ?item rdfs:label ?itemLabel .
  FILTER(LANG(?itemLabel) = "en")
  FILTER(LCASE(STR(?itemLabel)) = LCASE("${escapeSPARQL(searchTerm)}"))
  ?item wdt:P2175 ?condition .
  OPTIONAL {
    ?item schema:description ?itemDescription .
    FILTER(LANG(?itemDescription) = "en")
  }
}
LIMIT 10
  `.trim();

    console.log(`[Wikidata] Executing exact search (public) for "${searchTerm}"`);

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), WIKIDATA_SEARCH_TIMEOUT_MS);

        const response = await fetch(PUBLIC_WIKIDATA_SPARQL, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
                Accept: "application/sparql-results+json",
                "User-Agent": WIKIDATA_USER_AGENT,
            },
            body: new URLSearchParams({ query }).toString(),
            signal: controller.signal,
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
            const errorText = await response.text().catch(() => "");
            console.warn(
                `[Wikidata] Exact search failed: ${response.status} ${response.statusText}`,
                errorText.substring(0, 200)
            );
            return [];
        }

        const data = await response.json();
        const bindings = data?.results?.bindings || [];

        return bindings.map((binding: any) => {
            const iri = binding.item?.value || "";
            const id = iri.replace("http://www.wikidata.org/entity/", "");
            const label = binding.itemLabel?.value || searchTerm;
            const description = binding.itemDescription?.value;

            return {
                wikidata_id: id,
                wikidata_iri: iri,
                label,
                description,
                matchScore: 4,
                matchType: "exact_label",
                matchedText: label,
            };
        });
    } catch (error: any) {
        if (error.name === "AbortError") {
            console.error("[Wikidata] Exact search timed out");
        } else {
            console.error("[Wikidata] Exact search error:", error.message || error);
        }
        return [];
    }
}

/**
 * Search for drugs using label and alias matches
 */
async function searchWikidataAliases(
    searchTerm: string
): Promise<WikidataSearchResult[]> {
    const query = `
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX schema: <http://schema.org/>

SELECT DISTINCT ?item ?itemLabel ?itemDescription ?alias
WHERE {
  ?item wdt:P2175 ?condition .
  
  # Match label or alias (case-insensitive)
  {
    ?item rdfs:label ?itemLabel .
    FILTER(LANG(?itemLabel) = "en")
    FILTER(REGEX(LCASE(STR(?itemLabel)), LCASE("${escapeSPARQL(searchTerm)}")))
    BIND(?itemLabel AS ?alias)
  }
  UNION
  {
    ?item skos:altLabel ?altLabel .
    FILTER(LANG(?altLabel) = "en")
    FILTER(REGEX(LCASE(STR(?altLabel)), LCASE("${escapeSPARQL(searchTerm)}")))
    ?item rdfs:label ?itemLabel .
    FILTER(LANG(?itemLabel) = "en")
    BIND(?altLabel AS ?alias)
  }
  
  # Get description if available
  OPTIONAL {
    ?item schema:description ?itemDescription .
    FILTER(LANG(?itemDescription) = "en")
  }
}
LIMIT 20
  `.trim();

    console.log(`[Wikidata] Executing alias search (public) for "${searchTerm}"`);

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), WIKIDATA_SEARCH_TIMEOUT_MS);

        const response = await fetch(PUBLIC_WIKIDATA_SPARQL, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
                Accept: "application/sparql-results+json",
                "User-Agent": WIKIDATA_USER_AGENT,
            },
            body: new URLSearchParams({ query }).toString(),
            signal: controller.signal,
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
            const errorText = await response.text().catch(() => "");
            console.warn(
                `[Wikidata] Alias search failed: ${response.status} ${response.statusText}`,
                errorText.substring(0, 200)
            );
            return [];
        }

        const data = await response.json();
        const bindings = data?.results?.bindings || [];

        // Group by item to collect aliases
        const itemMap = new Map<string, any>();

        for (const binding of bindings) {
            const iri = binding.item?.value || "";
            const id = iri.replace("http://www.wikidata.org/entity/", "");
            const label = binding.itemLabel?.value || searchTerm;
            const description = binding.itemDescription?.value;
            const alias = binding.alias?.value || label;

            if (!itemMap.has(id)) {
                itemMap.set(id, {
                    wikidata_id: id,
                    wikidata_iri: iri,
                    label,
                    description,
                    aliases: new Set<string>(),
                    matchedText: alias,
                });
            }

            itemMap.get(id).aliases.add(alias);
        }

        return Array.from(itemMap.values()).map((item) => {
            // Determine match score based on how close the match is
            const lowerTerm = searchTerm.toLowerCase();
            const lowerLabel = item.label.toLowerCase();
            const lowerMatched = item.matchedText.toLowerCase();

            let matchScore = 2;
            let matchType = "partial";

            if (lowerLabel === lowerTerm) {
                matchScore = 4;
                matchType = "exact_label";
            } else if (lowerMatched === lowerTerm) {
                matchScore = 3;
                matchType = "exact_alias";
            } else if (lowerLabel.includes(lowerTerm) || lowerTerm.includes(lowerLabel)) {
                matchScore = 2;
                matchType = "partial";
            } else {
                matchScore = 1;
                matchType = "weak";
            }

            return {
                wikidata_id: item.wikidata_id,
                wikidata_iri: item.wikidata_iri,
                label: item.label,
                description: item.description,
                matchScore,
                matchType,
                matchedText: item.matchedText,
                aliases: Array.from(item.aliases),
            };
        });
    } catch (error: any) {
        if (error.name === "AbortError") {
            console.error("[Wikidata] Alias search timed out");
        } else {
            console.error("[Wikidata] Alias search error:", error.message || error);
        }
        return [];
    }
}

/**
 * Search for brand names (pharmaceutical products): items with P3781 (has active ingredient)
 * pointing to an ingredient that has P2175 (medical condition treated).
 * Returns the ingredient so the pipeline resolves to a drug with "diseases treated";
 * label is the brand name so autocomplete shows e.g. "Lipitor".
 */
async function searchWikidataBrands(
    searchTerm: string
): Promise<WikidataSearchResult[]> {
    const escaped = escapeSPARQL(searchTerm);
    const unionQuery = `
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT DISTINCT ?product ?productLabel ?ingredient ?ingredientLabel
WHERE {
  ?product wdt:P3781 ?ingredient .
  ?ingredient wdt:P2175 ?cond .
  ?ingredient rdfs:label ?ingredientLabel .
  FILTER(LANG(?ingredientLabel) = "en")
  {
    ?product rdfs:label ?productLabel .
    FILTER(LANG(?productLabel) = "en")
    FILTER(CONTAINS(LCASE(STR(?productLabel)), LCASE("${escaped}")))
  }
  UNION
  {
    ?product skos:altLabel ?altLabel .
    FILTER(LANG(?altLabel) = "en")
    FILTER(CONTAINS(LCASE(STR(?altLabel)), LCASE("${escaped}")))
    ?product rdfs:label ?productLabel .
    FILTER(LANG(?productLabel) = "en")
  }
}
LIMIT 10
  `.trim();

    console.log(`[Wikidata] Executing brand search (public) for "${searchTerm}"`);

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), WIKIDATA_SEARCH_TIMEOUT_MS);

        const response = await fetch(PUBLIC_WIKIDATA_SPARQL, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
                Accept: "application/sparql-results+json",
                "User-Agent": WIKIDATA_USER_AGENT,
            },
            body: new URLSearchParams({ query: unionQuery }).toString(),
            signal: controller.signal,
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
            const errorText = await response.text().catch(() => "");
            console.warn(
                `[Wikidata] Brand search failed: ${response.status} ${response.statusText}`,
                errorText.substring(0, 200)
            );
            return [];
        }

        const data = await response.json();
        const bindings = data?.results?.bindings || [];

        const seen = new Set<string>();
        return bindings
            .map((binding: any) => {
                const ingredientIri = binding.ingredient?.value || "";
                const ingredientId = ingredientIri.replace(
                    "http://www.wikidata.org/entity/",
                    ""
                );
                if (seen.has(ingredientId)) return null;
                seen.add(ingredientId);
                const productLabel = binding.productLabel?.value || searchTerm;
                const ingredientLabel =
                    binding.ingredientLabel?.value || "";
                return {
                    wikidata_id: ingredientId,
                    wikidata_iri: ingredientIri,
                    label: productLabel,
                    description: ingredientLabel
                        ? `brand of ${ingredientLabel}`
                        : undefined,
                    matchScore: 3,
                    matchType: "brand",
                    matchedText: productLabel,
                };
            })
            .filter(Boolean) as WikidataSearchResult[];
    } catch (error: any) {
        if (error.name === "AbortError") {
            console.error("[Wikidata] Brand search timed out");
        } else {
            console.error(
                "[Wikidata] Brand search error:",
                error.message || error
            );
        }
        return [];
    }
}

/**
 * Escape special characters for SPARQL string literals
 */
function escapeSPARQL(str: string): string {
    return str
        .replace(/\\/g, "\\\\")
        .replace(/"/g, '\\"')
        .replace(/\n/g, "\\n")
        .replace(/\r/g, "\\r")
        .replace(/\t/g, "\\t");
}

/**
 * Filter results to only include drugs (check if the result is actually a medication)
 */
function isWikidataDrug(result: WikidataSearchResult): boolean {
    // Basic heuristic: check if description contains drug-related terms
    const description = result.description?.toLowerCase() || "";
    const label = result.label.toLowerCase();

    const drugKeywords = [
        "drug",
        "medication",
        "medicine",
        "pharmaceutical",
        "antibiotic",
        "vaccine",
        "treatment",
        "therapy",
        "inhibitor",
    ];

    return drugKeywords.some(
        (keyword) => description.includes(keyword) || label.includes(keyword)
    );
}

/**
 * Ground a drug term to Wikidata
 * Returns ranked results with match scores
 */
export async function groundDrugToWikidata(
    drugName: string
): Promise<WikidataSearchResult[]> {
    const results = await searchWikidataDrugs(drugName);

    // Filter to only include likely drugs
    const drugResults = results.filter((r) => {
        // Keep high-confidence matches regardless
        if (r.matchScore >= 3) return true;
        // For lower scores, apply drug filter
        return isWikidataDrug(r);
    });

    console.log(
        `[Wikidata] Grounded "${drugName}" to ${drugResults.length} Wikidata drugs`
    );

    return drugResults;
}
