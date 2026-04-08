import React from "react";

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

const DEFAULT_MARK_CLASS =
  "bg-amber-200 dark:bg-amber-900/55 text-inherit rounded px-0.5";

export type HighlightTermsInTextOptions = {
  /** Override default <mark> classes (e.g. for colored chips). */
  markClassName?: string;
};

/**
 * Wrap case-insensitive matches of any term in <mark> (longest terms first to avoid partial steals).
 */
export function highlightTermsInText(
  text: string,
  terms: string[],
  options?: HighlightTermsInTextOptions
): React.ReactNode {
  const cleaned = [...new Set(terms.map((t) => t.trim()).filter(Boolean))];
  if (!text || cleaned.length === 0) return text;

  const pattern = [...cleaned].sort((a, b) => b.length - a.length).map(escapeRegExp).join("|");
  if (!pattern) return text;

  const markClassName = options?.markClassName ?? DEFAULT_MARK_CLASS;

  const re = new RegExp(`(${pattern})`, "gi");
  const out: React.ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  let k = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) {
      out.push(text.slice(last, m.index));
    }
    out.push(
      <mark
        key={`hl-${k++}`}
        className={markClassName}
      >
        {m[0]}
      </mark>
    );
    last = m.index + m[0].length;
    if (m[0].length === 0) {
      re.lastIndex += 1;
    }
  }
  if (last < text.length) {
    out.push(text.slice(last));
  }
  if (out.length === 0) return text;
  return <>{out}</>;
}
