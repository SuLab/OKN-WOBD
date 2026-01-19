/** @refresh reset */
"use client";

import { useEffect, useState, useRef, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { ChatHistory } from "@/components/chat/ChatHistory";
import { ChatComposer } from "@/components/chat/ChatComposer";
import { InspectDrawer } from "@/components/chat/InspectDrawer";
import type { ChatMessage } from "@/types";
import {
  loadMessagesFromStorage,
  saveMessagesToStorage,
  clearMessagesFromStorage,
  generateMessageId,
} from "@/lib/chat/messages";
import { getSessionId } from "@/lib/chat/session";
import {
  executeTemplateQuery,
  executeOpenQuery,
  executeRawSPARQL,
} from "@/lib/chat/query-executor";
import { needsMultiHop } from "@/lib/agents/complexity-detector";
import { planMultiHopQuery } from "@/lib/agents/query-planner";
import { executeQueryPlan } from "@/lib/agents/query-executor";
import type { ContextPack } from "@/lib/context-packs/types";

// Wrap ChatPage with Suspense to prevent Fast Refresh issues
export default function ChatPageWrapper() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <ChatPage />
    </Suspense>
  );
}

function ChatPage() {
  const searchParams = useSearchParams();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const isLoadingRef = useRef<HTMLDivElement>(null);
  const processingQueryRef = useRef<string | null>(null); // Track currently processing query to prevent duplicates
  const processingMessageIdsRef = useRef<Set<string>>(new Set()); // Track message IDs being processed to prevent duplicates
  const wasClearedRef = useRef(false); // Track if messages were manually cleared to prevent auto-query
  const abortControllerRef = useRef<AbortController | null>(null); // Track abort controller for canceling queries

  // Load messages from storage on mount
  useEffect(() => {
    const stored = loadMessagesFromStorage();
    setMessages(stored);
  }, []);

  // Handle initial query from URL
  const hasProcessedInitialQuery = useRef(false);
  const lastQueryRef = useRef<string | null>(null);
  const [messagesInitialized, setMessagesInitialized] = useState(false);

  // Mark messages as initialized after first load from storage
  useEffect(() => {
    // After messages are loaded from storage (or determined to be empty), mark as initialized
    if (!messagesInitialized) {
      // Use a small delay to ensure storage load completes
      const timer = setTimeout(() => {
        setMessagesInitialized(true);
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [messagesInitialized]);

  useEffect(() => {
    const q = searchParams.get("q");

    // Reset the ref if messages are cleared
    if (messages.length === 0) {
      hasProcessedInitialQuery.current = false;
      lastQueryRef.current = null;
    }

    // Process query if:
    // 1. Query exists in URL
    // 2. Messages have been initialized (loaded from storage or determined to be empty)
    // 3. It's a different query than last processed (or we haven't processed any yet)
    // 4. Messages weren't just manually cleared
    if (q &&
      messagesInitialized &&
      (q !== lastQueryRef.current || !hasProcessedInitialQuery.current) &&
      !wasClearedRef.current) {
      hasProcessedInitialQuery.current = true;
      lastQueryRef.current = q;
      handleMessage({ text: q, lane: "template" });
    }

    // Reset the cleared flag after checking
    if (wasClearedRef.current && messages.length === 0) {
      wasClearedRef.current = false;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, messages.length, messagesInitialized]);

  // Save messages to storage whenever they change
  useEffect(() => {
    if (messages.length > 0) {
      saveMessagesToStorage(messages);
    }
  }, [messages]);

  function handleCancel() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsLoading(false);
      processingQueryRef.current = null;

      // Add cancellation message
      const cancelMessage: ChatMessage = {
        id: generateMessageId(),
        role: "error",
        content: "Query was cancelled by user.",
        timestamp: new Date().toISOString(),
        error: "Cancelled",
      };
      setMessages((prev) => [...prev, cancelMessage]);
    }
  }

  async function handleMessage({
    text,
    lane,
  }: {
    text: string;
    lane: "template" | "open" | "raw";
  }) {
    // Check for @graph or @suggest commands
    const trimmedText = text.trim();
    if (trimmedText.startsWith("@graph") || trimmedText.startsWith("@graphs") ||
      trimmedText.startsWith("@suggest") || trimmedText.startsWith("@suggestions")) {
      await handleGraphCommand(trimmedText);
      return;
    }

    // Prevent duplicate processing of the same query (only if currently processing)
    const queryKey = `${trimmedText}_${lane}`;
    if (processingQueryRef.current === queryKey) {
      console.warn(`[ChatPage] Query "${trimmedText}" is already being processed, skipping duplicate`);
      return;
    }

    processingQueryRef.current = queryKey;

    // Create abort controller for this query
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    // Add user message (always add it, even if similar ones exist)
    const userMessage: ChatMessage = {
      id: generateMessageId(),
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
      lane,
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    // Check if multi-hop is needed (only for template lane)
    if (lane === "template" && needsMultiHop(text)) {
      try {
        await handleMultiHopQuery(text, abortController);
      } catch (error: any) {
        console.error("[ChatPage] Multi-hop query error:", error);
        // Error is already handled in handleMultiHopQuery
      }
      return;
    }

    // Single-hop flow
    try {
      let result;
      if (lane === "raw") {
        result = await executeRawSPARQL(text, "wobd", abortController.signal);
      } else if (lane === "open") {
        result = await executeOpenQuery(text, "wobd", true, abortController.signal);
      } else {
        result = await executeTemplateQuery(text, "wobd", abortController.signal);
      }

      // Check if query was aborted
      if (abortController.signal.aborted) {
        return;
      }

      // Add assistant response (prevent duplicates by checking message ID only)
      setMessages((prev) => {
        // Check if this message ID already exists to prevent duplicates
        if (prev.some(msg => msg.id === result.message.id)) {
          console.warn(`[ChatPage] Duplicate message detected with ID ${result.message.id}, skipping`);
          return prev;
        }
        // Track this message ID to prevent future duplicates
        processingMessageIdsRef.current.add(result.message.id);
        return [...prev, result.message];
      });
      setSelectedMessageId(result.message.id);
    } catch (error: any) {
      // Don't show error if query was cancelled
      if (error.name === "AbortError" || abortController.signal.aborted) {
        return;
      }

      // Add error message
      const errorMessage: ChatMessage = {
        id: generateMessageId(),
        role: "error",
        content: `Error: ${error.message || "Unknown error occurred"}`,
        timestamp: new Date().toISOString(),
        lane,
        error: error.message,
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      // Clear processing query ref after completion
      processingQueryRef.current = null;
      abortControllerRef.current = null;
    }
  }

  async function handleMultiHopQuery(text: string, abortController: AbortController) {
    // Wrap entire function in try-catch to prevent synchronous errors from breaking React
    try {
      // Load context pack via API
      const packId = "wobd";
      const packResponse = await fetch(`/api/context-packs?pack_id=${packId}`);
      if (!packResponse.ok) {
        throw new Error("Failed to load context pack");
      }
      const pack: ContextPack = await packResponse.json();

      // Generate plan
      const llmEndpoint = "/api/tools/llm/complete";
      const sessionId = getSessionId();
      const plan = await planMultiHopQuery(text, pack, llmEndpoint, sessionId);

      // Show plan preview (configurable: auto-execute or wait for approval)
      const autoExecute = true; // TODO: Make this a user setting

      const planPreviewMessage: ChatMessage = {
        id: generateMessageId(),
        role: "assistant",
        content: `Generated query plan with ${plan.steps.length} steps`,
        timestamp: new Date().toISOString(),
        lane: "template",
        query_plan: plan,
        plan_id: plan.id,
        is_plan_preview: true,
      };
      setMessages(prev => [...prev, planPreviewMessage]);

      if (!autoExecute) {
        setIsLoading(false);
        processingQueryRef.current = null;
        abortControllerRef.current = null;
        return;
      }

      // Execute plan with streaming
      for await (const event of executeQueryPlan(plan, pack)) {
        // Check if query was aborted
        if (abortController.signal.aborted) {
          return;
        }

        if (event.type === "step_completed") {
          // Update messages with step results
          const stepMessage: ChatMessage = {
            id: generateMessageId(),
            role: "assistant",
            content: `Step ${event.step.id} completed: ${event.step.description}`,
            timestamp: new Date().toISOString(),
            lane: "template",
            plan_id: plan.id,
            step_id: event.step.id,
            intent: event.step.intent,
            sparql: event.step.sparql,
            results: event.step.results,
            metadata: {
              latency_ms: event.step.latency_ms,
              row_count: event.step.results?.results?.bindings?.length || 0,
            },
          };
          setMessages(prev => [...prev, stepMessage]);
          setSelectedMessageId(stepMessage.id);
        } else if (event.type === "step_failed") {
          const errorMessage: ChatMessage = {
            id: generateMessageId(),
            role: "error",
            content: `Step ${event.step.id} failed: ${event.error}`,
            timestamp: new Date().toISOString(),
            lane: "template",
            plan_id: plan.id,
            step_id: event.step.id,
            error: event.error,
          };
          setMessages(prev => [...prev, errorMessage]);
        } else if (event.type === "plan_completed") {
          // Synthesize final results
          // Find the last step that has results (skip entity_resolution steps for final display)
          const stepsWithResults = event.results.filter(s =>
            s.results && s.intent.task !== "entity_resolution"
          );
          const finalStep = stepsWithResults[stepsWithResults.length - 1] || event.results[event.results.length - 1];

          if (finalStep && finalStep.results) {
            const finalMessage: ChatMessage = {
              id: generateMessageId(),
              role: "assistant",
              content: `Query plan completed. Final results: ${finalStep.results?.results?.bindings?.length || 0} rows`,
              timestamp: new Date().toISOString(),
              lane: "template",
              plan_id: plan.id,
              results: finalStep.results,
              sparql: finalStep.sparql,
              metadata: {
                row_count: finalStep.results?.results?.bindings?.length || 0,
                latency_ms: finalStep.latency_ms,
              },
            };
            setMessages(prev => [...prev, finalMessage]);
            setSelectedMessageId(finalMessage.id);
          } else {
            // No results found - show summary
            const finalMessage: ChatMessage = {
              id: generateMessageId(),
              role: "assistant",
              content: `Query plan completed. No results found.`,
              timestamp: new Date().toISOString(),
              lane: "template",
              plan_id: plan.id,
            };
            setMessages(prev => [...prev, finalMessage]);
            setSelectedMessageId(finalMessage.id);
          }
        }
      }
    } catch (error: any) {
      // Don't show error if query was cancelled
      if (error.name === "AbortError" || abortController.signal.aborted) {
        return;
      }

      const errorMessage: ChatMessage = {
        id: generateMessageId(),
        role: "error",
        content: `Multi-hop query failed: ${error.message}`,
        timestamp: new Date().toISOString(),
        error: error.message,
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      processingQueryRef.current = null;
      abortControllerRef.current = null;
    }
  }

  async function handleGraphCommand(text: string) {
    const userMessage: ChatMessage = {
      id: generateMessageId(),
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      // Parse command: @graph, @graphs, @graph <shortname>, @suggest, @suggest <shortname>
      const parts = text.trim().split(/\s+/);
      const command = parts[0]; // @graph, @graphs, @suggest
      const shortname = parts[1]; // optional shortname
      const isSuggest = command === "@suggest" || command === "@suggestions";

      if (isSuggest) {
        // Handle suggestions
        // Default to full mode (quick=false) to get content-based suggestions
        let url = "/api/tools/registry/graphs/suggestions";
        if (shortname) {
          url += `?graphs=${encodeURIComponent(shortname)}&quick=false`;
        } else {
          url += "?quick=false";
        }

        const response = await fetch(url);
        const data = await response.json();

        if (data.error) {
          throw new Error(data.error);
        }

        let content = "";
        if (data.suggestions && data.suggestions.length > 0) {
          const suggestionsList = data.suggestions
            .map((s: any, idx: number) => {
              const question = s.question || s.topic || "Query suggestion";
              const description = s.description || "";
              const basedOn = s.basedOn ? `\n    (Based on: ${s.basedOn})` : "";
              const example = s.exampleQuery ? `\n    Example SPARQL:\n    ${s.exampleQuery.split("\n").map((l: string) => `    ${l}`).join("\n")}` : "";
              return `${idx + 1}. ${question}\n    ${description}${basedOn}${example}`;
            })
            .join("\n\n");

          content = `Scientific Questions & Query Suggestions for ${shortname ? `graph: ${shortname}` : "all graphs"}\n\n` +
            `${suggestionsList}\n\n` +
            `💡 These questions are based on actual content discovered in the graph(s). You can ask these questions directly or use the example SPARQL queries as a starting point!`;
        } else {
          content = `No suggestions available for ${shortname || "the specified graphs"}.`;
        }

        const assistantMessage: ChatMessage = {
          id: generateMessageId(),
          role: "assistant",
          content,
          timestamp: new Date().toISOString(),
        };

        setMessages((prev) => [...prev, assistantMessage]);
        setSelectedMessageId(assistantMessage.id);
      } else {
        // Handle graph info
        let url = "/api/tools/graphs/info";
        if (shortname) {
          url += `?shortname=${encodeURIComponent(shortname)}`;
        }

        const response = await fetch(url);
        const data = await response.json();

        let content = "";
        if (shortname) {
          // Details for a specific graph
          if (data.error) {
            const available = data.available_graphs?.join(", ") || "unknown";
            content = `Graph "${shortname}" not found.\n\nAvailable graphs: ${available}\n\nUse @graph to see the full list.`;
          } else {
            content = `Graph: ${data.label}\n\n` +
              `Shortname: ${data.shortname}\n` +
              `Graph IRI: ${data.graph_iri}\n` +
              `Endpoint: ${data.endpoint || "N/A"}\n\n` +
              `${data.description || ""}\n\n` +
              `Use in SPARQL queries:\n` +
              `FROM <${data.graph_iri}>\n` +
              `WHERE { ... }\n\n` +
              `💡 Tip: Use @suggest ${shortname} to get query suggestions for this graph!`;
          }
        } else {
          // List all graphs with descriptions
          const graphList = data.graphs
            .map((g: any) => {
              const desc = g.description ? `\n    ${g.description}` : "";
              return `  • ${g.label} (${g.shortname})${desc}`;
            })
            .join("\n\n");

          content = `Available Graphs in FRINK Federated SPARQL\n\n` +
            `Total: ${data.total} graphs\n\n` +
            `${graphList}\n\n` +
            `Use @graph <shortname> to get details about a specific graph.\n` +
            `Use @suggest <shortname> to get query suggestions for a graph.\n` +
            `Example: @graph nde or @suggest nde`;
        }

        const assistantMessage: ChatMessage = {
          id: generateMessageId(),
          role: "assistant",
          content,
          timestamp: new Date().toISOString(),
        };

        setMessages((prev) => [...prev, assistantMessage]);
        setSelectedMessageId(assistantMessage.id);
      }
    } catch (error: any) {
      const errorMessage: ChatMessage = {
        id: generateMessageId(),
        role: "error",
        content: `Error fetching graph information: ${error.message || "Unknown error"}`,
        timestamp: new Date().toISOString(),
        error: error.message,
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }

  const selectedMessage = messages.find((m) => m.id === selectedMessageId) || null;

  async function handleSelectPartialMatch(
    messageId: string,
    mondoIRI: string,
    mondoId: string,
    _originalQuery: string, // This is the assistant message content, not the user query
    lane: "template" | "open" | "raw"
  ) {
    // Find the assistant message and its corresponding user message
    const assistantMessageIndex = messages.findIndex(m => m.id === messageId);
    if (assistantMessageIndex === -1) return;

    const userMessageIndex = assistantMessageIndex > 0 ? assistantMessageIndex - 1 : -1;
    const userMessage = userMessageIndex >= 0 && messages[userMessageIndex].role === "user"
      ? messages[userMessageIndex]
      : null;

    if (!userMessage) {
      console.error("Could not find original user message for partial match selection");
      return;
    }

    // Get the original user query - prefer the raw phrase from ontology state, otherwise use user message
    const assistantMessage = messages[assistantMessageIndex];
    const originalQuery = assistantMessage.ontology_state?.raw_phrase || userMessage.content;

    // Re-run the query with the MONDO ID explicitly included
    // This will cause the ontology workflow to recognize and use the MONDO term directly
    const queryWithMONDO = `${originalQuery} ${mondoId}`;

    setIsLoading(true);

    try {
      let result;
      if (lane === "raw") {
        result = await executeRawSPARQL(queryWithMONDO);
      } else if (lane === "open") {
        result = await executeOpenQuery(queryWithMONDO);
      } else {
        result = await executeTemplateQuery(queryWithMONDO);
      }

      // Update the assistant message with new results
      const updatedAssistantMessage: ChatMessage = {
        ...result.message,
        id: messageId, // Keep the same ID
        timestamp: new Date().toISOString(),
      };

      setMessages(prev => {
        const updated = [...prev];
        updated[assistantMessageIndex] = updatedAssistantMessage;
        return updated;
      });

      setSelectedMessageId(messageId);
    } catch (error: any) {
      // Update with error
      const errorMessage: ChatMessage = {
        id: messageId,
        role: "error",
        content: `Error re-running query with selected term: ${error.message || "Unknown error occurred"}`,
        timestamp: new Date().toISOString(),
        lane,
        error: error.message,
      };

      setMessages(prev => {
        const updated = [...prev];
        updated[assistantMessageIndex] = errorMessage;
        return updated;
      });
    } finally {
      setIsLoading(false);
    }
  }

  function handleClearMessages() {
    if (confirm("Are you sure you want to clear all messages? This cannot be undone.")) {
      // Set flag to prevent auto-query from URL after clearing
      wasClearedRef.current = true;
      setMessages([]);
      clearMessagesFromStorage();
      setSelectedMessageId(null);
      // Reset the initial query ref so new queries from URL can be processed (but only on next navigation)
      hasProcessedInitialQuery.current = false;
      lastQueryRef.current = null;
      // Reset message count ref
      lastMessageCountRef.current = 0;
      // Reset scroll position to top
      if (chatContainerRef.current) {
        chatContainerRef.current.scrollTop = 0;
      }
    }
  }

  async function handleRetryWithoutLimit(messageId: string, query: string, lane: "template" | "open" | "raw") {
    // Find the existing assistant message
    const assistantMessageIndex = messages.findIndex(m => m.id === messageId);
    if (assistantMessageIndex === -1) return;

    const assistantMessage = messages[assistantMessageIndex];

    // Find the corresponding user message (should be the previous message)
    const userMessageIndex = assistantMessageIndex > 0 ? assistantMessageIndex - 1 : -1;
    const userMessage = userMessageIndex >= 0 && messages[userMessageIndex].role === "user"
      ? messages[userMessageIndex]
      : null;

    setIsLoading(true);

    // Update user message to indicate no limit version (if it exists)
    if (userMessage) {
      const originalContent = userMessage.content.replace(/\s*\(no limit\)\s*$/i, "").trim();
      const updatedUserMessage: ChatMessage = {
        ...userMessage,
        content: `${originalContent} (no limit)`,
      };
      setMessages(prev => {
        const updated = [...prev];
        updated[userMessageIndex] = updatedUserMessage;
        return updated;
      });
    }

    try {
      // Execute query without limit - always use raw SPARQL since we have the query
      const result = await executeRawSPARQL(query);

      // Update the existing assistant message with new results
      const updatedAssistantMessage: ChatMessage = {
        ...result.message,
        id: assistantMessage.id, // Keep the same ID
        timestamp: new Date().toISOString(), // Update timestamp
        // Preserve the original user message reference if needed
      };

      setMessages(prev => {
        const updated = [...prev];
        updated[assistantMessageIndex] = updatedAssistantMessage;
        return updated;
      });

      // Keep the message selected
      setSelectedMessageId(assistantMessage.id);
    } catch (error: any) {
      // Update with error
      const errorMessage: ChatMessage = {
        ...assistantMessage,
        role: "error",
        content: `Error removing limit: ${error.message || "Unknown error occurred"}`,
        timestamp: new Date().toISOString(),
        error: error.message,
      };

      setMessages(prev => {
        const updated = [...prev];
        updated[assistantMessageIndex] = errorMessage;
        return updated;
      });
    } finally {
      setIsLoading(false);
    }
  }


  // Track the last message count to detect when new messages are added
  const lastMessageCountRef = useRef(0);

  // Reset scroll position when messages are cleared
  useEffect(() => {
    if (messages.length === 0) {
      // Reset scroll to top when messages are cleared
      if (chatContainerRef.current) {
        chatContainerRef.current.scrollTop = 0;
      }
      lastMessageCountRef.current = 0;
    }
  }, [messages.length]);

  // Scroll to bottom when new messages arrive (before loading indicator)
  useEffect(() => {
    if (messages.length > lastMessageCountRef.current) {
      // New message was added - scroll to bottom to show it
      requestAnimationFrame(() => {
        setTimeout(() => {
          if (chatContainerRef.current) {
            chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
          }
        }, 100);
      });
      lastMessageCountRef.current = messages.length;
    }
  }, [messages.length]);

  // Scroll to loading indicator when loading state changes (but only after messages have rendered)
  useEffect(() => {
    if (isLoading) {
      // Wait for messages to render, then scroll to loading indicator
      requestAnimationFrame(() => {
        setTimeout(() => {
          if (chatContainerRef.current) {
            // Ensure we're at the bottom first
            chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
          }
          // Then scroll loading indicator into view (use "nearest" to avoid hiding content above)
          if (isLoadingRef.current) {
            isLoadingRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
          }
        }, 200);
      });
    }
  }, [isLoading]);

  return (
    <div className="flex h-[calc(100vh-80px)] bg-white dark:bg-slate-950 overflow-hidden">
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header with clear button */}
        {messages.length > 0 && (
          <div className="flex justify-end items-center px-6 pt-4 pb-2 border-b border-slate-200 dark:border-slate-800">
            <button
              onClick={handleClearMessages}
              className="px-3 py-1.5 text-sm text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 rounded border border-slate-300 dark:border-slate-700 transition-colors"
              title="Clear all messages"
            >
              Clear Messages
            </button>
          </div>
        )}
        <div ref={chatContainerRef} className="flex-1 overflow-y-auto p-6 bg-white dark:bg-slate-950" style={{ paddingBottom: 0 }}>
          <ChatHistory
            messages={messages}
            onMessageSelect={setSelectedMessageId}
            selectedMessageId={selectedMessageId}
            onRetryWithoutLimit={handleRetryWithoutLimit}
            onSelectPartialMatch={handleSelectPartialMatch}
          />
          {isLoading && (
            <div ref={isLoadingRef} className="flex justify-start mt-4 p-6">
              <div className="bg-slate-100 dark:bg-slate-800 rounded-lg px-4 py-3 border border-slate-200 dark:border-slate-700">
                <div className="flex items-center gap-3">
                  <div className="animate-spin h-4 w-4 border-2 border-accent border-t-transparent rounded-full" />
                  <span className="text-slate-600 dark:text-slate-400">Processing query...</span>
                  <div className="tooltip-container">
                    <button
                      onClick={handleCancel}
                      className="ml-2 p-1.5 hover:bg-slate-200 dark:hover:bg-slate-700 rounded transition-colors"
                      aria-label="Stop query"
                    >
                      <svg
                        className="w-4 h-4 text-slate-600 dark:text-slate-400"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M6 18L18 6M6 6l12 12"
                        />
                      </svg>
                    </button>
                    <span className="tooltip">Stop query</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Input area - auto-sized to fit content */}
        <div className="border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 flex-shrink-0">
          <div className="p-4">
            <ChatComposer
              initialValue={searchParams.get("q") || ""}
              onMessage={handleMessage}
            />
          </div>
        </div>
      </div>
      <InspectDrawer message={selectedMessage} />
    </div>
  );
}



