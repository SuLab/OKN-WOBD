import { NextResponse } from "next/server";
import { loadContextPack } from "@/lib/context-packs/loader";
import type { Intent } from "@/types";
import {
  parseOverridesFromText,
  buildInitialIntent,
  makeRoutingDecision,
} from "@/lib/intent/router";
import { fillSlots } from "@/lib/intent/slot-filler";
import { classifyIntentDeterministic } from "@/lib/intent/classifier";
import { fillSlotsWithLLM } from "@/lib/intent/slot-filler-llm";
import {
  detectOntologyIntent,
  processOntologyQuery,
} from "@/lib/ontology/preprocessor";

// Phase 3: Intent routing for lanes A/B/C (currently deterministic, no LLM)
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { text, pack_id, overrides } = body;

    if (!text || typeof text !== "string") {
      return NextResponse.json(
        { error: "Missing or invalid 'text' parameter" },
        { status: 400 }
      );
    }

    const explicitPack = pack_id ? loadContextPack(pack_id) : null;
    if (pack_id && !explicitPack) {
      return NextResponse.json(
        { error: `Context pack not found: ${pack_id}` },
        { status: 404 }
      );
    }

    // Parse overrides from the text itself (e.g., /open, /sparql, @wobd)
    const derivedOverrides = parseOverridesFromText(text);
    const effectivePackId = derivedOverrides.context_pack || pack_id || "wobd";
    const pack = loadContextPack(effectivePackId);

    if (!pack) {
      return NextResponse.json(
        { error: `Context pack not found: ${effectivePackId}` },
        { status: 404 }
      );
    }

    // Merge explicit overrides (body.overrides) with derived ones from text
    const mergedOverrides = {
      ...derivedOverrides,
      ...(overrides || {}),
    };

    // 1) Build base intent using heuristic router
    let intent: Intent = buildInitialIntent(text, pack, mergedOverrides);

    // 2) Deterministic classifier refines task + confidence
    const classified = classifyIntentDeterministic(text, pack, intent);
    intent = classified.intent;

    // 2.5) For GXA tasks, use gene-expression-atlas-okn graph only (direct endpoint)
    const gxaTasks = [
      "gene_expression_dataset_search",
      "gene_expression_genes_in_experiment",
      "gene_expression_experiments_for_gene",
      "gene_expression_gene_cross_dataset_summary",
      "gene_expression_genes_agreement",
      "gene_expression_genes_discordance",
    ];
    if (gxaTasks.includes(intent.task)) {
      intent.graphs = ["gene-expression-atlas-okn"];
      intent.notes = `${intent.notes || ""} | GXA query, using graph: gene-expression-atlas-okn`.trim();
    }

    // 3) Slot-filler populates slots (keywords, q, limit, etc.) heuristically
    intent = fillSlots(intent, text);

    // 4) Optional LLM-assisted slot filling for template lane, if allowed
    if (intent.lane === "template" && pack.guardrails.allow_open_nl2sparql) {
      const llmUrl = new URL(
        "/api/tools/llm/complete",
        request.url
      ).toString();

      const llmResult = await fillSlotsWithLLM(text, intent, llmUrl);
      if (llmResult.used_llm) {
        intent = llmResult.intent;
      } else if (llmResult.error) {
        intent.notes = `${intent.notes || ""} | LLM slot filling skipped: ${llmResult.error
          }`.trim();
      }
    }

    // 4.5) Check for ontology-grounded workflow
    // Only run for dataset_search tasks
    if (intent.task === "dataset_search" && detectOntologyIntent(text, intent)) {
      try {
        const llmUrl = new URL(
          "/api/tools/llm/complete",
          request.url
        ).toString();
        const ontologyState = await processOntologyQuery(text, intent, pack, llmUrl);
        // Store ontology state in intent slots
        intent.slots.ontology_state = ontologyState;
        intent.ontology_workflow = true;

        // Handle different entity types: diseases use health_conditions, species use species slot
        if (ontologyState.grounded_mondo_terms.length > 0) {
          const entityType = ontologyState.entity_type || "disease";

          // Collect all high-confidence matches (score >= 2) from all grounded entities
          // When we have multiple entity types (disease, species, drug), we want to include ALL of them
          // even if they have different scores, so we can populate multiple slots
          const identifiedEntities = ontologyState.debug_info?.identified_entities || [];
          const hasMultipleEntityTypes = new Set(identifiedEntities.map((e: any) => e.domain.toLowerCase())).size > 1;

          let selectedTerms: typeof ontologyState.grounded_mondo_terms = [];

          if (hasMultipleEntityTypes) {
            // When we have multiple entity types, include ALL terms with score >= 1
            // This ensures we get disease, species, and drug terms all together
            selectedTerms = ontologyState.grounded_mondo_terms
              .filter(term => (term.matchScore || 0) >= 1)
              .slice(0, 10); // Allow more terms when we have multiple types
            console.log(`[Intent] Multiple entity types detected, using ${selectedTerms.length} terms across all types`);
          } else {
            // Single entity type - use the original high-confidence logic
            const score4Terms = ontologyState.grounded_mondo_terms
              .filter(term => (term.matchScore || 0) === 4 && term.matchType === "label");
            const score3Terms = ontologyState.grounded_mondo_terms
              .filter(term => (term.matchScore || 0) === 3);
            const score2Terms = ontologyState.grounded_mondo_terms
              .filter(term => (term.matchScore || 0) === 2);

            if (score4Terms.length > 0) {
              selectedTerms = score4Terms.slice(0, 5);
            } else if (score3Terms.length > 0) {
              selectedTerms = score3Terms.slice(0, 5);
            } else if (score2Terms.length > 0) {
              selectedTerms = score2Terms.slice(0, 5);
            } else {
              selectedTerms = [ontologyState.grounded_mondo_terms[0]];
            }
          }

          // Group terms by their entity type (from identified_entities)
          // This allows us to populate multiple slots when we have entities of different types
          const diseaseTerms: typeof selectedTerms = [];
          const speciesTerms: typeof selectedTerms = [];
          const drugTerms: typeof selectedTerms = [];

          for (const term of selectedTerms) {
            // Determine the ontology type from the IRI pattern (more reliable than label matching)
            const iri = term.mondo || "";

            if (iri.includes("/MONDO_") || iri.includes("purl.obolibrary.org/obo/MONDO")) {
              // MONDO IRI -> disease
              diseaseTerms.push(term);
            } else if (iri.includes("/taxonomy/") || iri.includes("uniprot.org/taxonomy")) {
              // UniProt taxonomy IRI -> species
              speciesTerms.push(term);
            } else if (iri.includes("wikidata.org/entity/")) {
              // Wikidata IRI -> drug
              drugTerms.push(term);
            } else {
              // Fallback: try to match by label with identified entities
              const matchingEntity = identifiedEntities.find((e: any) =>
                e.term.toLowerCase() === term.label?.toLowerCase() ||
                term.label?.toLowerCase().includes(e.term.toLowerCase()) ||
                e.term.toLowerCase().includes(term.label?.toLowerCase())
              );

              const domain = matchingEntity?.domain?.toLowerCase() || entityType;

              if (domain === "species" || domain === "organism") {
                speciesTerms.push(term);
              } else if (domain === "drug" || domain === "medication") {
                drugTerms.push(term);
              } else {
                diseaseTerms.push(term);
              }
            }
          }

          // Set slots for each entity type found
          if (diseaseTerms.length > 0) {
            intent.slots.health_conditions = diseaseTerms.map(t => t.mondo);
            console.log(`[Intent] Using ${diseaseTerms.length} disease terms (MONDO):`,
              diseaseTerms.map(t => `${t.obo_id || t.mondo} (${t.label}, score: ${t.matchScore})`).join(", "));
          }

          if (speciesTerms.length > 0) {
            intent.slots.species = speciesTerms.map(t => t.mondo);
            console.log(`[Intent] Using ${speciesTerms.length} species terms (UniProt):`,
              speciesTerms.map(t => `${t.obo_id || t.mondo} (${t.label}, score: ${t.matchScore})`).join(", "));
          }

          if (drugTerms.length > 0) {
            intent.slots.drugs = drugTerms.map(t => t.mondo);
            console.log(`[Intent] Using ${drugTerms.length} drug terms (Wikidata):`,
              drugTerms.map(t => `${t.obo_id || t.mondo} (${t.label}, score: ${t.matchScore})`).join(", "));
          }

          intent.slots.nde_encoding = ontologyState.nde_encoding || "iri";
        } else {
          // Mark fallback if no grounded terms found
          const entityType = ontologyState.entity_type || "disease";
          intent.notes = `${intent.notes || ""} | Ontology workflow: no ${entityType} terms found, will use fallback`.trim();
        }

        // Check for gene expression queries and add appropriate graphs
        const hasGene = ontologyState.entity_type === "gene" ||
          ontologyState.debug_info?.identified_entities?.some((e: any) => e.domain === "gene");
        const hasGeneExpression = ontologyState.debug_info?.has_gene_expression ||
          ontologyState.debug_info?.identified_entities?.some((e: any) => e.domain === "gene_expression");

        if (hasGene || hasGeneExpression) {
          // Add gene expression graphs to the intent
          const geneGraphs = ontologyState.debug_info?.recommended_graphs || [
            "spoke-genelab",
            "spoke-okn",
            "gene-expression-atlas-okn"
          ];

          // Merge with existing graphs (avoid duplicates)
          const existingGraphs = intent.graphs || [];
          intent.graphs = [...new Set([...existingGraphs, ...geneGraphs])];

          intent.notes = `${intent.notes || ""} | Gene expression query detected, using gene expression graphs: ${geneGraphs.join(", ")}`.trim();
          console.log(`[Intent] Gene expression query detected, added graphs: ${geneGraphs.join(", ")}`);
        }

        intent.notes = `${intent.notes || ""} | Ontology-grounded workflow used`.trim();
      } catch (error: any) {
        // If ontology processing fails, continue with normal flow
        console.error("Ontology workflow error:", error);
        intent.notes = `${intent.notes || ""} | Ontology workflow failed: ${error.message
          }`.trim();
        // Still mark as attempted so UI can show the error
        intent.ontology_workflow = true;
        intent.slots.ontology_state = {
          entity_type: "disease",
          raw_phrase: text,
          candidate_labels: [],
          grounded_mondo_terms: [],
          synonyms: [],
          fallback_used: true,
          stage_errors: {
            workflow: error.message,
          },
        };
      }
    }

    // 5) Routing decision (template vs open) based on confidence/threshold
    const decision = makeRoutingDecision(intent, pack);
    intent.lane = decision.lane;
    intent.graph_mode = decision.graph_mode;
    intent.graphs = decision.graphs;
    intent.notes = `${intent.notes || ""} | ${decision.notes}`.trim();

    return NextResponse.json(intent);
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || "Intent classification failed" },
      { status: 500 }
    );
  }
}

