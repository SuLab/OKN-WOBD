"use client";

import React, { useState, useMemo } from "react";
import type { SPARQLResult } from "@/types";

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

    // Compute values safely for useMemo dependencies (even if results is empty)
    const vars = results?.head?.vars || [];
    const bindings = results?.results?.bindings || [];
    const hasDatasetColumn = vars.includes("dataset");
    const entityColumns = vars.filter(v =>
        v === "diseaseName" || v === "speciesName" || v === "drugName" ||
        (v.endsWith("Name") && v !== "name" && v !== "datasetName")
    );

    // Group results by dataset if enabled and dataset column exists
    // This hook must be called unconditionally (even if bindings is empty)
    const processedBindings = useMemo(() => {
        if (bindings.length === 0) {
            return [];
        }
        if (!groupByDataset || !hasDatasetColumn) {
            // No grouping - return original bindings
            return bindings.map(b => {
                const row: any = {};
                vars.forEach(v => {
                    row[v] = b[v]?.value || "";
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
                        const value = binding[v]?.value || "";
                        row[v] = value ? [value] : [];
                    } else {
                        // Other columns keep single value (use first occurrence)
                        row[v] = binding[v]?.value || "";
                    }
                });
                grouped.set(datasetValue, row);
            } else {
                // Add to existing grouped row
                const row = grouped.get(datasetValue)!;
                if (entityColumns.length > 0) {
                    // Only consolidate entity columns if they exist
                    entityColumns.forEach(v => {
                        const value = binding[v]?.value || "";
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
                                    const displayValue = formatValueForDisplay(value);
                                    const titleText = formatValue(value);

                                    return (
                                        <td
                                            key={varName}
                                            className={`px-4 py-2 text-slate-900 dark:text-slate-300 ${isEntityColumn && Array.isArray(value) && value.length > 1 ? "" : ""}`}
                                        >
                                            {isEntityColumn && Array.isArray(value) && value.length > 1 ? (
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

