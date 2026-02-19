"use client";

import React, { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import type { ContextPack } from "@/lib/context-packs/types";
import type { SPARQLResult } from "@/types";
import { SlotForm, isSlotFilled, getSlotMeta } from "@/components/dashboard/SlotForm";
import { NDEResultCards } from "@/components/dashboard/NDEResultCards";
import { ResultsTable } from "@/components/chat/ResultsTable";
import { getTemplateMeta } from "@/lib/landing/template-meta";
import { runTemplateQuery, isNDEShape, PACK_ID } from "@/lib/dashboard/run-query";
import { Info } from "lucide-react";

export default function TemplatePage() {
  const params = useParams();
  const templateId = typeof params.templateId === "string" ? params.templateId : "";

  const [pack, setPack] = useState<ContextPack | null>(null);
  const [packError, setPackError] = useState<string | null>(null);
  const [slotValues, setSlotValues] = useState<Record<string, string | string[]>>({});
  const [results, setResults] = useState<SPARQLResult | null>(null);
  const [resultsError, setResultsError] = useState<string | null>(null);
  const [filteredEmptyHint, setFilteredEmptyHint] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const runningRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/tools/context/packs/${PACK_ID}`)
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

  const template = pack?.templates?.find((t) => t.id === templateId) ?? null;
  const meta = getTemplateMeta(templateId);

  const runQuery = useCallback(async () => {
    if (!pack || !template) return;
    if (runningRef.current) return;
    runningRef.current = true;
    setResultsError(null);
    setResults(null);
    setFilteredEmptyHint(null);
    setLoading(true);
    abortRef.current = new AbortController();
    const signal = abortRef.current.signal;

    try {
      const { results: res, error: err, filteredEmptyHint: hint } = await runTemplateQuery({
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
        return;
      }
      setResults(res);
      setFilteredEmptyHint(hint ?? null);
    } catch (e: unknown) {
      if (signal.aborted) return;
      const isAbort =
        (e instanceof Error && e.name === "AbortError") ||
        (typeof (e as { name?: string })?.name === "string" && (e as { name: string }).name === "AbortError");
      setResultsError(isAbort ? "Query was cancelled." : (e instanceof Error ? e.message : String((e as Error)?.message ?? "Unknown error")));
      setResults(null);
    } finally {
      setLoading(false);
      abortRef.current = null;
      runningRef.current = false;
    }
  }, [pack, template, templateId, slotValues]);

  const handleSlotChange = useCallback((values: Record<string, string | string[]>) => {
    setSlotValues(values);
  }, []);

  const required = template?.required_slots ?? [];
  const optional = template?.optional_slots ?? [];
  const missingRequired = required.filter((slot) => !isSlotFilled(slotValues[slot]));
  const canRun = missingRequired.length === 0;
  const hasOptional = optional.length > 0;

  if (packError) {
    return (
      <div className="p-6 max-w-5xl mx-auto" style={{ backgroundColor: "var(--niaid-page-bg)" }}>
        <p className="text-red-600 dark:text-red-400">{packError}</p>
        <Link href="/" className="mt-4 inline-block text-sm text-niaid-link hover:underline">
          ← Back to templates
        </Link>
      </div>
    );
  }

  if (!pack) {
    return (
      <div className="p-6 max-w-5xl mx-auto flex items-center justify-center min-h-[200px]" style={{ backgroundColor: "var(--niaid-page-bg)" }}>
        <p className="text-slate-600 dark:text-slate-400">Loading…</p>
      </div>
    );
  }

  if (!template || !meta) {
    return (
      <div className="p-6 max-w-5xl mx-auto" style={{ backgroundColor: "var(--niaid-page-bg)" }}>
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
      className="min-h-[calc(100vh-80px)] flex flex-col p-6"
      style={{ backgroundColor: "var(--niaid-page-bg)" }}
    >
      <div className="max-w-5xl mx-auto w-full space-y-6">
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
                  {template.description}
                </h1>
                {meta.blurb && (
                  <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                    {meta.blurb}
                  </p>
                )}
              </div>
            </div>

            <SlotForm
              template={template}
              values={slotValues}
              onChange={handleSlotChange}
              disabled={loading}
            />

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

            {hasOptional && (
              <p className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                <Info className="w-4 h-4 flex-shrink-0" aria-hidden />
                Tip: Leave optional fields blank to see all results.
              </p>
            )}
          </div>
        </div>

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
                {isNDEShape(results.head.vars) ? (
                  <NDEResultCards
                    results={results}
                    templateId={templateId}
                    templateLabel={template.description}
                    emptyMessage={filteredEmptyHint ?? undefined}
                  />
                ) : (
                  <ResultsTable results={results} />
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
