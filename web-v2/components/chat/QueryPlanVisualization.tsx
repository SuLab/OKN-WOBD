"use client";

import type { QueryPlan, QueryStep, ChatMessage } from "@/types";
import { useState } from "react";
import { ResultsTable } from "./ResultsTable";
import { SparqlEditor } from "./SparqlEditor";

interface QueryPlanVisualizationProps {
    plan: QueryPlan;
    allMessages: ChatMessage[]; // Messages with step results
}

export function QueryPlanVisualization({ plan, allMessages }: QueryPlanVisualizationProps) {
    const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());

    const toggleStep = (stepId: string) => {
        setExpandedSteps(prev => {
            const next = new Set(prev);
            if (next.has(stepId)) {
                next.delete(stepId);
            } else {
                next.add(stepId);
            }
            return next;
        });
    };

    const getStepMessage = (stepId: string) => {
        return allMessages.find(m => m.step_id === stepId);
    };

    const getStatusBadge = (step: QueryStep) => {
        const message = getStepMessage(step.id);
        const status = message ? (message.error ? "failed" : "complete") : step.status;

        const badges = {
            pending: { icon: "⏳", color: "text-slate-400", bg: "bg-slate-700" },
            running: { icon: "🔄", color: "text-blue-400", bg: "bg-blue-900/30" },
            complete: { icon: "✅", color: "text-green-400", bg: "bg-green-900/30" },
            failed: { icon: "❌", color: "text-red-400", bg: "bg-red-900/30" },
        };

        const badge = badges[status];

        return (
            <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium ${badge.color} ${badge.bg}`}>
                <span>{badge.icon}</span>
                <span>{status}</span>
            </span>
        );
    };

    const completedSteps = plan.steps.filter(s => {
        const msg = getStepMessage(s.id);
        return msg && !msg.error;
    }).length;

    return (
        <div className="space-y-4 p-4">
            <div className="pb-3 border-b border-slate-700">
                <h3 className="text-sm font-semibold text-slate-200">Query Plan</h3>
                <p className="text-xs text-slate-400 mt-1">
                    Progress: {completedSteps}/{plan.steps.length} steps complete
                </p>
            </div>

            <div className="space-y-4">
                {plan.steps.map((step, idx) => {
                    const message = getStepMessage(step.id);
                    const isExpanded = expandedSteps.has(step.id);
                    const resultCount = message?.results?.results?.bindings?.length || 0;

                    return (
                        <div key={step.id} className="border border-slate-700 rounded-lg overflow-hidden">
                            <div className="p-3 bg-slate-800/50">
                                <div className="flex items-start justify-between">
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2 mb-2">
                                            <span className="text-xs font-semibold text-slate-400">
                                                Step {idx + 1}
                                            </span>
                                            {getStatusBadge(step)}
                                            {message?.metadata?.latency_ms && (
                                                <span className="text-xs text-slate-500">
                                                    {message.metadata.latency_ms}ms
                                                </span>
                                            )}
                                        </div>
                                        <p className="text-sm text-slate-200 font-medium">{step.description}</p>
                                        <p className="text-xs text-slate-400 mt-1">
                                            Target: {step.target_graphs.join(", ")}
                                        </p>
                                        {step.uses_results_from && (
                                            <p className="text-xs text-slate-500 mt-1">
                                                Uses results from: {step.uses_results_from}
                                            </p>
                                        )}
                                    </div>
                                    {message && (
                                        <button
                                            onClick={() => toggleStep(step.id)}
                                            className="text-xs text-blue-400 hover:text-blue-300"
                                        >
                                            {isExpanded ? "▼ Collapse" : "▶ Expand"}
                                        </button>
                                    )}
                                </div>
                            </div>

                            {isExpanded && message && (
                                <div className="border-t border-slate-700 p-3 bg-slate-900/30 space-y-3">
                                    {message.sparql && (
                                        <details>
                                            <summary className="text-xs font-semibold text-slate-300 cursor-pointer hover:text-slate-200">
                                                View SPARQL Query
                                            </summary>
                                            <div className="mt-2">
                                                <SparqlEditor value={message.sparql} readOnly />
                                            </div>
                                        </details>
                                    )}

                                    {message.results && (
                                        <details open>
                                            <summary className="text-xs font-semibold text-slate-300 cursor-pointer hover:text-slate-200">
                                                View Results ({resultCount} rows)
                                            </summary>
                                            <div className="mt-2">
                                                <ResultsTable bindings={message.results.results.bindings} />
                                            </div>
                                        </details>
                                    )}

                                    {message.error && (
                                        <div className="p-3 bg-red-900/20 border border-red-800 rounded text-xs text-red-300">
                                            <p className="font-semibold">Error:</p>
                                            <p className="mt-1">{message.error}</p>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
