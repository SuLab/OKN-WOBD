import type { QueryPlan, QueryStep, ExecutionEvent, StepResultContext, Intent, SPARQLResult } from "@/types";
import type { ContextPack } from "@/lib/context-packs/types";
import { generateSPARQLFromIntent } from "@/lib/templates/generator";
import { resolveEntity, entityResolutionToContext } from "./entity-resolver";

export async function* executeQueryPlan(
    plan: QueryPlan,
    contextPack: ContextPack
): AsyncGenerator<ExecutionEvent> {
    yield { type: "plan_generated", plan };

    const completedSteps = new Map<string, QueryStep>();
    const contexts = new Map<string, StepResultContext>();
    const pendingSteps = new Set(plan.steps.map(s => s.id));

    while (pendingSteps.size > 0) {
        // Find executable steps
        const executable = plan.steps.filter(step =>
            pendingSteps.has(step.id) &&
            step.depends_on.every(depId => completedSteps.has(depId))
        );

        if (executable.length === 0) {
            // Dependency cycle
            for (const step of plan.steps.filter(s => pendingSteps.has(s.id))) {
                step.status = "failed";
                step.error = "Dependency cycle or missing dependency";
                yield { type: "step_failed", step, error: step.error };
            }
            break;
        }

        // Execute steps sequentially (to allow yielding)
        for (const step of executable) {
            try {
                step.status = "running";
                yield { type: "step_started", step };

                console.log(`[Executor] Processing step ${step.id} with task: "${step.intent.task}"`);

                // Inject results from previous steps
                const updatedIntent = injectResultsIntoSlots(step, contexts);

                // For multi-hop queries, mark as ontology workflow so templates handle it correctly
                if (step.uses_results_from) {
                    updatedIntent.ontology_workflow = true;

                    // Create minimal ontology_state for template compatibility
                    if (!updatedIntent.slots.ontology_state) {
                        updatedIntent.slots.ontology_state = {
                            entity_type: "disease", // Default to disease for drug→disease→dataset flow
                            grounded_mondo_terms: [], // Empty since we already have IRIs
                        };
                    }
                }

                step.intent = updatedIntent;

                // Handle entity_resolution steps separately (before SPARQL generation)
                console.log(`[Executor] Checking step ${step.id} task: "${step.intent.task}"`);
                if (step.intent.task === "entity_resolution") {
                    console.log(`[Executor] Detected entity_resolution step: ${step.id}`);
                    const entityType = step.intent.slots.entity_type as string;
                    const entityName = step.intent.slots.entity_name as string;
                    const targetOntology = step.intent.slots.target_ontology as string;

                    if (!entityType || !entityName || !targetOntology) {
                        throw new Error(
                            `Entity resolution step ${step.id} missing required slots: entity_type, entity_name, target_ontology`
                        );
                    }

                    console.log(
                        `[Executor] Executing entity resolution for ${entityType} "${entityName}" → ${targetOntology}`
                    );

                    const resolutionResult = await resolveEntity(entityType, entityName, targetOntology);
                    console.log(`[Executor] Entity resolution result:`, JSON.stringify(resolutionResult, null, 2));

                    // Check if resolution was successful
                    if (!resolutionResult.entity_iris || resolutionResult.entity_iris.length === 0) {
                        throw new Error(
                            `Failed to resolve ${entityType} "${entityName}" to ${targetOntology}. No matching entities found.`
                        );
                    }

                    // Convert resolution result to step results format
                    step.results = {
                        head: { vars: ["entity_iri", "entity_label"] },
                        results: {
                            bindings: resolutionResult.entity_iris.map(iri => ({
                                entity_iri: { type: "uri", value: iri },
                                entity_label: {
                                    type: "literal",
                                    value: resolutionResult.entity_labels?.[0] || entityName,
                                },
                            })),
                        },
                    };

                    step.sparql = `# Entity Resolution: ${entityType} "${entityName}" → ${targetOntology}\n# Resolved to: ${resolutionResult.entity_iris.join(", ")}`;
                    step.latency_ms = 0; // Entity resolution is fast, no need to track latency separately

                    // Extract context from resolution result
                    const context = entityResolutionToContext(step.id, resolutionResult);
                    console.log(`[Executor] Entity resolution context:`, JSON.stringify(context, null, 2));
                    contexts.set(step.id, context);
                    completedSteps.set(step.id, step);
                    pendingSteps.delete(step.id);
                    step.status = "complete";

                    yield { type: "step_completed", step, context };
                    continue; // Skip to next step - don't execute SPARQL
                }

                // Also replace templates in raw SPARQL if present
                if (step.sparql && step.uses_results_from) {
                    step.sparql = replaceSPARQLTemplates(step.sparql, contexts);
                    console.log(`[Executor] Replaced templates in raw SPARQL for ${step.id}`);
                }

                // Execute step
                const result = await executeStep(step, contextPack);

                step.results = result.sparql_results;
                step.sparql = result.sparql;
                step.latency_ms = result.latency_ms;
                step.status = "complete";

                // Extract context
                const context = extractResultContext(step);
                console.log(`[Executor] Extracted context from ${step.id}:`, JSON.stringify(context, null, 2));
                contexts.set(step.id, context);
                completedSteps.set(step.id, step);
                pendingSteps.delete(step.id);

                yield { type: "step_completed", step, context };

                // Check if a drug→disease query step returned no diseases - terminate gracefully
                // This applies to any step that queries Wikidata for diseases and has drug_iris in context
                if (step.intent.task === "raw_sparql" &&
                    step.target_graphs.includes("wikidata") &&
                    contexts.has(step.uses_results_from || "")) {
                    const prevContext = contexts.get(step.uses_results_from || "");
                    const hasDrugIRIs = prevContext?.drug_iris && prevContext.drug_iris.length > 0;
                    const hasDiseaseIRIs = context.disease_iris &&
                        Array.isArray(context.disease_iris) &&
                        context.disease_iris.length > 0;

                    // If this was a drug→disease query but found no diseases, terminate
                    if (hasDrugIRIs && !hasDiseaseIRIs) {
                        // No diseases found - mark remaining dependent steps as failed and terminate
                        const dependentSteps = plan.steps.filter(s =>
                            s.depends_on.includes(step.id) && pendingSteps.has(s.id)
                        );

                        for (const depStep of dependentSteps) {
                            depStep.status = "failed";
                            depStep.error = "Cannot proceed: No diseases were found for this drug in Wikidata. The query cannot continue to search for datasets.";
                            yield { type: "step_failed", step: depStep, error: depStep.error };
                            pendingSteps.delete(depStep.id);
                        }

                        // Break out of execution loop
                        break;
                    }
                }
            } catch (error: any) {
                step.status = "failed";
                step.error = error.message;
                pendingSteps.delete(step.id);
                yield { type: "step_failed", step, error: error.message };
            }
        }
    }

    yield {
        type: "plan_completed",
        results: Array.from(completedSteps.values())
    };
}

function extractResultContext(step: QueryStep): StepResultContext {
    const context: StepResultContext = { step_id: step.id };

    if (!step.results?.results?.bindings) {
        console.warn(`[Executor] No bindings in results for ${step.id}`);
        return context;
    }

    const bindings = step.results.results.bindings;
    console.log(`[Executor] Extracting context from ${step.id} with ${bindings.length} bindings`);
    console.log(`[Executor] First binding sample:`, JSON.stringify(bindings[0], null, 2));

    // Extract entities
    if (step.intent.task === "entity_lookup") {
        context.entities_resolved = {};
        bindings.forEach(b => {
            const label = b.label?.value;
            const iri = b.entity?.value || b.subject?.value;
            if (label && iri) context.entities_resolved![label] = iri;
        });
    }

    // Extract disease IRIs (prefer mondoIRI if available, otherwise use disease)
    if (bindings.some(b => b.mondoIRI || b.mondo_id || b.disease)) {
        console.log(`[Executor] Sample binding for disease extraction:`, JSON.stringify(bindings[0], null, 2));

        const diseaseIRIs = bindings.map(b => {
            // Prefer MONDO IRI if it exists (wdtn:P5270 - normalized URI)
            if (b.mondoIRI?.value) {
                console.log(`[Executor] Found MONDO IRI (normalized): ${b.mondoIRI.value}`);
                return b.mondoIRI.value;
            }
            // Try to construct MONDO IRI from literal ID (wdt:P5270)
            if (b.mondo_id?.value) {
                const mondoId = b.mondo_id.value.toString().trim();
                // Convert "0005015" or "MONDO:0005015" to full IRI
                const numericId = mondoId.replace(/^MONDO:/, '');
                const mondoIRI = `http://purl.obolibrary.org/obo/MONDO_${numericId}`;
                console.log(`[Executor] Constructed MONDO IRI from literal: ${mondoIRI}`);
                return mondoIRI;
            }
            // Fallback to disease IRI (Wikidata IRI)
            if (b.disease?.value) {
                console.log(`[Executor] Using disease IRI (Wikidata): ${b.disease.value}`);
                return b.disease.value;
            }
            return null;
        }).filter(Boolean) as string[];

        context.disease_iris = [...new Set(diseaseIRIs)];
        console.log(`[Executor] Extracted ${context.disease_iris.length} disease IRIs from ${step.id}`);
        console.log(`[Executor] First 3 disease IRIs:`, context.disease_iris.slice(0, 3));

        // Also extract disease labels for fallback text search
        const diseaseLabels = bindings.map(b => b.diseaseLabel?.value || b.mondoLabel?.value).filter(Boolean) as string[];
        if (diseaseLabels.length > 0) {
            context.disease_labels = [...new Set(diseaseLabels)];
            console.log(`[Executor] Extracted ${context.disease_labels.length} disease labels from ${step.id}`);
        }
    }

    // Extract gene IRIs
    if (bindings.some(b => b.gene)) {
        context.gene_iris = [...new Set(bindings.map(b => b.gene?.value).filter(Boolean) as string[])];
    }

    // Extract species IRIs
    if (bindings.some(b => b.species)) {
        context.species_iris = [...new Set(bindings.map(b => b.species?.value).filter(Boolean) as string[])];
    }

    // Extract drug IRIs
    if (bindings.some(b => b.drug)) {
        context.drug_iris = [...new Set(bindings.map(b => b.drug?.value).filter(Boolean) as string[])];
    }

    // Extract dataset IDs
    if (step.intent.task === "dataset_search") {
        context.dataset_ids = [...new Set(bindings.map(b => b.dataset?.value).filter(Boolean) as string[])];
    }

    return context;
}

function injectResultsIntoSlots(
    step: QueryStep,
    previousContexts: Map<string, StepResultContext>
): Intent {
    if (!step.uses_results_from) return step.intent;

    const prevContext = previousContexts.get(step.uses_results_from);
    if (!prevContext) {
        console.warn(`[Executor] No context found for ${step.uses_results_from}`);
        return step.intent;
    }

    console.log(`[Executor] Injecting results from ${step.uses_results_from}:`, JSON.stringify(prevContext, null, 2));

    const updatedSlots = JSON.parse(JSON.stringify(step.intent.slots));

    // FALLBACK: If step1 returned no MONDO IRIs but we have disease labels,
    // use disease labels as keywords for text search
    if (step.id === "step2" && step.intent.task === "dataset_search") {
        const step1Context = previousContexts.get("step1");

        if (step1Context) {
            // Check if we have MONDO IRIs
            const hasMondoIRIs = step1Context.disease_iris?.some(iri =>
                iri.startsWith("http://purl.obolibrary.org/obo/MONDO_")
            );

            // If no MONDO IRIs but we have disease labels, fall back to text search
            if (!hasMondoIRIs && step1Context.disease_labels && step1Context.disease_labels.length > 0) {
                console.warn(`[Executor] No MONDO mappings found in step1. Falling back to text search with disease labels`);
                updatedSlots.keywords = step1Context.disease_labels.join(" ");
                delete updatedSlots.health_conditions; // Remove empty health_conditions
                console.log(`[Executor] Fallback keywords:`, updatedSlots.keywords);
            }
        }
    }

    // Replace templates like {{step1.disease_iris}}
    replaceTemplatesRecursive(updatedSlots, previousContexts);

    console.log(`[Executor] Updated slots for ${step.id}:`, JSON.stringify(updatedSlots, null, 2));

    return { ...step.intent, slots: updatedSlots };
}

function replaceTemplatesRecursive(obj: any, contexts: Map<string, StepResultContext>) {
    for (const key in obj) {
        if (typeof obj[key] === 'string') {
            // Check if it's a template string
            const templateMatch = obj[key].match(/\{\{(\w+)\.(\w+)\}\}/);

            if (templateMatch) {
                const [, stepId, field] = templateMatch;
                const ctx = contexts.get(stepId);

                if (!ctx) {
                    // No context found - for array fields, convert to empty array
                    if (field.endsWith('_iris') || field.endsWith('_ids')) {
                        obj[key] = [];
                    } else {
                        // Keep template string for non-array fields (shouldn't happen normally)
                        // Leave as-is
                    }
                    continue;
                }

                const fieldValue = (ctx as any)[field];
                if (!fieldValue || (Array.isArray(fieldValue) && fieldValue.length === 0)) {
                    // Field value is empty - for array fields, convert to empty array
                    if (field.endsWith('_iris') || field.endsWith('_ids')) {
                        obj[key] = [];
                    } else {
                        // For non-array fields, use empty string or keep template
                        obj[key] = "";
                    }
                    continue;
                }

                // Replace the template with the actual value
                obj[key] = obj[key].replace(/\{\{(\w+)\.(\w+)\}\}/g, (match: string, sId: string, f: string) => {
                    if (sId === stepId && f === field) {
                        if (Array.isArray(fieldValue)) {
                            return JSON.stringify(fieldValue);
                        }
                        return String(fieldValue);
                    }
                    return match;
                });

                // Try to parse back to array if it was stringified
                try {
                    const parsed = JSON.parse(obj[key]);
                    if (Array.isArray(parsed)) obj[key] = parsed;
                } catch {
                    // Not JSON, keep as string
                }
            }
        } else if (typeof obj[key] === 'object' && obj[key] !== null) {
            replaceTemplatesRecursive(obj[key], contexts);
        }
    }
}

/**
 * Replace templates in raw SPARQL queries with proper SPARQL formatting
 * Arrays of IRIs are formatted as space-separated URIs: <iri1> <iri2> ...
 */
function replaceSPARQLTemplates(sparql: string, contexts: Map<string, StepResultContext>): string {
    return sparql.replace(/\{\{(\w+)\.(\w+)\}\}/g, (match: string, stepId: string, field: string) => {
        const ctx = contexts.get(stepId);
        if (!ctx) {
            console.warn(`[Executor] No context found for ${stepId} when replacing ${match}`);
            return match;
        }

        const fieldValue = (ctx as any)[field];
        if (!fieldValue) {
            console.warn(`[Executor] No field ${field} in context for ${stepId}`);
            return match;
        }

        // Format arrays as space-separated URIs for SPARQL VALUES clause
        if (Array.isArray(fieldValue)) {
            const formatted = fieldValue.map(iri => `<${iri}>`).join(' ');
            console.log(`[Executor] Formatted ${match} as: ${formatted}`);
            return formatted;
        }

        return String(fieldValue);
    });
}

async function executeStep(
    step: QueryStep,
    contextPack: ContextPack
): Promise<{ sparql_results: SPARQLResult; sparql: string; latency_ms: number }> {
    const startTime = Date.now();

    console.log(`[Executor] Executing step ${step.id}:`, JSON.stringify(step.intent, null, 2));

    // Use raw SPARQL if provided, otherwise generate from intent
    let sparql: string;
    if (step.sparql) {
        console.log(`[Executor] Using provided SPARQL for ${step.id}`);
        console.log(`[Executor] Raw SPARQL length: ${step.sparql.length} chars`);
        console.log(`[Executor] Raw SPARQL content:`, step.sparql);
        sparql = step.sparql;
    } else {
        // Generate SPARQL from intent
        console.log(`[Executor] Generating SPARQL for ${step.id} with intent:`, JSON.stringify(step.intent, null, 2));
        try {
            const result = await generateSPARQLFromIntent(step.intent, contextPack);
            console.log(`[Executor] Template generation result:`, result);
            console.log(`[Executor] result.ok:`, result.ok);
            console.log(`[Executor] result.query:`, result.query ? `${result.query.substring(0, 100)}...` : 'UNDEFINED');
            console.log(`[Executor] result.error:`, result.error);
            if (!result.query) {
                console.error(`[Executor] Template generation returned no query for ${step.id}`);
                throw new Error(`Failed to generate SPARQL for step ${step.id}: No query in result`);
            }
            sparql = result.query;
        } catch (error: any) {
            console.error(`[Executor] Error generating SPARQL for ${step.id}:`, error);
            throw new Error(`Failed to generate SPARQL for step ${step.id}: ${error.message}`);
        }
    }

    console.log(`[Executor] Generated SPARQL for ${step.id}:`, sparql.substring(0, 200));

    // Execute SPARQL
    const response = await fetch("/api/tools/sparql/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            query: sparql,
            pack_id: contextPack.id,
            mode: step.intent.graph_mode,
            graphs: step.target_graphs,
            attempt_repair: true,
            run_preflight: false,
        }),
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || "SPARQL execution failed");
    }

    const result = await response.json();
    const latency_ms = Date.now() - startTime;

    const sparql_results: SPARQLResult = {
        head: result.head,
        results: {
            bindings: result.bindings || [],
        },
    };

    return { sparql_results, sparql, latency_ms };
}
