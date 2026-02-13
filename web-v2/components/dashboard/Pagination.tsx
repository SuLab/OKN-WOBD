"use client";

import React from "react";

/** Default number of results per page (matches NIAID Dataset Discovery Portal feel). */
export const DEFAULT_PAGE_SIZE = 25;

/** NIAID-style pagination: first, prev, page numbers with ellipsis, next, last. */
export interface PaginationProps {
  /** 1-based current page */
  page: number;
  /** Total number of items */
  totalItems: number;
  /** Items per page */
  pageSize: number;
  onPageChange: (page: number) => void;
  /** Optional aria label for the nav */
  ariaLabel?: string;
}

/**
 * Compute which page numbers to show (e.g. 1, 2, 3, 4, 5, "...", 138).
 * Mirrors NIAID Dataset Discovery Portal: first few, ellipsis, last.
 */
function getPageNumbers(current: number, totalPages: number): (number | "ellipsis")[] {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }
  const list: (number | "ellipsis")[] = [];
  if (current <= 4) {
    for (let i = 1; i <= 5; i++) list.push(i);
    list.push("ellipsis");
    list.push(totalPages);
  } else if (current >= totalPages - 3) {
    list.push(1);
    list.push("ellipsis");
    for (let i = totalPages - 4; i <= totalPages; i++) list.push(i);
  } else {
    list.push(1);
    list.push("ellipsis");
    for (let i = current - 2; i <= current + 2; i++) list.push(i);
    list.push("ellipsis");
    list.push(totalPages);
  }
  return list;
}

export function Pagination({
  page,
  totalItems,
  pageSize,
  onPageChange,
  ariaLabel = "Results pagination",
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const canPrev = page > 1;
  const canNext = page < totalPages;
  const pageNumbers = getPageNumbers(page, totalPages);

  const btnBase =
    "inline-flex items-center justify-center min-w-[2.25rem] h-9 px-2 rounded-md text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed";
  const btnActive = "text-white border border-transparent";
  const btnInactive =
    "bg-white dark:bg-slate-900 border border-niaid-paginationBorder text-niaid-paginationText hover:bg-slate-50 dark:hover:bg-slate-800";

  return (
    <nav aria-label={ariaLabel} className="flex flex-wrap items-center justify-center gap-1">
      <button
        type="button"
        aria-label="First page"
        onClick={() => onPageChange(1)}
        disabled={!canPrev}
        className={`${btnBase} ${btnInactive}`}
      >
        &#171;
      </button>
      <button
        type="button"
        aria-label="Previous page"
        onClick={() => onPageChange(page - 1)}
        disabled={!canPrev}
        className={`${btnBase} ${btnInactive}`}
      >
        &#8249;
      </button>
      {pageNumbers.map((item, i) =>
        item === "ellipsis" ? (
          <span
            key={`ellipsis-${i}`}
            className="min-w-[2.25rem] h-9 flex items-center justify-center text-slate-500"
            aria-hidden="true"
          >
            &#8230;
          </span>
        ) : (
          <button
            key={item}
            type="button"
            aria-label={item === page ? `Page ${item}, current page` : `Page ${item}`}
            aria-current={item === page ? "page" : undefined}
            onClick={() => onPageChange(item)}
            className={`${btnBase} ${item === page ? btnActive : btnInactive}`}
            style={item === page ? { backgroundColor: "var(--niaid-pagination-active)" } : undefined}
          >
            {item}
          </button>
        )
      )}
      <button
        type="button"
        aria-label="Next page"
        onClick={() => onPageChange(page + 1)}
        disabled={!canNext}
        className={`${btnBase} ${btnInactive}`}
      >
        &#8250;
      </button>
      <button
        type="button"
        aria-label="Last page"
        onClick={() => onPageChange(totalPages)}
        disabled={!canNext}
        className={`${btnBase} ${btnInactive}`}
      >
        &#187;
      </button>
    </nav>
  );
}
