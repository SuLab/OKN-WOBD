"use client";

import React, { useEffect, useState, useCallback, useRef, useMemo } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import type { ContextPack } from "@/lib/context-packs/types";
import type { SPARQLResult } from "@/types";
import type { MondoExpansionStats } from "@/lib/ontology/mondo-descendants-ols";
import { SlotForm, isSlotFilled, getSlotMeta } from "@/components/dashboard/SlotForm";
import { MondoExpansionRecap } from "@/components/dashboard/MondoExpansionRecap";
import { NDEResultCards } from "@/components/dashboard/NDEResultCards";
import { ResultsTable } from "@/components/chat/ResultsTable";
import { getTemplateMeta } from "@/lib/landing/template-meta";
import {
  runTemplateQuery,
  isNDEShape,
  PACK_ID,
  GXA_TASKS,
  type ExecutedQueryItem,
} from "@/lib/dashboard/run-query";
import { SparqlEditor } from "@/components/chat/SparqlEditor";
import { datasetSearchTemplate } from "@/lib/templates/templates/dataset_search";
import { geoDatasetSearchTemplate } from "@/lib/templates/templates/geo_dataset_search";
import { withBasePath } from "@/lib/base-path";
import type { TemplateDefinition } from "@/lib/context-packs/types";
import { Info, ChevronDown, ChevronRight, Copy, Check } from "lucide-react";

/** Merge pack YAML template metadata with built-in NDE template slots so new slots (e.g. MONDO expansion) are not dropped if the pack file lags. */
function mergeNdeTemplateWithBuiltin(
  packTemplate: TemplateDefinition | undefined,
  id: string
): TemplateDefinition | null {
  if (!packTemplate) return null;
  if (id === "dataset_search") {
    const b = datasetSearchTemplate;
    const opt = [...new Set([...(packTemplate.optional_slots ?? []), ...(b.optional_slots ?? [])])];
    return { ...packTemplate, optional_slots: opt };
  }
  if (id === "geo_dataset_search") {
    const b = geoDatasetSearchTemplate;
    const opt = [...new Set([...(packTemplate.optional_slots ?? []), ...(b.optional_slots ?? [])])];
    return { ...packTemplate, optional_slots: opt };
  }
  return packTemplate;
}

function parseHighlightTerms(raw: unknown): string[] {
  if (Array.isArray(raw)) {
    return raw.map((x) => String(x).trim()).filter(Boolean);
  }
  if (typeof raw === "string" && raw.trim()) {
    return [raw.trim()];
  }
  return [];
}

/** Terms to highlight in NDE cards for dataset / GEO keyword search + ontology facet labels. */
function datasetKeywordHighlightTerms(
  templateId: string,
  slots: Record<string, string | string[]>
): string[] {
  if (templateId !== "dataset_search" && templateId !== "geo_dataset_search") {
    return [];
  }
  const parts: string[] = [];
  const rawList = slots.keywords_list;
  if (Array.isArray(rawList) && rawList.length > 0) {
    parts.push(...rawList.map((x) => String(x).trim()).filter(Boolean));
  } else {
    const kw = slots.keywords;
    if (Array.isArray(kw)) {
      parts.push(...kw.map((x) => String(x).trim()).filter(Boolean));
    } else if (typeof kw === "string" && kw.trim()) {
      parts.push(kw.trim());
    }
  }
  for (const key of [
    "health_condition_labels",
    "species_labels",
    "infectious_agent_labels",
  ] as const) {
    parts.push(...parseHighlightTerms(slots[key]));
  }
  return [...new Set(parts)];
}

/** GXA / gene-expression templates: highlight chosen ontology labels in the results table. */
function gxaOntologyHighlightTerms(slots: Record<string, string | string[]>): string[] {
  const parts: string[] = [];
  for (const key of [
    "organism_taxon_ids_labels",
    "tissue_uberon_ids_labels",
    "tissue_uberon_ids_ols_labels",
    "disease_efo_labels",
  ] as const) {
    parts.push(...parseHighlightTerms(slots[key]));
  }
  return [...new Set(parts)];
}

/** dataset_search: need keywords and/or at least one facet (matches server-side query builder). */
function ndeDatasetSearchHasKeywordsOrFacet(slots: Record<string, string | string[]>): boolean {
  const kw = slots.keywords;
  if (typeof kw === "string" && kw.trim() !== "") return true;
  if (Array.isArray(kw) && kw.some((x) => String(x).trim() !== "")) return true;
  const rawList = slots.keywords_list;
  if (Array.isArray(rawList) && rawList.some((x) => String(x).trim() !== "")) return true;
  const hc = slots.health_condition;
  if (typeof hc === "string" && hc.trim() !== "") return true;
  if (Array.isArray(hc) && hc.some((x) => String(x).trim() !== "")) return true;
  const ia = slots.infectious_agent;
  if (typeof ia === "string" && ia.trim() !== "") return true;
  if (Array.isArray(ia) && ia.some((x) => String(x).trim() !== "")) return true;
  const sp = slots.species;
  if (typeof sp === "string" && sp.trim() !== "") return true;
  if (Array.isArray(sp) && sp.some((x) => String(x).trim() !== "")) return true;
  return false;
}

export default function TemplatePage() {
  const params = useParams();
  const templateId = typeof params.templateId === "string" ? params.templateId : "";

  const [pack, setPack] = useState<ContextPack | null>(null);
  const [packError, setPackError] = useState<string | null>(null);
  const [slotValues, setSlotValues] = useState<Record<string, string | string[]>>({});
  const [results, setResults] = useState<SPARQLResult | null>(null);
  const [resultsError, setResultsError] = useState<string | null>(null);
  const [filteredEmptyHint, setFilteredEmptyHint] = useState<string | null>(null);
  const [executedQueries, setExecutedQueries] = useState<ExecutedQueryItem[]>([]);
  const [showQueriesOpen, setShowQueriesOpen] = useState(false);
  const [copiedQueryIndex, setCopiedQueryIndex] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  /** Labels from OLS for MONDO subclass expansion (last successful NDE template query). */
  const [mondoExpansionHighlightLabels, setMondoExpansionHighlightLabels] = useState<string[]>([]);
  const [mondoExpansionStats, setMondoExpansionStats] = useState<MondoExpansionStats | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const runningRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    fetch(withBasePath(`/api/tools/context/packs/${PACK_ID}`))
      .then((r) => {
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
      })
      .then((data: ContextPack) => {
        if (!cancelled) {
          setPack(data);
          setPackError(null);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setPackError(e.message || "Failed to load context pack");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const template = useMemo(() => {
    const t = pack?.templates?.find((x) => x.id === templateId);
    return mergeNdeTemplateWithBuiltin(t, templateId);
  }, [pack, templateId]);
  const meta = getTemplateMeta(templateId);

  const formHighlightTerms = useMemo(() => {
    let base: string[] = [];
    if (templateId === "dataset_search" || templateId === "geo_dataset_search") {
      base = datasetKeywordHighlightTerms(templateId, slotValues);
    } else if ((GXA_TASKS as readonly string[]).includes(templateId)) {
      base = gxaOntologyHighlightTerms(slotValues);
    }
    if (mondoExpansionHighlightLabels.length === 0) return base;
    return [...new Set([...base, ...mondoExpansionHighlightLabels])];
  }, [templateId, slotValues, mondoExpansionHighlightLabels]);

  const diseaseNamesFromResults = useMemo(() => {
    if (!results?.results?.bindings?.length) return [];
    const out: string[] = [];
    for (const b of results.results.bindings) {
      const v = b.diseaseNames?.value;
      if (typeof v === "string" && v.trim()) out.push(v);
    }
    return out;
  }, [results]);

  const showMondoExpansionRecap = Boolean(
    mondoExpansionStats &&
      results &&
      (templateId === "dataset_search" || templateId === "geo_dataset_search")
  );

  const runQuery = useCallback(async () => {
    if (!pack || !template) return;
    if (runningRef.current) return;
    runningRef.current = true;
    setResultsError(null);
    setResults(null);
    setFilteredEmptyHint(null);
    setExecutedQueries([]);
    setMondoExpansionHighlightLabels([]);
    setMondoExpansionStats(null);
    setLoading(true);
    abortRef.current = new AbortController();
    const signal = abortRef.current.signal;

    try {
      const {
        results: res,
        error: err,
        filteredEmptyHint: hint,
        executedQueries: queries,
        mondoExpansionHighlightLabels: expansionHl,
        mondoExpansionStats: expansionStat,
      } = await runTemplateQuery({
        templateId,
        slots: slotValues,
        pack,
        signal,
      });
      if (signal.aborted) return;
      if (err) {
        const timeoutLike =
          /timed out|took too long|operation was aborted|request was aborted/i.test(err);
        setResultsError(
          timeoutLike
            ? "Query timed out. Gene expression across experiments can take up to 2 minutes; try again or reduce the number of experiments."
            : err
        );
        setResults(null);
        setFilteredEmptyHint(null);
        setExecutedQueries(queries ?? []);
        setMondoExpansionHighlightLabels([]);
        setMondoExpansionStats(null);
        return;
      }
      setResults(res);
      setFilteredEmptyHint(hint ?? null);
      setExecutedQueries(queries ?? []);
      setMondoExpansionHighlightLabels(expansionHl ?? []);
      setMondoExpansionStats(expansionStat ?? null);
    } catch (e: unknown) {
      if (signal.aborted) return;
      const isAbort =
        (e instanceof Error && e.name === "AbortError") ||
        (typeof (e as { name?: string })?.name === "string" && (e as { name: string }).name === "AbortError");
      setResultsError(isAbort ? "Query was cancelled." : (e instanceof Error ? e.message : String((e as Error)?.message ?? "Unknown error")));
      setResults(null);
      setMondoExpansionHighlightLabels([]);
      setMondoExpansionStats(null);
    } finally {
      setLoading(false);
      abortRef.current = null;
      runningRef.current = false;
    }
  }, [pack, template, templateId, slotValues]);

  const handleSlotChange = useCallback((values: Record<string, string | string[]>) => {
    setSlotValues(values);
  }, []);

  const handleCopyQuery = useCallback((query: string, index: number) => {
    navigator.clipboard.writeText(query).then(
      () => {
        setCopiedQueryIndex(index);
        setTimeout(() => setCopiedQueryIndex(null), 2000);
      },
      () => {}
    );
  }, []);

  const required = template?.required_slots ?? [];
  const optional = template?.optional_slots ?? [];
  const missingRequired = required.filter((slot) => !isSlotFilled(slotValues[slot]));
  const datasetSearchNeedsCriterion =
    templateId === "dataset_search" && !ndeDatasetSearchHasKeywordsOrFacet(slotValues);
  const canRun = missingRequired.length === 0 && !datasetSearchNeedsCriterion;
  const hasOptional = optional.length > 0;

  if (packError) {
    return (
      <div
        className="mx-auto flex max-w-5xl flex-1 flex-col p-4 sm:p-6"
        style={{ backgroundColor: "var(--niaid-page-bg)" }}
      >
        <p className="text-red-600 dark:text-red-400">{packError}</p>
        <Link href="/" className="mt-4 inline-block text-sm text-niaid-link hover:underline">
          ← Back to templates
        </Link>
      </div>
    );
  }

  if (!pack) {
    return (
      <div
        className="mx-auto flex max-w-5xl flex-1 items-center justify-center p-4 sm:p-6"
        style={{ backgroundColor: "var(--niaid-page-bg)" }}
      >
        <p className="text-slate-600 dark:text-slate-400">Loading…</p>
      </div>
    );
  }

  if (!template || !meta) {
    return (
      <div
        className="mx-auto flex max-w-5xl flex-1 flex-col p-4 sm:p-6"
        style={{ backgroundColor: "var(--niaid-page-bg)" }}
      >
        <p className="text-slate-600 dark:text-slate-400">Template not found.</p>
        <Link href="/" className="mt-4 inline-block text-sm text-niaid-link hover:underline">
          ← Back to templates
        </Link>
      </div>
    );
  }

  const Icon = meta.icon;

  return (
    <div
      className="flex flex-1 flex-col p-4 sm:p-5"
      style={{ backgroundColor: "var(--niaid-page-bg)" }}
    >
      <div className="mx-auto w-full max-w-5xl space-y-4 sm:space-y-5">
        <Link
          href="/"
          className="inline-flex items-center gap-1 text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-niaid-link"
        >
          ← Back to templates
        </Link>

        <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm overflow-visible">
          <div className="p-4 sm:p-6 space-y-4">
            <div className="flex items-start gap-3">
              <span className={`flex-shrink-0 ${meta.iconColor}`} aria-hidden>
                <Icon className="w-7 h-7" />
              </span>
              <div>
                <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
                  {meta.description}
                </h1>
                {meta.blurb && (
                  <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                    {meta.blurb}
                  </p>
                )}
              </div>
            </div>

            {templateId === "geo_dataset_search" && (
              <p className="text-sm text-slate-600 dark:text-slate-400 border-l-2 border-slate-300 dark:border-slate-600 pl-3 py-0.5">
                Keywords and metadata filters are optional. Leave everything blank to list NCBI GEO series
                (GSE) in NDE, or narrow with text and/or filters. Multiple filters combine with{" "}
                <span className="font-medium text-slate-700 dark:text-slate-300">AND</span>.
              </p>
            )}

            <SlotForm
              template={template}
              values={slotValues}
              onChange={handleSlotChange}
              disabled={loading}
              primarySectionTitle={
                templateId === "dataset_search" || templateId === "geo_dataset_search"
                  ? "Match by text"
                  : undefined
              }
              metadataSectionTitle={
                templateId === "dataset_search" || templateId === "geo_dataset_search"
                  ? "Or match by metadata"
                  : undefined
              }
            />

            {datasetSearchNeedsCriterion && (
              <p className="text-sm text-amber-800 dark:text-amber-200/90" role="status">
                Add keywords and/or at least one metadata filter to run this search.
              </p>
            )}
            <div className="pt-2 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={runQuery}
                disabled={loading || !canRun}
                className="inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-md text-white text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-default"
                style={{ backgroundColor: "var(--niaid-button)" }}
              >
                {loading ? (
                  <>
                    <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" aria-hidden />
                    Running…
                  </>
                ) : (
                  meta.buttonLabel
                )}
              </button>
              {loading && (
                <button
                  type="button"
                  onClick={() => abortRef.current?.abort()}
                  className="text-sm px-3 py-2 rounded border border-slate-300 dark:border-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300"
                >
                  Cancel
                </button>
              )}
            </div>

            {hasOptional &&
              (templateId === "dataset_search" || templateId === "geo_dataset_search" ? (
                <p className="flex items-start gap-2 text-xs text-slate-500 dark:text-slate-400">
                  <Info className="w-4 h-4 flex-shrink-0 mt-0.5" aria-hidden />
                  Leave a metadata filter blank to skip it. Empty filters do not restrict the query.
                </p>
              ) : (
                <p className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                  <Info className="w-4 h-4 flex-shrink-0" aria-hidden />
                  Tip: Leave optional fields blank to see all results.
                </p>
              ))}
          </div>
        </div>

        {(results || resultsError) && executedQueries.length > 0 && (
          <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm overflow-hidden">
            <button
              type="button"
              onClick={() => setShowQueriesOpen((open) => !open)}
              className="w-full flex items-center gap-2 px-4 py-3 text-left text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
            >
              {showQueriesOpen ? (
                <ChevronDown className="w-4 h-4 flex-shrink-0" aria-hidden />
              ) : (
                <ChevronRight className="w-4 h-4 flex-shrink-0" aria-hidden />
              )}
              <span>{showQueriesOpen ? "Hide Queries" : "Show Queries"}</span>
            </button>
            {showQueriesOpen && (
              <div className="border-t border-slate-200 dark:border-slate-700 p-4 space-y-4">
                {executedQueries.map((item, index) => {
                  const lineCount = (item.query.match(/\n/g)?.length ?? 0) + 1;
                  const isShortBlock = lineCount <= 4;
                  const editorHeight = isShortBlock ? "100px" : "280px";
                  return (
                    <div key={index} className="space-y-1">
                      {(item.label || item.graph) && (
                        <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
                          {item.label ?? `Graph: ${item.graph}`}
                        </p>
                      )}
                      <div className="relative rounded-md border border-slate-200 dark:border-slate-700 overflow-hidden">
                        <div className="absolute top-2 right-2 z-10">
                          <button
                            type="button"
                            onClick={() => handleCopyQuery(item.query, index)}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-md transition-colors shadow-sm border border-slate-200 dark:border-slate-700"
                            title="Copy query to use in FRINK"
                          >
                            {copiedQueryIndex === index ? (
                              <>
                                <Check className="w-4 h-4 text-green-500 dark:text-green-400" aria-hidden />
                                <span className="text-green-500 dark:text-green-400">Copied!</span>
                              </>
                            ) : (
                              <>
                                <Copy className="w-4 h-4" aria-hidden />
                                <span>Copy</span>
                              </>
                            )}
                          </button>
                        </div>
                        <SparqlEditor
                          value={item.query}
                          readOnly
                          height={editorHeight}
                          className="[&_.monaco-editor]:cursor-default"
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {(results || resultsError) && (
          <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm overflow-hidden p-4">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-3">
              Results
            </h2>
            {resultsError && (
              <p className="py-4 text-red-600 dark:text-red-400" role="alert">
                {resultsError}
              </p>
            )}
            {results && (
              <>
                {showMondoExpansionRecap && mondoExpansionStats && (
                  <MondoExpansionRecap
                    stats={mondoExpansionStats}
                    highlightLabels={mondoExpansionHighlightLabels}
                    diseaseNamesFromResults={diseaseNamesFromResults}
                  />
                )}
                {isNDEShape(results.head.vars) ? (
                  <NDEResultCards
                    results={results}
                    templateId={templateId}
                    templateLabel={meta.description}
                    emptyMessage={filteredEmptyHint ?? undefined}
                    highlightTerms={formHighlightTerms}
                  />
                ) : (
                  <ResultsTable results={results} highlightTerms={formHighlightTerms} />
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
