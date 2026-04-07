// Fixed SPARQL templates for ontology-grounded query chaining
// All queries use FROM clauses for graph scoping - no GRAPH enumeration

import { mondoDigitsToOboIri } from "@/lib/ontology/mondo-iri";

/** FRINK GXA uses http://purl.org/okn/wobd/log2fc; legacy exports use spokegenelab:. */
function gxaAssocLog2fcBinding(assocVar: string, log2Var: string, uniq: string): string {
  return `  OPTIONAL { ${assocVar} wobd:log2fc ?_gxa_${uniq}_lw . }
  OPTIONAL { ${assocVar} spokegenelab:log2fc ?_gxa_${uniq}_ls . }
  BIND(COALESCE(?_gxa_${uniq}_lw, ?_gxa_${uniq}_ls) AS ${log2Var})
  FILTER(BOUND(${log2Var}))`;
}

function gxaAssocAdjPBinding(assocVar: string, adjVar: string, uniq: string): string {
  return `  OPTIONAL { ${assocVar} wobd:adj_p_value ?_gxa_${uniq}_aw . }
  OPTIONAL { ${assocVar} spokegenelab:adj_p_value ?_gxa_${uniq}_as . }
  BIND(COALESCE(?_gxa_${uniq}_aw, ?_gxa_${uniq}_as) AS ${adjVar})`;
}

/**
 * Build SPARQL query to ground candidate labels to MONDO terms in Ubergraph
 * Stage 2: Ground candidate labels to MONDO
 */
export function buildMONDOGroundingQuery(
  candidateLabels: string[],
  rawPhrase: string
): string {
  // Combine raw phrase with candidate labels
  const searchTerms = [rawPhrase, ...candidateLabels].filter(Boolean);

  if (searchTerms.length === 0) {
    throw new Error("At least one search term required for MONDO grounding");
  }

  // Escape quotes in search terms
  const escapedTerms = searchTerms.map(term => term.replace(/"/g, '\\"'));

  const valuesBlock = escapedTerms
    .map(term => `    "${term}"`)
    .join("\n");

  return `PREFIX rdfs:     <http://www.w3.org/2000/01/rdf-schema#>
PREFIX obo:      <http://purl.obolibrary.org/obo/>
PREFIX oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>

SELECT DISTINCT ?mondo ?label ?matchedText ?matchedPred
FROM <https://purl.org/okn/frink/kg/ubergraph>
WHERE {
  VALUES ?q {
${valuesBlock}
  }

  ?mondo rdfs:label ?label .
  FILTER(STRSTARTS(STR(?mondo), "http://purl.obolibrary.org/obo/MONDO_"))

  {
    # Match on label - substring match (case-insensitive)
    FILTER(CONTAINS(LCASE(STR(?label)), LCASE(?q)))
    BIND(?label AS ?matchedText)
    BIND(rdfs:label AS ?matchedPred)
  }
  UNION
  {
    # Match on label - exact match (case-insensitive)
    FILTER(LCASE(STR(?label)) = LCASE(?q))
    BIND(?label AS ?matchedText)
    BIND(rdfs:label AS ?matchedPred)
  }
  UNION
  {
    # Match on synonyms - substring match
    ?mondo ?matchedPred ?matchedText .
    VALUES ?matchedPred {
      oboInOwl:hasExactSynonym
      oboInOwl:hasRelatedSynonym
      oboInOwl:hasBroadSynonym
      oboInOwl:hasNarrowSynonym
      oboInOwl:hasSynonym
      obo:IAO_0000118
    }
    FILTER(CONTAINS(LCASE(STR(?matchedText)), LCASE(?q)))
  }
  UNION
  {
    # Match on synonyms - exact match
    ?mondo ?matchedPred ?matchedText .
    VALUES ?matchedPred {
      oboInOwl:hasExactSynonym
      oboInOwl:hasRelatedSynonym
      oboInOwl:hasBroadSynonym
      oboInOwl:hasNarrowSynonym
      oboInOwl:hasSynonym
      obo:IAO_0000118
    }
    FILTER(LCASE(STR(?matchedText)) = LCASE(?q))
  }
}
LIMIT 200`;
}

/**
 * Build SPARQL query to expand MONDO synonyms in Ubergraph
 * Stage 3: Expand MONDO synonyms
 */
export function buildMONDOSynonymQuery(mondoIRIs: string[]): string {
  if (mondoIRIs.length === 0) {
    throw new Error("At least one MONDO IRI required for synonym expansion");
  }

  const valuesBlock = mondoIRIs
    .map(iri => `    <${iri}>`)
    .join("\n");

  return `PREFIX rdfs:     <http://www.w3.org/2000/01/rdf-schema#>
PREFIX obo:      <http://purl.obolibrary.org/obo/>
PREFIX oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>

SELECT DISTINCT ?mondo ?label ?syn
FROM <https://purl.org/okn/frink/kg/ubergraph>
WHERE {
  VALUES ?mondo {
${valuesBlock}
  }

  OPTIONAL { ?mondo rdfs:label ?label }
  OPTIONAL {
    ?mondo ?p ?syn .
    VALUES ?p {
      oboInOwl:hasExactSynonym
      oboInOwl:hasRelatedSynonym
      oboInOwl:hasBroadSynonym
      oboInOwl:hasNarrowSynonym
      oboInOwl:hasSynonym
      obo:IAO_0000118
    }
  }
}`;
}

/**
 * Build SPARQL query to detect NDE healthCondition encoding
 * Stage 4: Determine NDE healthCondition encoding (IRI vs CURIE)
 */
export function buildNDEEncodingQuery(): string {
  return `PREFIX schema: <http://schema.org/>

SELECT DISTINCT ?condition
FROM <https://purl.org/okn/frink/kg/nde>
WHERE {
  ?d a schema:Dataset ;
     schema:healthCondition ?condition .
}
LIMIT 20`;
}

/**
 * Build SPARQL query to find datasets by MONDO IRIs (IRI encoding) + optional text search
 * Stage 5: Dataset query with IRI encoding + optional text matching
 * 
 * @param mondoIRIs - Array of MONDO IRIs to match
 * @param labels - Optional array of entity labels for text matching
 * @param synonyms - Optional array of synonyms (not used, kept for compatibility)
 * @param useTextMatching - If true, adds text matching as fallback. Default: false (IRI-only for precision)
 */
export function buildNDEDatasetQueryIRI(
  mondoIRIs: string[],
  labels: string[] = [],
  synonyms: string[] = [],
  useTextMatching: boolean = false
): string {
  if (mondoIRIs.length === 0) {
    throw new Error("At least one MONDO IRI required for dataset query");
  }

  const valuesBlock = mondoIRIs
    .map(iri => `    <${iri}>`)
    .join("\n");

  // Only use labels (preferred names) for text search - no synonyms
  const textTerms = labels
    .filter(Boolean)
    .filter((term, index, self) =>
      // Remove duplicates (case-insensitive)
      self.findIndex(t => t.toLowerCase() === term.toLowerCase()) === index
    );

  // Build filter: match by IRI (primary) OR by disease name (optional fallback)
  // healthCondition points to an individual (?disease) which has schema:name
  const iriFilters = mondoIRIs.map(iri => `?disease = <${iri}>`).join(" ||\n      ");

  let filterClause = "";
  // Only add text matching if explicitly enabled (for high-confidence matches or fallback scenarios)
  if (useTextMatching && textTerms.length > 0) {
    // Escape quotes for SPARQL string literals
    const escapedTerms = textTerms.map(term => term.replace(/"/g, '\\"'));
    // Build CONTAINS filters for disease names (OR'd together)
    const nameFilters = escapedTerms.map(term =>
      `CONTAINS(LCASE(?diseaseName), LCASE("${term}"))`
    ).join(" ||\n      ");

    filterClause = `FILTER(\n      ${iriFilters} ||\n      ${nameFilters}\n    )`;
  } else {
    // Only IRI matching (more precise, less noisy)
    filterClause = `FILTER(\n      ${iriFilters}\n    )`;
  }

  return `PREFIX schema: <http://schema.org/>

SELECT DISTINCT ?dataset ?name ?description ?diseaseName ?identifier
FROM <https://purl.org/okn/frink/kg/nde>
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name ;
           schema:healthCondition ?disease .
  ?disease schema:name ?diseaseName .
  OPTIONAL { ?dataset schema:description ?description }
  OPTIONAL { ?dataset schema:identifier ?identifier }
  ${filterClause}
}
LIMIT 50`;
}

/**
 * Build SPARQL query to find datasets by MONDO CURIE strings + optional text search
 * Stage 5: Dataset query with CURIE encoding + optional text matching
 * 
 * @param mondoIRIs - Array of MONDO IRIs to match (converted to CURIEs)
 * @param labels - Optional array of entity labels for text matching
 * @param synonyms - Optional array of synonyms (not used, kept for compatibility)
 * @param useTextMatching - If true, adds text matching as fallback. Default: false (CURIE-only for precision)
 */
export function buildNDEDatasetQueryCURIE(
  mondoIRIs: string[],
  labels: string[] = [],
  synonyms: string[] = [],
  useTextMatching: boolean = false
): string {
  if (mondoIRIs.length === 0) {
    throw new Error("At least one MONDO IRI required for dataset query");
  }

  const valuesBlock = mondoIRIs
    .map(iri => `    <${iri}>`)
    .join("\n");

  // Only use labels (preferred names) for text search - no synonyms
  const textTerms = labels
    .filter(Boolean)
    .filter((term, index, self) =>
      // Remove duplicates (case-insensitive)
      self.findIndex(t => t.toLowerCase() === term.toLowerCase()) === index
    );

  // Build filter: match by CURIE string (primary) OR by disease name (optional fallback)
  // healthCondition points to an individual (?disease) which has schema:name
  // For CURIE encoding, we need to convert MONDO IRIs to CURIE strings
  const curieStrings = mondoIRIs.map(iri =>
    iri.replace(/^http:\/\/purl\.obolibrary\.org\/obo\/MONDO_/, "MONDO:")
  );
  const curieFilters = curieStrings.map(curie => `STR(?disease) = "${curie}"`).join(" ||\n      ");

  let filterClause = "";
  // Only add text matching if explicitly enabled (for high-confidence matches or fallback scenarios)
  if (useTextMatching && textTerms.length > 0) {
    // Escape quotes for SPARQL string literals
    const escapedTerms = textTerms.map(term => term.replace(/"/g, '\\"'));
    // Build CONTAINS filters for disease names (OR'd together)
    const nameFilters = escapedTerms.map(term =>
      `CONTAINS(LCASE(?diseaseName), LCASE("${term}"))`
    ).join(" ||\n      ");

    filterClause = `FILTER(\n      ${curieFilters} ||\n      ${nameFilters}\n    )`;
  } else {
    // Only CURIE matching (more precise, less noisy)
    filterClause = `FILTER(\n      ${curieFilters}\n    )`;
  }

  return `PREFIX schema: <http://schema.org/>

SELECT DISTINCT ?dataset ?name ?description ?diseaseName ?identifier
FROM <https://purl.org/okn/frink/kg/nde>
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name ;
           schema:healthCondition ?disease .
  ?disease schema:name ?diseaseName .
  OPTIONAL { ?dataset schema:description ?description }
  OPTIONAL { ?dataset schema:identifier ?identifier }
  ${filterClause}
}
LIMIT 50`;
}

/**
 * Build SPARQL query to find datasets by species IRIs (UniProt taxonomy) + optional text search
 * Similar to buildNDEDatasetQueryIRI but uses schema:species instead of schema:healthCondition
 * 
 * @param speciesIRIs - Array of UniProt taxonomy IRIs to match
 * @param labels - Optional array of entity labels for text matching
 * @param synonyms - Optional array of synonyms (not used, kept for compatibility)
 * @param useTextMatching - If true, adds text matching as fallback. Default: false (IRI-only for precision)
 */
export function buildNDESpeciesQueryIRI(
  speciesIRIs: string[],
  labels: string[] = [],
  synonyms: string[] = [],
  useTextMatching: boolean = false
): string {
  if (speciesIRIs.length === 0) {
    throw new Error("At least one species IRI required for species query");
  }

  const valuesBlock = speciesIRIs
    .map(iri => `    <${iri}>`)
    .join("\n");

  // Only use labels (preferred names) for text search - no synonyms
  const textTerms = labels
    .filter(Boolean)
    .filter((term, index, self) =>
      // Remove duplicates (case-insensitive)
      self.findIndex(t => t.toLowerCase() === term.toLowerCase()) === index
    );

  // Build filter: match by IRI (primary) OR by species name (optional fallback)
  // species points to an individual (?species) which has schema:name
  const iriFilters = speciesIRIs.map(iri => `?species = <${iri}>`).join(" ||\n      ");

  let filterClause = "";
  // Only add text matching if explicitly enabled (for high-confidence matches or fallback scenarios)
  if (useTextMatching && textTerms.length > 0) {
    // Escape quotes for SPARQL string literals
    const escapedTerms = textTerms.map(term => term.replace(/"/g, '\\"'));
    // Build CONTAINS filters for species names (OR'd together)
    const nameFilters = escapedTerms.map(term =>
      `CONTAINS(LCASE(?speciesName), LCASE("${term}"))`
    ).join(" ||\n      ");

    filterClause = `FILTER(\n      ${iriFilters} ||\n      ${nameFilters}\n    )`;
  } else {
    // Only IRI matching (more precise, less noisy)
    filterClause = `FILTER(\n      ${iriFilters}\n    )`;
  }

  return `PREFIX schema: <http://schema.org/>

SELECT DISTINCT ?dataset ?name ?description ?speciesName ?identifier
FROM <https://purl.org/okn/frink/kg/nde>
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name ;
           schema:species ?species .
  ?species schema:name ?speciesName .
  OPTIONAL { ?dataset schema:description ?description }
  OPTIONAL { ?dataset schema:identifier ?identifier }
  ${filterClause}
}
LIMIT 50`;
}

/**
 * Build SPARQL query to find datasets by species CURIE strings + optional text search
 * Similar to buildNDEDatasetQueryCURIE but uses schema:species instead of schema:healthCondition
 * 
 * @param speciesIRIs - Array of UniProt taxonomy IRIs to match
 * @param labels - Optional array of entity labels for text matching
 * @param synonyms - Optional array of synonyms (not used, kept for compatibility)
 * @param useTextMatching - If true, adds text matching as fallback. Default: false (URI-only for precision)
 */
export function buildNDESpeciesQueryCURIE(
  speciesIRIs: string[],
  labels: string[] = [],
  synonyms: string[] = [],
  useTextMatching: boolean = false
): string {
  if (speciesIRIs.length === 0) {
    throw new Error("At least one species IRI required for species query");
  }

  // Only use labels (preferred names) for text search - no synonyms
  const textTerms = labels
    .filter(Boolean)
    .filter((term, index, self) =>
      // Remove duplicates (case-insensitive)
      self.findIndex(t => t.toLowerCase() === term.toLowerCase()) === index
    );

  // Build filter: match by UniProt taxonomy URI string (primary) OR by species name (optional fallback)
  // species points to an individual (?species) which has schema:name
  // For CURIE encoding, we use the full UniProt taxonomy URI as a string
  const uriFilters = speciesIRIs.map(iri => `STR(?species) = "${iri}"`).join(" ||\n      ");

  let filterClause = "";
  // Only add text matching if explicitly enabled (for high-confidence matches or fallback scenarios)
  if (useTextMatching && textTerms.length > 0) {
    // Escape quotes for SPARQL string literals
    const escapedTerms = textTerms.map(term => term.replace(/"/g, '\\"'));
    // Build CONTAINS filters for species names (OR'd together)
    const nameFilters = escapedTerms.map(term =>
      `CONTAINS(LCASE(?speciesName), LCASE("${term}"))`
    ).join(" ||\n      ");

    filterClause = `FILTER(\n      ${uriFilters} ||\n      ${nameFilters}\n    )`;
  } else {
    // Only URI string matching (more precise, less noisy)
    filterClause = `FILTER(\n      ${uriFilters}\n    )`;
  }

  return `PREFIX schema: <http://schema.org/>

SELECT DISTINCT ?dataset ?name ?description ?speciesName ?identifier
FROM <https://purl.org/okn/frink/kg/nde>
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name ;
           schema:species ?species .
  ?species schema:name ?speciesName .
  OPTIONAL { ?dataset schema:description ?description }
  OPTIONAL { ?dataset schema:identifier ?identifier }
  ${filterClause}
}
LIMIT 50`;
}

/**
 * Build SPARQL query for fallback text search
 * Stage 6: Fallback text search (only if ontology workflow fails)
 * @param geoOnly - If true, restrict to NCBI GEO datasets. In NDE, GEO uses schema:identifier values like GSE100, GSE10000 (pattern GSE[0-9]+); verified against frink NDE.
 */
export function buildNDEFallbackQuery(
  rawPhrase: string,
  candidateLabels: string[],
  geoOnly: boolean = false
): string {
  const searchTerms = [rawPhrase, ...candidateLabels].filter(Boolean);

  if (searchTerms.length === 0) {
    throw new Error("At least one search term required for fallback query");
  }

  // Escape for regex - properly escape special characters for SPARQL REGEX
  const escapedTerms = searchTerms.map(term => {
    const cleaned = term.trim().replace(/\.$/, "");
    return cleaned.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }).filter(Boolean);

  const regexPattern = escapedTerms.join("|");
  const geoFilter = geoOnly
    ? `\n  FILTER(REGEX(STR(COALESCE(?identifier, "")), "GSE[0-9]+", "i"))`
    : "";

  return `PREFIX schema: <http://schema.org/>

SELECT DISTINCT ?dataset ?name ?description ?identifier
FROM <https://purl.org/okn/frink/kg/nde>
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name .
  OPTIONAL { ?dataset schema:description ?description }
  OPTIONAL { ?dataset schema:identifier ?identifier }

  FILTER(
    REGEX(STR(?name), "${regexPattern}", "i")
    || (BOUND(?description) &&
        REGEX(STR(?description), "${regexPattern}", "i"))
  )
  ${geoFilter}
}
LIMIT 50`;
}

function escapeSparqlStringLiteral(s: string): string {
  return s.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

function escapeRegexForSparql(term: string): string {
  const cleaned = term.trim().replace(/\.$/, "");
  return cleaned.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function resolveHealthConditionIri(input: string): string | null {
  const trimmed = input.replace(/[<>]/g, "").trim();
  const mondoPurl = trimmed.match(/^https?:\/\/purl\.obolibrary\.org\/obo\/MONDO_(\d+)$/i);
  if (mondoPurl) return mondoDigitsToOboIri(mondoPurl[1]);
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  const mondo = trimmed.match(/^MONDO[:_\s]+0*(\d+)$/i);
  if (mondo) return mondoDigitsToOboIri(mondo[1]);
  return null;
}

function resolveSpeciesIrisForFacet(input: string): string[] {
  const trimmed = input.replace(/[<>]/g, "").trim();
  if (/^\d+$/.test(trimmed)) {
    return [
      `https://www.uniprot.org/taxonomy/${trimmed}`,
      `http://purl.obolibrary.org/obo/NCBITaxon_${trimmed}`,
    ];
  }
  if (/^https?:\/\/www\.uniprot\.org\/taxonomy\/\d+$/i.test(trimmed)) return [trimmed];
  if (/^https?:\/\/purl\.obolibrary\.org\/obo\/NCBITaxon_\d+$/i.test(trimmed)) return [trimmed];
  return [];
}

function buildKeywordRegexFilter(keywordRegexTerms: string[]): string {
  const terms = keywordRegexTerms.map((t) => t.trim()).filter(Boolean).map(escapeRegexForSparql);
  if (terms.length === 0) {
    throw new Error("At least one keyword term required for dataset keyword search");
  }
  if (terms.length === 1) {
    const t = terms[0];
    return `  FILTER(
    REGEX(STR(?name), "${t}", "i")
    || (BOUND(?description) && REGEX(STR(?description), "${t}", "i"))
  )`;
  }
  const pieces = terms.map(
    (t) =>
      `(REGEX(STR(?name), "${t}", "i") || (BOUND(?description) && REGEX(STR(?description), "${t}", "i")))`
  );
  return `  FILTER(
    ${pieces.join(" &&\n    ")}
  )`;
}

function buildFacetHealthConditionBlock(inputs: string[]): string {
  const iris: string[] = [];
  const textTerms: string[] = [];
  for (const raw of inputs) {
    const t = raw.trim();
    if (!t) continue;
    const resolved = resolveHealthConditionIri(t);
    if (resolved) iris.push(resolved.replace(/[<>]/g, ""));
    else {
      const trimmed = t.replace(/[<>]/g, "").trim();
      if (/^https?:\/\//i.test(trimmed)) iris.push(trimmed);
      else textTerms.push(t);
    }
  }
  const uniqueIris = [...new Set(iris)];
  if (uniqueIris.length === 0 && textTerms.length === 0) return "";

  const filterParts: string[] = [];
  if (uniqueIris.length > 0) {
    filterParts.push(uniqueIris.map((iri) => `?hcTerm = <${iri}>`).join(" || "));
  }
  for (const term of textTerms) {
    const esc = escapeSparqlStringLiteral(term);
    filterParts.push(`(BOUND(?hcName) && CONTAINS(LCASE(?hcName), LCASE("${esc}")))`);
  }

  if (textTerms.length === 0) {
    return `
  ?dataset schema:healthCondition ?hcTerm .
  FILTER(${filterParts.join(" || ")})`;
  }
  return `
  ?dataset schema:healthCondition ?hcTerm .
  OPTIONAL { ?hcTerm schema:name ?hcName }
  FILTER(${filterParts.join(" || ")})`;
}

function buildFacetSpeciesBlock(inputs: string[]): string {
  const iris: string[] = [];
  const textTerms: string[] = [];
  for (const raw of inputs) {
    const t = raw.trim();
    if (!t) continue;
    const found = resolveSpeciesIrisForFacet(t);
    if (found.length > 0) iris.push(...found);
    else textTerms.push(t);
  }
  const uniqueIris = [...new Set(iris.map((i) => i.replace(/[<>]/g, "")))];
  if (uniqueIris.length === 0 && textTerms.length === 0) return "";

  const filterParts: string[] = [];
  if (uniqueIris.length > 0) {
    filterParts.push(uniqueIris.map((iri) => `?spTerm = <${iri}>`).join(" || "));
  }
  for (const term of textTerms) {
    const esc = escapeSparqlStringLiteral(term);
    filterParts.push(`CONTAINS(LCASE(?spName), LCASE("${esc}"))`);
  }
  return `
  ?dataset schema:species ?spTerm .
  ?spTerm schema:name ?spName .
  FILTER(${filterParts.join(" || ")})`;
}

function buildFacetInfectiousAgentBlock(inputs: string[]): string {
  const iris: string[] = [];
  const textTerms: string[] = [];
  for (const raw of inputs) {
    const t = raw.trim();
    if (!t) continue;
    const found = resolveSpeciesIrisForFacet(t);
    if (found.length > 0) iris.push(...found);
    else textTerms.push(t);
  }
  const uniqueIris = [...new Set(iris.map((i) => i.replace(/[<>]/g, "")))];
  if (uniqueIris.length === 0 && textTerms.length === 0) return "";

  const filterParts: string[] = [];
  if (uniqueIris.length > 0) {
    filterParts.push(uniqueIris.map((iri) => `?iaTerm = <${iri}>`).join(" || "));
  }
  for (const term of textTerms) {
    const trimmed = term.replace(/[<>]/g, "").trim();
    if (/^https?:\/\//i.test(trimmed)) {
      filterParts.push(`?iaTerm = <${trimmed}>`);
    } else {
      const esc = escapeSparqlStringLiteral(term);
      filterParts.push(`CONTAINS(LCASE(?iaName), LCASE("${esc}"))`);
    }
  }
  return `
  ?dataset schema:infectiousAgent ?iaTerm .
  ?iaTerm schema:name ?iaName .
  FILTER(${filterParts.join(" || ")})`;
}

/**
 * NDE dataset search: keyword REGEX on schema:name / optional schema:description,
 * with optional AND filters on schema:healthCondition, schema:species, schema:infectiousAgent
 * (term IRI equality when input is a URI/CURIE, else CONTAINS on schema:name).
 * Health-condition values may be MONDO CURIE/IRI (resolved to MONDO IRIs), other http(s) term IRIs, or free text (schema:name CONTAINS).
 * Species and infectious-agent slot values may be NCBI taxon IDs (mapped to UniProt taxonomy + NCBITaxon IRIs), full URIs, or text.
 *
 * @param keywordRegexTerms - Terms matched with REGEX (AND across terms); omit or empty for facet-only search
 * @param geoOnly - If true, restrict to GEO-style datasets (schema:identifier GSE[0-9]+)
 */
export function buildNDEDatasetKeywordAndFacetQuery(
  keywordRegexTerms: string[],
  options: {
    healthConditionInputs?: string[];
    speciesInputs?: string[];
    infectiousAgentInputs?: string[];
    geoOnly?: boolean;
  } = {}
): string {
  const { healthConditionInputs = [], speciesInputs = [], infectiousAgentInputs = [], geoOnly = false } =
    options;
  const kwTerms = keywordRegexTerms.map((t) => t.trim()).filter(Boolean);
  const keywordFilter =
    kwTerms.length > 0 ? buildKeywordRegexFilter(kwTerms) : "";
  const healthBlock =
    healthConditionInputs.length > 0 ? buildFacetHealthConditionBlock(healthConditionInputs) : "";
  const speciesBlock = speciesInputs.length > 0 ? buildFacetSpeciesBlock(speciesInputs) : "";
  const agentBlock =
    infectiousAgentInputs.length > 0 ? buildFacetInfectiousAgentBlock(infectiousAgentInputs) : "";
  const geoBlock = geoOnly
    ? `
  FILTER(REGEX(STR(COALESCE(?ident, "")), "GSE[0-9]+", "i"))`
    : "";

  const hasFacet = Boolean(healthBlock || speciesBlock || agentBlock);
  if (!geoOnly && !keywordFilter && !hasFacet) {
    throw new Error(
      "Provide keywords and/or at least one filter (health condition, pathogen species, or host species)."
    );
  }

  // One row per dataset; optional portal links (NDEResultCards uses identifier, urls, sameAsList, owlSameAsList).
  const resourceOptionals = `
  OPTIONAL { ?dataset schema:identifier ?ident }
  OPTIONAL { ?dataset schema:url ?url }
  OPTIONAL { ?dataset schema:sameAs ?sameAs }
  OPTIONAL { ?dataset owl:sameAs ?owlSameAs }`;

  return `SELECT ?dataset ?name ?description
  (GROUP_CONCAT(DISTINCT STR(?ident); SEPARATOR=" ") AS ?identifier)
  (GROUP_CONCAT(DISTINCT STR(?url); SEPARATOR=" ") AS ?urls)
  (GROUP_CONCAT(DISTINCT STR(?sameAs); SEPARATOR=" ") AS ?sameAsList)
  (GROUP_CONCAT(DISTINCT STR(?owlSameAs); SEPARATOR=" ") AS ?owlSameAsList)
FROM <https://purl.org/okn/frink/kg/nde>
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name .
  OPTIONAL { ?dataset schema:description ?description }${resourceOptionals}
${keywordFilter}${healthBlock}${speciesBlock}${agentBlock}${geoBlock}
}
GROUP BY ?dataset ?name ?description`.trim();
}

/**
 * Build SPARQL query to find diseases treated by a drug in Wikidata
 * Maps drug to diseases via P2175 (medical condition treated) and P6680 (exact match to MONDO)
 * 
 * @param drugIRIs - Array of Wikidata drug IRIs (e.g., ["http://www.wikidata.org/entity/Q18216"])
 * @returns SPARQL query that returns disease IRIs (MONDO) and labels
 */
export function buildWikidataDrugToDiseasesQuery(
  drugIRIs: string[]
): string {
  if (drugIRIs.length === 0) {
    throw new Error("At least one Wikidata drug IRI required");
  }

  const drugFilters = drugIRIs.map(iri => `?drug = <${iri}>`).join(" ||\n    ");

  return `PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?disease ?diseaseLabel ?mondoIRI
FROM <https://purl.org/okn/frink/kg/wikidata>
WHERE {
  # Filter to our drug(s)
  FILTER(${drugFilters})
  
  # Find diseases this drug treats (P2175 = medical condition treated)
  ?drug wdt:P2175 ?disease .
  
  # Get the disease label
  ?disease rdfs:label ?diseaseLabel .
  FILTER(LANG(?diseaseLabel) = "en")
  
  # Get MONDO mapping if it exists (P6680 = exact match)
  OPTIONAL {
    ?disease wdt:P6680 ?mondoIRI .
  }
}
LIMIT 50`;
}

export function buildWikidataDrugQuery(
  wikidataIRIs: string[],
  drugNames?: string[],
  useTextMatching: boolean = false
): string {
  if (wikidataIRIs.length === 0) {
    throw new Error("At least one Wikidata IRI required for drug query");
  }

  // Build filter for Wikidata IRIs
  const iriFilters = wikidataIRIs.map(iri => `?drug = <${iri}>`).join(" ||\n    ");

  // Build optional text matching on names
  let textFilter = "";
  if (useTextMatching && drugNames && drugNames.length > 0) {
    const nameRegex = drugNames.map(name => name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join("|");
    textFilter = ` ||\n    (BOUND(?drugName) && REGEX(STR(?drugName), "${nameRegex}", "i"))`;
  }

  return `PREFIX schema: <http://schema.org/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?dataset ?name ?description ?drugName ?identifier
FROM <https://purl.org/okn/frink/kg/nde>
FROM <https://purl.org/okn/frink/kg/wikidata>
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name .

  # Link dataset to drug via some property (adjust based on actual schema)
  # This is a placeholder - actual predicate may vary
  ?dataset schema:about ?drug .

  OPTIONAL { ?dataset schema:description ?description }
  OPTIONAL { ?dataset schema:identifier ?identifier }
  OPTIONAL { ?drug rdfs:label ?drugName }

  # Filter by Wikidata drug IRI${useTextMatching ? " or by drug name" : ""}
  FILTER(
    ${iriFilters}${textFilter}
  )
}
LIMIT 50`;
}

/**
 * Build a subquery that selects ?contrast (or ?outputVar) WHERE contrast matches factor terms (and optionally tissue/experiment).
 * Used to filter contrasts BEFORE joining to associations for better performance (avoids CONTAINS on large join).
 * @param outputVar - Variable to SELECT (default "?contrast"); use "?c1" for discordance query
 * @param organismFilterInSubquery - Optional BIND/OPTIONAL/FILTER (study taxon) scoped to outputVar
 */
function buildFactorContrastSubquery(
  factorTerms?: string[],
  tissueFilterInSubquery: string = "",
  extraFilter: string = "",
  outputVar: string = "?contrast",
  organismFilterInSubquery: string = ""
): string {
  if (!factorTerms || factorTerms.length === 0) return "";

  const safeTerms = factorTerms.map((t) => t.replace(/"/g, '\\"').toLowerCase()).filter(Boolean);
  if (safeTerms.length === 0) return "";

  const termConditions = safeTerms
    .map(
      (t) =>
        `(CONTAINS(LCASE(COALESCE(?contrastLabel, "")), "${t}") || ` +
        `CONTAINS(LCASE(COALESCE(?f1, "")), "${t}") || ` +
        `CONTAINS(LCASE(COALESCE(?f2, "")), "${t}"))`
    )
    .join(" || ");

  return `{
    SELECT DISTINCT ${outputVar} WHERE {
      ${outputVar} a biolink:Assay .
      OPTIONAL { ${outputVar} biolink:name ?contrastLabel . }
      OPTIONAL { ${outputVar} spokegenelab:factors_1 ?f1 . }
      OPTIONAL { ${outputVar} spokegenelab:factors_2 ?f2 . }
      FILTER(REGEX(STR(${outputVar}), "E-[A-Z0-9-]+-g[0-9]+_g[0-9]+"))
      ${tissueFilterInSubquery.replace(/\?contrast/g, outputVar)}
      ${extraFilter.replace(/\?contrast/g, outputVar)}
      ${organismFilterInSubquery}
      FILTER(${termConditions})
    }
  }`;
}

/** Normalize slot / pasted values to NCBI taxonomy numeric IDs (GXA uses OBO NCBITaxon_* IRIs). */
function normalizeGxaNcbiTaxonNumericIds(organismTaxonIds: string[]): string[] {
  const out: string[] = [];
  for (const raw of organismTaxonIds) {
    const s = raw.replace(/"/g, "").trim();
    if (!s) continue;
    const mObo = s.match(/obo\/NCBITaxon_(\d+)/i) || s.match(/NCBITaxon[_:](\d+)/i);
    if (mObo) {
      out.push(mObo[1]);
      continue;
    }
    if (/^\d+$/.test(s)) {
      out.push(s);
    }
  }
  return [...new Set(out)];
}

function buildGXATaxonMatchFilterExpr(taxonVar: string, numericIds: string[]): string {
  if (numericIds.length === 0) return "";
  const esc = (r: string) => r.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const parts: string[] = [];
  for (const id of numericIds) {
    parts.push(`${taxonVar} = <http://purl.obolibrary.org/obo/NCBITaxon_${id}>`);
    parts.push(`REGEX(STR(${taxonVar}), "NCBITaxon[_:]${esc(id)}(?:[^0-9]|$)")`);
  }
  return parts.join(" || ");
}

/** SPARQL expression for GXA experiment accession from an Assay (contrast) IRI. */
function gxaExperimentIdFromContrastExpr(contrastVar: string): string {
  return `REPLACE(STR(${contrastVar}), "^.*/(E-[A-Z0-9-]+)-.*$", "$1")`;
}

function buildGXAOrganismStudyTaxonParts(
  numericIds: string[],
  experimentIdExpr: string,
  tag: string
): { setup: string; disjunct: string } {
  const tOkn = `?__gxTaxOkn_${tag}`;
  const tSp = `?__gxTaxSpoke_${tag}`;
  const sOkn = `?__gxStudyOkn_${tag}`;
  const sSp = `?__gxStudySpoke_${tag}`;
  const setup = `
    BIND(IRI(CONCAT("http://purl.org/okn/wobd/study/", ${experimentIdExpr})) AS ${sOkn})
    OPTIONAL { ${sOkn} biolink:in_taxon ${tOkn} . }
    BIND(IRI(CONCAT("https://spoke.ucsf.edu/genelab/", ${experimentIdExpr})) AS ${sSp})
    OPTIONAL { ${sSp} biolink:in_taxon ${tSp} . }`;
  const disjunct = `(BOUND(${tOkn}) && (${buildGXATaxonMatchFilterExpr(tOkn, numericIds)})) || (BOUND(${tSp}) && (${buildGXATaxonMatchFilterExpr(tSp, numericIds)}))`;
  return { setup, disjunct };
}

/**
 * Restrict to experiments whose Study has biolink:in_taxon matching NCBI taxon IDs (OKN-WOBD and/or
 * SPOKE GeneLab study IRIs). Uses OPTIONAL + FILTER, not FILTER EXISTS: Virtuoso incorrectly
 * satisfied EXISTS when the inner pattern used BIND(REPLACE(STR(?contrast), ...)), which let
 * unrelated studies satisfy the organism constraint (e.g. mouse E-GEOD-3749 under Arabidopsis).
 */
function buildGXAOrganismFilterFromExprs(
  organismTaxonIds: string[] | undefined,
  experimentIdExprs: string[],
  tags: string[]
): string {
  if (!organismTaxonIds || organismTaxonIds.length === 0 || experimentIdExprs.length === 0) {
    return "";
  }
  const ids = normalizeGxaNcbiTaxonNumericIds(organismTaxonIds);
  if (ids.length === 0) return "";
  const parts = experimentIdExprs.map((ex, i) =>
    buildGXAOrganismStudyTaxonParts(ids, ex, tags[i] ?? `t${i}`)
  );
  const setup = parts.map((p) => p.setup).join("");
  const filterInner = parts.map((p) => `(${p.disjunct})`).join(" && ");
  return `${setup}\n    FILTER( ${filterInner} )`;
}

/**
 * Build disease filter for GXA: Study --studies--> Disease (EFO).
 * Study IRI is constructed from experimentId (e.g. spokegenelab:E-GEOD-76).
 */
function buildGXADiseaseFilter(diseaseEfoIds?: string[]): string {
  if (!diseaseEfoIds || diseaseEfoIds.length === 0) return "";

  const safeEfo = diseaseEfoIds
    .map((id) => id.replace(/^EFO_?/, "").replace(/"/g, "").trim())
    .filter(Boolean);
  if (safeEfo.length === 0) return "";

  const iriList = safeEfo.map((id) => `<http://www.ebi.ac.uk/efo/EFO_${id}>`).join(" ");
  return `
    BIND(IRI(CONCAT("https://spoke.ucsf.edu/genelab/", ?experimentId)) AS ?study)
    ?study spokegenelab:studies ?disease .
    FILTER(?disease IN (${iriList}))`;
}

/**
 * Build SPARQL query to list gene expression experiments (datasets) that have DE results.
 * Returns experiment accession, number of contrasts, and sample contrast labels for coverage discovery.
 * Used for Phase 1 "what expression data exists" and for bridging NDE with GXA.
 *
 * @param limit - Max experiments to return
 * @param organismTaxonIds - Optional NCBITaxon IDs (e.g. ["10090", "9606"]) to filter by organism
 * @param tissueUberonIds - Optional UBERON IDs (e.g. ["UBERON_0002082"]) to filter by tissue/anatomy
 * @param factorTerms - Optional text terms to match in factors/contrast labels (e.g. ["aortic banding"])
 * @param diseaseEfoIds - Optional EFO Disease IDs (e.g. ["0001461", "0002460"]) to filter by Study--studies-->Disease
 */
export function buildGXAExperimentCoverageQuery(
  limit: number = 100,
  organismTaxonIds?: string[],
  tissueUberonIds?: string[],
  factorTerms?: string[],
  diseaseEfoIds?: string[]
): string {
  const organismFilter = buildGXAOrganismFilterFromExprs(
    organismTaxonIds,
    ["?experimentId"],
    ["cov"]
  );

  let tissueFilter = "";
  if (tissueUberonIds && tissueUberonIds.length > 0) {
    const safeUberon = tissueUberonIds
      .map((id) => id.replace(/^UBERON_/, "").replace(/"/g, "").trim())
      .filter(Boolean);
    if (safeUberon.length > 0) {
      const iriList = safeUberon.map((id) => `<http://purl.obolibrary.org/obo/UBERON_${id}>`).join(" ");
      tissueFilter = `
    ?contrast biolink:has_attribute ?tissue .
    FILTER(?tissue IN (${iriList}))`;
    }
  }

  const diseaseFilter = buildGXADiseaseFilter(diseaseEfoIds);

  // Factor filter: use subquery to filter contrasts FIRST (before joining associations) for better performance
  const factorSubquery = buildFactorContrastSubquery(factorTerms, tissueFilter);
  const useFactorSubquery = factorSubquery !== "";
  const useDiseaseFilter = diseaseFilter !== "";

  // When BOTH factor terms and disease filter are present, use OR logic (UNION) so we return
  // experiments that match factor (e.g. "influenza" in contrast label) OR disease (study--studies-->EFO).
  // This avoids 0 results when the graph has one but not the other (e.g. contrast label has "influenza" but no EFO link).
  const useOrLogic = useFactorSubquery && useDiseaseFilter;

  let whereClause: string;
  if (useOrLogic) {
    const safeEfo = (diseaseEfoIds ?? [])
      .map((id) => id.replace(/^EFO_?/, "").replace(/"/g, "").trim())
      .filter(Boolean);
    const diseaseIriList = safeEfo.map((id) => `<http://www.ebi.ac.uk/efo/EFO_${id}>`).join(" ");
    whereClause = `{
    # Branch A: contrast matches factor (e.g. "influenza" in contrast label)
    ${factorSubquery}
    ?association a biolink:GeneExpressionMixin ;
        biolink:subject ?contrast .
    OPTIONAL { ?contrast biolink:name ?contrastLabel . }
    BIND(REPLACE(STR(?contrast), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentId)
    ${organismFilter}
  } UNION {
    # Branch B: study linked to disease (EFO)
    ?association a biolink:GeneExpressionMixin ;
        biolink:subject ?contrast .
    ?contrast a biolink:Assay .
    OPTIONAL { ?contrast biolink:name ?contrastLabel . }
    BIND(REPLACE(STR(?contrast), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentId)
    FILTER(REGEX(STR(?contrast), "E-[A-Z0-9-]+-g[0-9]+_g[0-9]+"))${tissueFilter}
    BIND(IRI(CONCAT("https://spoke.ucsf.edu/genelab/", ?experimentId)) AS ?study)
    ?study spokegenelab:studies ?disease .
    FILTER(?disease IN (${diseaseIriList}))
    ${organismFilter}
  }`;
  } else {
    const contrastSource = useFactorSubquery
      ? `# Subquery: filter contrasts by factor/tissue before joining associations (avoids timeout)
    ${factorSubquery}
    ?association a biolink:GeneExpressionMixin ;
        biolink:subject ?contrast .`
      : `?association a biolink:GeneExpressionMixin ;
        biolink:subject ?contrast .
    ?contrast a biolink:Assay .
    OPTIONAL { ?contrast biolink:name ?contrastLabel . }
    BIND(REPLACE(STR(?contrast), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentId)
    FILTER(REGEX(STR(?contrast), "E-[A-Z0-9-]+-g[0-9]+_g[0-9]+"))${tissueFilter}`;

    const postSubquery = useFactorSubquery
      ? `
    OPTIONAL { ?contrast biolink:name ?contrastLabel . }
    BIND(REPLACE(STR(?contrast), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentId)`
      : "";

    whereClause = `${contrastSource}${postSubquery}${organismFilter}${diseaseFilter}`;
  }

  return `PREFIX biolink: <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>

SELECT ?experimentId (COUNT(DISTINCT ?contrast) AS ?contrastCount) (SAMPLE(?contrastLabel) AS ?sampleContrastLabel)
FROM <https://purl.org/okn/frink/kg/gene-expression-atlas-okn>
WHERE {
    ${whereClause}
}
GROUP BY ?experimentId
ORDER BY DESC(?contrastCount)
LIMIT ${Math.min(limit, 500)}`;
}

/**
 * Build SPARQL query to get coverage (experimentId, contrastCount, sampleContrastLabel) for a
 * specific list of experiment IDs. Used by NDE↔GXA bridge to attach GXA data to NDE dataset rows.
 *
 * @param experimentIds - E-GEOD accessions (e.g. ["E-GEOD-76", "E-GEOD-123"])
 */
export function buildGXACoverageForExperimentIdsQuery(experimentIds: string[]): string {
  if (experimentIds.length === 0) {
    return "";
  }
  const safeIds = experimentIds
    .slice(0, 50)
    .map((id) => id.replace(/"/g, '\\"').trim())
    .filter(Boolean);
  if (safeIds.length === 0) return "";
  // Match contrasts by CONTAINS so we don't depend on exact URI shape (same as genes-for-experiment)
  const containsFilters = safeIds.map((id) => `CONTAINS(STR(?contrast), "${id}")`).join(" || ");
  // Extract experimentId; optional suffix (E-GEOD-76 or E-GEOD-76-g1_g2) so BIND works for both
  return `PREFIX biolink: <https://w3id.org/biolink/vocab/>

SELECT ?experimentId (COUNT(DISTINCT ?contrast) AS ?contrastCount) (SAMPLE(?contrastLabel) AS ?sampleContrastLabel)
FROM <https://purl.org/okn/frink/kg/gene-expression-atlas-okn>
WHERE {
  ?association a biolink:GeneExpressionMixin ;
      biolink:subject ?contrast .
  OPTIONAL { ?contrast biolink:name ?contrastLabel . }
  FILTER(${containsFilters})
  BIND(REPLACE(STR(?contrast), "^.*/(E-[A-Z0-9-]+)(-.*)?$", "$1") AS ?experimentId)
}
GROUP BY ?experimentId
ORDER BY ?experimentId`;
}

/**
 * Build SPARQL query to list DE genes for a given GXA experiment (per-contrast, contrast-aware).
 * Returns one row per (gene, contrast) with DE metrics and contrast labels.
 *
 * @param experimentId - GXA experiment accession (e.g. "E-GEOD-23301")
 * @param limit - Max number of rows to return (default 100)
 * @param upregulated - If true, only genes with log2fc > 0; if false, only log2fc < 0; if undefined, no direction filter.
 * @param organismTaxonIds - Optional NCBITaxon IDs to filter by organism (e.g. ["10090", "9606"])
 * @param tissueUberonIds - Optional UBERON IDs to filter by tissue (e.g. ["0002082"])
 * @param factorTerms - Optional text terms to match in factors/contrast labels (e.g. ["aortic banding"])
 * @param minAbsLog2fc - Optional minimum |log2fc| to match GXA default (e.g. 1 = 2-fold change)
 * @param maxAdjPValue - Optional max adj p-value to match GXA default (e.g. 0.05)
 */
export function buildGXAGenesForExperimentQuery(
  experimentId: string,
  limit: number = 100,
  upregulated?: boolean,
  organismTaxonIds?: string[],
  tissueUberonIds?: string[],
  factorTerms?: string[],
  minAbsLog2fc?: number,
  maxAdjPValue?: number
): string {
  if (!experimentId) {
    throw new Error("experimentId is required for GXA genes-for-experiment query");
  }

  const safeId = experimentId.replace(/"/g, '\\"');

  let log2fcFilter = "";
  if (upregulated === true) {
    log2fcFilter = "\n    FILTER(?log2fc > 0)";
  } else if (upregulated === false) {
    log2fcFilter = "\n    FILTER(?log2fc < 0)";
  }
  if (minAbsLog2fc != null && minAbsLog2fc > 0) {
    log2fcFilter += `\n    FILTER(ABS(?log2fc) >= ${minAbsLog2fc})`;
  }
  if (maxAdjPValue != null && maxAdjPValue >= 0 && maxAdjPValue < 1) {
    log2fcFilter += `\n    FILTER(BOUND(?adjPValue) && ?adjPValue <= ${maxAdjPValue})`;
  }

  const organismFilter = buildGXAOrganismFilterFromExprs(
    organismTaxonIds,
    [gxaExperimentIdFromContrastExpr("?contrast")],
    ["gfe"]
  );

  let tissueFilter = "";
  if (tissueUberonIds && tissueUberonIds.length > 0) {
    const safeUberon = tissueUberonIds
      .map((id) => id.replace(/^UBERON_/, "").replace(/"/g, "").trim())
      .filter(Boolean);
    if (safeUberon.length > 0) {
      const iriList = safeUberon.map((id) => `<http://purl.obolibrary.org/obo/UBERON_${id}>`).join(" ");
      tissueFilter = `\n  # Tissue filter (Phase 4)\n  ?contrast biolink:has_attribute ?tissue .\n  FILTER(?tissue IN (${iriList}))`;
    }
  }

  // Factor filter: use subquery to filter contrasts first (includes experiment filter for smaller set)
  const factorSubquery = buildFactorContrastSubquery(
    factorTerms,
    tissueFilter,
    `FILTER(CONTAINS(STR(?contrast), "${safeId}"))`
  );
  const useFactorSubquery = factorSubquery !== "";

  const contrastJoin = useFactorSubquery
    ? `# Subquery: filter contrasts by factor/tissue/experiment before joining associations
  ${factorSubquery}
  ?assoc a biolink:GeneExpressionMixin ;
         biolink:object ?gene ;
         biolink:subject ?contrast .
${gxaAssocLog2fcBinding("?assoc", "?log2fc", "gfe")}`
    : `?assoc a biolink:GeneExpressionMixin ;
         biolink:object ?gene ;
         biolink:subject ?contrast .
${gxaAssocLog2fcBinding("?assoc", "?log2fc", "gfe")}
${gxaAssocAdjPBinding("?assoc", "?adjPValue", "gfea")}
  ?contrast a biolink:Assay .
  FILTER(CONTAINS(STR(?contrast), "${safeId}"))`;

  const contrastRest = useFactorSubquery
    ? gxaAssocAdjPBinding("?assoc", "?adjPValue", "gfea")
    : "";

  const tissueInMain = useFactorSubquery ? "" : tissueFilter;
  const factorInMain = useFactorSubquery ? "" : (() => {
    if (!factorTerms || factorTerms.length === 0) return "";
    const safeTerms = factorTerms.map((t) => t.replace(/"/g, '\\"').toLowerCase()).filter(Boolean);
    if (safeTerms.length === 0) return "";
    const termConditions = safeTerms
      .map(
        (t) =>
          `(CONTAINS(LCASE(COALESCE(?contrastLabel, "")), "${t}") || ` +
          `CONTAINS(LCASE(COALESCE(?f1, "")), "${t}") || ` +
          `CONTAINS(LCASE(COALESCE(?f2, "")), "${t}"))`
      )
      .join(" || ");
    return `\n  OPTIONAL { ?contrast spokegenelab:factors_1 ?f1 . }\n  OPTIONAL { ?contrast spokegenelab:factors_2 ?f2 . }\n  FILTER(${termConditions})`;
  })();

  return `PREFIX biolink:      <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>
PREFIX wobd:        <http://purl.org/okn/wobd/>

SELECT DISTINCT
  ?experimentId
  ?contrast
  ?contrastId
  ?contrastLabel
  ?gene
  ?geneSymbol
  ?log2fc
  ?adjPValue
FROM <https://purl.org/okn/frink/kg/gene-expression-atlas-okn>
WHERE {
  ${contrastJoin}
  ${contrastRest}
  BIND(REPLACE(STR(?contrast), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentId)
  OPTIONAL { ?contrast spokegenelab:contrast_id ?contrastIdProp . }
  BIND(COALESCE(?contrastIdProp, REPLACE(STR(?contrast), "^.*-(g[0-9]+_g[0-9]+)$", "$1")) AS ?contrastId)
  OPTIONAL { ?contrast biolink:name ?contrastLabel . }
  OPTIONAL { ?gene biolink:symbol ?geneSymbol . }${organismFilter}${tissueInMain}${factorInMain}${log2fcFilter}
}
ORDER BY ?contrastId ?geneSymbol
LIMIT ${Math.min(limit, 500)}`;
}

/**
 * Build SPARQL query to find GXA experiments/contrasts where given genes are DE.
 * Returns one row per (contrast, gene) with DE metrics and labels. Includes ?experimentId
 * (GXA accession, e.g. E-GEOD-139813) for comparison with the Atlas UI; ?contrast is the
 * canonical Assay IRI for joins.
 *
 * @param geneSymbols - Array of gene symbols to search for (e.g., ["Dusp2"])
 * @param limit - Max number of rows to return (default 100)
 * @param upregulated - If true, only genes with log2fc > 0; if false, only log2fc < 0; if undefined, no direction filter.
 * @param organismTaxonIds - Optional NCBITaxon IDs to filter by organism (e.g. ["10090", "9606"])
 * @param tissueUberonIds - Optional UBERON IDs to filter by tissue (e.g. ["0002082"])
 * @param factorTerms - Optional text terms to match in factors/contrast labels (e.g. ["aortic banding"])
 * @param includeDirectionColumn - When true, SELECT includes ?direction ("up"/"down" from log2fc) like the cross-dataset summary query.
 */
export function buildGXAExperimentsForGenesQuery(
  geneSymbols: string[],
  limit: number = 100,
  upregulated?: boolean,
  organismTaxonIds?: string[],
  tissueUberonIds?: string[],
  factorTerms?: string[],
  includeDirectionColumn: boolean = false
): string {
  if (!geneSymbols || geneSymbols.length === 0) {
    throw new Error("At least one gene symbol is required for GXA experiments-for-gene query");
  }

  const geneFilters = geneSymbols.map(symbol =>
    `LCASE(?geneSymbol) = "${symbol.toLowerCase()}"`
  ).join(" ||\n    ");

  let log2fcFilter = "";
  if (upregulated === true) {
    log2fcFilter = "\n    FILTER(?log2fc > 0)";
  } else if (upregulated === false) {
    log2fcFilter = "\n    FILTER(?log2fc < 0)";
  }

  const organismFilter = buildGXAOrganismFilterFromExprs(
    organismTaxonIds,
    [gxaExperimentIdFromContrastExpr("?contrast")],
    ["gxeg"]
  );

  let tissueFilter = "";
  if (tissueUberonIds && tissueUberonIds.length > 0) {
    const safeUberon = tissueUberonIds
      .map((id) => id.replace(/^UBERON_/, "").replace(/"/g, "").trim())
      .filter(Boolean);
    if (safeUberon.length > 0) {
      const iriList = safeUberon.map((id) => `<http://purl.obolibrary.org/obo/UBERON_${id}>`).join(" ");
      tissueFilter = `\n  # Tissue filter (Phase 4)\n  ?contrast biolink:has_attribute ?tissue .\n  FILTER(?tissue IN (${iriList}))`;
    }
  }

  // Factor filter: use subquery to filter contrasts first
  const factorSubquery = buildFactorContrastSubquery(factorTerms, tissueFilter);
  const useFactorSubquery = factorSubquery !== "";

  const contrastSource = useFactorSubquery
    ? `# Subquery: filter contrasts by factor/tissue before joining
  ${factorSubquery}
  ?assoc a biolink:GeneExpressionMixin ;
         biolink:object ?gene ;
         biolink:subject ?contrast .
${gxaAssocLog2fcBinding("?assoc", "?log2fc", "gxeg")}`
    : `?assoc a biolink:GeneExpressionMixin ;
         biolink:object ?gene ;
         biolink:subject ?contrast .
${gxaAssocLog2fcBinding("?assoc", "?log2fc", "gxeg")}
  ?contrast a biolink:Assay .`;

  const factorInMain = useFactorSubquery ? "" : (() => {
    if (!factorTerms || factorTerms.length === 0) return "";
    const safeTerms = factorTerms.map((t) => t.replace(/"/g, '\\"').toLowerCase()).filter(Boolean);
    if (safeTerms.length === 0) return "";
    const termConditions = safeTerms
      .map(
        (t) =>
          `(CONTAINS(LCASE(COALESCE(?contrastLabel, "")), "${t}") || ` +
          `CONTAINS(LCASE(COALESCE(?f1, "")), "${t}") || ` +
          `CONTAINS(LCASE(COALESCE(?f2, "")), "${t}"))`
      )
      .join(" || ");
    return `\n  OPTIONAL { ?contrast biolink:name ?contrastLabel . }\n  OPTIONAL { ?contrast spokegenelab:factors_1 ?f1 . }\n  OPTIONAL { ?contrast spokegenelab:factors_2 ?f2 . }\n  FILTER(${termConditions})`;
  })();

  const tissueInMain = useFactorSubquery ? "" : tissueFilter;

  const directionSelect = includeDirectionColumn ? "\n  ?direction" : "";
  const directionBind = includeDirectionColumn
    ? "\n  BIND(IF(?log2fc > 0, \"up\", \"down\") AS ?direction)"
    : "";

  return `PREFIX biolink:      <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>
PREFIX wobd:        <http://purl.org/okn/wobd/>

SELECT DISTINCT
  ?experimentId
  ?contrast
  ?contrastLabel
  ?gene
  ?geneSymbol${directionSelect}
  ?log2fc
  ?adjPValue
FROM <https://purl.org/okn/frink/kg/gene-expression-atlas-okn>
WHERE {
  ${contrastSource}
${gxaAssocAdjPBinding("?assoc", "?adjPValue", "gxega")}
  ?gene biolink:symbol ?geneSymbol .
  FILTER(
    ${geneFilters}
  )${log2fcFilter}${organismFilter}${tissueInMain}${factorInMain}

  BIND(REPLACE(STR(?contrast), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentId)
  OPTIONAL { ?contrast biolink:name ?contrastLabel . }${directionBind}
}
ORDER BY ?geneSymbol ?experimentId STR(?contrast)
LIMIT ${Math.min(limit, 500)}`;
}

/**
 * Build SPARQL query to summarize a gene's DE evidence across experiments (Phase 3 cross-dataset).
 * Returns one row per (gene, experiment, contrast) plus aggregates: total contrasts, upregulated count, downregulated count.
 *
 * @param geneSymbol - Gene symbol (e.g. "DUSP2")
 * @param limit - Max rows (default 100)
 * @param organismTaxonIds - Optional NCBITaxon IDs to filter by organism
 * @param tissueUberonIds - Optional UBERON IDs to filter by tissue
 * @param factorTerms - Optional text terms to match in factors/contrast labels
 */
export function buildGXAGeneCrossDatasetSummaryQuery(
  geneSymbol: string,
  limit: number = 100,
  organismTaxonIds?: string[],
  tissueUberonIds?: string[],
  factorTerms?: string[]
): string {
  if (!geneSymbol?.trim()) {
    throw new Error("gene_symbol is required for GXA gene cross-dataset summary");
  }
  const safeSymbol = geneSymbol.trim().toLowerCase().replace(/"/g, '\\"');

  const organismFilter = buildGXAOrganismFilterFromExprs(
    organismTaxonIds,
    [gxaExperimentIdFromContrastExpr("?contrast")],
    ["gxsum"]
  );

  let tissueFilter = "";
  if (tissueUberonIds && tissueUberonIds.length > 0) {
    const safeUberon = tissueUberonIds
      .map((id) => id.replace(/^UBERON_/, "").replace(/"/g, "").trim())
      .filter(Boolean);
    if (safeUberon.length > 0) {
      const iriList = safeUberon.map((id) => `<http://purl.obolibrary.org/obo/UBERON_${id}>`).join(" ");
      tissueFilter = `\n  ?contrast biolink:has_attribute ?tissue .\n  FILTER(?tissue IN (${iriList}))`;
    }
  }

  // Factor filter: use subquery to filter contrasts first
  const factorSubquery = buildFactorContrastSubquery(factorTerms, tissueFilter);
  const useFactorSubquery = factorSubquery !== "";

  const contrastSource = useFactorSubquery
    ? `# Subquery: filter contrasts by factor/tissue before joining
  ${factorSubquery}
  ?assoc a biolink:GeneExpressionMixin ;
         biolink:object ?gene ;
         biolink:subject ?contrast .
${gxaAssocLog2fcBinding("?assoc", "?log2fc", "gxsum")}`
    : `?assoc a biolink:GeneExpressionMixin ;
         biolink:object ?gene ;
         biolink:subject ?contrast .
${gxaAssocLog2fcBinding("?assoc", "?log2fc", "gxsum")}
  ?contrast a biolink:Assay .`;

  const factorInMain = useFactorSubquery ? "" : (() => {
    if (!factorTerms || factorTerms.length === 0) return "";
    const safeTerms = factorTerms.map((t) => t.replace(/"/g, '\\"').toLowerCase()).filter(Boolean);
    if (safeTerms.length === 0) return "";
    const termConditions = safeTerms
      .map(
        (t) =>
          `(CONTAINS(LCASE(COALESCE(?contrastLabel, "")), "${t}") || ` +
          `CONTAINS(LCASE(COALESCE(?f1, "")), "${t}") || ` +
          `CONTAINS(LCASE(COALESCE(?f2, "")), "${t}"))`
      )
      .join(" || ");
    return `\n  OPTIONAL { ?contrast spokegenelab:factors_1 ?f1 . }\n  OPTIONAL { ?contrast spokegenelab:factors_2 ?f2 . }\n  FILTER(${termConditions})`;
  })();

  const tissueInMain = useFactorSubquery ? "" : tissueFilter;

  return `PREFIX biolink:      <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>
PREFIX wobd:        <http://purl.org/okn/wobd/>

SELECT DISTINCT
  ?geneSymbol
  ?experimentId
  ?contrastId
  ?contrastLabel
  ?direction
  ?log2fc
  ?adjPValue
FROM <https://purl.org/okn/frink/kg/gene-expression-atlas-okn>
WHERE {
  ${contrastSource}
${gxaAssocAdjPBinding("?assoc", "?adjPValue", "gxsuma")}
  ?gene biolink:symbol ?geneSymbol .
  FILTER(LCASE(?geneSymbol) = "${safeSymbol}")

  BIND(REPLACE(STR(?contrast), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentId)
  OPTIONAL { ?contrast spokegenelab:contrast_id ?contrastIdProp . }
  BIND(COALESCE(?contrastIdProp, REPLACE(STR(?contrast), "^.*-(g[0-9]+_g[0-9]+)$", "$1")) AS ?contrastId)
  OPTIONAL { ?contrast biolink:name ?contrastLabel . }${organismFilter}${tissueInMain}${factorInMain}

  BIND(IF(?log2fc > 0, "up", "down") AS ?direction)
}
ORDER BY ?experimentId ?contrastId
LIMIT ${Math.min(limit, 500)}`;
}

/**
 * Build SPARQL query to find genes DE in the same direction across multiple experiments (Phase 3 agreement).
 * Returns genes that are consistently upregulated OR consistently downregulated in >= minExperiments experiments.
 *
 * @param minExperiments - Minimum number of distinct experiments (default 2)
 * @param direction - "up", "down", or undefined for either
 * @param limit - Max rows (default 50)
 * @param organismTaxonIds - Optional NCBITaxon IDs to filter by organism
 * @param tissueUberonIds - Optional UBERON IDs to filter by tissue
 * @param factorTerms - Optional text terms to match in factors/contrast labels
 */
export function buildGXAGenesAgreementQuery(
  minExperiments: number = 2,
  direction?: "up" | "down",
  limit: number = 50,
  organismTaxonIds?: string[],
  tissueUberonIds?: string[],
  factorTerms?: string[]
): string {
  const dirFilter =
    direction === "up"
      ? "FILTER(?log2fc > 0)"
      : direction === "down"
        ? "FILTER(?log2fc < 0)"
        : "FILTER(?log2fc != 0)";

  const organismFilter = buildGXAOrganismFilterFromExprs(
    organismTaxonIds,
    [gxaExperimentIdFromContrastExpr("?contrast")],
    ["gxagr"]
  );

  let tissueFilter = "";
  if (tissueUberonIds && tissueUberonIds.length > 0) {
    const safeUberon = tissueUberonIds
      .map((id) => id.replace(/^UBERON_/, "").replace(/"/g, "").trim())
      .filter(Boolean);
    if (safeUberon.length > 0) {
      const iriList = safeUberon.map((id) => `<http://purl.obolibrary.org/obo/UBERON_${id}>`).join(" ");
      tissueFilter = `\n  ?contrast biolink:has_attribute ?tissue .\n  FILTER(?tissue IN (${iriList}))`;
    }
  }

  // Factor filter: use subquery to filter contrasts first
  const factorSubquery = buildFactorContrastSubquery(factorTerms, tissueFilter);
  const useFactorSubquery = factorSubquery !== "";

  const contrastSource = useFactorSubquery
    ? `# Subquery: filter contrasts by factor/tissue before joining
  ${factorSubquery}
  ?assoc a biolink:GeneExpressionMixin ;
         biolink:object ?gene ;
         biolink:subject ?contrast .
${gxaAssocLog2fcBinding("?assoc", "?log2fc", "gxagr")}`
    : `?assoc a biolink:GeneExpressionMixin ;
         biolink:object ?gene ;
         biolink:subject ?contrast .
${gxaAssocLog2fcBinding("?assoc", "?log2fc", "gxagr")}
  ?contrast a biolink:Assay .`;

  const factorInMain = useFactorSubquery ? "" : (() => {
    if (!factorTerms || factorTerms.length === 0) return "";
    const safeTerms = factorTerms.map((t) => t.replace(/"/g, '\\"').toLowerCase()).filter(Boolean);
    if (safeTerms.length === 0) return "";
    const termConditions = safeTerms
      .map(
        (t) =>
          `(CONTAINS(LCASE(COALESCE(?contrastLabel, "")), "${t}") || ` +
          `CONTAINS(LCASE(COALESCE(?f1, "")), "${t}") || ` +
          `CONTAINS(LCASE(COALESCE(?f2, "")), "${t}"))`
      )
      .join(" || ");
    return `\n  OPTIONAL { ?contrast biolink:name ?contrastLabel . }\n  OPTIONAL { ?contrast spokegenelab:factors_1 ?f1 . }\n  OPTIONAL { ?contrast spokegenelab:factors_2 ?f2 . }\n  FILTER(${termConditions})`;
  })();

  const tissueInMain = useFactorSubquery ? "" : tissueFilter;

  return `PREFIX biolink:      <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>
PREFIX wobd:        <http://purl.org/okn/wobd/>

SELECT ?geneSymbol ?direction (COUNT(DISTINCT ?experimentId) AS ?experimentCount)
  (GROUP_CONCAT(DISTINCT ?experimentId; separator=" | ") AS ?sampleExperimentIds)
  (GROUP_CONCAT(DISTINCT ?contrastLabel; separator=" | ") AS ?sampleContrastLabels)
FROM <https://purl.org/okn/frink/kg/gene-expression-atlas-okn>
WHERE {
  ${contrastSource}
  OPTIONAL { ?gene biolink:symbol ?geneSymbol . }
  OPTIONAL { ?contrast biolink:name ?contrastLabel . }
  ${dirFilter}
  BIND(REPLACE(STR(?contrast), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentId)
  BIND(IF(?log2fc > 0, "up", "down") AS ?direction)${organismFilter}${tissueInMain}${factorInMain}
}
GROUP BY ?gene ?geneSymbol ?direction
HAVING (COUNT(DISTINCT ?experimentId) >= ${Math.max(1, minExperiments)})
ORDER BY DESC(?experimentCount) ?geneSymbol
LIMIT ${Math.min(limit, 200)}`;
}

/**
 * Build SPARQL query to find genes DE in opposite directions across contrasts (Phase 3 discordance).
 * Returns genes that are upregulated in some contrasts and downregulated in others.
 * Includes log2fc, adj_p_value, array_design, measurement for both up and down contrasts.
 *
 * @param limit - Max rows (default 50)
 * @param organismTaxonIds - Optional NCBITaxon IDs to filter by organism
 * @param tissueUberonIds - Optional UBERON IDs to filter by tissue
 * @param factorTerms - Optional text terms to match in factors/contrast labels
 */
export function buildGXAGenesDiscordanceQuery(
  limit: number = 50,
  organismTaxonIds?: string[],
  tissueUberonIds?: string[],
  factorTerms?: string[]
): string {
  // Full organism+tissue FILTER at end forces Virtuoso to join ~all up/down DE rows on ?gene first
  // (hundreds of millions of intermediates → OOM). When tissue and/or organism is set, prefilter
  // ?c1 and ?c2 via subqueries so associations only touch matching contrasts.
  const organismFilterMain = buildGXAOrganismFilterFromExprs(
    organismTaxonIds,
    [gxaExperimentIdFromContrastExpr("?c1"), gxaExperimentIdFromContrastExpr("?c2")],
    ["up", "down"]
  );

  let tissueFilterC1 = "";
  let tissueIriList = "";
  if (tissueUberonIds && tissueUberonIds.length > 0) {
    const safeUberon = tissueUberonIds
      .map((id) => id.replace(/^UBERON_/, "").replace(/"/g, "").trim())
      .filter(Boolean);
    if (safeUberon.length > 0) {
      tissueIriList = safeUberon.map((id) => `<http://purl.obolibrary.org/obo/UBERON_${id}>`).join(" ");
      tissueFilterC1 = `\n  ?c1 biolink:has_attribute ?tissue .\n  FILTER(?tissue IN (${tissueIriList}))`;
    }
  }

  const hasTissue = tissueIriList.length > 0;
  const hasOrganism =
    normalizeGxaNcbiTaxonNumericIds(organismTaxonIds ?? []).length > 0;
  const organismSubC1 = hasOrganism
    ? buildGXAOrganismFilterFromExprs(organismTaxonIds, [gxaExperimentIdFromContrastExpr("?c1")], ["dsc1"])
    : "";
  const organismSubC2 = hasOrganism
    ? buildGXAOrganismFilterFromExprs(organismTaxonIds, [gxaExperimentIdFromContrastExpr("?c2")], ["dsc2"])
    : "";
  const tissueInnerC1 = hasTissue
    ? `\n      ?c1 biolink:has_attribute ?tissue .\n      FILTER(?tissue IN (${tissueIriList}))`
    : "";
  const tissueInnerC2 = hasTissue
    ? `\n      ?c2 biolink:has_attribute ?tissue .\n      FILTER(?tissue IN (${tissueIriList}))`
    : "";

  const factorSubquery = buildFactorContrastSubquery(
    factorTerms,
    tissueFilterC1,
    "",
    "?c1",
    hasOrganism ? organismSubC1 : ""
  );
  const useFactorSubquery = factorSubquery !== "";

  const contrastAssayRegex = "E-[A-Z0-9-]+-g[0-9]+_g[0-9]+";

  let c1Prefix = "";
  if (useFactorSubquery) {
    c1Prefix = `# Subquery: filter ?c1 contrasts (factor / tissue / organism) before associations
  ${factorSubquery}
  `;
  } else if (hasTissue || hasOrganism) {
    c1Prefix = `{
    SELECT DISTINCT ?c1 WHERE {
      ?c1 a biolink:Assay .
      FILTER(REGEX(STR(?c1), "${contrastAssayRegex}"))${tissueInnerC1}${organismSubC1}
    }
  }
  `;
  }

  const c2Prefix =
    hasTissue || hasOrganism
      ? `{
    SELECT DISTINCT ?c2 WHERE {
      ?c2 a biolink:Assay .
      FILTER(REGEX(STR(?c2), "${contrastAssayRegex}"))${tissueInnerC2}${organismSubC2}
    }
  }
  `
      : "";

  const movedFacetToSubquery = useFactorSubquery || hasTissue || hasOrganism;
  const organismFilterTail = movedFacetToSubquery ? "" : organismFilterMain;
  const tissueInMain = movedFacetToSubquery ? "" : tissueFilterC1;

  const factorInMain = useFactorSubquery ? "" : (() => {
    if (!factorTerms || factorTerms.length === 0) return "";
    const safeTerms = factorTerms.map((t) => t.replace(/"/g, '\\"').toLowerCase()).filter(Boolean);
    if (safeTerms.length === 0) return "";
    const termConditions = safeTerms
      .map(
        (t) =>
          `(CONTAINS(LCASE(COALESCE(?cl1, "")), "${t}") || ` +
          `CONTAINS(LCASE(COALESCE(?f1a, "")), "${t}") || ` +
          `CONTAINS(LCASE(COALESCE(?f1b, "")), "${t}"))`
      )
      .join(" || ");
    return `\n  OPTIONAL { ?c1 biolink:name ?cl1 . }\n  OPTIONAL { ?c1 spokegenelab:factors_1 ?f1a . }\n  OPTIONAL { ?c1 spokegenelab:factors_2 ?f1b . }\n  FILTER(${termConditions})`;
  })();

  return `PREFIX biolink:      <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>
PREFIX wobd:        <http://purl.org/okn/wobd/>

SELECT ?gene ?geneSymbol ?experimentIdUp ?experimentIdDown ?contrastLabelUp ?contrastLabelDown
  ?log2fcUp ?log2fcDown ?adjPValueUp ?adjPValueDown
  ?arrayDesignUp ?measurementUp ?arrayDesignDown ?measurementDown
FROM <https://purl.org/okn/frink/kg/gene-expression-atlas-okn>
WHERE {
  ${c1Prefix}?a1 a biolink:GeneExpressionMixin ; biolink:object ?gene ; biolink:subject ?c1 .
${gxaAssocLog2fcBinding("?a1", "?l1", "d1")}
  FILTER(?l1 > 0)
  ${c2Prefix}?a2 a biolink:GeneExpressionMixin ; biolink:object ?gene ; biolink:subject ?c2 .
${gxaAssocLog2fcBinding("?a2", "?l2", "d2")}
  FILTER(?l2 < 0)
  FILTER(?a1 != ?a2)
  OPTIONAL { ?gene biolink:symbol ?geneSymbol . }
${gxaAssocAdjPBinding("?a1", "?adjPValueUp", "d1a")}
${gxaAssocAdjPBinding("?a2", "?adjPValueDown", "d2a")}
  OPTIONAL { ?c1 spokegenelab:array_design ?arrayDesignUp . }
  OPTIONAL { ?c1 spokegenelab:measurement ?measurementUp . }
  OPTIONAL { ?c2 spokegenelab:array_design ?arrayDesignDown . }
  OPTIONAL { ?c2 spokegenelab:measurement ?measurementDown . }
  BIND(REPLACE(STR(?c1), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentIdUp)
  BIND(REPLACE(STR(?c2), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentIdDown)
  BIND(?l1 AS ?log2fcUp)
  BIND(?l2 AS ?log2fcDown)
  OPTIONAL { ?c1 biolink:name ?contrastLabelUp . }
  OPTIONAL { ?c2 biolink:name ?contrastLabelDown . }${organismFilterTail}${tissueInMain}${factorInMain}
}
LIMIT ${Math.min(limit, 200)}`;
}

/**
 * Build SPARQL query to find datasets by BOTH disease (MONDO) AND organism (UniProt taxonomy)
 * This is useful for queries like "influenza" which can refer to both the disease and the pathogen
 *
 * When keywordFallbackTerms is provided, datasets that match name/description by keyword are
 * also returned (avoids 0 results when ontology IRIs are not present in the graph).
 *
 * @param diseaseIRIs - Array of MONDO IRIs for diseases
 * @param organismIRIs - Array of UniProt taxonomy IRIs for organisms/pathogens
 * @param diseaseLabels - Optional array of disease labels for text matching
 * @param organismLabels - Optional array of organism labels for text matching
 * @param useTextMatching - If true, adds text matching as fallback
 * @param keywordFallbackTerms - Optional terms to match on ?name / ?description (e.g. ["influenza"])
 * @param limit - Max number of dataset rows to return (default 500, capped at 500)
 * @param geoOnly - If true, restrict to NCBI GEO datasets. In NDE, GEO uses schema:identifier GSE[0-9]+ (e.g. GSE100, GSE100000); also match url/sameAs containing geo/ncbi.
 */
export function buildNDEDiseaseAndOrganismQuery(
  diseaseIRIs: string[],
  organismIRIs: string[],
  diseaseLabels: string[] = [],
  organismLabels: string[] = [],
  useTextMatching: boolean = false,
  keywordFallbackTerms: string[] = [],
  limit: number = 500,
  geoOnly: boolean = false
): string {
  if (diseaseIRIs.length === 0 && organismIRIs.length === 0 && keywordFallbackTerms.length === 0) {
    throw new Error("At least one disease or organism IRI or keyword term required");
  }

  let diseasePattern = "";
  let organismPattern = "";
  let selectVars = "?dataset ?name ?description ?identifier";

  // Build disease pattern if we have disease IRIs
  if (diseaseIRIs.length > 0) {
    const diseaseIRIFilters = diseaseIRIs.map(iri => `?disease = <${iri}>`).join(" || ");
    let diseaseFilter = `FILTER(${diseaseIRIFilters})`;

    if (useTextMatching && diseaseLabels.length > 0) {
      const escapedLabels = diseaseLabels.map(label => label.replace(/"/g, '\\"'));
      const nameFilters = escapedLabels.map(label =>
        `CONTAINS(LCASE(?diseaseName), LCASE("${label}"))`
      ).join(" || ");
      diseaseFilter = `FILTER((${diseaseIRIFilters}) || (${nameFilters}))`;
    }

    // Required block when disease IRIs are provided: only return datasets that have one of these diseases
    diseasePattern = `
  # Match by disease/health condition (required when disease IRIs provided)
  ?dataset schema:healthCondition ?disease .
  ?disease schema:name ?diseaseName .
  ${diseaseFilter}`;
    // diseaseName is aggregated per dataset (GROUP_CONCAT) so we get one row per dataset
  }

  // Build organism pattern if we have organism IRIs
  if (organismIRIs.length > 0) {
    const organismIRIFilters = organismIRIs.map(iri => `?organism = <${iri}>`).join(" || ");
    let organismFilter = `FILTER(${organismIRIFilters})`;

    if (useTextMatching && organismLabels.length > 0) {
      const escapedLabels = organismLabels.map(label => label.replace(/"/g, '\\"'));
      const nameFilters = escapedLabels.map(label =>
        `CONTAINS(LCASE(?organismName), LCASE("${label}"))`
      ).join(" || ");
      organismFilter = `FILTER((${organismIRIFilters}) || (${nameFilters}))`;
    }

    // Required block when organism IRIs are provided: only return datasets that have one of these organisms
    organismPattern = `
  # Match by infectious agent or species (required when organism IRIs provided)
  {
    ?dataset schema:infectiousAgent ?organism .
    ?organism schema:name ?organismName .
  }
  UNION
  {
    ?dataset schema:species ?organism .
    ?organism schema:name ?organismName .
  }
  ${organismFilter}`;
    // organismName is aggregated per dataset (GROUP_CONCAT) so we get one row per dataset
  }

  // Require at least one match: disease OR organism OR keyword in name/description
  let requireMatch = "";
  if (keywordFallbackTerms.length > 0) {
    const rawTerms = keywordFallbackTerms
      .map((t) => t.trim())
      .filter(Boolean)
      .slice(0, 5);
    // Expand with common synonyms so we match more (e.g. influenza -> also match "flu")
    const expandSynonyms = (term: string): string[] => {
      const lower = term.toLowerCase();
      if (lower === "influenza") return [term, "flu"];
      return [term];
    };
    const termsWithSynonyms = rawTerms.flatMap(expandSynonyms);
    const escaped = [...new Set(termsWithSynonyms)]
      .map((t) => t.replace(/\\/g, "\\\\").replace(/"/g, '\\"'))
      .filter(Boolean)
      .slice(0, 8);
    // Use COALESCE so we match on name or description even when description is unbound
    const keywordConditions = escaped.map(
      (t) =>
        `REGEX(STR(?name), "${t}", "i") || REGEX(STR(COALESCE(?description, "")), "${t}", "i")`
    );
    const keywordClause = keywordConditions.join(" || ");
    requireMatch =
      diseaseIRIs.length > 0 || organismIRIs.length > 0
        ? `FILTER(BOUND(?disease) || BOUND(?organism) || (${keywordClause}))`
        : `FILTER(${keywordClause})`;
  }
  // When disease/organism IRIs are provided, their blocks are now required (not OPTIONAL),
  // so no need for FILTER(BOUND(?disease) || BOUND(?organism)) here.

  // Restrict to NCBI GEO datasets when geoOnly: identifier GSE\\d+ or url/sameAs containing geo/ncbi
  const geoFilter = geoOnly
    ? `
  FILTER(
    REGEX(STR(COALESCE(?identifier, "")), "GSE[0-9]+", "i")
    || REGEX(STR(COALESCE(?url, "")), "ncbi.*geo|geo.*ncbi", "i")
    || REGEX(STR(COALESCE(?sameAs, "")), "ncbi.*geo|geo.*ncbi", "i")
    || REGEX(STR(COALESCE(?owlSameAs, "")), "ncbi.*geo|geo.*ncbi", "i")
  )`
    : "";

  // One row per dataset: group by base vars only; aggregate url/sameAs and disease/organism names
  const groupByVars = selectVars.trim().split(/\s+/).filter(Boolean).join(" ");
  const diseaseAggregate =
    diseaseIRIs.length > 0
      ? `  (GROUP_CONCAT(DISTINCT ?diseaseName; SEPARATOR="; ") AS ?diseaseNames)`
      : "";
  const organismAggregate =
    organismIRIs.length > 0
      ? `  (GROUP_CONCAT(DISTINCT ?organismName; SEPARATOR="; ") AS ?organismNames)`
      : "";
  const aggregates = [diseaseAggregate, organismAggregate].filter(Boolean).join("\n");
  return `PREFIX schema: <http://schema.org/>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

SELECT ${selectVars}
  (GROUP_CONCAT(DISTINCT STR(?url); SEPARATOR=" ") AS ?urls)
  (GROUP_CONCAT(DISTINCT STR(?sameAs); SEPARATOR=" ") AS ?sameAsList)
  (GROUP_CONCAT(DISTINCT STR(?owlSameAs); SEPARATOR=" ") AS ?owlSameAsList)
${aggregates}
FROM <https://purl.org/okn/frink/kg/nde>
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name .
  OPTIONAL { ?dataset schema:description ?description }
  OPTIONAL { ?dataset schema:identifier ?identifier }
  OPTIONAL { ?dataset schema:url ?url }
  OPTIONAL { ?dataset schema:sameAs ?sameAs }
  OPTIONAL { ?dataset owl:sameAs ?owlSameAs }
  ${diseasePattern}
  ${organismPattern}
  ${requireMatch}
  ${geoFilter}
}
GROUP BY ${groupByVars}
LIMIT ${Math.min(limit, 500)}`;
}

/**
 * Build SPARQL query for SPOKE-OKN: summary of genes associated with the given disease IRIs
 * (MONDO or Wikidata). Returns one row with total distinct gene count and sample gene symbols.
 * @param diseaseIRIs - Full IRIs (e.g. http://purl.obolibrary.org/obo/MONDO_0005015)
 * @param sampleLimit - Max sample genes in GROUP_CONCAT (default 15)
 */
export function buildSPOKEOKNSummaryForDiseasesQuery(
  diseaseIRIs: string[],
  sampleLimit: number = 15
): string | null {
  if (diseaseIRIs.length === 0) return null;
  const iriList = diseaseIRIs
    .map((iri) => iri.trim())
    .filter(Boolean)
    .slice(0, 50)
    .map((iri) => `<${iri.replace(/[<>]/g, "")}>`)
    .join(" ");
  return `PREFIX biolink: <https://w3id.org/biolink/vocab/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT (COUNT(DISTINCT ?gene) AS ?geneCount) (GROUP_CONCAT(DISTINCT ?geneSymbol; SEPARATOR=", ") AS ?sampleGeneSymbols)
WHERE {
  VALUES ?disease { ${iriList} }
  {
    ?assoc biolink:subject ?disease ; biolink:object ?gene .
    ?gene a biolink:Gene .
  } UNION {
    ?assoc biolink:object ?disease ; biolink:subject ?gene .
    ?gene a biolink:Gene .
  }
  OPTIONAL { ?gene biolink:name ?geneSymbol . }
  OPTIONAL { ?gene rdfs:label ?geneSymbol . }
  FILTER(BOUND(?geneSymbol) && STR(?geneSymbol) != "")
}
LIMIT 1`;
}

/**
 * Build SPARQL query for SPOKE-GeneLab (GXA graph): summary of genes in expression studies
 * for the given EFO disease IRIs. Study biolink:studies Disease (EFO; same pattern as
 * scripts/demos/analysis_tools/drug_disease.py). Returns one row with gene count and sample gene symbols.
 * @param efoDiseaseIRIs - Full EFO IRIs (e.g. http://www.ebi.ac.uk/efo/EFO_0000275)
 * @param sampleLimit - Max sample genes in GROUP_CONCAT (default 15)
 */
export function buildSPOKEGeneLabSummaryForDiseasesQuery(
  efoDiseaseIRIs: string[],
  sampleLimit: number = 15
): string | null {
  if (efoDiseaseIRIs.length === 0) return null;
  const iriList = efoDiseaseIRIs
    .map((iri) => iri.trim())
    .filter(Boolean)
    .slice(0, 50)
    .map((iri) => `<${iri.replace(/[<>]/g, "")}>`)
    .join(" ");
  return `PREFIX biolink: <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>

SELECT (COUNT(DISTINCT ?gene) AS ?geneCount) (GROUP_CONCAT(DISTINCT ?geneSymbol; SEPARATOR=", ") AS ?sampleGeneSymbols)
FROM <https://purl.org/okn/frink/kg/gene-expression-atlas-okn>
WHERE {
  VALUES ?disease { ${iriList} }
  ?assoc a biolink:GeneExpressionMixin ;
         biolink:subject ?contrast ;
         biolink:object ?gene .
  ?contrast a biolink:Assay .
  FILTER(REGEX(STR(?contrast), "E-[A-Z0-9-]+-g[0-9]+_g[0-9]+"))
  BIND(REPLACE(STR(?contrast), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentId)
  BIND(IRI(CONCAT("https://spoke.ucsf.edu/genelab/", ?experimentId)) AS ?study)
  ?study biolink:studies ?disease .
  OPTIONAL { ?gene biolink:symbol ?geneSymbol . }
  OPTIONAL { ?gene biolink:name ?geneSymbol . }
  FILTER(BOUND(?geneSymbol) && STR(?geneSymbol) != "")
}
LIMIT 1`;
}
