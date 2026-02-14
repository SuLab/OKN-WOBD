// Generic entity resolver for multi-hop queries
// Routes entity resolution requests to appropriate resolvers based on entity type

import { groundDrugToWikidata, type WikidataSearchResult } from "@/lib/ontology/wikidata-client";
import type { StepResultContext } from "@/types";

export interface EntityResolutionResult {
    entity_iris: string[];
    drug_iris?: string[];
    gene_iris?: string[];
    disease_iris?: string[];
    species_iris?: string[];
    entity_labels?: string[];
    metadata?: {
        entity_type: string;
        entity_name: string;
        target_ontology: string;
        match_score?: number;
        match_type?: string;
    };
}

/**
 * Resolve an entity by name to IRIs in the target ontology
 */
export async function resolveEntity(
    entityType: string,
    entityName: string,
    targetOntology: string
): Promise<EntityResolutionResult> {
    console.log(`[EntityResolver] Resolving ${entityType} "${entityName}" to ${targetOntology}`);

    const result: EntityResolutionResult = {
        entity_iris: [],
    };

    // Route to appropriate resolver based on entity type and target ontology
    if (entityType === "drug" && targetOntology === "Wikidata") {
        const drugResults = await groundDrugToWikidata(entityName);
        if (drugResults.length > 0) {
            const bestMatch = drugResults[0];
            result.entity_iris = [bestMatch.wikidata_iri];
            result.drug_iris = [bestMatch.wikidata_iri];
            result.entity_labels = [bestMatch.label];
            result.metadata = {
                entity_type: entityType,
                entity_name: entityName,
                target_ontology: targetOntology,
                match_score: bestMatch.matchScore,
                match_type: bestMatch.matchType,
            };
            console.log(
                `[EntityResolver] Resolved ${entityType} "${entityName}" to ${bestMatch.wikidata_iri} (${bestMatch.label}, score: ${bestMatch.matchScore})`
            );
        } else {
            console.warn(`[EntityResolver] Could not resolve ${entityType} "${entityName}" to ${targetOntology}`);
        }
    } else if (entityType === "gene" && targetOntology === "Wikidata") {
        // TODO: Implement gene resolution to Wikidata
        console.warn(`[EntityResolver] Gene resolution to Wikidata not yet implemented`);
    } else if (entityType === "disease" && targetOntology === "MONDO") {
        // TODO: Implement disease resolution to MONDO (could use OLS or Ubergraph)
        console.warn(`[EntityResolver] Disease resolution to MONDO not yet implemented`);
    } else {
        console.warn(
            `[EntityResolver] Unsupported entity type/ontology combination: ${entityType} → ${targetOntology}`
        );
    }

    return result;
}

/**
 * Convert entity resolution result to StepResultContext for passing to subsequent steps
 */
export function entityResolutionToContext(
    stepId: string,
    resolutionResult: EntityResolutionResult
): StepResultContext {
    const context: StepResultContext = {
        step_id: stepId,
    };

    // Add type-specific fields
    if (resolutionResult.drug_iris) {
        context.drug_iris = resolutionResult.drug_iris;
    }
    if (resolutionResult.gene_iris) {
        context.gene_iris = resolutionResult.gene_iris;
    }
    if (resolutionResult.disease_iris) {
        context.disease_iris = resolutionResult.disease_iris;
    }
    if (resolutionResult.species_iris) {
        context.species_iris = resolutionResult.species_iris;
    }
    if (resolutionResult.entity_labels) {
        // Store labels for fallback text search if needed
        if (resolutionResult.drug_iris) {
            // For drugs, we might not need labels, but store them anyway
        }
    }

    return context;
}
