"use client";

import React, { useState, useEffect } from "react";
import type { SPARQLResult } from "@/types";
import { Pagination, DEFAULT_PAGE_SIZE } from "./Pagination";

const NIAID_RESOURCE_BASE = "https://data.niaid.nih.gov/resources?id=";

/** NIAID portal accepts study ids like sdy1, sdy112 (ImmPort). */
const NIAID_STUDY_ID_PATTERN = /^(SDY\d+)$/i;
/** NDE also accepts GEO accessions as resource id (e.g. GSE1000 → resources?id=gse1000). */
const NDE_GEO_ID_PATTERN = /^GSE\d+$/i;

/**
 * Extract the NIAID Data Discovery Portal resource id.
 * We only use values that are clearly study ids (e.g. SDY1) or from a NIAID URL.
 * We do NOT use arbitrary dataset IRI path segments (e.g. m38y09r3r9) as that is an internal id.
 */
function toNIAIDResourceId(identifier: string): string | null {
  if (!identifier || typeof identifier !== "string") return null;
  const s = identifier.trim();
  if (NIAID_STUDY_ID_PATTERN.test(s)) return s.toLowerCase();
  try {
    const url = s.startsWith("http") ? new URL(s) : new URL(`https://example.com/${s}`);
    const idParam = url.searchParams.get("id");
    if (idParam && NIAID_STUDY_ID_PATTERN.test(idParam)) return idParam.toLowerCase();
    const segment = url.pathname.replace(/\/$/, "").split("/").pop();
    if (segment && NIAID_STUDY_ID_PATTERN.test(segment)) return segment.toLowerCase();
  } catch {
    // not a URL
  }
  return null;
}

/** Extract string value from a SPARQL binding value (object with type/value or raw). */
function bindingValue(raw: { type: string; value: string } | undefined): string {
  if (!raw) return "";
  if (typeof raw === "object" && "value" in raw) return String(raw.value ?? "");
  return String(raw);
}

/**
 * Build NIAID Data Discovery Portal (NDE) resource URL.
 * Accepts SDY ids (e.g. sdy1) and GEO accessions (e.g. GSE1000 → id=gse1000).
 * See https://data.niaid.nih.gov/resources?id=gse1000
 */
function getNDEResourceUrl(identifier: string, datasetUri?: string): string | null {
  const idFromIdentifier = toNIAIDResourceId(identifier) || (datasetUri ? toNIAIDResourceId(datasetUri) : null);
  if (idFromIdentifier) return `${NIAID_RESOURCE_BASE}${encodeURIComponent(idFromIdentifier)}`;
  // NDE portal also uses GEO accession as resource id (lowercase, e.g. gse1000)
  const geoId = identifier?.trim();
  if (geoId && NDE_GEO_ID_PATTERN.test(geoId))
    return `${NIAID_RESOURCE_BASE}${encodeURIComponent(geoId.toLowerCase())}`;
  const geoIdFromUri = datasetUri?.trim();
  if (geoIdFromUri && NDE_GEO_ID_PATTERN.test(geoIdFromUri))
    return `${NIAID_RESOURCE_BASE}${encodeURIComponent(geoIdFromUri.toLowerCase())}`;
  return null;
}

/** True if URL looks like the NIAID Data Ecosystem / NDE portal (e.g. data.niaid.nih.gov). */
function isNDEPortalUrl(url: string): boolean {
  if (!url || typeof url !== "string") return false;
  try {
    const u = new URL(url.trim());
    return u.hostname === "data.niaid.nih.gov" || u.hostname.endsWith(".niaid.nih.gov");
  } catch {
    return false;
  }
}

/**
 * Find first NDE portal URL in space-separated binding values (urls, sameAsList, owlSameAsList).
 * NDE query returns GROUP_CONCAT so these are space-separated lists.
 */
function findNDEUrlInBindingLists(urlsStr: string, sameAsStr: string, owlSameAsStr: string): string | null {
  const combined = [urlsStr, sameAsStr, owlSameAsStr].filter(Boolean).join(" ");
  if (!combined.trim()) return null;
  const candidates = combined.trim().split(/\s+/);
  return candidates.find((s) => isNDEPortalUrl(s)) ?? null;
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
  /** Shown when there are no bindings (e.g. "only gene expression" filter returned empty). */
  emptyMessage?: string;
}

export function NDEResultCards({
  results,
  templateId,
  templateLabel,
  emptyMessage,
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
      <div className="text-center py-8 text-slate-600 dark:text-slate-400 space-y-2">
        <p>{emptyMessage ?? "No results to display"}</p>
      </div>
    );
  }

  const resultLabel = templateLabel || templateId || "Results";

  /** Vars to show as metadata tags (exclude name, description, identifier, hasGeneExpression, GXA/SPOKE-GeneLab link vars). */
  const metadataVars = vars.filter(
    (v) =>
      v !== "dataset" &&
      v !== "identifier" &&
      v !== "name" &&
      v !== "description" &&
      v !== "title" &&
      v !== "hasGeneExpression" &&
      v !== "gxaExperimentId" &&
      v !== "gxaContrastCount" &&
      v !== "gxaSampleContrastLabel" &&
      v !== "spokeGenelabStudyUrl" &&
      v !== "urls" &&
      v !== "sameAsList" &&
      v !== "owlSameAsList"
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
        const datasetUri = bindingValue(row.dataset);
        const urlsStr = bindingValue(row.urls);
        const sameAsStr = bindingValue(row.sameAsList);
        const owlSameAsStr = bindingValue(row.owlSameAsList);
        const ndeUrlFromId = getNDEResourceUrl(identifier, datasetUri);
        const ndeUrlFromLists = findNDEUrlInBindingLists(urlsStr, sameAsStr, owlSameAsStr);
        const ndeUrl = ndeUrlFromId ?? ndeUrlFromLists ?? null;
        const eGeod = identifier ? gseToEGeod(identifier) : null;
        const hasGeneExpression =
          bindingValue(row.hasGeneExpression) === "true" || (eGeod != null);
        const gxaContrastCount = bindingValue(row.gxaContrastCount);
        const gxaSampleContrastLabel = bindingValue(row.gxaSampleContrastLabel);
        const geoUrl = eGeod
          ? `https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE${eGeod.replace(/^E-GEOD-/i, "")}`
          : null;

        const isDescExpanded = expandedDescriptions.has(globalIndex);
        const isMetaExpanded = showAllMetadata.has(globalIndex);

        const titleDisplay = name || identifier || "Untitled";
        // Title links only to NDE when we have an NDE portal URL; no GEO fallback (GEO has its own badge).
        const titleHref = ndeUrl ?? undefined;

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

              {/* Gene expression badge + View resource (NIAID portal) + GXA/GEO/SPOKE-GeneLab */}
              <div className="flex flex-wrap items-center justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                {hasGeneExpression && (
                  <span
                    className="inline-flex items-center px-2.5 py-1 rounded text-xs font-medium bg-emerald-100 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-200 border border-emerald-300 dark:border-emerald-700"
                    title="Dataset has gene expression data (GXA/NCBI GEO)"
                  >
                    Gene expression{gxaContrastCount ? ` (${gxaContrastCount} contrast${gxaContrastCount === "1" ? "" : "s"})` : ""}
                  </span>
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
                {ndeUrl && (
                  <a
                    href={ndeUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-white text-sm font-medium hover:opacity-90 transition-opacity shrink-0"
                    style={{ backgroundColor: "var(--niaid-pagination-active)" }}
                    title="View on NIAID Data Discovery Portal"
                  >
                    View resource &#8594;
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
