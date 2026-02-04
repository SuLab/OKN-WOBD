// Preflight probes for SPARQL queries

import { executeSPARQL } from "./executor";

export interface PreflightResult {
  predicate_check?: {
    exists: boolean;
    count?: number;
  };
  class_check?: {
    exists: boolean;
    count?: number;
  };
  sample_query?: {
    row_count: number;
    latency_ms: number;
  };
  warnings: string[];
}

export async function runPreflight(
  query: string,
  endpoint: string,
  predicates?: string[],
  classes?: string[]
): Promise<PreflightResult> {
  const result: PreflightResult = { warnings: [] };

  // Check predicates if provided
  if (predicates && predicates.length > 0) {
    try {
      const predicateQuery = `
        SELECT ?p (COUNT(*) as ?c) WHERE {
          ?s ?p ?o .
          FILTER(?p IN (${predicates.map(p => `<${p}>`).join(", ")}))
        } GROUP BY ?p LIMIT 50
      `;
      const execResult = await executeSPARQL(predicateQuery, endpoint, { timeout_s: 5 });
      if (execResult.row_count > 0) {
        result.predicate_check = { exists: true, count: execResult.row_count };
      } else {
        result.predicate_check = { exists: false };
        result.warnings.push("None of the expected predicates found in the graph");
      }
    } catch (error: any) {
      result.warnings.push(`Predicate check failed: ${error.message}`);
    }
  }

  // Check classes if provided
  if (classes && classes.length > 0) {
    try {
      const classQuery = `
        ASK WHERE {
          ?s a <${classes[0]}> .
        }
      `;
      const execResult = await executeSPARQL(classQuery, endpoint, { timeout_s: 5 });
      // For ASK queries, we need to parse the boolean result differently
      // This is simplified - in practice, ASK returns a boolean in the bindings
      result.class_check = { exists: execResult.row_count > 0 };
    } catch (error: any) {
      result.warnings.push(`Class check failed: ${error.message}`);
    }
  }

  // Run sample query with LIMIT 5
  try {
    const sampleQuery = query.replace(/LIMIT\s+\d+/i, "LIMIT 5");
    const execResult = await executeSPARQL(sampleQuery, endpoint, { timeout_s: 10 });
    result.sample_query = {
      row_count: execResult.row_count,
      latency_ms: execResult.latency_ms,
    };
    if (execResult.error) {
      result.warnings.push(`Sample query error: ${execResult.error}`);
    }
  } catch (error: any) {
    result.warnings.push(`Sample query failed: ${error.message}`);
  }

  return result;
}






