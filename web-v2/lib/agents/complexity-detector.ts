import type { Intent } from "@/types";

export function needsMultiHop(query: string, intent?: Intent): boolean {
    const lower = query.toLowerCase();

    // Check if a drug entity was identified in the intent
    // Drug queries asking for datasets/data ALWAYS need multi-hop (drug → diseases → datasets)
    if (intent?.slots?.drugs && Array.isArray(intent.slots.drugs) && intent.slots.drugs.length > 0) {
        // If the query is about datasets/data and we have a drug entity, use multi-hop
        if (lower.match(/\b(dataset|data|study|experiment)s?\b/)) {
            return true;
        }
    }

    // Drug-related queries ALWAYS need multi-hop
    // Because NDE datasets are annotated by disease, not drug
    // Must query: Drug → Diseases → Datasets
    if (lower.match(/\b(drug|treatment|therapy|medication|compound)\b/)) {
        return true;
    }

    // Specific drug names (common medications) - also trigger multi-hop
    // Add more drug names as needed
    if (lower.match(/\b(aspirin|ibuprofen|metformin|insulin|penicillin|acetaminophen|tocilizumab|remdesivir|paxlovid)\b/i)) {
        return true;
    }

    // Queries asking for data/datasets "related to" or "about" a specific term
    // where the term ends with "-mab" (monoclonal antibodies) or "-nib" (kinase inhibitors)
    // These are drug naming conventions
    if (lower.match(/\b(dataset|data|study|experiment)s?\s+(about|on|for|related to)\s+\w*(mab|nib|vir|zumab)\b/i)) {
        return true;
    }

    // Gene queries often need gene→disease→datasets (but not yet implemented)
    // For now, disable this to let them go through the normal ontology workflow
    // if (lower.match(/\b(gene|brca|mutation|protein)\b/)) {
    //     return true;
    // }

    // Complex entity combinations (but not for simple "disease vaccines" queries)
    // Vaccine queries should go through normal ontology workflow
    if (!lower.match(/\bvaccine/)) {
        if ((lower.match(/\band\b/g) || []).length >= 2) {
            return true;
        }
    }

    // Explicit relationship queries (but not simple "datasets related to X" queries)
    // "datasets related to X" should use normal ontology workflow for non-drug entities
    if (!lower.match(/\b(dataset|data|study|experiment)s?\s+(about|on|for|related to)\b/)) {
        if (lower.match(/\b(treat|cause|associate|relate|link)\w*\s+(with|to)\b/)) {
            return true;
        }
    }

    return false;
}
