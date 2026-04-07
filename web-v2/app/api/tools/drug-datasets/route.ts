import { NextResponse } from "next/server";
import { loadContextPack } from "@/lib/context-packs/loader";
import { buildDrugDatasetsPlan } from "@/lib/dashboard/drug-datasets-plan";
import { executeQueryPlan } from "@/lib/agents/query-executor";
import { augmentNdeDatasetBindingsWithGxa } from "@/lib/dashboard/nde-gxa-augment";
import type { SPARQLResult } from "@/types";

const PACK_ID = "wobd";

function getBindingValue(raw: { type: string; value: string } | string | undefined): string {
  if (raw == null) return "";
  if (typeof raw === "object" && "value" in raw) return String((raw as { value: string }).value ?? "");
  return String(raw);
}

function getBindingField(b: Record<string, unknown>, key: string): string {
  const raw = b[key] ?? b[key.charAt(0).toUpperCase() + key.slice(1)];
  return getBindingValue(raw as { type: string; value: string } | string | undefined);
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
    let executedQueries: { graph?: string; query: string; label?: string }[] = [];

    // Server-side fetch needs an absolute URL; use request origin so step 2/3 can call SPARQL execute
    const baseUrl = request.headers.get("x-forwarded-host")
      ? `${request.headers.get("x-forwarded-proto") || "https"}://${request.headers.get("x-forwarded-host")}`
      : new URL(request.url).origin;

    for await (const event of executeQueryPlan(plan, pack, { baseUrl })) {
      if (event.type === "step_failed") {
        lastError = event.step.error ?? event.error ?? "Step failed";
      }
      if (event.type === "plan_completed") {
        executedQueries = (event.results ?? [])
          .filter((s) => s.sparql)
          .map((s) => ({
            graph: s.target_graphs?.[0],
            query: s.sparql!,
            label: s.description,
          }));
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

    const bindings = finalResults.results?.bindings ?? [];
    if (process.env.NODE_ENV !== "production") {
      const sampleIds = bindings.slice(0, 3).map((b) => getBindingField(b as Record<string, unknown>, "identifier"));
      console.log("[drug-datasets] NDE bindings:", bindings.length, "sample identifiers:", sampleIds);
    }
    finalResults = await augmentNdeDatasetBindingsWithGxa(pack, finalResults as SPARQLResult);

    const augmentedBindings = finalResults.results?.bindings ?? [];
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
      executed_queries: executedQueries,
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      { error: message, results: null },
      { status: 500 }
    );
  }
}
