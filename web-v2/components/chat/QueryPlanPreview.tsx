"use client";

import type { QueryPlan } from "@/types";

interface QueryPlanPreviewProps {
    plan: QueryPlan;
    onExecute?: () => void;
    onCancel?: () => void;
    isExecuting?: boolean;
}

export function QueryPlanPreview({ plan, onExecute, onCancel, isExecuting }: QueryPlanPreviewProps) {
    const graphsInvolved = [...new Set(plan.steps.flatMap(s => s.target_graphs))];

    return (
        <div className="border border-slate-600 rounded-lg p-4 bg-slate-800/50">
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h3 className="text-sm font-semibold text-slate-200">
                        Query Plan: {plan.steps.length} steps
                    </h3>
                    <p className="text-xs text-slate-400 mt-1">
                        Graphs: {graphsInvolved.join(", ")}
                    </p>
                </div>
                {onExecute && (
                    <div className="flex gap-2">
                        <button
                            onClick={onCancel}
                            disabled={isExecuting}
                            className="px-3 py-1.5 text-sm bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 text-slate-300 rounded transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            onClick={onExecute}
                            disabled={isExecuting}
                            className="px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 text-white rounded transition-colors"
                        >
                            {isExecuting ? "Executing..." : "Execute Plan"}
                        </button>
                    </div>
                )}
            </div>

            <div className="space-y-3">
                {plan.steps.map((step, idx) => (
                    <div key={step.id} className="flex items-start gap-3">
                        <div className="flex-shrink-0 w-6 h-6 rounded-full bg-slate-700 flex items-center justify-center text-xs font-semibold text-slate-300">
                            {idx + 1}
                        </div>
                        <div className="flex-1">
                            <p className="text-sm text-slate-200 font-medium">{step.description}</p>
                            <p className="text-xs text-slate-400 mt-1">
                                Target: {step.target_graphs.join(", ")}
                            </p>
                            {step.depends_on.length > 0 && (
                                <p className="text-xs text-slate-500 mt-1">
                                    Depends on: {step.depends_on.join(", ")}
                                </p>
                            )}
                        </div>
                        {idx < plan.steps.length - 1 && (
                            <div className="text-slate-600 text-lg">↓</div>
                        )}
                    </div>
                ))}
            </div>

            {plan.graph_routing_rationale && (
                <div className="mt-4 pt-4 border-t border-slate-700">
                    <p className="text-xs text-slate-400">
                        <span className="font-semibold">Rationale:</span> {plan.graph_routing_rationale}
                    </p>
                </div>
            )}
        </div>
    );
}
