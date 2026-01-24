// NDE healthCondition encoding detection with caching
// Determines whether NDE uses MONDO IRIs or CURIE strings

import { executeSPARQL } from "@/lib/sparql/executor";
import { buildNDEEncodingQuery } from "./templates";
import type { SPARQLResult } from "@/types";

type NDEEncoding = "iri" | "curie";

interface EncodingCache {
  encoding: NDEEncoding | null;
  timestamp: number;
}

// In-memory cache with 24-hour TTL
let encodingCache: EncodingCache = {
  encoding: null,
  timestamp: 0,
};

const CACHE_TTL_MS = 24 * 60 * 60 * 1000; // 24 hours

/**
 * Detect whether NDE uses MONDO IRIs or CURIE strings for healthCondition
 * Caches result for 24 hours
 */
export async function detectNDEEncoding(): Promise<NDEEncoding> {
  // Check cache
  const now = Date.now();
  if (
    encodingCache.encoding !== null &&
    now - encodingCache.timestamp < CACHE_TTL_MS
  ) {
    return encodingCache.encoding;
  }

  try {
    const query = buildNDEEncodingQuery();
    const result = await executeSPARQL(query);

    // Analyze sample conditions to determine encoding
    const bindings = result.result.results.bindings;
    
    if (bindings.length === 0) {
      // No data - default to IRI
      encodingCache = {
        encoding: "iri",
        timestamp: now,
      };
      return "iri";
    }

    // Check first few bindings to determine pattern
    let iriCount = 0;
    let curieCount = 0;

    for (const binding of bindings.slice(0, 10)) {
      const condition = binding.condition?.value || "";
      
      if (condition.startsWith("http://") || condition.startsWith("https://")) {
        iriCount++;
      } else if (condition.match(/^MONDO:\d+$/i)) {
        curieCount++;
      }
    }

    // Determine encoding based on majority
    const encoding: NDEEncoding = iriCount >= curieCount ? "iri" : "curie";

    // Update cache
    encodingCache = {
      encoding,
      timestamp: now,
    };

    return encoding;
  } catch (error: any) {
    console.error("NDE encoding detection failed:", error);
    // Default to IRI on error
    encodingCache = {
      encoding: "iri",
      timestamp: now,
    };
    return "iri";
  }
}

/**
 * Clear the encoding cache (useful for testing or forced refresh)
 */
export function clearEncodingCache(): void {
  encodingCache = {
    encoding: null,
    timestamp: 0,
  };
}




