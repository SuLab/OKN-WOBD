import { ArrowRight } from "lucide-react";

export interface EvidenceMapItem {
  label: string;
  body: string;
}

export function EvidenceMap({ items }: { items: EvidenceMapItem[] }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr_auto_1fr]">
        {items.map((item, index) => (
          <div key={item.label} className="contents">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800/60">
              <div className="text-xs font-semibold uppercase tracking-wider text-okn-primary">
                {item.label}
              </div>
              <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                {item.body}
              </p>
            </div>
            {index < items.length - 1 && (
              <div className="flex items-center justify-center text-slate-400" aria-hidden>
                <ArrowRight className="hidden h-5 w-5 md:block" />
                <ArrowRight className="h-5 w-5 rotate-90 md:hidden" />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
