// SPARQL safety validation

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  normalized_query?: string;
}

// Note: FORBIDDEN_OPS is now passed via guardrails.forbid_ops parameter
// Keeping this for reference but it's not used directly
const _FORBIDDEN_OPS = [
  "INSERT", "DELETE", "LOAD", "CLEAR", "DROP",
  "CREATE", "MOVE", "COPY", "ADD"
];

export function validateSPARQL(query: string, guardrails: {
  forbid_ops: string[];
  max_limit: number;
}): ValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];
  const upperQuery = query.toUpperCase();

  // Check for forbidden operations
  for (const op of guardrails.forbid_ops) {
    if (upperQuery.includes(op)) {
      errors.push(`Forbidden operation detected: ${op}`);
    }
  }

  // Require SELECT or ASK (no CONSTRUCT/DESCRIBE for now, can be added later).
  // Be robust: as long as the query string contains SELECT or ASK anywhere (ignoring case),
  // we treat it as a read-only query. This avoids false negatives due to comments, PREFIX
  // blocks, or minor formatting differences introduced by tooling.
  const hasSelectOrAsk =
    /\bSELECT\b/.test(upperQuery) || /\bASK\b/.test(upperQuery);

  if (!hasSelectOrAsk) {
    errors.push(
      "Query must be SELECT or ASK (CONSTRUCT/DESCRIBE not yet supported)"
    );
  }

  // Check for LIMIT
  const hasLimit = /LIMIT\s+\d+/i.test(query);
  if (!hasLimit) {
    warnings.push("Query missing LIMIT clause - results may be large");
  } else {
    // Extract and check limit value
    const limitMatch = query.match(/LIMIT\s+(\d+)/i);
    if (limitMatch) {
      const limitValue = parseInt(limitMatch[1], 10);
      if (limitValue > guardrails.max_limit) {
        warnings.push(`LIMIT ${limitValue} exceeds max_limit ${guardrails.max_limit}`);
      }
    }
  }

  // Don't inject LIMIT automatically - let queries run without limit if not specified
  // The guardrails.max_limit will be enforced by the endpoint if needed
  let normalized_query = query;

  return {
    valid: errors.length === 0,
    errors,
    warnings,
    normalized_query: normalized_query !== query ? normalized_query : undefined,
  };
}

export function extractServiceEndpoints(query: string): string[] {
  const serviceRegex = /SERVICE\s+<([^>]+)>/gi;
  const endpoints: string[] = [];
  let match;

  while ((match = serviceRegex.exec(query)) !== null) {
    endpoints.push(match[1]);
  }

  return endpoints;
}

export function checkServicePolicy(
  serviceEndpoints: string[],
  policy: "allowlist" | "allow_any_frink" | "allow_any" | "forbid_all",
  allowlist?: string[],
  frinkEndpoints?: string[]
): { allowed: boolean; reason?: string } {
  if (serviceEndpoints.length === 0) {
    return { allowed: true };
  }

  switch (policy) {
    case "forbid_all":
      return { allowed: false, reason: "SERVICE clauses are forbidden by policy" };

    case "allow_any":
      return { allowed: true };

    case "allowlist":
      if (!allowlist || allowlist.length === 0) {
        return { allowed: false, reason: "SERVICE allowlist is empty" };
      }
      for (const endpoint of serviceEndpoints) {
        if (!allowlist.includes(endpoint)) {
          return { allowed: false, reason: `SERVICE endpoint not in allowlist: ${endpoint}` };
        }
      }
      return { allowed: true };

    case "allow_any_frink":
      if (!frinkEndpoints || frinkEndpoints.length === 0) {
        // If we can't determine FRINK endpoints, be conservative
        return { allowed: false, reason: "Cannot verify FRINK endpoints" };
      }
      for (const endpoint of serviceEndpoints) {
        // Check if endpoint matches any FRINK endpoint pattern
        const isFrink = frinkEndpoints.some(fe =>
          endpoint.includes(fe) || fe.includes(endpoint)
        );
        if (!isFrink) {
          return { allowed: false, reason: `SERVICE endpoint not a known FRINK endpoint: ${endpoint}` };
        }
      }
      return { allowed: true };

    default:
      return { allowed: false, reason: "Unknown service policy" };
  }
}

