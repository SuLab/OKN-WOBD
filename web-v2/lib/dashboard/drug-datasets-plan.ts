import type { QueryPlan, QueryStep } from "@/types";

/** Fixed SPARQL for step 2: Wikidata drug → diseases with MONDO IDs (wdt:P2175, wdt:P5270, wdtn:P5270). */
const WIKIDATA_DRUG_TO_DISEASES = `
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wdtn: <http://www.wikidata.org/prop/direct-normalized/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?disease ?diseaseLabel ?mondo_id ?mondoIRI
FROM <https://purl.org/okn/frink/kg/wikidata>
WHERE {
  VALUES ?drug { {{step1.drug_iris}} }
  ?drug wdt:P2175 ?disease .
  ?disease rdfs:label ?diseaseLabel .
  FILTER(LANG(?diseaseLabel) = "en")
  OPTIONAL { ?disease wdt:P5270 ?mondo_id . }
  OPTIONAL { ?disease wdtn:P5270 ?mondoIRI . }
}
LIMIT 50
`.trim();

const MAX_DATASET_RESULTS_CAP = 500;

/**
 * Build a fixed 3-step plan: entity resolution (drug name(s) → Wikidata IRIs) →
 * Wikidata (diseases treated by drug + MONDO) → NDE (datasets for those diseases).
 * No LLM; used by the dashboard drug_datasets template.
 * @param drugNames - Drug name(s) to look up
 * @param options - Optional maxResults (capped at MAX_DATASET_RESULTS_CAP), geoOnly (step 3 uses geo_dataset_search)
 */
export function buildDrugDatasetsPlan(
  drugNames: string[],
  options?: { maxResults?: number; geoOnly?: boolean }
): QueryPlan {
  const planId = `drug-datasets-${Date.now()}`;
  const names = drugNames.map((n) => n.trim()).filter(Boolean);
  const maxResults =
    options?.maxResults != null && options.maxResults > 0
      ? Math.min(options.maxResults, MAX_DATASET_RESULTS_CAP)
      : undefined;
  const geoOnly = options?.geoOnly === true;
  const step1Description =
    names.length === 1
      ? `Resolve drug "${names[0]}" to Wikidata IRI`
      : `Resolve ${names.length} drugs to Wikidata IRIs`;
  const steps: QueryStep[] = [
    {
      id: "step1",
      description: step1Description,
      intent: {
        lane: "template",
        task: "entity_resolution",
        context_pack: "wobd",
        graph_mode: "federated",
        graphs: ["wikidata"],
        slots: {
          entity_type: "drug",
          entity_name: names[0] ?? "",
          entity_names: names,
          target_ontology: "Wikidata",
        },
        confidence: 1,
        notes: "Dashboard drug_datasets step 1",
      },
      target_graphs: ["wikidata"],
      depends_on: [],
      status: "pending",
    },
    {
      id: "step2",
      description: "Find diseases treated by drug in Wikidata with MONDO IDs",
      intent: {
        lane: "template",
        task: "raw_sparql",
        context_pack: "wobd",
        graph_mode: "federated",
        graphs: ["wikidata"],
        slots: {},
        confidence: 1,
        notes: "Dashboard drug_datasets step 2",
      },
      target_graphs: ["wikidata"],
      depends_on: ["step1"],
      uses_results_from: "step1",
      sparql: WIKIDATA_DRUG_TO_DISEASES,
      status: "pending",
    },
    {
      id: "step3",
      description: geoOnly ? "Query NDE GEO datasets for diseases from step 2" : "Query NDE datasets for diseases from step 2",
      intent: {
        lane: "template",
        task: geoOnly ? "geo_dataset_search" : "dataset_search",
        context_pack: "wobd",
        graph_mode: "federated",
        graphs: ["nde"],
        slots: {
          health_conditions: "{{step2.disease_iris}}",
          ...(maxResults != null ? { limit: maxResults } : {}),
        },
        confidence: 1,
        notes: "Dashboard drug_datasets step 3",
        ontology_workflow: true,
      },
      target_graphs: ["nde"],
      depends_on: ["step2"],
      uses_results_from: "step2",
      status: "pending",
    },
  ];

  return {
    id: planId,
    steps,
    original_query: `Find datasets about diseases treated by ${names.join(", ")}`,
    created_at: Date.now(),
    graph_routing_rationale: "Fixed drug→disease→datasets pipeline (dashboard)",
  };
}
