"use client";

import React, { useState, useRef, useCallback } from "react";
import type { TemplateDefinition } from "@/lib/context-packs/types";
import { SlotForm, isSlotFilled, getSlotMeta } from "./SlotForm";

const TOOLTIP_DELAY_MS = 200;

const GXA_TASKS = [
  "gene_expression_dataset_search",
  "gene_expression_genes_in_experiment",
  "gene_expression_experiments_for_gene",
  "gene_expression_gene_cross_dataset_summary",
  "gene_expression_genes_agreement",
  "gene_expression_genes_discordance",
];

export interface TemplateCardProps {
  template: TemplateDefinition;
  slotValues: Record<string, string | string[]>;
  onSlotChange: (values: Record<string, string | string[]>) => void;
  onRun: () => void;
  running?: boolean;
  disabled?: boolean;
}

function getMissingRequiredSlots(
  template: TemplateDefinition,
  values: Record<string, string | string[]>
): string[] {
  const required = template.required_slots ?? [];
  return required.filter((slot) => !isSlotFilled(values[slot]));
}

export function TemplateCard({
  template,
  slotValues,
  onSlotChange,
  onRun,
  running,
  disabled,
}: TemplateCardProps) {
  const missingRequired = getMissingRequiredSlots(template, slotValues);
  const canRun = missingRequired.length === 0;
  const [tooltipVisible, setTooltipVisible] = useState(false);
  const tooltipTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showTooltip = useCallback(() => {
    if (!canRun) {
      tooltipTimeoutRef.current = setTimeout(() => setTooltipVisible(true), TOOLTIP_DELAY_MS);
    }
  }, [canRun]);

  const hideTooltip = useCallback(() => {
    if (tooltipTimeoutRef.current) {
      clearTimeout(tooltipTimeoutRef.current);
      tooltipTimeoutRef.current = null;
    }
    setTooltipVisible(false);
  }, []);

  const requiredMessage = missingRequired.length > 0
    ? `Fill in required: ${missingRequired.map((s) => getSlotMeta(s).label).join(", ")}`
    : "";

  return (
    <article
      className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm overflow-visible"
      aria-labelledby={`card-title-${template.id}`}
    >
      <div
        className="px-4 py-2 flex items-center justify-between"
        style={{ backgroundColor: "var(--niaid-header)" }}
      >
        <span id={`card-title-${template.id}`} className="text-white font-semibold text-sm">
          {template.description}
        </span>
      </div>
      <div className="p-4 space-y-4">
        <SlotForm
          template={template}
          values={slotValues}
          onChange={onSlotChange}
          disabled={disabled}
        />
        <div
          className="relative"
          onMouseEnter={showTooltip}
          onMouseLeave={hideTooltip}
        >
          {tooltipVisible && !canRun && requiredMessage && (
            <div
              role="tooltip"
              className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 px-2.5 py-1.5 text-xs text-white bg-slate-800 dark:bg-slate-700 rounded shadow-lg whitespace-nowrap z-10"
            >
              {requiredMessage}
            </div>
          )}
          <button
            type="button"
            onClick={onRun}
            disabled={disabled || running || !canRun}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2 rounded-md text-white text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-default"
            style={{ backgroundColor: "var(--niaid-button)" }}
          >
            {running ? (
              <>
                <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" aria-hidden />
                Running…
              </>
            ) : (
              "Run query"
            )}
          </button>
        </div>
      </div>
    </article>
  );
}
