// Fixed SPARQL templates for ontology-grounded query chaining
// All queries use FROM clauses for graph scoping - no GRAPH enumeration

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

SELECT DISTINCT ?dataset ?name ?description ?diseaseName
FROM <https://purl.org/okn/frink/kg/nde>
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name ;
           schema:healthCondition ?disease .
  ?disease schema:name ?diseaseName .
  OPTIONAL { ?dataset schema:description ?description }
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

SELECT DISTINCT ?dataset ?name ?description ?diseaseName
FROM <https://purl.org/okn/frink/kg/nde>
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name ;
           schema:healthCondition ?disease .
  ?disease schema:name ?diseaseName .
  OPTIONAL { ?dataset schema:description ?description }
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

SELECT DISTINCT ?dataset ?name ?description ?speciesName
FROM <https://purl.org/okn/frink/kg/nde>
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name ;
           schema:species ?species .
  ?species schema:name ?speciesName .
  OPTIONAL { ?dataset schema:description ?description }
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

SELECT DISTINCT ?dataset ?name ?description ?speciesName
FROM <https://purl.org/okn/frink/kg/nde>
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name ;
           schema:species ?species .
  ?species schema:name ?speciesName .
  OPTIONAL { ?dataset schema:description ?description }
  ${filterClause}
}
LIMIT 50`;
}

/**
 * Build SPARQL query for fallback text search
 * Stage 6: Fallback text search (only if ontology workflow fails)
 */
export function buildNDEFallbackQuery(
  rawPhrase: string,
  candidateLabels: string[]
): string {
  const searchTerms = [rawPhrase, ...candidateLabels].filter(Boolean);

  if (searchTerms.length === 0) {
    throw new Error("At least one search term required for fallback query");
  }

  // Escape for regex - properly escape special characters for SPARQL REGEX
  // Note: In SPARQL REGEX, we need to escape regex special chars, but the string is already in quotes
  const escapedTerms = searchTerms.map(term => {
    // Remove trailing periods and other punctuation that might cause issues
    const cleaned = term.trim().replace(/\.$/, "");
    // Escape regex special characters
    return cleaned.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }).filter(Boolean);

  const regexPattern = escapedTerms.join("|");

  return `PREFIX schema: <http://schema.org/>

SELECT DISTINCT ?dataset ?name ?description
FROM <https://purl.org/okn/frink/kg/nde>
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name .
  OPTIONAL { ?dataset schema:description ?description }

  FILTER(
    REGEX(STR(?name), "${regexPattern}", "i")
    || (BOUND(?description) &&
        REGEX(STR(?description), "${regexPattern}", "i"))
  )
}
LIMIT 50`;
}

/**
 * Build SPARQL query to find datasets by Wikidata drug identifiers
 * @param wikidataIRIs - Array of Wikidata IRIs (e.g., ["http://www.wikidata.org/entity/Q421094"])
 * @param useTextMatching - If true, includes optional text matching on drug names
 */
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

SELECT DISTINCT ?dataset ?name ?description ?drugName
FROM <https://purl.org/okn/frink/kg/nde>
FROM <https://purl.org/okn/frink/kg/wikidata>
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name .
  
  # Link dataset to drug via some property (adjust based on actual schema)
  # This is a placeholder - actual predicate may vary
  ?dataset schema:about ?drug .
  
  OPTIONAL { ?dataset schema:description ?description }
  OPTIONAL { ?drug rdfs:label ?drugName }
  
  # Filter by Wikidata drug IRI${useTextMatching ? " or by drug name" : ""}
  FILTER(
    ${iriFilters}${textFilter}
  )
}
LIMIT 50`;
}

/**
 * Build SPARQL query to list gene expression experiments (datasets) that have DE results.
 * Returns experiment accession, number of contrasts, and sample contrast labels for coverage discovery.
 * Used for Phase 1 "what expression data exists" and for bridging NDE with GXA.
 */
export function buildGXAExperimentCoverageQuery(limit: number = 100): string {
  return `PREFIX biolink: <https://w3id.org/biolink/vocab/>

SELECT ?experimentId (COUNT(DISTINCT ?contrast) AS ?contrastCount) (SAMPLE(?contrastLabel) AS ?sampleContrastLabel)
FROM <https://purl.org/okn/frink/kg/gene-expression-atlas-okn>
WHERE {
    ?association a biolink:GeneExpressionMixin ;
        biolink:subject ?contrast .
    ?contrast a biolink:Assay .
    BIND(REPLACE(STR(?contrast), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentId)
    OPTIONAL { ?contrast biolink:name ?contrastLabel . }
    FILTER(REGEX(STR(?contrast), "E-[A-Z0-9-]+-g[0-9]+_g[0-9]+"))
}
GROUP BY ?experimentId
ORDER BY DESC(?contrastCount)
LIMIT ${Math.min(limit, 500)}`;
}

/**
 * Build SPARQL query to list DE genes for a given GXA experiment (per-contrast, contrast-aware).
 * Returns one row per (gene, contrast) with DE metrics and contrast labels.
 *
 * @param experimentId - GXA experiment accession (e.g. "E-GEOD-23301")
 * @param limit - Max number of rows to return (default 100)
 * @param upregulated - If true, only genes with log2fc > 0; if false, only log2fc < 0; if undefined, no direction filter.
 */
export function buildGXAGenesForExperimentQuery(
  experimentId: string,
  limit: number = 100,
  upregulated?: boolean
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

  return `PREFIX biolink:      <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>

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
  # Differential expression associations (same pattern as coverage query)
  ?assoc a biolink:GeneExpressionMixin ;
         biolink:object ?gene ;
         biolink:subject ?contrast ;
         spokegenelab:log2fc ?log2fc .
  OPTIONAL { ?assoc spokegenelab:adj_p_value ?adjPValue . }
  ?contrast a biolink:Assay .

  # Restrict to the requested experiment (CONTAINS is robust across URI schemes)
  FILTER(CONTAINS(STR(?contrast), "${safeId}"))

  BIND(REPLACE(STR(?contrast), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentId)
  OPTIONAL { ?contrast spokegenelab:contrast_id ?contrastIdProp . }
  BIND(COALESCE(?contrastIdProp, REPLACE(STR(?contrast), "^.*-(g[0-9]+_g[0-9]+)$", "$1")) AS ?contrastId)
  OPTIONAL { ?contrast biolink:name ?contrastLabel . }

  # Gene symbol (optional; some graphs only attach symbols in other graphs)
  OPTIONAL { ?gene biolink:symbol ?geneSymbol . }${log2fcFilter}
}
ORDER BY ?contrastId ?geneSymbol
LIMIT ${Math.min(limit, 500)}`;
}

/**
 * Build SPARQL query to find GXA experiments/contrasts where given genes are DE.
 * Returns one row per (experiment, contrast, gene) with DE metrics and labels.
 *
 * @param geneSymbols - Array of gene symbols to search for (e.g., ["Dusp2"])
 * @param limit - Max number of rows to return (default 100)
 * @param upregulated - If true, only genes with log2fc > 0; if false, only log2fc < 0; if undefined, no direction filter.
 */
export function buildGXAExperimentsForGenesQuery(
  geneSymbols: string[],
  limit: number = 100,
  upregulated?: boolean
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

  return `PREFIX biolink:      <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>

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
  # Differential expression associations
  ?assoc a biolink:GeneExpressionMixin ;
         biolink:object ?gene ;
         biolink:subject ?contrast ;
         spokegenelab:log2fc ?log2fc .
  OPTIONAL { ?assoc spokegenelab:adj_p_value ?adjPValue . }

  # Gene symbol filter
  ?gene biolink:symbol ?geneSymbol .
  FILTER(
    ${geneFilters}
  )${log2fcFilter}

  # Contrast / assay with study_id + label
  ?contrast a biolink:Assay ;
            spokegenelab:study_id ?experimentId ;
            spokegenelab:contrast_id ?contrastId .
  OPTIONAL { ?contrast biolink:name ?contrastLabel . }
}
ORDER BY ?geneSymbol ?experimentId ?contrastId
LIMIT ${Math.min(limit, 500)}`;
}

/**
 * Build SPARQL query to summarize a gene's DE evidence across experiments (Phase 3 cross-dataset).
 * Returns one row per (gene, experiment, contrast) plus aggregates: total contrasts, upregulated count, downregulated count.
 *
 * @param geneSymbol - Gene symbol (e.g. "DUSP2")
 * @param limit - Max rows (default 100)
 */
export function buildGXAGeneCrossDatasetSummaryQuery(
  geneSymbol: string,
  limit: number = 100
): string {
  if (!geneSymbol?.trim()) {
    throw new Error("gene_symbol is required for GXA gene cross-dataset summary");
  }
  const safeSymbol = geneSymbol.trim().toLowerCase().replace(/"/g, '\\"');

  return `PREFIX biolink:      <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>

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
  ?assoc a biolink:GeneExpressionMixin ;
         biolink:object ?gene ;
         biolink:subject ?contrast ;
         spokegenelab:log2fc ?log2fc .
  OPTIONAL { ?assoc spokegenelab:adj_p_value ?adjPValue . }
  ?contrast a biolink:Assay .
  ?gene biolink:symbol ?geneSymbol .
  FILTER(LCASE(?geneSymbol) = "${safeSymbol}")

  BIND(REPLACE(STR(?contrast), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentId)
  OPTIONAL { ?contrast spokegenelab:contrast_id ?contrastIdProp . }
  BIND(COALESCE(?contrastIdProp, REPLACE(STR(?contrast), "^.*-(g[0-9]+_g[0-9]+)$", "$1")) AS ?contrastId)
  OPTIONAL { ?contrast biolink:name ?contrastLabel . }
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
 */
export function buildGXAGenesAgreementQuery(
  minExperiments: number = 2,
  direction?: "up" | "down",
  limit: number = 50
): string {
  const dirFilter =
    direction === "up"
      ? "FILTER(?log2fc > 0)"
      : direction === "down"
        ? "FILTER(?log2fc < 0)"
        : "FILTER(?log2fc != 0)";

  return `PREFIX biolink:      <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>

SELECT ?geneSymbol ?direction (COUNT(DISTINCT ?experimentId) AS ?experimentCount) (SAMPLE(?experimentId) AS ?sampleExperimentId)
FROM <https://purl.org/okn/frink/kg/gene-expression-atlas-okn>
WHERE {
  ?assoc a biolink:GeneExpressionMixin ;
         biolink:object ?gene ;
         biolink:subject ?contrast ;
         spokegenelab:log2fc ?log2fc .
  ?contrast a biolink:Assay .
  OPTIONAL { ?gene biolink:symbol ?geneSymbol . }
  ${dirFilter}
  BIND(REPLACE(STR(?contrast), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentId)
  BIND(IF(?log2fc > 0, "up", "down") AS ?direction)
}
GROUP BY ?gene ?geneSymbol ?direction
HAVING (COUNT(DISTINCT ?experimentId) >= ${Math.max(1, minExperiments)})
ORDER BY DESC(?experimentCount) ?geneSymbol
LIMIT ${Math.min(limit, 200)}`;
}

/**
 * Build SPARQL query to find genes DE in opposite directions across contrasts (Phase 3 discordance).
 * Returns genes that are upregulated in some contrasts and downregulated in others.
 *
 * @param limit - Max rows (default 50)
 */
export function buildGXAGenesDiscordanceQuery(limit: number = 50): string {
  return `PREFIX biolink:      <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>

SELECT ?gene ?geneSymbol
FROM <https://purl.org/okn/frink/kg/gene-expression-atlas-okn>
WHERE {
  ?a1 a biolink:GeneExpressionMixin ; biolink:object ?gene ; spokegenelab:log2fc ?l1 .
  FILTER(?l1 > 0)
  ?a2 a biolink:GeneExpressionMixin ; biolink:object ?gene ; spokegenelab:log2fc ?l2 .
  FILTER(?l2 < 0)
  FILTER(?a1 != ?a2)
  OPTIONAL { ?gene biolink:symbol ?geneSymbol . }
}
LIMIT ${Math.min(limit, 200)}`;
}

/**
 * Build SPARQL query to find datasets by BOTH disease (MONDO) AND organism (UniProt taxonomy)
 * This is useful for queries like "influenza" which can refer to both the disease and the pathogen
 * 
 * @param diseaseIRIs - Array of MONDO IRIs for diseases
 * @param organismIRIs - Array of UniProt taxonomy IRIs for organisms/pathogens
 * @param diseaseLabels - Optional array of disease labels for text matching
 * @param organismLabels - Optional array of organism labels for text matching
 * @param useTextMatching - If true, adds text matching as fallback
 */
export function buildNDEDiseaseAndOrganismQuery(
  diseaseIRIs: string[],
  organismIRIs: string[],
  diseaseLabels: string[] = [],
  organismLabels: string[] = [],
  useTextMatching: boolean = false
): string {
  if (diseaseIRIs.length === 0 && organismIRIs.length === 0) {
    throw new Error("At least one disease or organism IRI required");
  }

  let diseasePattern = "";
  let organismPattern = "";
  let selectVars = "?dataset ?name ?description";

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

    diseasePattern = `
  # Match by disease/health condition
  OPTIONAL {
    ?dataset schema:healthCondition ?disease .
    ?disease schema:name ?diseaseName .
    ${diseaseFilter}
  }`;
    selectVars += " ?diseaseName";
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

    organismPattern = `
  # Match by infectious agent or species
  OPTIONAL {
    {
      ?dataset schema:infectiousAgent ?organism .
      ?organism schema:name ?organismName .
    }
    UNION
    {
      ?dataset schema:species ?organism .
      ?organism schema:name ?organismName .
    }
    ${organismFilter}
  }`;
    selectVars += " ?organismName";
  }

  // Require at least one match (disease OR organism)
  const requireMatch = diseaseIRIs.length > 0 && organismIRIs.length > 0
    ? "FILTER(BOUND(?disease) || BOUND(?organism))"
    : "";

  return `PREFIX schema: <http://schema.org/>

SELECT DISTINCT ${selectVars}
FROM <https://purl.org/okn/frink/kg/nde>
WHERE {
  ?dataset a schema:Dataset ;
           schema:name ?name .
  OPTIONAL { ?dataset schema:description ?description }
  ${diseasePattern}
  ${organismPattern}
  ${requireMatch}
}
LIMIT 50`;
}
