"use client";

import { useState, FormEvent, useEffect, useRef } from "react";
import { SparqlEditor, type SparqlEditorRef } from "./SparqlEditor";

type Lane = "template" | "open" | "raw";

interface ChatComposerProps {
  initialValue?: string;
  onMessage?: (message: { text: string; lane: Lane }) => void;
}

export function ChatComposer({ initialValue = "", onMessage }: ChatComposerProps) {
  const [textValue, setTextValue] = useState(initialValue);
  const [sparqlValue, setSparqlValue] = useState("");
  const [lane, setLane] = useState<Lane>("template");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [shouldAutoFocus, setShouldAutoFocus] = useState(false);
  const [showModifyInput, setShowModifyInput] = useState(false);
  const [modifyInstruction, setModifyInstruction] = useState("");
  const [isModifying, setIsModifying] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const sparqlEditorRef = useRef<SparqlEditorRef>(null);
  const lastCommandRef = useRef<string | null>(null);
  const shouldFocusRef = useRef(false);
  const manualModeChangeRef = useRef(false); // Track manual button clicks

  // Detect lane from input and handle mode switching
  useEffect(() => {
    // Check both textValue and sparqlValue for commands
    const textTrimmed = textValue.trim();
    const sparqlTrimmed = sparqlValue.trim();
    const textLower = textTrimmed.toLowerCase();
    const sparqlLower = sparqlTrimmed.toLowerCase();

    // Check /text first (before /sparql) to avoid conflicts
    if (textLower === "/text" || sparqlLower === "/text") {
      // Just switching mode - clear input and set lane to template (shown as Text)
      lastCommandRef.current = "/text";
      shouldFocusRef.current = true;
      setShouldAutoFocus(false); // Don't auto-focus textarea, it will be focused by the effect
      setLane("template");
      setTextValue("");
      setSparqlValue("");
      return;
    } else if (textLower.startsWith("/text")) {
      // /text with text - set lane to template (shown as Text) and keep text (will strip prefix on submit)
      lastCommandRef.current = "/text";
      shouldFocusRef.current = true;
      setShouldAutoFocus(false);
      setLane("template");
    } else if (sparqlLower.startsWith("/text")) {
      // /text in SPARQL editor - switch to template mode (shown as Text)
      lastCommandRef.current = "/text";
      shouldFocusRef.current = true;
      setShouldAutoFocus(false);
      setLane("template");
      const query = sparqlTrimmed.replace(/^\/text\s*/i, "").trim();
      setTextValue(query);
      setSparqlValue("");
    } else if (textLower === "/sparql" || sparqlLower === "/sparql") {
      // Just switching mode - clear input and set lane
      lastCommandRef.current = "/sparql";
      shouldFocusRef.current = true;
      setShouldAutoFocus(true); // Auto-focus SPARQL editor
      setLane("raw");
      setSparqlValue("");
      setTextValue("");
      return;
    } else if (textLower.startsWith("/sparql")) {
      // /sparql with text - set lane and extract SPARQL
      lastCommandRef.current = "/sparql";
      shouldFocusRef.current = true;
      setShouldAutoFocus(true); // Auto-focus SPARQL editor
      setLane("raw");
      const sparql = textTrimmed.replace(/^\/sparql\s*/i, "").trim();
      if (sparql) {
        setSparqlValue(sparql);
        setTextValue("");
      }
    } else {
      // No command detected - clear the last command ref if we have content
      // This allows the user to type after using a command
      if (textTrimmed || sparqlTrimmed) {
        lastCommandRef.current = null;
      }
    }

    // Clear command ref when user starts typing after a command
    // This ensures the fallback logic works correctly after the user has typed something
    if ((textTrimmed || sparqlTrimmed) && lastCommandRef.current) {
      // User has typed something after the command, so clear the ref
      // This will be handled in the else block above, but we ensure it here too
      if (!textLower.startsWith("/") && !sparqlLower.startsWith("/")) {
        lastCommandRef.current = null;
      }
    }

    // Don't auto-switch lanes based on content - only respond to explicit commands
    // If no commands and no input, ensure default is template mode
    // But don't reset if we just handled a command (check lastCommandRef)
    // Only reset if we're not in the middle of a command switch
    // IMPORTANT: Don't reset if we're currently modifying a query OR if we're in raw mode with content
    // ALSO: Don't reset if the user just manually clicked a mode button
    const shouldNotReset = isModifying ||
      manualModeChangeRef.current ||
      (lane === "raw" && sparqlValue.trim().length > 0) ||
      lastCommandRef.current === "/sparql" ||
      lastCommandRef.current === "/text";

    if (!textTrimmed && !sparqlTrimmed && !shouldNotReset) {
      // Only reset to template if we're not already there and we haven't just switched modes
      if (lane !== "template") {
        console.log("[ChatComposer] Auto-switching to template mode (both inputs empty)");
        setLane("template");
      }
      lastCommandRef.current = null;
    }
  }, [textValue, sparqlValue, lane, isModifying]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();

    // Prevent multiple submissions
    if (isSubmitting) {
      console.warn("[ChatComposer] Already submitting, ignoring duplicate submission");
      return;
    }

    const isRawLane = lane === "raw";
    let query = isRawLane ? sparqlValue.trim() : textValue.trim();

    // Strip command prefixes from query text
    if (!isRawLane) {
      query = query.replace(/^\/text\s*/i, "").replace(/^\/sparql\s*/i, "").trim();
    }

    // Don't submit if query is empty or just a command
    if (!query || query === "/text" || query === "/sparql") return;

    setIsSubmitting(true);

    try {
      // Call onMessage callback if provided
      if (onMessage) {
        onMessage({ text: query, lane });
        // Clear input after submission
        if (lane === "raw") {
          setSparqlValue("");
        } else {
          setTextValue("");
        }
      } else {
        // Fallback: handle submission directly
        await handleSubmission(query, lane);
      }
    } catch (error) {
      console.error("Submission error:", error);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleSubmission(query: string, currentLane: Lane) {
    // This is now handled by the parent via onMessage callback
    // Keep this as fallback for direct calls if needed
    if (onMessage) {
      onMessage({ text: query, lane: currentLane });
    }
  }

  // Handle SPARQL query modification with AI
  async function handleModifyQuery() {
    if (!modifyInstruction.trim() || !sparqlValue.trim()) return;
    await handleModifyQueryWithInstruction(modifyInstruction);
  }

  // Helper function that takes instruction directly (for quick actions)
  async function handleModifyQueryWithInstruction(instruction: string) {
    if (!instruction.trim() || !sparqlValue.trim()) return;

    setIsModifying(true);
    try {
      const response = await fetch("/api/tools/sparql/modify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sparql: sparqlValue,
          instruction: instruction,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to modify query");
      }

      const result = await response.json();

      // Check if validation failed and the fallback (original query) was returned
      if (result.fallback_used && result.validation_errors) {
        console.warn("[ChatComposer] Query modification produced invalid SPARQL:", result.validation_errors);
        alert(`⚠️ The AI-generated query had syntax errors and couldn't be applied:\n\n${result.validation_errors.join('\n')}\n\nThe original query has been kept. Please try a different instruction or modify the query manually.`);
        setShowModifyInput(false);
        return;
      }

      // Only update if we got a valid modified query
      if (result.modified_query && result.modified_query.trim().length > 0) {
        setSparqlValue(result.modified_query);
        setModifyInstruction("");
        setShowModifyInput(false);
      } else {
        console.error("[ChatComposer] Received empty modified query, keeping original");
        // Keep the modify panel open so user can try again
      }
    } catch (error) {
      console.error("Failed to modify query:", error);
      // TODO: Could show an error toast here
    } finally {
      setIsModifying(false);
    }
  }

  // Quick action presets for common modifications
  const quickActions = [
    { label: "Add LIMIT 50", instruction: "Add LIMIT 50 to this query" },
    { label: "Remove LIMIT", instruction: "Remove the LIMIT clause" },
    { label: "Add description", instruction: "Add ?description to the SELECT clause and an OPTIONAL clause to fetch schema:description" },
    { label: "Count only", instruction: "Change this to a COUNT query that returns the total number of results" },
  ];

  // Handle mode switching via clicks
  const handleModeClick = (newLane: Lane) => {
    console.log(`[ChatComposer] Switching from ${lane} to ${newLane}`);

    // Mark that this is a manual mode change
    manualModeChangeRef.current = true;

    if (newLane === "raw") {
      // Switching TO raw mode
      if (lane !== "raw") {
        // Don't clear sparqlValue if it already has content
        // Only clear textValue
        setTextValue("");
        if (!sparqlValue.trim()) {
          // Only clear SPARQL if it's empty
          setSparqlValue("");
        }
        setShouldAutoFocus(true); // Auto-focus SPARQL editor
      }
    } else {
      // Switching TO template/text mode (from raw)
      if (lane === "raw") {
        // Don't clear sparqlValue - keep it in case user switches back
        setShouldAutoFocus(false);
      }
    }
    shouldFocusRef.current = true;
    setLane(newLane);

    // Reset the manual flag after a short delay (after useEffect has run)
    setTimeout(() => {
      manualModeChangeRef.current = false;
    }, 100);
  };

  // Auto-resize textarea based on content
  useEffect(() => {
    if (textareaRef.current && lane !== "raw") {
      textareaRef.current.style.height = "auto";
      const scrollHeight = textareaRef.current.scrollHeight;
      const minHeight = 80;
      const maxHeight = 200;
      const newHeight = Math.min(Math.max(scrollHeight, minHeight), maxHeight);
      textareaRef.current.style.height = `${newHeight}px`;
    }
  }, [textValue, lane]);

  // Focus the appropriate input when lane changes (from buttons or slash commands)
  useEffect(() => {
    if (shouldFocusRef.current) {
      // Use setTimeout to ensure the DOM has updated, especially for Monaco editor
      const attemptFocus = (retries = 3) => {
        setTimeout(() => {
          if (lane === "raw") {
            // SPARQL editor will auto-focus via autoFocus prop
            shouldFocusRef.current = false;
            setShouldAutoFocus(false); // Reset after focusing
          } else if (textareaRef.current) {
            // Focus textarea for template/text mode
            textareaRef.current.focus();
            shouldFocusRef.current = false;
            setShouldAutoFocus(false);
          } else if (retries > 0) {
            // Retry if textarea not ready yet
            attemptFocus(retries - 1);
          } else {
            shouldFocusRef.current = false;
            setShouldAutoFocus(false);
          }
        }, 100);
      };

      attemptFocus();
    }
  }, [lane]);

  // Show user-friendly labels
  const inputTypeLabel = lane === "raw" ? "SPARQL Editor" : "Ask a question";

  return (
    <form onSubmit={onSubmit} className="w-full space-y-3">
      {/* Mode selector boxes - only show Text and SPARQL */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log("[ChatComposer] Text button clicked");
            handleModeClick("template");
          }}
          className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors cursor-pointer ${lane === "template"
            ? "bg-accent text-white dark:text-white"
            : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700 border border-slate-300 dark:border-slate-700"
            }`}
          title="Ask questions in natural language"
        >
          Text
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log("[ChatComposer] SPARQL button clicked, current lane:", lane);
            handleModeClick("raw");
          }}
          className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors cursor-pointer ${lane === "raw"
            ? "bg-accent text-white dark:text-white"
            : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700 border border-slate-300 dark:border-slate-700"
            }`}
          title="Write SPARQL queries directly"
        >
          SPARQL
        </button>
      </div>

      {/* Help text */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-slate-600 dark:text-slate-400">
          {inputTypeLabel}
        </span>
        {lane === "raw" && (
          <span className="text-xs text-slate-500 dark:text-slate-400">
            Type /text to switch to text mode, or just type to ask a question
          </span>
        )}
        {lane === "template" && (
          <span className="text-xs text-slate-500 dark:text-slate-400">
            Type /sparql for SPARQL editor, or @graph for graph info
          </span>
        )}
      </div>

      {/* Input area - textarea for Text mode, SPARQL editor for SPARQL mode */}
      {lane === "raw" ? (
        <div className="space-y-2">
          <div className="border border-slate-300 dark:border-slate-700 rounded-lg overflow-hidden" style={{ height: "200px", minHeight: "200px" }}>
            <SparqlEditor
              ref={sparqlEditorRef}
              value={sparqlValue}
              onChange={setSparqlValue}
              onExecute={() => onSubmit(new Event("submit") as any)}
              height="200px"
              autoFocus={shouldAutoFocus}
            />
          </div>

          {/* AI Modify feature */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setShowModifyInput(!showModifyInput)}
                disabled={!sparqlValue.trim()}
                className="px-3 py-1.5 text-xs bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:text-slate-500 text-slate-200 rounded-md transition-colors flex items-center gap-1"
                title="Use AI to modify your SPARQL query"
              >
                <span>✨</span>
                <span>{showModifyInput ? "Cancel" : "Modify with AI"}</span>
              </button>
              {!showModifyInput && sparqlValue.trim() && (
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  Ask AI to modify your query (e.g., "add LIMIT 100")
                </span>
              )}
            </div>

            {showModifyInput && (
              <div className="space-y-2">
                {/* Quick actions */}
                <div className="flex flex-wrap gap-2">
                  <span className="text-xs text-slate-500 dark:text-slate-400 self-center">Quick:</span>
                  {quickActions.map((action) => (
                    <button
                      key={action.label}
                      type="button"
                      onClick={() => handleModifyQueryWithInstruction(action.instruction)}
                      disabled={isModifying}
                      className="px-2 py-1 text-xs bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:text-slate-500 text-slate-300 rounded transition-colors"
                    >
                      {action.label}
                    </button>
                  ))}
                </div>

                {/* Custom instruction input */}
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={modifyInstruction}
                    onChange={(e) => setModifyInstruction(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleModifyQuery();
                      } else if (e.key === "Escape") {
                        setShowModifyInput(false);
                        setModifyInstruction("");
                      }
                    }}
                    placeholder="Or type a custom instruction..."
                    className="flex-1 px-3 py-1.5 text-sm bg-slate-800 border border-slate-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-slate-200 placeholder-slate-500"
                    disabled={isModifying}
                    autoFocus
                  />
                  <button
                    type="button"
                    onClick={handleModifyQuery}
                    disabled={isModifying || !modifyInstruction.trim()}
                    className="px-4 py-1.5 text-sm bg-blue-600 hover:bg-blue-500 disabled:bg-slate-600 disabled:text-slate-400 text-white rounded-md transition-colors"
                  >
                    {isModifying ? "Modifying..." : "Apply"}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        <textarea
          ref={textareaRef}
          value={textValue}
          onChange={(e) => {
            setTextValue(e.target.value);
            // Auto-resize on input
            if (textareaRef.current) {
              textareaRef.current.style.height = "auto";
              const scrollHeight = textareaRef.current.scrollHeight;
              const minHeight = 80;
              const maxHeight = 200;
              const newHeight = Math.min(Math.max(scrollHeight, minHeight), maxHeight);
              textareaRef.current.style.height = `${newHeight}px`;
            }
          }}
          onKeyDown={(e) => {
            // Cmd+Enter (Mac) or Ctrl+Enter (Windows/Linux) to submit
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
              e.preventDefault();
              onSubmit(e as any);
            }
          }}
          placeholder={
            lane === "template"
              ? "Type your question (e.g., 'Find datasets about diabetes')..."
              : "Type your question or use /sparql for SPARQL editor, /text for text mode..."
          }
          className="w-full px-4 py-3 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent resize-none font-mono text-sm text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 overflow-y-auto"
          style={{ minHeight: "80px", maxHeight: "200px" }}
        />
      )}

      {/* Submit button */}
      <div className="flex justify-end items-center gap-2">
        <span className="text-xs text-slate-500 dark:text-slate-400">
          {lane === "raw" ? "Cmd/Ctrl + Enter" : "Cmd/Ctrl + Enter to send"}
        </span>
        <button
          type="submit"
          disabled={isSubmitting || (!textValue.trim() && !sparqlValue.trim())}
          className="px-6 py-2 bg-accent text-white rounded-md font-medium hover:bg-accentDark dark:hover:bg-accentDark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isSubmitting ? "Sending..." : "Send"}
        </button>
      </div>
    </form>
  );
}



