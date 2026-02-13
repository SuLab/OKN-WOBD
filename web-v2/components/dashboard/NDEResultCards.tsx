"use client";

import React, { useState, useEffect } from "react";
import type { SPARQLResult } from "@/types";
import { Pagination, DEFAULT_PAGE_SIZE } from "./Pagination";

const NIAID_RESOURCE_BASE = "https://data.niaid.nih.gov/resources?id=";

/** NDE resource ID patterns (e.g. ImmPort SDY). */
const NDE_ID_PATTERN = /^(SDY\d+)$/i;

/** Extract string value from a SPARQL binding value (object with type/value or raw). */
function bindingValue(raw: { type: string; value: string } | undefined): string {
  if (!raw) return "";
  if (typeof raw === "object" && "value" in raw) return String(raw.value ?? "");
  return String(raw);
}

/** Whether the identifier is an NDE resource ID (e.g. ImmPort SDY). */
function isNDEResourceId(value: string): boolean {
  if (!value || typeof value !== "string") return false;
  return NDE_ID_PATTERN.test(value.trim());
}

/** Build NDE resource URL (lowercase id). */
function getNDEResourceUrl(identifier: string): string {
  const id = String(identifier).trim().toLowerCase();
  return `${NIAID_RESOURCE_BASE}${encodeURIComponent(id)}`;
}

/** Extract GSE number for GXA/GEO links. */
function gseToEGeod(value: string): string | null {
  if (!value || typeof value !== "string") return null;
  const match = value.trim().match(/GSE(\d+)/i);
  return match ? `E-GEOD-${match[1]}` : null;
}

/** Map binding var names to NDE-style metadata labels and tag color classes. */
const METADATA_LABELS: Record<string, { label: string; tagClass: string }> = {
  diseaseName: { label: "Health Condition", tagClass: "bg-niaid-tagHealthCondition text-gray-800" },
  speciesName: { label: "Species", tagClass: "bg-niaid-tagSpecies text-gray-800" },
  drugName: { label: "Drug", tagClass: "bg-niaid-tagFunding text-gray-800" },
  name: { label: "Name", tagClass: "bg-niaid-tagTopic text-gray-700" },
};

const DEFAULT_TAG_CLASS = "bg-niaid-tagTopic text-gray-700";

interface NDEResultCardsProps {
  results: SPARQLResult;
  templateId?: string;
  templateLabel?: string;
}

export function NDEResultCards({
  results,
  templateId,
  templateLabel,
}: NDEResultCardsProps) {
  const bindings = results?.results?.bindings ?? [];
  const vars = results?.head?.vars ?? [];

  const [expandedDescriptions, setExpandedDescriptions] = useState<Set<number>>(new Set());
  const [showAllMetadata, setShowAllMetadata] = useState<Set<number>>(new Set());
  const [page, setPage] = useState(1);
  const [pageSize] = useState(DEFAULT_PAGE_SIZE);

  useEffect(() => {
    setPage(1);
  }, [results]);

  if (bindings.length === 0) {
    return (
      <div className="text-center py-8 text-slate-600 dark:text-slate-400">
        No results to display
      </div>
    );
  }

  const resultLabel = templateLabel || templateId || "Results";

  /** Vars to show as metadata tags (exclude name, description, identifier used for title/desc/link). */
  const metadataVars = vars.filter(
    (v) => v !== "dataset" && v !== "identifier" && v !== "name" && v !== "description"
  );

  const totalItems = bindings.length;
  const paginatedBindings = bindings.slice((page - 1) * pageSize, page * pageSize);
  const showPagination = totalItems > pageSize;

  return (
    <div className="space-y-4" role="list" aria-label="Query results">
      <p className="text-sm text-slate-600 dark:text-slate-400" aria-live="polite">
        {showPagination
          ? `${resultLabel} (Showing ${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, totalItems)} of ${totalItems} results)`
          : `${resultLabel} (${totalItems} ${totalItems === 1 ? "result" : "results"})`}
      </p>
      {paginatedBindings.map((row, index) => {
        const globalIndex = (page - 1) * pageSize + index;
        const name = bindingValue(row.name) || bindingValue(row.title);
        const description = bindingValue(row.description);
        const identifier = bindingValue(row.identifier);
        const hasNDEId = isNDEResourceId(identifier);
        const ndeUrl = hasNDEId ? getNDEResourceUrl(identifier) : null;
        const eGeod = identifier ? gseToEGeod(identifier) : null;
        const gxaUrl = eGeod ? `https://www.ebi.ac.uk/gxa/experiments/${eGeod}` : null;
        const geoUrl = eGeod
          ? `https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE${eGeod.replace(/^E-GEOD-/i, "")}`
          : null;

        const isDescExpanded = expandedDescriptions.has(globalIndex);
        const isMetaExpanded = showAllMetadata.has(globalIndex);

        const titleDisplay = name || identifier || "Untitled";
        const titleHref = ndeUrl ?? (gxaUrl ? gxaUrl : undefined);

        return (
          <article
            key={globalIndex}
            className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm overflow-hidden"
            role="listitem"
          >
            {/* Header bar */}
            <div
              className="px-4 py-2 flex items-center justify-between"
              style={{ backgroundColor: "var(--niaid-header)" }}
            >
              <div className="flex items-center gap-2">
                <span className="text-white font-semibold text-sm">DATASET</span>
                <span className="text-white/90 text-xs">NIAID</span>
              </div>
              <span className="text-white/80 text-xs" aria-hidden="true">
                &#8250;
              </span>
            </div>

            <div className="p-4 space-y-3">
              {/* Title */}
              {titleHref ? (
                <h3 className="text-lg font-semibold">
                  <a
                    href={titleHref}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-niaid-link hover:underline"
                  >
                    {titleDisplay}
                  </a>
                </h3>
              ) : (
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                  {titleDisplay}
                </h3>
              )}

              {/* Description */}
              {description && (
                <div className="text-sm text-gray-700 dark:text-gray-300">
                  {description.length > 300 && !isDescExpanded ? (
                    <>
                      <p>{description.slice(0, 300)}...</p>
                      <button
                        type="button"
                        onClick={() =>
                          setExpandedDescriptions((prev) => {
                            const next = new Set(prev);
                            next.add(globalIndex);
                            return next;
                          })
                        }
                        className="text-niaid-link hover:underline text-xs mt-1"
                      >
                        Show more
                      </button>
                    </>
                  ) : (
                    <p>{description}</p>
                  )}
                </div>
              )}

              {/* Metadata tags */}
              {metadataVars.length > 0 && (
                <div className="flex flex-wrap gap-2 items-center">
                  {(isMetaExpanded ? metadataVars : metadataVars.slice(0, 5)).map((v) => {
                    const val = bindingValue(row[v]);
                    if (val === "" || val === name) return null;
                    const { label, tagClass } = METADATA_LABELS[v] ?? {
                      label: v,
                      tagClass: DEFAULT_TAG_CLASS,
                    };
                    return (
                      <span
                        key={v}
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${tagClass}`}
                      >
                        {label}: {val}
                      </span>
                    );
                  })}
                  {metadataVars.length > 5 && !isMetaExpanded && (
                    <button
                      type="button"
                      onClick={() =>
                        setShowAllMetadata((prev) => {
                          const next = new Set(prev);
                          next.add(globalIndex);
                          return next;
                        })
                      }
                      className="text-niaid-link hover:underline text-xs"
                    >
                      Show metadata +
                    </button>
                  )}
                </div>
              )}

              {/* View resource / GXA-GEO */}
              <div className="flex flex-wrap gap-2 pt-2">
                {ndeUrl && (
                  <a
                    href={ndeUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 px-4 py-2 rounded-md text-white text-sm font-medium hover:opacity-90 transition-opacity"
                    style={{ backgroundColor: "var(--niaid-button)" }}
                  >
                    View resource &#8594;
                  </a>
                )}
                {gxaUrl && (
                  <a
                    href={gxaUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center px-3 py-1.5 rounded text-xs font-medium bg-niaid-badgeNeutral text-gray-700 hover:bg-slate-200 border border-slate-300"
                  >
                    GXA &#8599;
                  </a>
                )}
                {geoUrl && (
                  <a
                    href={geoUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center px-3 py-1.5 rounded text-xs font-medium bg-niaid-badgeNeutral text-gray-700 hover:bg-slate-200 border border-slate-300"
                  >
                    GEO &#8599;
                  </a>
                )}
              </div>
            </div>
          </article>
        );
      })}
      {showPagination && (
        <div className="flex flex-col items-center gap-2 pt-2">
          <Pagination
            page={page}
            totalItems={totalItems}
            pageSize={pageSize}
            onPageChange={setPage}
            ariaLabel="Results pagination"
          />
        </div>
      )}
    </div>
  );
}
