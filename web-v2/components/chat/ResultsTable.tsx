"use client";

import React, { useState, useMemo } from "react";
import type { SPARQLResult } from "@/types";

/** GXA experiment ID columns – link to GEO/GXA sample metadata (Phase 5a) */
const GXA_EXPERIMENT_ID_COLUMNS = [
    "experimentId",
    "experiment_id",
    "sampleExperimentId",
    "sampleExperimentIds",
    "experimentIdUp",
    "experimentIdDown",
];

/** Columns containing URIs – make clickable (Phase 5a: gene only; contrast URLs don't resolve). */
const CLICKABLE_URI_COLUMNS = ["gene"];

/** Pipe-separated list columns – truncate with "show more" when long. */
const TRUNCATABLE_LIST_COLUMNS = ["sampleContrastLabels"];

/** GXA contrast label columns – allow wrap so full label is readable (Phase 6). */
const GXA_CONTRAST_LABEL_COLUMNS = [
    "contrastLabel",
    "sampleContrastLabel",
    "contrastLabelUp",
    "contrastLabelDown",
];

/** NDE dataset identifier column – may contain GSE IDs; show GXA/GEO links when GSE (Phase 7). */
const NDE_IDENTIFIER_COLUMN = "identifier";

/** Number of items to show before "show more". */
const INITIAL_VISIBLE_ITEMS = 3;

/** Extract GSE number from a value (e.g. "GSE76" or URL containing GSE76). Returns E-GEOD accession for GXA link. */
function gseToEGeod(value: string): string | null {
    if (!value || typeof value !== "string") return null;
    const match = value.trim().match(/GSE(\d+)/i);
    return match ? `E-GEOD-${match[1]}` : null;
}

/** Extract display value from binding – handles both raw values and SPARQL {type, value} objects. */
function extractCellValue(raw: unknown): string | string[] {
    if (raw == null || raw === "") return "";
    if (Array.isArray(raw)) {
        return raw.map((v) =>
            typeof v === "object" && v != null && "value" in v
                ? String((v as { value: unknown }).value ?? "")
                : String(v)
        );
    }
    if (typeof raw === "object" && "value" in raw) {
        return String((raw as { value: unknown }).value ?? "");
    }
    return String(raw);
}

/** Get metadata URLs for a GXA experiment ID (E-GEOD-*, E-MTAB-*). */
function getMetadataUrls(experimentId: string): { gxa?: string; geo?: string; arrayexpress?: string } {
    if (!experimentId || typeof experimentId !== "string") return {};
    const id = experimentId.trim();
    const urls: { gxa?: string; geo?: string; arrayexpress?: string } = {};
    if (/^E-GEOD-\d+$/i.test(id)) {
        urls.gxa = `https://www.ebi.ac.uk/gxa/experiments/${id}`;
        const geoNum = id.replace(/^E-GEOD-/i, "");
        urls.geo = `https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE${geoNum}`;
    } else if (/^E-MTAB-\d+$/i.test(id)) {
        urls.gxa = `https://www.ebi.ac.uk/gxa/experiments/${id}`;
        urls.arrayexpress = `https://www.ebi.ac.uk/arrayexpress/experiments/${id}`;
    }
    return urls;
}

function isGxaExperimentId(value: string): boolean {
    return /^E-(?:GEOD|MTAB)-\d+$/i.test(String(value || "").trim());
}

interface ResultsTableProps {
    results: SPARQLResult;
    onDownload?: (format: "csv" | "tsv", processedData?: any[]) => void;
}

interface GroupedRow {
    dataset: string;
    [key: string]: string | string[]; // Other fields, with entity fields as arrays
}

export function ResultsTable({ results, onDownload }: ResultsTableProps) {
    // All hooks must be called unconditionally at the top - BEFORE any early returns
    const [sortColumn, setSortColumn] = useState<string | null>(null);
    const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");
    const [groupByDataset, setGroupByDataset] = useState(false);
    const [expandedCells, setExpandedCells] = useState<Set<string>>(new Set());

    function toggleExpanded(cellKey: string) {
        setExpandedCells((prev) => {
            const next = new Set(prev);
            if (next.has(cellKey)) next.delete(cellKey);
            else next.add(cellKey);
            return next;
        });
    }

    // Compute values safely for useMemo dependencies (even if results is empty)
    const vars = results?.head?.vars || [];
    const bindings = results?.results?.bindings || [];
    const hasDatasetColumn = vars.includes("dataset");
    const entityColumns = vars.filter(v =>
        v === "diseaseName" || v === "speciesName" || v === "drugName" ||
        (v.endsWith("Name") && v !== "name" && v !== "datasetName")
    );
    const gxaExperimentIdColumns = vars.filter(v => GXA_EXPERIMENT_ID_COLUMNS.includes(v));
    const clickableUriColumns = vars.filter(v => CLICKABLE_URI_COLUMNS.includes(v));
    const truncatableListColumns = vars.filter(v => TRUNCATABLE_LIST_COLUMNS.includes(v));
    const gxaContrastLabelColumns = vars.filter(v => GXA_CONTRAST_LABEL_COLUMNS.includes(v));
    const hasIdentifierColumn = vars.includes(NDE_IDENTIFIER_COLUMN);

    // Group results by dataset if enabled and dataset column exists
    // This hook must be called unconditionally (even if bindings is empty)
    const processedBindings = useMemo(() => {
        if (bindings.length === 0) {
            return [];
        }
        if (!groupByDataset || !hasDatasetColumn) {
            // No grouping - return original bindings (use extractCellValue for robustness)
            return bindings.map(b => {
                const row: any = {};
                vars.forEach(v => {
                    row[v] = extractCellValue(b[v]);
                });
                return row;
            });
        }

        // Group by dataset
        const grouped = new Map<string, GroupedRow>();

        bindings.forEach(binding => {
            const datasetValue = binding.dataset?.value || "";
            if (!datasetValue) {
                // Skip if no dataset value
                return;
            }

            if (!grouped.has(datasetValue)) {
                // Create new grouped row
                const row: GroupedRow = { dataset: datasetValue };
                vars.forEach(v => {
                    if (v === "dataset") {
                        row[v] = datasetValue;
                    } else if (entityColumns.includes(v)) {
                        // Entity columns become arrays
                        const value = extractCellValue(binding[v]);
                        const str = Array.isArray(value) ? value[0] : value;
                        row[v] = str ? [str] : [];
                    } else {
                        // Other columns keep single value (use first occurrence)
                        row[v] = extractCellValue(binding[v]);
                    }
                });
                grouped.set(datasetValue, row);
            } else {
                // Add to existing grouped row
                const row = grouped.get(datasetValue)!;
                if (entityColumns.length > 0) {
                    // Only consolidate entity columns if they exist
                    entityColumns.forEach(v => {
                        const extracted = extractCellValue(binding[v]);
                        const value = Array.isArray(extracted) ? extracted[0] : extracted;
                        if (value) {
                            const existing = row[v] as string[];
                            if (!existing.includes(value)) {
                                existing.push(value);
                            }
                        }
                    });
                }
                // For non-entity columns, we keep the first value (already set)
            }
        });

        return Array.from(grouped.values());
    }, [bindings, groupByDataset, hasDatasetColumn, entityColumns, vars]);

    // Sort processed bindings if sort column is set
    const sortedBindings = [...processedBindings].sort((a, b) => {
        if (!sortColumn) return 0;

        const aVal = Array.isArray(a[sortColumn])
            ? (a[sortColumn] as string[]).join(", ")
            : String(a[sortColumn] || "");
        const bVal = Array.isArray(b[sortColumn])
            ? (b[sortColumn] as string[]).join(", ")
            : String(b[sortColumn] || "");

        const comparison = aVal.localeCompare(bVal);
        return sortDirection === "asc" ? comparison : -comparison;
    });

    function handleSort(column: string) {
        if (sortColumn === column) {
            setSortDirection(sortDirection === "asc" ? "desc" : "asc");
        } else {
            setSortColumn(column);
            setSortDirection("asc");
        }
    }

    function formatValue(value: string | string[] | undefined): string {
        if (!value) return "";
        if (Array.isArray(value)) {
            return value.join(", ");
        }
        return String(value);
    }

    function formatValueForDisplay(value: string | string[] | undefined): React.ReactNode {
        if (!value) return "";
        if (Array.isArray(value)) {
            if (value.length === 0) return "";
            if (value.length === 1) return value[0];
            // Show as badges for multiple values
            return (
                <div className="flex flex-wrap gap-1">
                    {value.map((v, idx) => (
                        <span
                            key={idx}
                            className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-accent/10 text-accent border border-accent/20"
                        >
                            {v}
                        </span>
                    ))}
                </div>
            );
        }
        return String(value);
    }

    /** Render experiment ID with links to GXA/GEO metadata (Phase 5a). Truncates with "show more" when long. */
    function renderExperimentIdCell(varName: string, rawValue: unknown, cellKey: string): React.ReactNode {
        const value = extractCellValue(rawValue);
        if (!value) return "";
        const raw = Array.isArray(value) ? value : [value];
        const ids = raw.flatMap((v) =>
            typeof v === "string" && v.includes(" | ")
                ? v.split(/\s*\|\s*/).map((s) => s.trim()).filter(Boolean)
                : [v]
        );
        const validIds = ids.filter((v): v is string => Boolean(typeof v === "string" && v && isGxaExperimentId(v)));
        if (validIds.length === 0) return formatValueForDisplay(value);

        const isExpanded = expandedCells.has(cellKey);
        const visibleIds =
            validIds.length <= INITIAL_VISIBLE_ITEMS
                ? validIds
                : isExpanded
                  ? validIds
                  : validIds.slice(0, INITIAL_VISIBLE_ITEMS);
        const hiddenCount = validIds.length - visibleIds.length;

        const linkClass =
            "inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-accent/20 text-accent hover:bg-accent/30 hover:underline border border-accent/40";

        return (
            <div className="flex flex-col gap-1">
                {visibleIds.map((id, idx) => {
                    const urls = getMetadataUrls(id);
                    const hasLinks = urls.gxa || urls.geo || urls.arrayexpress;
                    return (
                        <div key={idx} className="flex flex-wrap items-center gap-1.5">
                            <span className="font-mono text-xs">{id}</span>
                            {hasLinks && (
                                <span className="flex gap-1 flex-wrap">
                                    {urls.gxa && (
                                        <a
                                            href={urls.gxa}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className={linkClass}
                                            title="View sample metadata in Expression Atlas"
                                        >
                                            GXA ↗
                                        </a>
                                    )}
                                    {urls.geo && (
                                        <a
                                            href={urls.geo}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className={linkClass}
                                            title="View sample metadata in GEO"
                                        >
                                            GEO ↗
                                        </a>
                                    )}
                                    {urls.arrayexpress && (
                                        <a
                                            href={urls.arrayexpress}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className={linkClass}
                                            title="View sample metadata in ArrayExpress"
                                        >
                                            AE ↗
                                        </a>
                                    )}
                                </span>
                            )}
                        </div>
                    );
                })}
                {validIds.length > INITIAL_VISIBLE_ITEMS && (
                    <button
                        type="button"
                        onClick={() => toggleExpanded(cellKey)}
                        className="text-xs text-accent hover:underline text-left"
                    >
                        {isExpanded ? "Show less" : `Show ${validIds.length - INITIAL_VISIBLE_ITEMS} more`}
                    </button>
                )}
            </div>
        );
    }

    /** Render pipe-separated list with truncate + "show more" (e.g. sampleContrastLabels). */
    function renderTruncatableListCell(varName: string, rawValue: unknown, cellKey: string): React.ReactNode {
        const value = extractCellValue(rawValue);
        if (!value) return "";
        const raw = Array.isArray(value) ? value : [value];
        const items = raw.flatMap((v) =>
            typeof v === "string" && v.includes(" | ")
                ? v.split(/\s*\|\s*/).map((s) => s.trim()).filter(Boolean)
                : [v]
        ).filter((v): v is string => Boolean(typeof v === "string" && v));
        if (items.length === 0) return "";

        const isExpanded = expandedCells.has(cellKey);
        const visibleItems =
            items.length <= INITIAL_VISIBLE_ITEMS
                ? items
                : isExpanded
                  ? items
                  : items.slice(0, INITIAL_VISIBLE_ITEMS);
        const hiddenCount = items.length - visibleItems.length;

        return (
            <div className="flex flex-col gap-0.5">
                {visibleItems.map((item, idx) => (
                    <span key={idx} className="text-xs">
                        {item}
                    </span>
                ))}
                {items.length > INITIAL_VISIBLE_ITEMS && (
                    <button
                        type="button"
                        onClick={() => toggleExpanded(cellKey)}
                        className="text-xs text-accent hover:underline text-left"
                    >
                        {isExpanded ? "Show less" : `Show ${items.length - INITIAL_VISIBLE_ITEMS} more`}
                    </button>
                )}
            </div>
        );
    }

    /** Render NDE identifier cell: when value is or contains GSE ID, show GXA/GEO links (Phase 7 NDE↔GXA bridge). */
    function renderIdentifierCell(rawValue: unknown): React.ReactNode {
        const value = extractCellValue(rawValue);
        if (!value) return "";
        const raw = Array.isArray(value) ? value : [value];
        const strValues = raw
            .map((v) => (typeof v === "string" ? v : String(v)))
            .filter(Boolean);
        const eGeod = strValues.map((s) => gseToEGeod(s)).find(Boolean);
        const displayText = strValues.join(", ");
        if (!eGeod) {
            return <span className="text-xs">{displayText || ""}</span>;
        }
        const gxaUrl = `https://www.ebi.ac.uk/gxa/experiments/${eGeod}`;
        const geoNum = eGeod.replace(/^E-GEOD-/i, "");
        const geoUrl = `https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE${geoNum}`;
        const linkClass =
            "inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-accent/20 text-accent hover:bg-accent/30 hover:underline border border-accent/40";
        return (
            <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-xs">{displayText}</span>
                <a href={gxaUrl} target="_blank" rel="noopener noreferrer" className={linkClass} title="View expression data in Expression Atlas">
                    GXA ↗
                </a>
                <a href={geoUrl} target="_blank" rel="noopener noreferrer" className={linkClass} title="View in GEO">
                    GEO ↗
                </a>
            </div>
        );
    }

    /** Render gene/contrast URI as clickable link (Phase 5a). */
    function renderUriCell(rawValue: unknown): React.ReactNode {
        const value = extractCellValue(rawValue);
        if (!value) return "";
        const uris = Array.isArray(value) ? value : [value];
        const validUris = uris.filter((v): v is string => Boolean(typeof v === "string" && v && /^https?:\/\//.test(v)));
        if (validUris.length === 0) return formatValueForDisplay(value);

        const linkClass = "inline-flex items-center text-xs text-accent hover:underline";

        return (
            <div className="flex flex-col gap-0.5">
                {validUris.map((uri, idx) => {
                    const shortLabel = uri.includes("identifiers.org/ensembl")
                        ? uri.split("/").pop() || uri
                        : uri.includes("ncbi.nlm.nih.gov/gene")
                            ? "NCBI Gene " + (uri.match(/\/(\d+)$/)?.[1] || "")
                            : uri.replace(/^https?:\/\//, "").split("/").pop() || uri;
                    return (
                        <a
                            key={idx}
                            href={uri}
                            target="_blank"
                            rel="noopener noreferrer"
                            className={`${linkClass} max-w-full truncate`}
                            title={uri}
                        >
                            {shortLabel} ↗
                        </a>
                    );
                })}
            </div>
        );
    }

    // Early return check AFTER all hooks are called
    if (!results || !results.results || results.results.bindings.length === 0) {
        return (
            <div className="text-center py-8 text-slate-600 dark:text-slate-400">
                No results to display
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* Header with controls */}
            <div className="flex justify-between items-center gap-2">
                {/* Group by dataset toggle */}
                {hasDatasetColumn && (
                    <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300 cursor-pointer">
                        <input
                            type="checkbox"
                            checked={groupByDataset}
                            onChange={(e) => setGroupByDataset(e.target.checked)}
                            className="w-4 h-4 text-accent rounded border-slate-300 dark:border-slate-600 focus:ring-accent focus:ring-2"
                        />
                        <span>Group by dataset</span>
                    </label>
                )}

                {/* Download button */}
                {onDownload && (
                    <button
                        onClick={() => onDownload("tsv", processedBindings)}
                        className="px-3 py-1.5 text-sm bg-slate-700 dark:bg-slate-700 hover:bg-slate-600 dark:hover:bg-slate-600 text-white rounded border border-slate-600 dark:border-slate-600 transition-colors"
                    >
                        Download TSV
                    </button>
                )}
            </div>

            {/* Table */}
            <div className="overflow-x-auto border border-slate-300 dark:border-slate-700 rounded-lg">
                <table className="w-full text-sm">
                    <thead className="bg-slate-100 dark:bg-slate-800 border-b border-slate-300 dark:border-slate-700">
                        <tr>
                            {vars.map((varName) => (
                                <th
                                    key={varName}
                                    className="px-4 py-2 text-left font-semibold text-slate-900 dark:text-slate-300 cursor-pointer hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                                    onClick={() => handleSort(varName)}
                                >
                                    <div className="flex items-center gap-2">
                                        <span>{varName}</span>
                                        {sortColumn === varName && (
                                            <span className="text-xs">
                                                {sortDirection === "asc" ? "↑" : "↓"}
                                            </span>
                                        )}
                                    </div>
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 dark:divide-slate-700 bg-white dark:bg-slate-900">
                        {sortedBindings.map((binding, idx) => (
                            <tr
                                key={idx}
                                className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                            >
                                {vars.map((varName) => {
                                    const value = binding[varName];
                                    const isEntityColumn = entityColumns.includes(varName);
                                    const isGxaExperimentColumn = gxaExperimentIdColumns.includes(varName);
                                    const isUriColumn = clickableUriColumns.includes(varName);
                                    const isTruncatableListColumn = truncatableListColumns.includes(varName);
                                    const isContrastLabelColumn = gxaContrastLabelColumns.includes(varName);
                                    const isIdentifierColumn = varName === NDE_IDENTIFIER_COLUMN && hasIdentifierColumn;
                                    const displayValue = formatValueForDisplay(value);
                                    const titleText = formatValue(value);
                                    const cellKey = `${idx}-${varName}`;

                                    return (
                                        <td
                                            key={varName}
                                            className={`px-4 py-2 text-slate-900 dark:text-slate-300 ${isEntityColumn && Array.isArray(value) && value.length > 1 ? "" : ""}`}
                                        >
                                            {isGxaExperimentColumn ? (
                                                <div className="max-w-md" title={titleText}>
                                                    {renderExperimentIdCell(varName, value, cellKey)}
                                                </div>
                                            ) : isTruncatableListColumn ? (
                                                <div className="max-w-md" title={titleText}>
                                                    {renderTruncatableListCell(varName, value, cellKey)}
                                                </div>
                                            ) : isUriColumn ? (
                                                <div className="max-w-md" title={titleText}>
                                                    {renderUriCell(value)}
                                                </div>
                                            ) : isIdentifierColumn ? (
                                                <div className="max-w-md" title={titleText}>
                                                    {renderIdentifierCell(value)}
                                                </div>
                                            ) : isContrastLabelColumn ? (
                                                <div className="max-w-md break-words" title={titleText}>
                                                    {displayValue}
                                                </div>
                                            ) : isEntityColumn && Array.isArray(value) && value.length > 1 ? (
                                                <div className="max-w-md" title={titleText}>
                                                    {displayValue}
                                                </div>
                                            ) : (
                                                <div className="max-w-md truncate" title={titleText}>
                                                    {displayValue}
                                                </div>
                                            )}
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Footer with row count */}
            <div className="text-xs text-slate-600 dark:text-slate-400 text-center space-y-1">
                <div>Showing {sortedBindings.length} result{sortedBindings.length !== 1 ? "s" : ""}</div>
            </div>
        </div>
    );
}

