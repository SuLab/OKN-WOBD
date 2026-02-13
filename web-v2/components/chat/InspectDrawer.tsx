"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import type { ChatMessage } from "@/types";
import { ResultsTable } from "./ResultsTable";
import { SparqlEditor } from "./SparqlEditor";
import { QueryPlanVisualization } from "./QueryPlanVisualization";
import {
  downloadResultsAsCSV,
  downloadResultsAsTSV,
  downloadProcessedDataAsCSV,
  downloadProcessedDataAsTSV,
} from "@/lib/chat/download";

interface InspectDrawerProps {
  message: ChatMessage | null;
}

type Tab = "results" | "sparql" | "intent" | "context" | "ontology" | "debug" | "plan";

export function InspectDrawer({ message }: InspectDrawerProps) {
  // Default to results tab if message has results, otherwise SPARQL
  const defaultTab: Tab = message?.results ? "results" : "sparql";
  const [activeTab, setActiveTab] = useState<Tab>(defaultTab);
  const [copied, setCopied] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Load width from localStorage or use default
  const [width, setWidth] = useState(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("inspect_drawer_width");
      return saved ? parseInt(saved, 10) : 384;
    }
    return 384;
  });

  // Load collapsed state from localStorage
  useEffect(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("inspect_drawer_collapsed");
      if (saved === "true") {
        setIsCollapsed(true);
      }
    }
  }, []);

  // Save collapsed state to localStorage
  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem("inspect_drawer_collapsed", isCollapsed.toString());
    }
  }, [isCollapsed]);

  const [isResizing, setIsResizing] = useState(false);
  const drawerRef = useRef<HTMLDivElement>(null);

  // Save width to localStorage when it changes
  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem("inspect_drawer_width", width.toString());
    }
  }, [width]);

  // Reset to default tab when message changes
  useEffect(() => {
    if (message) {
      setActiveTab(message.results ? "results" : "sparql");
    }
  }, [message]);

  // Handle resize
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return;

      const newWidth = window.innerWidth - e.clientX;
      // Constrain width between 300px and 80% of viewport
      const minWidth = 300;
      const maxWidth = window.innerWidth * 0.8;
      setWidth(Math.max(minWidth, Math.min(maxWidth, newWidth)));
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    }

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [isResizing]);

  // Toggle collapse/expand state
  const toggleCollapse = useCallback(() => {
    setIsCollapsed(!isCollapsed);
  }, [isCollapsed]);

  if (!message || message.role === "user") {
    if (isCollapsed) {
      return (
        <div
          className="border-l border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 relative flex flex-col items-center justify-center"
          style={{ width: "48px", minWidth: "48px" }}
        >
          {/* Collapse/Expand button */}
          <button
            onClick={toggleCollapse}
            className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition-colors"
            title="Expand Inspect panel"
          >
            <svg
              className="w-5 h-5 text-slate-600 dark:text-slate-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 19l-7-7 7-7"
              />
            </svg>
          </button>
        </div>
      );
    }

    return (
      <div
        className="border-l border-slate-200 dark:border-slate-800 p-4 bg-white dark:bg-slate-900 relative flex-shrink-0 overflow-hidden"
        style={{ width: `${width}px`, minWidth: "300px", maxWidth: "calc(100vw - 200px)" }}
      >
        {/* Resize handle - wider and more visible */}
        <div
          onMouseDown={handleMouseDown}
          className="absolute left-0 top-0 bottom-0 w-1.5 cursor-col-resize hover:bg-accent/70 bg-transparent hover:bg-accent/50 transition-colors z-20 group"
          style={{ marginLeft: "-4px" }}
        >
          {/* Visual indicator line */}
          <div className="absolute left-1/2 top-0 bottom-0 w-0.5 bg-slate-400 dark:bg-slate-600 group-hover:bg-accent transition-colors transform -translate-x-1/2" />
        </div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-slate-900 dark:text-slate-100">Inspect</h3>
          <button
            onClick={toggleCollapse}
            className="p-1 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition-colors"
            title="Collapse Inspect panel"
          >
            <svg
              className="w-5 h-5 text-slate-600 dark:text-slate-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5l7 7-7 7"
              />
            </svg>
          </button>
        </div>
        <p className="text-sm text-slate-600 dark:text-slate-400">
          Select a message to inspect its details
        </p>
      </div>
    );
  }

  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: "results", label: "Results", count: message?.results?.results?.bindings?.length },
    { id: "sparql", label: "SPARQL" },
    { id: "intent", label: "Intent" },
    { id: "context", label: "Context" },
    ...(message?.ontology_state ? [{ id: "ontology" as Tab, label: "Ontology" }] : []),
    ...(message?.plan_id ? [{ id: "plan" as Tab, label: "Query Plan" }] : []),
    { id: "debug", label: "Debug" },
  ];

  function handleDownload(format: "csv" | "tsv", processedData?: any[]) {
    if (!message || !message.results) return;

    const vars = message.results.head.vars;
    const filename = format === "csv"
      ? `results_${message.id}.csv`
      : `results_${message.id}.tsv`;

    if (processedData) {
      // Use processed (grouped) data - entity arrays will be comma-separated
      if (format === "csv") {
        downloadProcessedDataAsCSV(processedData, vars, filename);
      } else {
        downloadProcessedDataAsTSV(processedData, vars, filename);
      }
    } else {
      // Use raw (ungrouped) data
      if (format === "csv") {
        downloadResultsAsCSV(message.results, filename);
      } else {
        downloadResultsAsTSV(message.results, filename);
      }
    }
  }

  async function handleCopySPARQL() {
    if (!message || !message.sparql) return;
    try {
      await navigator.clipboard.writeText(message.sparql);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy SPARQL:", err);
    }
  }

  if (isCollapsed) {
    return (
      <div
        className="border-l border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 relative flex flex-col items-center justify-center"
        style={{ width: "48px", minWidth: "48px" }}
      >
        {/* Collapse/Expand button */}
        <button
          onClick={toggleCollapse}
          className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition-colors"
          title="Expand Inspect panel"
        >
          <svg
            className="w-5 h-5 text-slate-600 dark:text-slate-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 19l-7-7 7-7"
            />
          </svg>
        </button>
      </div>
    );
  }

  return (
    <div
      ref={drawerRef}
      className="border-l border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex flex-col relative flex-shrink-0 overflow-hidden"
      style={{ width: `${width}px`, minWidth: "300px", maxWidth: "calc(100vw - 200px)" }}
    >
      {/* Resize handle - wider and more visible */}
      <div
        onMouseDown={handleMouseDown}
        className="absolute left-0 top-0 bottom-0 w-1.5 cursor-col-resize hover:bg-accent/70 bg-transparent hover:bg-accent/50 transition-colors z-20 group"
        style={{ marginLeft: "-4px" }}
      >
        {/* Visual indicator line */}
        <div className="absolute left-1/2 top-0 bottom-0 w-0.5 bg-slate-400 dark:bg-slate-600 group-hover:bg-accent transition-colors transform -translate-x-1/2" />
      </div>
      {/* Header */}
      <div className="p-4 border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold text-slate-900 dark:text-slate-100">Inspect</h3>
          <button
            onClick={toggleCollapse}
            className="p-1 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition-colors"
            title="Collapse Inspect panel"
          >
            <svg
              className="w-5 h-5 text-slate-600 dark:text-slate-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5l7 7-7 7"
              />
            </svg>
          </button>
        </div>
        <div className="text-xs text-slate-600 dark:text-slate-400">
          {message.run_id && (
            <span className="text-slate-500 dark:text-slate-400">Run: {message.run_id.substring(0, 8)}...</span>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 dark:border-slate-800 overflow-x-auto">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          const hasContent =
            (tab.id === "results" && message.results) ||
            (tab.id === "sparql" && message?.sparql) ||
            (tab.id === "intent" && message?.intent) ||
            tab.id === "context" ||
            (tab.id === "ontology" && message?.ontology_state) ||
            (tab.id === "debug" && message?.metadata);

          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${isActive
                ? "border-accent text-accent"
                : "border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-300"
                } ${!hasContent ? "opacity-50" : ""}`}
              disabled={!hasContent}
            >
              {tab.label}
              {tab.count !== undefined && (
                <span className="ml-1 text-xs">({tab.count})</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === "results" && (
          <div>
            {message.results && message.results.results && message.results.results.bindings ? (
              <ResultsTable
                results={message.results}
                onDownload={handleDownload}
              />
            ) : (
              <div className="text-slate-600 dark:text-slate-400 text-sm space-y-2">
                <p>No results available</p>
                {message.results && (
                  <pre className="text-xs bg-slate-100 dark:bg-slate-800 p-2 rounded overflow-auto text-slate-900 dark:text-slate-100">
                    {JSON.stringify(message.results, null, 2).substring(0, 500)}
                  </pre>
                )}
              </div>
            )}
          </div>
        )}

        {activeTab === "sparql" && (
          <div className="space-y-2">
            {message.sparql ? (
              <div className="relative">
                {/* Copy button in top-right corner of editor */}
                <div className="absolute top-2 right-2 z-10">
                  <button
                    onClick={handleCopySPARQL}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-md transition-colors shadow-sm border border-slate-200 dark:border-slate-700"
                    title="Copy SPARQL query"
                  >
                    {copied ? (
                      <>
                        <svg
                          className="w-4 h-4 text-green-500 dark:text-green-400"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M5 13l4 4L19 7"
                          />
                        </svg>
                        <span className="text-green-500 dark:text-green-400">Copied!</span>
                      </>
                    ) : (
                      <>
                        <svg
                          className="w-4 h-4"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                          />
                        </svg>
                        <span>Copy</span>
                      </>
                    )}
                  </button>
                </div>
                <SparqlEditor
                  value={message.sparql}
                  readOnly={true}
                  height="400px"
                />
              </div>
            ) : (
              <p className="text-slate-600 dark:text-slate-400 text-sm">No SPARQL query available</p>
            )}
          </div>
        )}

        {activeTab === "intent" && (
          <div className="space-y-4">
            {message.intent ? (
              <>
                <div>
                  <h4 className="text-sm font-semibold mb-2 text-slate-900 dark:text-slate-100">Task</h4>
                  <p className="text-sm text-slate-700 dark:text-slate-300">{message.intent.task}</p>
                </div>
                <div>
                  <h4 className="text-sm font-semibold mb-2 text-slate-900 dark:text-slate-100">Confidence</h4>
                  <p className="text-sm text-slate-700 dark:text-slate-300">
                    {(message.intent.confidence * 100).toFixed(1)}%
                  </p>
                </div>
                <div>
                  <h4 className="text-sm font-semibold mb-2 text-slate-900 dark:text-slate-100">Graphs</h4>
                  <p className="text-sm text-slate-700 dark:text-slate-300">
                    {message.intent.graphs.join(", ") || "All graphs"}
                  </p>
                </div>
                <div>
                  <h4 className="text-sm font-semibold mb-2 text-slate-900 dark:text-slate-100">Slots</h4>
                  <pre className="text-xs bg-slate-100 dark:bg-slate-800 p-3 rounded overflow-x-auto text-slate-900 dark:text-slate-100">
                    {JSON.stringify(message.intent.slots, null, 2)}
                  </pre>
                </div>
                {message.intent.notes && (
                  <div>
                    <h4 className="text-sm font-semibold mb-2 text-slate-900 dark:text-slate-100">Notes</h4>
                    <p className="text-sm text-slate-600 dark:text-slate-400">{message.intent.notes}</p>
                  </div>
                )}
              </>
            ) : (
              <p className="text-slate-600 dark:text-slate-400 text-sm">No intent information available</p>
            )}
          </div>
        )}

        {activeTab === "context" && (
          <div className="space-y-4">
            {message.intent?.context_pack && (
              <>
                <div>
                  <h4 className="text-sm font-semibold mb-2 text-slate-900 dark:text-slate-100">Context Pack</h4>
                  <p className="text-sm text-slate-700 dark:text-slate-300">{message.intent.context_pack}</p>
                </div>
                <div>
                  <h4 className="text-sm font-semibold mb-2 text-slate-900 dark:text-slate-100">Graph Mode</h4>
                  <p className="text-sm text-slate-700 dark:text-slate-300">
                    {message.intent.graph_mode || "federated"}
                  </p>
                </div>
                {message.run_id && (
                  <div>
                    <h4 className="text-sm font-semibold mb-2 text-slate-900 dark:text-slate-100">Run ID</h4>
                    <p className="text-xs text-slate-600 dark:text-slate-400 font-mono">{message.run_id}</p>
                  </div>
                )}
              </>
            )}
            {!message.intent?.context_pack && (
              <p className="text-slate-600 dark:text-slate-400 text-sm">No context information available</p>
            )}
          </div>
        )}

        {activeTab === "ontology" && (
          <div className="space-y-4">
            {message.ontology_state ? (
              <>
                <div>
                  <h4 className="text-sm font-semibold mb-2 text-slate-900 dark:text-slate-100">Entity Type</h4>
                  <p className="text-sm text-slate-700 dark:text-slate-300 capitalize">
                    {message.ontology_state.entity_type}
                  </p>
                </div>
                <div>
                  <h4 className="text-sm font-semibold mb-2 text-slate-900 dark:text-slate-100">Raw Phrase</h4>
                  <p className="text-sm text-slate-700 dark:text-slate-300">
                    {message.ontology_state.raw_phrase}
                  </p>
                </div>
                {message.ontology_state.candidate_labels.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold mb-2 text-slate-900 dark:text-slate-100">
                      Candidate Labels ({message.ontology_state.candidate_labels.length})
                    </h4>
                    <ul className="text-sm text-slate-700 dark:text-slate-300 list-disc list-inside space-y-1">
                      {message.ontology_state.candidate_labels.map((label, idx) => (
                        <li key={idx}>{label}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {message.ontology_state.grounded_mondo_terms.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold mb-2 text-slate-900 dark:text-slate-100">
                      Grounded MONDO Terms
                    </h4>
                    <div className="space-y-3">
                      {/* Selected matches (used for querying) - filter to only MONDO terms with score >= 2 */}
                      {(() => {
                        // Filter to only MONDO terms (exclude HP and other ontologies)
                        const mondoTerms = message.ontology_state.grounded_mondo_terms.filter(term => {
                          const iri = term.mondo || "";
                          return iri.includes("/MONDO_") && !iri.includes("/HP_");
                        });

                        if (mondoTerms.length === 0) {
                          return (
                            <div className="p-2 bg-yellow-50 dark:bg-yellow-500/20 rounded text-sm text-yellow-700 dark:text-yellow-300">
                              ⚠️ No MONDO terms found (only non-MONDO ontology terms were returned)
                            </div>
                          );
                        }

                        // Get high-confidence matches (score 4, 3, or 2) - these are used for querying
                        // Score 4 = exact label, Score 3 = exact synonym, Score 2 = other synonym types
                        const highConfidenceTerms = mondoTerms
                          .filter(term => (term.matchScore || 0) >= 2)
                          .slice(0, 3);

                        const selectedTerms = highConfidenceTerms.length > 0 ? highConfidenceTerms : [];

                        return (
                          <div className="space-y-2">
                            {selectedTerms.length > 0 && (
                              <>
                                <p className="text-xs font-semibold text-slate-600 dark:text-slate-400 mb-2">
                                  Selected for Query ({selectedTerms.length}):
                                </p>
                                {selectedTerms.map((term, idx) => {
                                  const mondoId = term.obo_id || term.mondo.replace(/^.*MONDO_/, "MONDO:");
                                  const score = term.matchScore || 0;
                                  const scoreLabel = score === 4 ? "Exact Label" : score === 3 ? "Exact Synonym" : score === 2 ? "Synonym" : "Partial";
                                  return (
                                    <div key={idx} className="p-3 bg-accent/10 dark:bg-accent/20 rounded-lg border border-accent/30">
                                      <div className="flex items-start gap-2 mb-2">
                                        <span className="text-xs font-semibold text-accent uppercase">#{idx + 1}</span>
                                        <a
                                          href={`https://monarchinitiative.org/disease/${mondoId.replace("MONDO:", "")}`}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          className="text-accent hover:underline font-mono text-xs"
                                        >
                                          {mondoId}
                                        </a>
                                      </div>
                                      <p className="text-slate-900 dark:text-slate-100 font-medium">
                                        {term.label}
                                      </p>
                                      {term.matchScore !== undefined && (
                                        <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
                                          Match: {scoreLabel} ({term.matchType}, score: {term.matchScore})
                                          {term.is_obsolete && (
                                            <span className="text-yellow-600 dark:text-yellow-400 ml-2">⚠️ Obsolete</span>
                                          )}
                                        </p>
                                      )}
                                      {term.matchedText && term.matchedText !== term.label && (
                                        <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
                                          Matched via: "{term.matchedText}"
                                        </p>
                                      )}
                                    </div>
                                  );
                                })}
                              </>
                            )}
                            {selectedTerms.length === 0 && (
                              <div className="p-2 bg-yellow-50 dark:bg-yellow-500/20 rounded text-sm text-yellow-700 dark:text-yellow-300">
                                ⚠️ No high-confidence matches found. Check partial matches below for confirmation.
                              </div>
                            )}
                          </div>
                        );
                      })()}

                      {/* Partial matches that need user confirmation - only show if no high-confidence matches */}
                      {(() => {
                        const partialMatches = message.ontology_state.debug_info?.partial_matches_need_confirmation || [];
                        const mondoTerms = message.ontology_state.grounded_mondo_terms?.filter(term => {
                          const iri = term.mondo || "";
                          return iri.includes("/MONDO_") && !iri.includes("/HP_");
                        }) || [];
                        const hasHighConfidence = mondoTerms.some(t => (t.matchScore || 0) >= 2);

                        // Only show partial matches if there are no high-confidence matches
                        if (partialMatches.length === 0 || hasHighConfidence) {
                          return null;
                        }

                        return (
                          <div className="mt-4">
                            <div className="p-3 bg-yellow-50 dark:bg-yellow-500/20 rounded-lg border border-yellow-300 dark:border-yellow-600 mb-3">
                              <p className="text-sm font-semibold text-yellow-800 dark:text-yellow-200 mb-1">
                                ⚠️ Partial Matches Found
                              </p>
                              <p className="text-xs text-yellow-700 dark:text-yellow-300">
                                These terms matched partially (substring match). No exact matches were found.
                                If one of these is correct, you can select it from the message bubble above, or re-run your query with the MONDO ID directly (e.g., "MONDO:0004980").
                              </p>
                            </div>
                            <div className="space-y-2">
                              {partialMatches.map((term, idx) => {
                                const mondoId = term.obo_id || term.mondo.replace(/^.*MONDO_/, "MONDO:");
                                return (
                                  <div
                                    key={idx}
                                    className="p-3 bg-yellow-50 dark:bg-yellow-500/20 rounded-lg border border-yellow-300 dark:border-yellow-600"
                                  >
                                    <div className="flex items-start gap-2 mb-2">
                                      <a
                                        href={`https://monarchinitiative.org/disease/${mondoId.replace("MONDO:", "")}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-accent hover:underline font-mono text-xs"
                                      >
                                        {mondoId}
                                      </a>
                                    </div>
                                    <p className="text-slate-900 dark:text-slate-100 font-medium">
                                      {term.label}
                                    </p>
                                    <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
                                      Match: {term.matchType} (score: {term.matchScore}) - Partial/substring match
                                    </p>
                                    {term.matchedText && (
                                      <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
                                        Matched via: "{term.matchedText}"
                                      </p>
                                    )}
                                    <p className="text-xs text-yellow-700 dark:text-yellow-300 mt-2">
                                      💡 <strong>Tip:</strong> If this is the correct term, try searching with the MONDO ID: <code className="bg-yellow-100 dark:bg-yellow-900 px-1 rounded">{mondoId}</code>
                                    </p>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        );
                      })()}

                      {/* Alternatives - only show MONDO terms */}
                      {(() => {
                        const mondoTerms = message.ontology_state.grounded_mondo_terms.filter(term => {
                          const iri = term.mondo || "";
                          return iri.includes("/MONDO_") && !iri.includes("/HP_");
                        });

                        // Get high-confidence matches (score >= 2) - these are the selected ones, up to 3
                        const highConfidenceTerms = mondoTerms.filter(term => (term.matchScore || 0) >= 2);
                        const selectedIRIs = highConfidenceTerms.length > 0
                          ? highConfidenceTerms.slice(0, 3).map(t => t.mondo)
                          : [];

                        // Show alternatives (non-selected MONDO terms)
                        const alternatives = mondoTerms.filter(term => !selectedIRIs.includes(term.mondo));

                        if (alternatives.length > 0) {
                          return (
                            <div className="mt-4">
                              <p className="text-xs font-semibold text-slate-600 dark:text-slate-400 mb-2">
                                Alternatives:
                              </p>
                              <div className="space-y-2">
                                {alternatives.slice(0, 5).map((term, idx) => {
                                  const mondoId = term.obo_id || term.mondo.replace(/^.*MONDO_/, "MONDO:");
                                  return (
                                    <div
                                      key={idx}
                                      className="p-2 bg-slate-100 dark:bg-slate-800 rounded text-sm"
                                    >
                                      <div className="flex items-start gap-2">
                                        <a
                                          href={`https://monarchinitiative.org/disease/${mondoId.replace("MONDO:", "")}`}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          className="text-accent hover:underline font-mono text-xs"
                                        >
                                          {mondoId}
                                        </a>
                                      </div>
                                      <p className="text-slate-700 dark:text-slate-300 mt-1">
                                        {term.label}
                                      </p>
                                      {term.matchScore !== undefined && (
                                        <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
                                          Match: {term.matchType} (score: {term.matchScore})
                                        </p>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          );
                        }
                        return null;
                      })()}
                    </div>
                  </div>
                )}
                {message.ontology_state.synonyms.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold mb-2 text-slate-900 dark:text-slate-100">
                      Synonyms ({message.ontology_state.synonyms.length} terms)
                    </h4>
                    <div className="space-y-2">
                      {message.ontology_state.synonyms.map((syn, idx) => (
                        <div
                          key={idx}
                          className="p-2 bg-slate-100 dark:bg-slate-800 rounded text-sm"
                        >
                          <div className="font-mono text-xs text-accent mb-1">
                            {syn.mondo}
                          </div>
                          {syn.label && (
                            <p className="text-slate-700 dark:text-slate-300 mb-1">
                              <span className="font-medium">Label:</span> {syn.label}
                            </p>
                          )}
                          {syn.synonyms.length > 0 && (
                            <div>
                              <p className="text-slate-600 dark:text-slate-400 text-xs mb-1">
                                Synonyms ({syn.synonyms.length}):
                              </p>
                              <ul className="text-xs text-slate-600 dark:text-slate-400 list-disc list-inside ml-2">
                                {syn.synonyms.slice(0, 10).map((synonym, sIdx) => (
                                  <li key={sIdx}>{synonym}</li>
                                ))}
                                {syn.synonyms.length > 10 && (
                                  <li className="italic">... and {syn.synonyms.length - 10} more</li>
                                )}
                              </ul>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {message.ontology_state.nde_encoding && (
                  <div>
                    <h4 className="text-sm font-semibold mb-2 text-slate-900 dark:text-slate-100">NDE Encoding</h4>
                    <p className="text-sm text-slate-700 dark:text-slate-300 uppercase">
                      {message.ontology_state.nde_encoding}
                    </p>
                  </div>
                )}
                {message.ontology_state.fallback_used && (
                  <div>
                    <h4 className="text-sm font-semibold mb-2 text-slate-900 dark:text-slate-100">Fallback Used</h4>
                    <p className="text-sm text-yellow-600 dark:text-yellow-400">
                      ⚠️ Text-based fallback search was used (ontology grounding may have failed)
                    </p>
                  </div>
                )}
                {message.ontology_state.stage_errors &&
                  Object.keys(message.ontology_state.stage_errors).length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold mb-2 text-red-600 dark:text-red-400">
                        Stage Errors
                      </h4>
                      <div className="space-y-2">
                        {Object.entries(message.ontology_state.stage_errors).map(
                          ([stage, error]) =>
                            error && (
                              <div
                                key={stage}
                                className="p-2 bg-red-50 dark:bg-red-500/20 rounded text-sm"
                              >
                                <p className="font-medium text-red-700 dark:text-red-300 capitalize">
                                  {stage.replace(/_/g, " ")}:
                                </p>
                                <p className="text-red-600 dark:text-red-400 text-xs mt-1">
                                  {error}
                                </p>
                              </div>
                            )
                        )}
                      </div>
                    </div>
                  )}
                {message.ontology_state.debug_info && (
                  <div>
                    <h4 className="text-sm font-semibold mb-2 text-slate-900 dark:text-slate-100">
                      Debug Information
                    </h4>
                    <div className="space-y-2 text-sm">
                      {message.ontology_state.debug_info.search_terms_used && (
                        <div>
                          <p className="text-slate-600 dark:text-slate-400 mb-1">
                            Search terms used:
                          </p>
                          <ul className="list-disc list-inside text-xs text-slate-600 dark:text-slate-400 ml-2">
                            {message.ontology_state.debug_info.search_terms_used.map((term, idx) => (
                              <li key={idx}>{term}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {message.ontology_state.debug_info.ontology_query_executed !== undefined && (
                        <p className="text-slate-600 dark:text-slate-400">
                          {(() => {
                            const ontologyName = (message.ontology_state.entity_type as string) === "drug" || (message.ontology_state.entity_type as string) === "medication"
                              ? "Wikidata"
                              : message.ontology_state.entity_type === "species"
                                ? "NCBITaxon"
                                : "MONDO";
                            const executed = message.ontology_state.debug_info.ontology_query_executed ?? false;
                            return `${ontologyName} query executed: ${executed ? "Yes" : "No"}`;
                          })()}
                        </p>
                      )}
                      {message.ontology_state.debug_info.ontology_query_result_count !== undefined && (
                        <p className="text-slate-600 dark:text-slate-400">
                          {(() => {
                            const ontologyName = (message.ontology_state.entity_type as string) === "drug" || (message.ontology_state.entity_type as string) === "medication"
                              ? "Wikidata"
                              : message.ontology_state.entity_type === "species"
                                ? "NCBITaxon"
                                : "MONDO";
                            const count = message.ontology_state.debug_info.ontology_query_result_count ?? 0;
                            return `${ontologyName} query returned: ${count} results`;
                          })()}
                        </p>
                      )}
                      {message.ontology_state.debug_info.ontology_query_result_count === 0 && (
                        <p className="text-yellow-600 dark:text-yellow-400 text-xs mt-2">
                          ⚠️ No {(() => {
                            const ontologyName = (message.ontology_state.entity_type as string) === "drug" || (message.ontology_state.entity_type as string) === "medication"
                              ? "Wikidata"
                              : message.ontology_state.entity_type === "species"
                                ? "NCBITaxon"
                                : "MONDO";
                            return ontologyName;
                          })()} terms found. This could mean:
                          <ul className="list-disc list-inside ml-4 mt-1">
                            <li>The terms don't exist in {(() => {
                              const ontologyName = (message.ontology_state.entity_type as string) === "drug" || (message.ontology_state.entity_type as string) === "medication"
                                ? "Wikidata"
                                : message.ontology_state.entity_type === "species"
                                  ? "NCBITaxon"
                                  : "MONDO/Ubergraph";
                              return ontologyName;
                            })()}</li>
                            <li>The query syntax needs adjustment</li>
                            <li>Check server terminal for detailed logs</li>
                          </ul>
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <p className="text-slate-600 dark:text-slate-400 text-sm">
                No ontology information available
              </p>
            )}
          </div>
        )}

        {activeTab === "plan" && message.query_plan && (
          <QueryPlanVisualization
            plan={message.query_plan}
            allMessages={[]}
          />
        )}

        {activeTab === "debug" && (
          <div className="space-y-4">
            {message.metadata && (
              <>
                {message.metadata.latency_ms !== undefined && (
                  <div>
                    <h4 className="text-sm font-semibold mb-2 text-slate-900 dark:text-slate-100">Latency</h4>
                    <p className="text-sm text-slate-700 dark:text-slate-300">{message.metadata.latency_ms}ms</p>
                  </div>
                )}
                {message.metadata.row_count !== undefined && (
                  <div>
                    <h4 className="text-sm font-semibold mb-2 text-slate-900 dark:text-slate-100">Row Count</h4>
                    <p className="text-sm text-slate-700 dark:text-slate-300">{message.metadata.row_count}</p>
                  </div>
                )}
                {message.metadata.repair_attempt && (
                  <div>
                    <h4 className="text-sm font-semibold mb-2">Repair Attempt</h4>
                    <div className="text-sm space-y-1">
                      <p className="text-slate-700 dark:text-slate-300">
                        Attempted: {message.metadata.repair_attempt.attempted ? "Yes" : "No"}
                      </p>
                      {message.metadata.repair_attempt.success && (
                        <p className="text-green-600 dark:text-green-400">Success: Yes</p>
                      )}
                      {message.metadata.repair_attempt.changes.length > 0 && (
                        <div>
                          <p className="text-slate-600 dark:text-slate-400 mb-1">Changes:</p>
                          <ul className="list-disc list-inside text-xs text-slate-600 dark:text-slate-400">
                            {message.metadata.repair_attempt.changes.map((change, idx) => (
                              <li key={idx}>{change}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                )}
                {message.metadata.preflight_result && (
                  <div>
                    <h4 className="text-sm font-semibold mb-2 text-slate-900 dark:text-slate-100">Preflight Results</h4>
                    <pre className="text-xs bg-slate-100 dark:bg-slate-800 p-3 rounded overflow-x-auto text-slate-900 dark:text-slate-100">
                      {JSON.stringify(message.metadata.preflight_result, null, 2)}
                    </pre>
                  </div>
                )}
              </>
            )}
            {!message.metadata && (
              <p className="text-slate-600 dark:text-slate-400 text-sm">No debug information available</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
