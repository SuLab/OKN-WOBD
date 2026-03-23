#!/usr/bin/env node
/** Quick probes against GXA endpoint to see graph shape. */
const ENDPOINT = "https://frink.apps.renci.org/gene-expression-atlas-okn/sparql";

async function run(query, label) {
  const start = Date.now();
  try {
    const res = await fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/sparql-query", "Accept": "application/sparql-results+json" },
      body: query,
      signal: AbortSignal.timeout(15000),
    });
    const elapsed = ((Date.now() - start) / 1000).toFixed(1);
    if (!res.ok) return console.log(`[${label}] ${res.status} ${elapsed}s`);
    const j = await res.json();
    const b = j.results?.bindings ?? [];
    console.log(`[${label}] ${elapsed}s, rows: ${b.length}`);
    if (b.length > 0) console.log(JSON.stringify(b[0], null, 0).slice(0, 200));
    return b;
  } catch (e) {
    console.log(`[${label}] error:`, e.message?.slice(0, 60));
    return [];
  }
}

const QUERIES = [
  [
    "Study (E-GEOD) with in_taxon",
    `PREFIX biolink: <https://w3id.org/biolink/vocab/>
     SELECT ?s ?t WHERE { ?s biolink:in_taxon ?t . FILTER(STRSTARTS(STR(?s), "https://spoke.ucsf.edu/genelab/E-")) } LIMIT 3`,
  ],
  [
    "gene with in_taxon (NCBITaxon)",
    `PREFIX biolink: <https://w3id.org/biolink/vocab/>
     SELECT ?gene ?taxon WHERE { ?gene biolink:in_taxon ?taxon . FILTER(CONTAINS(STR(?taxon), "NCBITaxon")) } LIMIT 2`,
  ],
  [
    "one association subject + object (gene)",
    `PREFIX biolink: <https://w3id.org/biolink/vocab/>
     SELECT ?subj ?obj WHERE { ?a a biolink:GeneExpressionMixin ; biolink:subject ?subj ; biolink:object ?obj . } LIMIT 1`,
  ],
];

async function main() {
  for (const [label, q] of QUERIES) {
    await run(q, label);
  }
}
main();
