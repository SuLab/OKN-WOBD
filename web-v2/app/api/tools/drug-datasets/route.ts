import { NextResponse } from "next/server";
import { loadContextPack } from "@/lib/context-packs/loader";
import { buildDrugDatasetsPlan } from "@/lib/dashboard/drug-datasets-plan";
import { executeQueryPlan } from "@/lib/agents/query-executor";
import { buildGXACoverageForExperimentIdsQuery } from "@/lib/ontology/templates";
import { executeSPARQL } from "@/lib/sparql/executor";
import type { SPARQLResult } from "@/types";

const PACK_ID = "wobd";

/** Get string value from a SPARQL binding value (object with type/value or raw). */
function getBindingValue(raw: { type: string; value: string } | string | undefined): string {
  if (raw == null) return "";
  if (typeof raw === "object" && "value" in raw) return String((raw as { value: string }).value ?? "");
  return String(raw);
}

/** Get a binding value by key, trying lowercase and capitalized (some endpoints vary). */
function getBindingField(b: Record<string, unknown>, key: string): string {
  const raw = b[key] ?? b[key.charAt(0).toUpperCase() + key.slice(1)];
  return getBindingValue(raw as { type: string; value: string } | string | undefined);
}

/** Convert NDE identifier to GXA experiment id (e.g. GSE76 or E-GEOD-76 -> E-GEOD-76). */
function identifierToEGeod(identifier: string): string | null {
  if (!identifier || typeof identifier !== "string") return null;
  const s = identifier.trim();
  const gseMatch = s.match(/GSE(\d+)/i);
  if (gseMatch) return `E-GEOD-${gseMatch[1]}`;
  const eGeodMatch = s.match(/E-GEOD-(\d+)/i);
  return eGeodMatch ? `E-GEOD-${eGeodMatch[1]}` : null;
}

/** Extract all E-GEOD experiment IDs from a string (handles GSE123, E-GEOD-123, URLs, etc.). */
function extractEGeodIdsFromText(text: string): string[] {
  if (!text || typeof text !== "string") return [];
  const ids = new Set<string>();
  const gseMatches = text.matchAll(/GSE(\d+)/gi);
  for (const m of gseMatches) ids.add(`E-GEOD-${m[1]}`);
  const eGeodMatches = text.matchAll(/E-GEOD-(\d+)/gi);
  for (const m of eGeodMatches) ids.add(`E-GEOD-${m[1]}`);
  return [...ids];
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const drugs = Array.isArray(body.drugs)
      ? (body.drugs as string[]).map((d) => String(d).trim()).filter(Boolean)
      : typeof body.drug === "string" && body.drug.trim()
        ? [body.drug.trim()]
        : [];
    const onlyGeneExpression = body.onlyGeneExpression === true || body.onlyGeneExpression === "true";
    const maxResults =
      body.maxResults != null && body.maxResults !== ""
        ? Math.min(500, Math.max(1, Number(body.maxResults) || 500))
        : undefined;

    if (drugs.length === 0) {
      return NextResponse.json(
        { error: "Missing or invalid 'drug' or 'drugs' parameter" },
        { status: 400 }
      );
    }

    const pack = loadContextPack(PACK_ID);
    if (!pack) {
      return NextResponse.json(
        { error: `Context pack not found: ${PACK_ID}` },
        { status: 404 }
      );
    }

    const plan = buildDrugDatasetsPlan(drugs, {
      ...(maxResults != null ? { maxResults } : {}),
      geoOnly: onlyGeneExpression,
    });
    let lastError: string | null = null;
    let finalResults: SPARQLResult | null = null;

    // Server-side fetch needs an absolute URL; use request origin so step 2/3 can call SPARQL execute
    const baseUrl = request.headers.get("x-forwarded-host")
      ? `${request.headers.get("x-forwarded-proto") || "https"}://${request.headers.get("x-forwarded-host")}`
      : new URL(request.url).origin;

    for await (const event of executeQueryPlan(plan, pack, { baseUrl })) {
      if (event.type === "step_failed") {
        lastError = event.step.error ?? event.error ?? "Step failed";
      }
      if (event.type === "plan_completed") {
        const finalStepId = plan.steps[plan.steps.length - 1].id;
        const finalStep = event.results.find((s) => s.id === finalStepId);
        if (finalStep?.results && finalStep.intent?.task !== "entity_resolution") {
          finalResults = {
            head: finalStep.results.head ?? { vars: [] },
            results: {
              bindings: finalStep.results.results?.bindings ?? [],
            },
          };
        } else if (!lastError) {
          lastError =
            finalStep?.error ||
            "No dataset results. Step 3 (NDE search) did not complete or returned no rows.";
        }
        break;
      }
    }

    if (lastError && !finalResults) {
      return NextResponse.json(
        { error: lastError, results: null },
        { status: 200 }
      );
    }

    if (!finalResults) {
      return NextResponse.json(
        { error: "No results from pipeline", results: null },
        { status: 200 }
      );
    }

    // Step 4: Annotate bindings with hasGeneExpression via GXA lookup
    const bindings = finalResults.results?.bindings ?? [];
    const headVars = finalResults.head?.vars ?? [];
    // Collect E-GEOD candidates from identifier, name, description, url, sameAs (NDE links GEO via schema:url / schema:sameAs / owl:sameAs)
    const eGeodCandidatesPerBinding: Set<string>[] = bindings.map((b) => {
      const raw = b as Record<string, unknown>;
      const idVal = getBindingField(raw, "identifier");
      const nameVal = getBindingField(raw, "name");
      const descVal = getBindingField(raw, "description");
      const urlsVal = getBindingField(raw, "urls");
      const sameAsVal = getBindingField(raw, "sameAsList");
      const owlSameAsVal = getBindingField(raw, "owlSameAsList");
      const fromId = identifierToEGeod(idVal);
      const ids = new Set<string>();
      if (fromId) ids.add(fromId);
      for (const e of extractEGeodIdsFromText(nameVal)) ids.add(e);
      for (const e of extractEGeodIdsFromText(descVal)) ids.add(e);
      for (const e of extractEGeodIdsFromText(urlsVal)) ids.add(e);
      for (const e of extractEGeodIdsFromText(sameAsVal)) ids.add(e);
      for (const e of extractEGeodIdsFromText(owlSameAsVal)) ids.add(e);
      return ids;
    });
    const eGeodIds = [...new Set(eGeodCandidatesPerBinding.flatMap((s) => [...s]))];
    if (process.env.NODE_ENV !== "production") {
      const sampleIds = bindings.slice(0, 3).map((b) => getBindingField(b as Record<string, unknown>, "identifier"));
      console.log("[drug-datasets] NDE bindings:", bindings.length, "sample identifiers:", sampleIds);
      console.log("[drug-datasets] E-GEOD candidates:", eGeodIds.length, eGeodIds.slice(0, 10));
    }
    const eGeodToCoverage = new Map<
      string,
      { experimentId: string; contrastCount: string; sampleContrastLabel: string }
    >();
    let gxaExperimentIds = new Set<string>();
    if (eGeodIds.length > 0) {
      const gxaQuery = buildGXACoverageForExperimentIdsQuery(eGeodIds);
      if (gxaQuery) {
        const gxaEndpoint = pack?.endpoint_mode?.direct_endpoints?.["gene-expression-atlas-okn"];
        if (gxaEndpoint) {
          try {
            const gxaRes = await executeSPARQL(gxaQuery, gxaEndpoint, { timeout_s: 60 });
            const gxaBindings = gxaRes.result?.results?.bindings ?? [];
            gxaExperimentIds = new Set(
              gxaBindings.map((b: Record<string, unknown>) => {
                const v = b.experimentId ?? b.experimentid;
                return getBindingValue(v as { type: string; value: string } | string | undefined);
              }).filter(Boolean)
            );
            for (const b of gxaBindings as Record<string, unknown>[]) {
              const eid = getBindingValue((b.experimentId ?? b.experimentid) as { type: string; value: string } | string | undefined);
              const cc = getBindingValue((b.contrastCount ?? b.contrastcount) as { type: string; value: string } | string | undefined);
              const scl = getBindingValue((b.sampleContrastLabel ?? b.samplecontrastlabel) as { type: string; value: string } | string | undefined);
              if (eid) eGeodToCoverage.set(eid, { experimentId: eid, contrastCount: cc || "0", sampleContrastLabel: scl || "" });
            }
            if (process.env.NODE_ENV !== "production") {
              console.log("[drug-datasets] GXA endpoint OK, experiments in GXA:", gxaExperimentIds.size, [...gxaExperimentIds].slice(0, 5));
            }
          } catch (err) {
            if (process.env.NODE_ENV !== "production") {
              console.warn("[drug-datasets] GXA lookup failed (non-fatal):", err instanceof Error ? err.message : err);
            }
          }
        } else if (process.env.NODE_ENV !== "production") {
          console.warn("[drug-datasets] No gene-expression-atlas-okn direct endpoint in pack");
        }
      }
    }
    const hasGeneExpressionVar = "hasGeneExpression";
    const augmentedBindings = bindings.map((b, i) => {
      const candidateSet = eGeodCandidatesPerBinding[i];
      const firstMatch = [...candidateSet].find((e) => gxaExperimentIds.has(e));
      const hasGeneExpression = candidateSet.size > 0 && !!firstMatch;
      const coverage = firstMatch ? eGeodToCoverage.get(firstMatch) : null;
      const out: Record<string, unknown> = {
        ...b,
        [hasGeneExpressionVar]: {
          type: "literal" as const,
          value: hasGeneExpression ? "true" : "false",
        },
      };
      if (coverage) {
        out.gxaExperimentId = { type: "literal" as const, value: coverage.experimentId };
        out.gxaContrastCount = { type: "literal" as const, value: coverage.contrastCount };
        out.gxaSampleContrastLabel = { type: "literal" as const, value: coverage.sampleContrastLabel };
        out.spokeGenelabStudyUrl = { type: "literal" as const, value: `https://spoke.ucsf.edu/genelab/${coverage.experimentId}` };
      }
      return out;
    });
    const extraVars = [hasGeneExpressionVar, "gxaExperimentId", "gxaContrastCount", "gxaSampleContrastLabel", "spokeGenelabStudyUrl"].filter(
      (v) => !headVars.includes(v)
    );
    finalResults = {
      ...finalResults,
      head: { vars: [...headVars, ...extraVars] },
      results: {
        bindings: augmentedBindings as Array<Record<string, { type: string; value: string }>>,
      },
    };

    let outBindings = augmentedBindings;
    let filteredEmptyHint: string | null = null;
    // When onlyGeneExpression is true we already restricted step 3 to GEO (geo_dataset_search), so the
    // result set is already GEO-only. Do NOT filter by hasGeneExpression (GXA coverage), or we'd show 0
    // when GXA has no experiments for these IDs. Show all GEO results; the badge shows which have GXA.
    if (onlyGeneExpression && augmentedBindings.length === 0) {
      filteredEmptyHint =
        "No GEO datasets were found for diseases treated by this drug. The NDE graph may not have GEO (GSE) entries for these conditions. Try unchecking \"Only show datasets with gene expression data\" to see all NDE datasets for these diseases.";
    }

    return NextResponse.json({
      results: finalResults,
      error: null,
      filtered_empty_hint: filteredEmptyHint ?? undefined,
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      { error: message, results: null },
      { status: 500 }
    );
  }
}
