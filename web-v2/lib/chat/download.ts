// Download utilities for SPARQL results

import type { SPARQLResult } from "@/types";

export function downloadResultsAsCSV(results: SPARQLResult, filename?: string): void {
  const csv = convertResultsToCSV(results);
  downloadFile(csv, filename || "results.csv", "text/csv");
}

export function downloadResultsAsTSV(results: SPARQLResult, filename?: string): void {
  const tsv = convertResultsToTSV(results);
  downloadFile(tsv, filename || "results.tsv", "text/tab-separated-values");
}

/**
 * Download processed (grouped) data as TSV
 * Entity arrays are converted to comma-separated strings for pandas compatibility
 */
export function downloadProcessedDataAsTSV(
  processedData: any[],
  vars: string[],
  filename?: string
): void {
  const header = vars.join("\t");
  const rows = processedData.map((row) =>
    vars.map((varName) => {
      const value = row[varName];
      // Convert arrays to comma-separated strings (pandas-friendly)
      if (Array.isArray(value)) {
        return value.join(", ");
      }
      return String(value || "");
    }).join("\t")
  );
  const tsv = [header, ...rows].join("\n");
  downloadFile(tsv, filename || "results.tsv", "text/tab-separated-values");
}

/**
 * Download processed (grouped) data as CSV
 * Entity arrays are converted to comma-separated strings for pandas compatibility
 */
export function downloadProcessedDataAsCSV(
  processedData: any[],
  vars: string[],
  filename?: string
): void {
  const header = vars.map(escapeCSV).join(",");
  const rows = processedData.map((row) =>
    vars
      .map((varName) => {
        const value = row[varName];
        // Convert arrays to comma-separated strings (pandas-friendly)
        let stringValue: string;
        if (Array.isArray(value)) {
          stringValue = value.join(", ");
        } else {
          stringValue = String(value || "");
        }
        return escapeCSV(stringValue);
      })
      .join(",")
  );
  const csv = [header, ...rows].join("\n");
  downloadFile(csv, filename || "results.csv", "text/csv");
}

function convertResultsToCSV(results: SPARQLResult): string {
  const vars = results.head.vars;
  const bindings = results.results.bindings;

  // Header row
  const header = vars.map(escapeCSV).join(",");

  // Data rows
  const rows = bindings.map((binding) =>
    vars
      .map((varName) => {
        const value = binding[varName]?.value || "";
        return escapeCSV(value);
      })
      .join(",")
  );

  return [header, ...rows].join("\n");
}

function convertResultsToTSV(results: SPARQLResult): string {
  const vars = results.head.vars;
  const bindings = results.results.bindings;

  // Header row
  const header = vars.join("\t");

  // Data rows
  const rows = bindings.map((binding) =>
    vars.map((varName) => binding[varName]?.value || "").join("\t")
  );

  return [header, ...rows].join("\n");
}

function escapeCSV(value: string): string {
  // Escape quotes and wrap in quotes if contains comma, newline, or quote
  if (value.includes(",") || value.includes("\n") || value.includes('"')) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

function downloadFile(content: string, filename: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

