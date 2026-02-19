// SPARQL execution against FRINK federation endpoint

import type { SPARQLResult } from "@/types";

const FRINK_FEDERATION_URL = process.env.NEXT_PUBLIC_FRINK_FEDERATION_URL ||
  "https://frink.apps.renci.org/federation/sparql";

export interface ExecutionOptions {
  timeout_s?: number;
  max_rows?: number;
}

export interface ExecutionResult {
  result: SPARQLResult;
  latency_ms: number;
  row_count: number;
  error?: string;
}

export async function executeSPARQL(
  query: string,
  endpoint: string = FRINK_FEDERATION_URL,
  options: ExecutionOptions = {}
): Promise<ExecutionResult> {
  const startTime = Date.now();
  const timeout = options.timeout_s ? options.timeout_s * 1000 : 25000;

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/sparql-query",
        "Accept": "application/sparql-results+json",
      },
      body: query,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`SPARQL endpoint error: ${response.status} ${response.statusText}\n${errorText}`);
    }

    const result: SPARQLResult = await response.json();
    const latency_ms = Date.now() - startTime;
    const row_count = result.results?.bindings?.length || 0;

    return {
      result,
      latency_ms,
      row_count,
    };
  } catch (error: any) {
    const latency_ms = Date.now() - startTime;
    const isAbort = error?.name === "AbortError" || /aborted|abort/i.test(String(error?.message ?? ""));
    const errorMessage = isAbort
      ? "Query timed out. The endpoint took too long to respond; try again or simplify the query."
      : (error?.message || "Unknown error executing SPARQL query");
    return {
      result: { head: { vars: [] }, results: { bindings: [] } },
      latency_ms,
      row_count: 0,
      error: errorMessage,
    };
  }
}

export function injectFromClauses(query: string, graphShortnames: string[]): string {
  if (graphShortnames.length === 0) {
    return query;
  }

  // Find the WHERE clause
  const whereIndex = query.toUpperCase().indexOf("WHERE");
  if (whereIndex === -1) {
    return query;
  }

  // Insert FROM clauses before WHERE
  const fromClauses = graphShortnames.map(
    shortname => `FROM <https://purl.org/okn/frink/kg/${shortname}>`
  ).join("\n");

  const beforeWhere = query.substring(0, whereIndex).trim();
  const afterWhere = query.substring(whereIndex);

  return `${beforeWhere}\n${fromClauses}\n${afterWhere}`;
}

export function removeFromClauses(query: string): string {
  // Remove all FROM clauses
  return query.replace(/FROM\s+<[^>]+>\s*/gi, "").replace(/\n\s*\n/g, "\n");
}






