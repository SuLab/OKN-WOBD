#!/usr/bin/env node
/**
 * Test GXA genes agreement query against the direct endpoint.
 * Run from web-v2: node scripts/test-gxa-agreement-query.mjs
 */

const GXA_ENDPOINT = "https://frink.apps.renci.org/gene-expression-atlas-okn/sparql";

// Minimal probe: count one association (fast)
const PROBE_QUERY = `PREFIX biolink: <https://w3id.org/biolink/vocab/>
SELECT (COUNT(*) AS ?c) WHERE { ?a a biolink:GeneExpressionMixin . }`;

// Probe: which predicate does Study→Disease use? (spokegenelab:studies vs biolink:studies)
const PREFIXES = `PREFIX biolink: <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>
`;
const PROBE_SPOKE_STUDIES = `${PREFIXES}
SELECT (COUNT(*) AS ?c) WHERE {
  ?study a biolink:Study .
  ?study spokegenelab:studies ?disease .
}`;
const PROBE_BIOLINK_STUDIES = `${PREFIXES}
SELECT (COUNT(*) AS ?c) WHERE {
  ?study a biolink:Study .
  ?study biolink:studies ?disease .
}`;
const PROBE_SAMPLE_DISEASES = `${PREFIXES}
SELECT DISTINCT ?disease WHERE {
  ?study a biolink:Study .
  ?study biolink:studies ?disease .
} LIMIT 10`;

// Human + MONDO diabetes filter: does any study have MONDO:0005015?
const MONDO_DIABETES_IRI = "http://purl.obolibrary.org/obo/MONDO_0005015";
const PROBE_HUMAN_MONDO_DIABETES = `${PREFIXES}
SELECT (COUNT(DISTINCT ?study) AS ?c) WHERE {
  ?study a biolink:Study .
  ?study biolink:in_taxon ?taxon .
  FILTER(?taxon IN ("9606"))
  ?study biolink:studies ?disease .
  FILTER(?disease = <${MONDO_DIABETES_IRI}>)
}`;
// Human + any disease: list a few disease IRIs that appear
const PROBE_HUMAN_DISEASES = `${PREFIXES}
SELECT DISTINCT ?disease WHERE {
  ?study a biolink:Study .
  ?study biolink:in_taxon ?taxon .
  FILTER(?taxon IN ("9606"))
  ?study biolink:studies ?disease .
} LIMIT 20`;

// Organism contrast subquery with LIMIT 500 (agreement query pattern)
const AGREEMENT_QUERY = `PREFIX biolink:      <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>

SELECT ?geneSymbol ?direction (COUNT(DISTINCT ?experimentId) AS ?experimentCount)
  (GROUP_CONCAT(DISTINCT ?experimentId; separator=" | ") AS ?sampleExperimentIds)
  (GROUP_CONCAT(DISTINCT ?contrastLabel; separator=" | ") AS ?sampleContrastLabels)
WHERE {
  {
    SELECT ?contrast WHERE {
      ?contrast a biolink:Assay .
      FILTER(REGEX(STR(?contrast), "E-[A-Z0-9-]+-g[0-9]+_g[0-9]+"))
      BIND(REPLACE(STR(?contrast), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentId)
      BIND(IRI(CONCAT("https://spoke.ucsf.edu/genelab/", ?experimentId)) AS ?study)
      ?study biolink:in_taxon ?taxon .
      FILTER(?taxon IN ("9606"))
    }
    LIMIT 500
  }
  ?assoc a biolink:GeneExpressionMixin ;
         biolink:object ?gene ;
         biolink:subject ?contrast ;
         spokegenelab:log2fc ?log2fc .
  OPTIONAL { ?gene biolink:symbol ?geneSymbol . }
  OPTIONAL { ?contrast biolink:name ?contrastLabel . }
  FILTER(?log2fc > 0)
  BIND(REPLACE(STR(?contrast), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentId)
  BIND(IF(?log2fc > 0, "up", "down") AS ?direction)
}
GROUP BY ?gene ?geneSymbol ?direction
HAVING (COUNT(DISTINCT ?experimentId) >= 2)
ORDER BY DESC(?experimentCount) ?geneSymbol
LIMIT 30`;

async function runQuery(query, label, timeoutMs = 120000) {
  const start = Date.now();
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(GXA_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/sparql-query", "Accept": "application/sparql-results+json" },
      body: query,
      signal: controller.signal,
    });
    clearTimeout(t);
    const elapsed = ((Date.now() - start) / 1000).toFixed(1);
    if (!res.ok) {
      const text = await res.text();
      console.log(`[${label}] HTTP ${res.status} (${elapsed}s): ${text.slice(0, 200)}`);
      return;
    }
    const json = await res.json();
    const bindings = json.results?.bindings ?? [];
    console.log(`[${label}] OK in ${elapsed}s, rows: ${bindings.length}`);
    if (bindings.length > 0) console.log(`[${label}] sample:`, JSON.stringify(bindings[0], null, 0).slice(0, 120));
    return bindings.length;
  } catch (e) {
    clearTimeout(t);
    const elapsed = ((Date.now() - start) / 1000).toFixed(1);
    console.log(`[${label}] FAIL after ${elapsed}s:`, e.name, e.message?.slice(0, 80));
    return -1;
  }
}

async function runProbeQuery(query, label, timeoutMs = 30000) {
  const start = Date.now();
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(GXA_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/sparql-query", "Accept": "application/sparql-results+json" },
      body: query,
      signal: controller.signal,
    });
    clearTimeout(t);
    const elapsed = ((Date.now() - start) / 1000).toFixed(1);
    if (!res.ok) {
      console.log(`[${label}] HTTP ${res.status} (${elapsed}s)`);
      return null;
    }
    const json = await res.json();
    const bindings = json.results?.bindings ?? [];
    if (bindings.length > 0 && bindings[0].c) {
      console.log(`[${label}] count: ${bindings[0].c.value} (${elapsed}s)`);
      return parseInt(bindings[0].c.value, 10);
    }
    if (bindings.length > 0) {
      console.log(`[${label}] sample bindings: ${bindings.length} (${elapsed}s)`);
      bindings.slice(0, 3).forEach((b, i) => console.log(`  [${i}]`, b.disease?.value ?? b));
      return bindings.length;
    }
    console.log(`[${label}] 0 rows (${elapsed}s)`);
    return 0;
  } catch (e) {
    clearTimeout(t);
    console.log(`[${label}] FAIL:`, e.message?.slice(0, 80));
    return null;
  }
}

async function main() {
  console.log("GXA endpoint:", GXA_ENDPOINT);
  const n1 = await runQuery(PROBE_QUERY, "probe", 30000);
  if (n1 === undefined) return;

  console.log("\n--- Study→Disease predicate probe ---");
  const spokeCount = await runProbeQuery(PROBE_SPOKE_STUDIES, "spokegenelab:studies");
  const biolinkCount = await runProbeQuery(PROBE_BIOLINK_STUDIES, "biolink:studies");
  if (typeof biolinkCount === "number" && biolinkCount > 0) {
    await runProbeQuery(PROBE_SAMPLE_DISEASES, "sample diseases (biolink:studies)");
  }
  console.log("\n--- Human (9606) + disease probe ---");
  await runProbeQuery(PROBE_HUMAN_MONDO_DIABETES, "human studies with MONDO diabetes");
  await runProbeQuery(PROBE_HUMAN_DISEASES, "human studies disease IRIs (sample)");
  console.log("");

  const n2 = await runQuery(AGREEMENT_QUERY, "agreement (500 contrasts, limit 30)", 180000);
  console.log("Done. Agreement rows:", n2);
}

main();
