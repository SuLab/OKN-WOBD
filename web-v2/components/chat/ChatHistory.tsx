"use client";

import React, { useState, useEffect } from "react";
import type { ChatMessage } from "@/types";
import { QueryPlanPreview } from "./QueryPlanPreview";
import { MermaidDiagram } from "./MermaidDiagram";

interface ChatHistoryProps {
  messages: ChatMessage[];
  onMessageSelect?: (messageId: string) => void;
  selectedMessageId?: string | null;
  onRetryWithoutLimit?: (messageId: string, query: string, lane: "template" | "open" | "raw") => void;
  onSelectPartialMatch?: (messageId: string, mondoIRI: string, mondoId: string, originalQuery: string, lane: "template" | "open" | "raw") => void;
}

export function ChatHistory({
  messages,
  onMessageSelect,
  selectedMessageId,
  onRetryWithoutLimit,
  onSelectPartialMatch,
}: ChatHistoryProps) {
  if (messages.length === 0) {
    return (
      <div className="flex items-center justify-center h-full min-h-0">
        <div className="text-center space-y-2">
          <p className="text-slate-600 dark:text-slate-400">No messages yet</p>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Ask a question to get started. Try:
          </p>
          <ul className="text-sm text-slate-600 dark:text-slate-400 list-disc list-inside space-y-1">
            <li>{`"Find datasets about diabetes"`}</li>
            <li>{`"/text Find COVID-19 datasets"`}</li>
            <li>{`"/sparql SELECT ?s WHERE { ?s ?p ?o } LIMIT 10"`}</li>
          </ul>
        </div>
      </div>
    );
  }

  return (
    <div className="pl-2 pr-2 min-h-0">
      <div className="space-y-4">
        {messages.map((message, index) => (
          <MessageBubble
            key={message.id}
            message={message}
            messageIndex={index}
            messages={messages}
            isSelected={selectedMessageId === message.id}
            onSelect={() => onMessageSelect?.(message.id)}
            onRetryWithoutLimit={onRetryWithoutLimit}
            onSelectPartialMatch={onSelectPartialMatch}
          />
        ))}
      </div>
    </div>
  );
}

function MessageBubble({
  message,
  messageIndex,
  messages,
  isSelected,
  onSelect,
  onRetryWithoutLimit,
  onSelectPartialMatch,
}: {
  message: ChatMessage;
  messageIndex: number;
  messages: ChatMessage[];
  isSelected?: boolean;
  onSelect?: () => void;
  onRetryWithoutLimit?: (query: string, lane: "template" | "text" | "raw") => void;
  onSelectPartialMatch?: (messageId: string, mondoIRI: string, mondoId: string, originalQuery: string, lane: "template" | "text" | "raw") => void;
}) {
  const isUser = message.role === "user";
  const isError = message.role === "error";
  const isSelectable = !isUser && (message.results || message.sparql || message.intent);

  // Check for partial matches that need confirmation
  const partialMatches = message.ontology_state?.debug_info?.partial_matches_need_confirmation || [];
  const hasPartialMatches = partialMatches.length > 0;
  const hasHighConfidenceMatches = message.ontology_state?.grounded_mondo_terms?.some(t => (t.matchScore || 0) >= 2) || false;
  const fallbackUsed = message.ontology_state?.fallback_used || false;

  // Get entity type for display
  const entityType = message.ontology_state?.entity_type || "entity";
  const entityTypeLabel = entityType === "disease" || entityType === "condition"
    ? "disease"
    : entityType === "species" || entityType === "organism"
      ? "species/organism"
      : entityType === "drug"
        ? "drug"
        : "entity";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} ${isSelected ? "px-1" : ""}`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-3 transition-all ${isUser
          ? "bg-accent text-white dark:text-white"
          : isError
            ? "bg-red-50 dark:bg-red-500/20 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-500/50"
            : "bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-slate-100 border border-slate-200 dark:border-slate-700"
          } ${isSelectable
            ? "cursor-pointer hover:ring-2 hover:ring-accent/50"
            : ""
          } ${isSelected ? "ring-2 ring-accent outline-none" : ""
          }`}
        onClick={isSelectable ? onSelect : undefined}
      >
        {/* Message content */}
        {isUser && message.lane === "raw" && message.content ? (
          <CollapsibleSPARQL query={message.content} />
        ) : (
          <div className="whitespace-pre-wrap break-words text-sm">{message.content}</div>
        )}

        {/* Mermaid diagram - when assistant message includes mermaid */}
        {!isUser && message.mermaid && message.id && (
          <MermaidDiagram code={message.mermaid} id={message.id} />
        )}

        {/* Query plan preview - only show for plan preview messages */}
        {!isUser && message.is_plan_preview && message.query_plan && (
          <div className="mt-3">
            <QueryPlanPreview plan={message.query_plan} />
          </div>
        )}

        {/* Partial matches selection UI - only show if no high-confidence matches AND fallback was not used */}
        {!isUser && hasPartialMatches && !hasHighConfidenceMatches && !fallbackUsed && (
          <div className="mt-3 pt-3 border-t border-slate-300 dark:border-slate-700/50">
            <p className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-2">
              ⚠️ Found partial matches for <span className="font-mono text-accent">{entityTypeLabel}</span>. Select one to use:
            </p>
            <div className="space-y-2">
              {partialMatches.map((term, idx) => {
                const mondoId = term.obo_id || term.mondo.replace(/^.*MONDO_/, "MONDO:");
                return (
                  <button
                    key={idx}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (onSelectPartialMatch && message.id && message.lane) {
                        // Find the original user message that triggered this response
                        const userMessage = messageIndex > 0 && messages[messageIndex - 1]?.role === "user"
                          ? messages[messageIndex - 1]
                          : null;
                        // Use raw_phrase from ontology state if available, otherwise use user message content
                        const originalQuery = message.ontology_state?.raw_phrase || userMessage?.content || "";
                        if (originalQuery) {
                          onSelectPartialMatch(message.id, term.mondo, mondoId, originalQuery, message.lane);
                        }
                      }
                    }}
                    className="w-full text-left p-2 bg-yellow-50 dark:bg-yellow-500/20 hover:bg-yellow-100 dark:hover:bg-yellow-500/30 rounded border border-yellow-300 dark:border-yellow-600 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="font-mono text-xs text-accent">{mondoId}</div>
                        <div className="text-sm font-medium text-slate-900 dark:text-slate-100 mt-1">{term.label}</div>
                        {term.matchedText && (
                          <div className="text-xs text-slate-600 dark:text-slate-400 mt-1">
                            Matched via: "{term.matchedText}"
                          </div>
                        )}
                      </div>
                      <div className="text-accent ml-2 text-lg">→</div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Metadata */}
        {message.metadata && (
          <div className="mt-2 pt-2 border-t border-slate-300 dark:border-slate-700/50 text-xs text-slate-600 dark:text-slate-400 space-y-1">
            {message.metadata.row_count !== undefined && (
              <div>
                {message.metadata.results_limited && message.metadata.limit_applied ? (
                  <span>
                    {message.metadata.row_count} results (limited to {message.metadata.limit_applied} in query,{" "}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        if (message.sparql && onRetryWithoutLimit && message.lane && message.id) {
                          const queryWithoutLimit = message.sparql.replace(/LIMIT\s+\d+/i, "").trim();
                          onRetryWithoutLimit(message.id, queryWithoutLimit, message.lane);
                        }
                      }}
                      className="text-accent hover:underline"
                    >
                      remove limit
                    </button>
                    )
                  </span>
                ) : (
                  <span>{message.metadata.row_count} results</span>
                )}
              </div>
            )}
            {message.metadata.latency_ms !== undefined && (
              <div>Latency: {message.metadata.latency_ms}ms</div>
            )}
            {message.results?.results?.bindings && message.results.results.bindings.length > 0 && (
              <div className="mt-2 text-slate-600 dark:text-slate-400">
                👉 Click to view results in the inspect panel →
              </div>
            )}
          </div>
        )}

        {/* Error details */}
        {isError && message.error && (
          <div className="mt-2 pt-2 border-t border-red-200 dark:border-red-500/30 text-xs text-red-600 dark:text-red-400">
            {message.error}
          </div>
        )}

        {/* Timestamp - hide for diagram messages */}
        {!message.mermaid && (
          <div className="mt-1 text-xs opacity-60">
            {new Date(message.timestamp).toLocaleTimeString()}
          </div>
        )}
      </div>
    </div>
  );
}

function CollapsibleSPARQL({ query }: { query: string }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);
  const [isLoadingSummary, setIsLoadingSummary] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    // Generate summary when component mounts
    async function generateSummary() {
      setIsLoadingSummary(true);
      try {
        const response = await fetch("/api/tools/sparql/summarize", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sparql: query }),
        });

        if (response.ok) {
          const result = await response.json();
          setSummary(result.summary);
        }
      } catch (error) {
        console.error("Failed to generate SPARQL summary:", error);
      } finally {
        setIsLoadingSummary(false);
      }
    }

    generateSummary();
  }, [query]);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(query);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error("Failed to copy SPARQL query:", error);
    }
  };

  return (
    <div className="space-y-2">
      {/* Summary */}
      {isLoadingSummary ? (
        <div className="text-sm italic text-slate-300">
          Generating summary...
        </div>
      ) : summary ? (
        <div className="text-sm font-medium">
          {summary}
        </div>
      ) : null}

      {/* Expand/Collapse button */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          setIsExpanded(!isExpanded);
        }}
        className="flex items-center gap-2 text-xs text-slate-300 hover:text-white transition-colors"
      >
        <span>{isExpanded ? "▼" : "▶"}</span>
        <span>{isExpanded ? "Hide" : "Show"} SPARQL query</span>
      </button>

      {isExpanded && (
        <div className="mt-2 relative">
          {/* Copy button in top-right corner */}
          <button
            onClick={handleCopy}
            className="absolute top-2 right-2 z-10 p-1.5 bg-slate-700 hover:bg-slate-600 rounded transition-colors"
            title="Copy SPARQL query"
          >
            {copied ? (
              <svg className="w-4 h-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            ) : (
              <svg className="w-4 h-4 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            )}
          </button>

          <div className="p-3 pr-12 bg-slate-800/50 rounded border border-slate-700 overflow-x-auto">
            <pre className="text-xs font-mono text-slate-300 whitespace-pre-wrap break-words">
              {query}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
