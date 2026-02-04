// One repair attempt for SPARQL queries

export interface RepairResult {
  repaired_query?: string;
  changes: string[];
  success: boolean;
}

export function attemptRepair(
  originalQuery: string,
  error?: string
): RepairResult {
  const changes: string[] = [];
  let repaired = originalQuery;

  // Strategy 1: Relax FILTER constraints
  // Remove overly specific FILTER clauses that might be too restrictive
  const filterRegex = /FILTER\s*\([^)]+\)/gi;
  const filters = repaired.match(filterRegex);
  if (filters && filters.length > 2) {
    // Remove the last FILTER (often the most specific)
    const lastFilter = filters[filters.length - 1];
    repaired = repaired.replace(lastFilter, "");
    changes.push("Removed overly specific FILTER clause");
  }

  // Strategy 2: Switch label matching strategy
  // Change exact string matching to regex matching
  if (repaired.includes('FILTER(STR(?label) = "') || repaired.includes("FILTER(STR(?name) = \"")) {
    repaired = repaired.replace(
      /FILTER\(STR\((\w+)\)\s*=\s*"([^"]+)"/gi,
      'FILTER(REGEX(STR($1), "$2", "i"))'
    );
    changes.push("Switched from exact string match to case-insensitive regex");
  }

  // Strategy 3: Remove OPTIONAL if it's causing issues
  // This is a last resort - only if we have multiple OPTIONALs
  const optionalCount = (repaired.match(/OPTIONAL/gi) || []).length;
  if (optionalCount > 3) {
    // Remove the last OPTIONAL block
    const optionalRegex = /OPTIONAL\s*\{[^}]*\}/gs;
    const matches = repaired.match(optionalRegex);
    if (matches && matches.length > 0) {
      repaired = repaired.replace(matches[matches.length - 1], "");
      changes.push("Removed last OPTIONAL clause to simplify query");
    }
  }

  // Strategy 4: Increase LIMIT if it's very small
  const limitMatch = repaired.match(/LIMIT\s+(\d+)/i);
  if (limitMatch) {
    const currentLimit = parseInt(limitMatch[1], 10);
    if (currentLimit < 10) {
      repaired = repaired.replace(/LIMIT\s+\d+/i, `LIMIT ${Math.min(currentLimit * 2, 50)}`);
      changes.push(`Increased LIMIT from ${currentLimit} to ${Math.min(currentLimit * 2, 50)}`);
    }
  }

  return {
    repaired_query: changes.length > 0 ? repaired : undefined,
    changes,
    success: changes.length > 0,
  };
}






