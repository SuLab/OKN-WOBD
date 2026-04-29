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

  // Do not remove FILTER clauses with a naive /FILTER\s*\([^)]+\)/ regex: nested parens
  // (e.g. BOUND(?x), IN (...), organism taxon blocks) cause the match to end at the first
  // ")", deleting only a prefix of the FILTER and leaving invalid SPARQL (e.g. leading "&&").

  // Strategy 2: Switch label matching strategy
  // Change exact string matching to regex matching
  if (repaired.includes('FILTER(STR(?label) = "') || repaired.includes("FILTER(STR(?name) = \"")) {
    repaired = repaired.replace(
      /FILTER\(STR\((\w+)\)\s*=\s*"([^"]+)"/gi,
      'FILTER(REGEX(STR($1), "$2", "i"))'
    );
    changes.push("Switched from exact string match to case-insensitive regex");
  }

  // Strategy 3 (removed): naive OPTIONAL removal via /OPTIONAL\s*\{[^}]*\}/ is unsafe for nested
  // OPTIONAL { ... OPTIONAL { ... } ... } patterns (common in NDE dataset_search). It deletes
  // the inner block only or leaves dangling "}", yielding invalid SPARQL and FRINK 400 parse errors.

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






