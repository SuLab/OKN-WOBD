"use client";

import React from "react";
import type { MondoExpansionStats } from "@/lib/ontology/mondo-descendants-ols";

function labelsFoundInDiseaseColumn(
  highlightLabels: string[],
  diseaseTexts: string[]
): string[] {
  if (highlightLabels.length === 0 || diseaseTexts.length === 0) return [];
  const haystack = diseaseTexts.join("; ").toLowerCase();
  const seen = new Set<string>();
  const out: string[] = [];
  for (const label of highlightLabels) {
    const t = label.trim();
    if (t.length < 2) continue;
    const k = t.toLowerCase();
    if (haystack.includes(k) && !seen.has(k)) {
      seen.add(k);
      out.push(t);
      if (out.length >= 12) break;
    }
  }
  return out;
}

export interface MondoExpansionRecapProps {
  stats: MondoExpansionStats;
  /** Full OLS highlight list (intersected with result `diseaseNames` text). */
  highlightLabels: string[];
  /** Per-row `diseaseNames` binding values (or empty). */
  diseaseNamesFromResults: string[];
}

/**
 * Summary when “Include MONDO subclasses” added IRIs via OLS (trust + debugging).
 */
export function MondoExpansionRecap({
  stats,
  highlightLabels,
  diseaseNamesFromResults,
}: MondoExpansionRecapProps) {
  const inResults = labelsFoundInDiseaseColumn(highlightLabels, diseaseNamesFromResults);
  const applied =
    stats.appliedToSparqlFilter !== false;

  return (
    <div
      className="mb-4 rounded-lg border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-800/60 px-3 py-2.5 text-sm text-slate-800 dark:text-slate-200"
      role="region"
      aria-label="MONDO subclass expansion summary"
    >
      <p className="font-semibold text-slate-900 dark:text-slate-100">MONDO subclass expansion</p>
      <ul className="mt-1.5 list-disc pl-5 space-y-1">
        <li>
          {stats.rootsExpanded} root term{stats.rootsExpanded === 1 ? "" : "s"} expanded →{" "}
          <strong>{stats.mondoIrisInFilter}</strong> distinct MONDO IRIs collected (cap{" "}
          <strong>{stats.iriCap}</strong>).
          {stats.truncated && (
            <span className="text-amber-800 dark:text-amber-200 font-medium">
              {" "}
              List may be truncated (cap or OLS pagination).
            </span>
          )}
        </li>
        <li>
          <strong>{stats.highlightLabelCount}</strong> OLS labels kept for highlighting (cap{" "}
          {stats.highlightLabelCap}).
        </li>
        {inResults.length > 0 && (
          <li>
            <span className="text-slate-600 dark:text-slate-400">
              Subclass labels that appear in result health metadata:{" "}
            </span>
            <span className="text-slate-800 dark:text-slate-200">{inResults.join("; ")}</span>
          </li>
        )}
      </ul>
      {!applied && (
        <p className="mt-2 text-xs text-amber-900 dark:text-amber-100 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded px-2 py-1.5">
          This run used keyword matching on dataset names/descriptions; expanded MONDO IRIs were not
          applied in the SPARQL filter. Expansion labels still apply to highlighting where text matches.
        </p>
      )}
    </div>
  );
}
