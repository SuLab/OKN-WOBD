/**
 * Annotate NDE dataset SPARQL rows with GXA coverage (hasGeneExpression, experiment metadata).
 * Shared by drug_datasets API and dataset_search dashboard flow.
 */

import type { ContextPack } from "@/lib/context-packs/types";
import { eGeodCandidatesPerNdeBinding, ndeBindingString } from "@/lib/dashboard/nde-geo-evidence";
import { buildGXACoverageForExperimentIdsQuery } from "@/lib/ontology/templates";
import { executeSPARQL } from "@/lib/sparql/executor";
import type { SPARQLResult } from "@/types";

// Re-export for callers that imported from this module
export { extractEGeodIdsFromText, identifierToEGeod, eGeodCandidatesPerNdeBinding } from "@/lib/dashboard/nde-geo-evidence";

const HAS_GE_VAR = "hasGeneExpression";

/**
 * Run federated GXA coverage query for experiment ids; returns experiment ids present in GXA and detail map.
 */
export async function fetchGxaCoverageForExperiments(
  pack: ContextPack | null,
  eGeodIds: string[]
): Promise<{
  gxaExperimentIds: Set<string>;
  eGeodToCoverage: Map<string, { experimentId: string; contrastCount: string; sampleContrastLabel: string }>;
}> {
  const empty = {
    gxaExperimentIds: new Set<string>(),
    eGeodToCoverage: new Map<
      string,
      { experimentId: string; contrastCount: string; sampleContrastLabel: string }
    >(),
  };
  if (eGeodIds.length === 0) return empty;

  const gxaQuery = buildGXACoverageForExperimentIdsQuery(eGeodIds);
  if (!gxaQuery) return empty;

  const federatedEndpoint =
    pack?.endpoint_mode?.federated_endpoint ||
    process.env.NEXT_PUBLIC_FRINK_FEDERATION_URL ||
    "https://apps.okn.us/federation/sparql";

  try {
    const gxaRes = await executeSPARQL(gxaQuery, federatedEndpoint, { timeout_s: 120 });
    const gxaBindings = gxaRes.result?.results?.bindings ?? [];
    const gxaExperimentIds = new Set(
      gxaBindings
        .map((b: Record<string, unknown>) => {
          const v = b.experimentId ?? b.experimentid;
          return ndeBindingString(v as { type: string; value: string } | string | undefined);
        })
        .filter(Boolean)
    );
    const eGeodToCoverage = new Map<
      string,
      { experimentId: string; contrastCount: string; sampleContrastLabel: string }
    >();
    for (const b of gxaBindings as Record<string, unknown>[]) {
      const eid = ndeBindingString(
        (b.experimentId ?? b.experimentid) as { type: string; value: string } | string | undefined
      );
      const cc = ndeBindingString(
        (b.contrastCount ?? b.contrastcount) as { type: string; value: string } | string | undefined
      );
      const scl = ndeBindingString(
        (b.sampleContrastLabel ?? b.samplecontrastlabel) as { type: string; value: string } | string | undefined
      );
      if (eid) eGeodToCoverage.set(eid, { experimentId: eid, contrastCount: cc || "0", sampleContrastLabel: scl || "" });
    }
    return { gxaExperimentIds, eGeodToCoverage };
  } catch (err) {
    if (process.env.NODE_ENV !== "production") {
      console.warn("[nde-gxa-augment] GXA lookup failed:", err instanceof Error ? err.message : err);
    }
    return empty;
  }
}

/**
 * Add hasGeneExpression and optional GXA metadata columns to NDE dataset query results.
 */
export async function augmentNdeDatasetBindingsWithGxa(
  pack: ContextPack | null,
  sparqlResult: SPARQLResult
): Promise<SPARQLResult> {
  const bindings = (sparqlResult.results?.bindings ?? []) as Array<Record<string, unknown>>;
  const headVars = sparqlResult.head?.vars ?? [];

  const candidateSets = eGeodCandidatesPerNdeBinding(bindings);
  const eGeodIds = [...new Set(candidateSets.flatMap((s) => [...s]))];
  const { gxaExperimentIds, eGeodToCoverage } = await fetchGxaCoverageForExperiments(pack, eGeodIds);

  const augmentedBindings = bindings.map((b, i) => {
    const candidateSet = candidateSets[i];
    const firstMatch = [...candidateSet].find((e) => gxaExperimentIds.has(e));
    const hasGeneExpression = candidateSet.size > 0 && !!firstMatch;
    const coverage = firstMatch ? eGeodToCoverage.get(firstMatch) : null;
    const out: Record<string, unknown> = {
      ...b,
      [HAS_GE_VAR]: {
        type: "literal" as const,
        value: hasGeneExpression ? "true" : "false",
      },
    };
    if (coverage) {
      out.gxaExperimentId = { type: "literal" as const, value: coverage.experimentId };
      out.gxaContrastCount = { type: "literal" as const, value: coverage.contrastCount };
      out.gxaSampleContrastLabel = { type: "literal" as const, value: coverage.sampleContrastLabel };
      out.spokeGenelabStudyUrl = {
        type: "literal" as const,
        value: `https://spoke.ucsf.edu/genelab/${coverage.experimentId}`,
      };
    }
    return out;
  });

  const extraVars = [
    HAS_GE_VAR,
    "gxaExperimentId",
    "gxaContrastCount",
    "gxaSampleContrastLabel",
    "spokeGenelabStudyUrl",
  ].filter((v) => !headVars.includes(v));

  return {
    ...sparqlResult,
    head: { vars: [...headVars, ...extraVars] },
    results: {
      bindings: augmentedBindings as Array<Record<string, { type: string; value: string }>>,
    },
  };
}

/** Keep rows where GXA matched at least one E-GEOD candidate (post-augmentation). */
export function filterBindingsToGxaCoverageOnly(
  bindings: Array<Record<string, unknown>>
): Array<Record<string, unknown>> {
  return bindings.filter((b) => {
    const v = b[HAS_GE_VAR];
    const s =
      typeof v === "object" && v !== null && "value" in v
        ? String((v as { value: string }).value)
        : String(v ?? "");
    return s === "true";
  });
}
