/**
 * MONDO descendant expansion via OLS4 v2 entities API (hierarchicalAncestor filter).
 * The legacy OLS term /children and /hierarchicalDescendants routes return empty for MONDO;
 * v2/entities is fast and returns proper subclass terms in the mondo ontology.
 */

import { resolveHealthConditionIri } from "@/lib/ontology/templates";

const OLS_V2_ENTITIES = "https://www.ebi.ac.uk/ols4/api/v2/entities";
const OLS_MONDO_TERM = "https://www.ebi.ac.uk/ols4/api/ontologies/mondo/terms";

const MONDO_OBO_PREFIX = "http://purl.obolibrary.org/obo/MONDO_";

/**
 * Shared cap for MONDO subclass expansion: max merged IRIs in the SPARQL filter and max distinct
 * labels for UI highlighting (keeps query size, regex, and behavior aligned).
 */
export const DEFAULT_MONDO_DESCENDANT_EXPAND_CAP = 200;

/** @alias {@link DEFAULT_MONDO_DESCENDANT_EXPAND_CAP} */
export const DEFAULT_MAX_MONDO_IRIS_FOR_NDE_EXPAND = DEFAULT_MONDO_DESCENDANT_EXPAND_CAP;

/** @alias {@link DEFAULT_MONDO_DESCENDANT_EXPAND_CAP} */
export const DEFAULT_MAX_MONDO_HIGHLIGHT_LABELS = DEFAULT_MONDO_DESCENDANT_EXPAND_CAP;

interface OLSEntityElement {
  iri?: string;
  ontologyId?: string;
  isObsolete?: boolean;
  /** OLS4 may return a string or a structured/localized value. */
  label?: unknown;
}

interface OLSEntitiesPage {
  elements?: OLSEntityElement[];
  totalPages?: number;
}

/** Stats when MONDO subclass expansion ran (trust / debugging UI). */
export interface MondoExpansionStats {
  rootsExpanded: number;
  /** Distinct MONDO OBO IRIs in the expanded filter list. */
  mondoIrisInFilter: number;
  iriCap: number;
  /** True if OLS pagination was cut short or the global IRI cap was hit. */
  truncated: boolean;
  highlightLabelCount: number;
  highlightLabelCap: number;
  /**
   * Set by dataset_search when ontology workflow uses REGEX fallback (IRIs not in SPARQL).
   * Omitted or true when expanded MONDO IRIs are in the query filter.
   */
  appliedToSparqlFilter?: boolean;
}

export interface MondoHealthExpansionResult {
  expandedInputs: string[];
  highlightLabels: string[];
  /** Present when at least one MONDO root was expanded. */
  stats?: MondoExpansionStats;
}

function isMondoOboIri(iri: string): boolean {
  return iri.startsWith(MONDO_OBO_PREFIX);
}

/**
 * Normalize OLS `label` fields to a single display string.
 * v2/entities (and some term payloads) may use objects or arrays instead of plain strings.
 */
function olsLabelToDisplayString(raw: unknown): string | null {
  if (raw === undefined || raw === null) return null;
  if (typeof raw === "string") {
    const t = raw.trim();
    return t.length > 0 ? t : null;
  }
  if (typeof raw === "number" || typeof raw === "boolean") {
    return String(raw);
  }
  if (Array.isArray(raw)) {
    for (const item of raw) {
      const s = olsLabelToDisplayString(item);
      if (s) return s;
    }
    return null;
  }
  if (typeof raw === "object") {
    const o = raw as Record<string, unknown>;
    if (typeof o.value === "string") {
      const t = o.value.trim();
      if (t) return t;
    }
    if (typeof o.label === "string") {
      const t = o.label.trim();
      if (t) return t;
    }
  }
  return null;
}

/** Preferred label for one MONDO IRI (OLS4 classic terms API). */
export async function fetchMondoTermPreferredLabel(
  iri: string,
  signal?: AbortSignal
): Promise<string | null> {
  const url = `${OLS_MONDO_TERM}?iri=${encodeURIComponent(iri)}`;
  const res = await fetch(url, {
    headers: {
      Accept: "application/json",
      "User-Agent": "OKN-WOBD-web-v2/1.0 (MONDO expansion; +https://github.com/SuLab/OKN-WOBD)",
    },
    cache: "no-store",
    signal,
  });
  if (!res.ok) return null;
  const data = (await res.json()) as {
    _embedded?: { terms?: Array<{ label?: unknown }> };
  };
  const term = data._embedded?.terms?.[0];
  return olsLabelToDisplayString(term?.label);
}

function pushLabel(labels: Set<string>, raw: unknown, maxLabels: number): void {
  if (labels.size >= maxLabels) return;
  const t = olsLabelToDisplayString(raw);
  if (!t || t.length < 2) return;
  labels.add(t);
}

/**
 * Fetch MONDO class IRIs that are hierarchical descendants of `ancestorIri` (OLS indexed),
 * always including `ancestorIri` itself. Skips obsolete terms. Collects preferred labels
 * for highlighting (capped).
 */
export async function fetchMondoDescendantIrisAndLabelsFromOLS(
  ancestorIri: string,
  options?: { maxIris?: number; maxLabels?: number; signal?: AbortSignal }
): Promise<{ iris: string[]; labels: string[]; truncated: boolean }> {
  const maxIris = Math.max(1, options?.maxIris ?? DEFAULT_MONDO_DESCENDANT_EXPAND_CAP);
  const maxLabels = Math.max(1, options?.maxLabels ?? DEFAULT_MONDO_DESCENDANT_EXPAND_CAP);
  const iris = new Set<string>();
  const labels = new Set<string>();
  iris.add(ancestorIri);

  const rootLabel = await fetchMondoTermPreferredLabel(ancestorIri, options?.signal);
  pushLabel(labels, rootLabel, maxLabels);

  const pageSize = 200;
  let page = 0;
  let totalPages = 1;

  while (iris.size < maxIris && page < totalPages) {
    const params = new URLSearchParams({
      search: "*",
      ontologyId: "mondo",
      hierarchicalAncestor: ancestorIri,
      size: String(pageSize),
      page: String(page),
    });
    const url = `${OLS_V2_ENTITIES}?${params.toString()}`;
    const res = await fetch(url, {
      headers: {
        Accept: "application/json",
        "User-Agent": "OKN-WOBD-web-v2/1.0 (MONDO expansion; +https://github.com/SuLab/OKN-WOBD)",
      },
      cache: "no-store",
      signal: options?.signal,
    });
    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      throw new Error(`OLS descendants request failed: ${res.status} ${errText.slice(0, 200)}`);
    }

    const data = (await res.json()) as OLSEntitiesPage;
    totalPages = typeof data.totalPages === "number" && data.totalPages > 0 ? data.totalPages : 1;
    const elements = data.elements ?? [];

    for (const el of elements) {
      if (iris.size >= maxIris) break;
      if (!el.iri || el.ontologyId !== "mondo") continue;
      if (!isMondoOboIri(el.iri)) continue;
      if (el.isObsolete) continue;
      iris.add(el.iri);
      pushLabel(labels, el.label, maxLabels);
    }

    if (iris.size >= maxIris) break;
    if (elements.length === 0) break;
    page += 1;
  }

  const truncated = iris.size >= maxIris && page < totalPages;
  return {
    iris: [...iris],
    labels: finalizeHighlightLabels([...labels], maxLabels),
    truncated,
  };
}

/** Dedupe case-insensitively; prefer longer strings first for highlight matching. */
export function finalizeHighlightLabels(raw: string[], max: number): string[] {
  const sorted = [...raw]
    .map((t) => (typeof t === "string" ? t.trim() : olsLabelToDisplayString(t) ?? ""))
    .filter((t) => t.length >= 2)
    .sort((a, b) => b.length - a.length);
  const seen = new Set<string>();
  const out: string[] = [];
  for (const t of sorted) {
    const k = t.toLowerCase();
    if (seen.has(k)) continue;
    seen.add(k);
    out.push(t);
    if (out.length >= max) break;
  }
  return out;
}

/**
 * Expand MONDO-valued health condition slot entries to include OLS descendants (shared IRIs + labels cap).
 * Non-MONDO values (free text, other IRIs) are left unchanged.
 */
function countMondoOboIrisInList(strings: string[]): number {
  let n = 0;
  for (const s of strings) {
    const t = s.trim();
    if (!t) continue;
    const r = resolveHealthConditionIri(t) || t.replace(/[<>]/g, "").trim();
    if (isMondoOboIri(r)) n += 1;
  }
  return n;
}

export async function expandHealthConditionInputsWithMondoDescendants(
  inputs: string[],
  options?: { maxTotalIris?: number; maxHighlightLabels?: number; signal?: AbortSignal }
): Promise<MondoHealthExpansionResult> {
  const maxTotal = Math.max(1, options?.maxTotalIris ?? DEFAULT_MONDO_DESCENDANT_EXPAND_CAP);
  const maxHl = options?.maxHighlightLabels ?? DEFAULT_MONDO_DESCENDANT_EXPAND_CAP;
  const out: string[] = [];
  const seen = new Set<string>();
  const labelAccum: string[] = [];
  let mondoRootsExpanded = 0;
  let anyFetchTruncated = false;

  const pushUnique = (v: string) => {
    if (!v || seen.has(v)) return;
    if (out.length >= maxTotal) return;
    seen.add(v);
    out.push(v);
  };

  for (const raw of inputs) {
    const t = raw.trim();
    if (!t) continue;

    const resolved = resolveHealthConditionIri(t);
    if (resolved && isMondoOboIri(resolved)) {
      mondoRootsExpanded += 1;
      const room = maxTotal - out.length;
      if (room <= 0) break;
      const { iris, labels, truncated } = await fetchMondoDescendantIrisAndLabelsFromOLS(resolved, {
        maxIris: room,
        maxLabels: maxHl,
        signal: options?.signal,
      });
      if (truncated) anyFetchTruncated = true;
      labelAccum.push(...labels);
      for (const iri of iris) {
        pushUnique(iri);
        if (out.length >= maxTotal) break;
      }
    } else {
      pushUnique(t);
    }
    if (out.length >= maxTotal) break;
  }

  const highlightLabels = finalizeHighlightLabels(labelAccum, maxHl);
  const hitGlobalCap = out.length >= maxTotal;
  const truncated = anyFetchTruncated || hitGlobalCap;
  const mondoIrisInFilter = countMondoOboIrisInList(out);

  const stats: MondoExpansionStats | undefined =
    mondoRootsExpanded > 0
      ? {
          rootsExpanded: mondoRootsExpanded,
          mondoIrisInFilter,
          iriCap: maxTotal,
          truncated,
          highlightLabelCount: highlightLabels.length,
          highlightLabelCap: maxHl,
        }
      : undefined;

  return {
    expandedInputs: out,
    highlightLabels,
    stats,
  };
}
