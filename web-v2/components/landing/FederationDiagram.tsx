import { Bot, FileSearch, Network, ShieldCheck } from "lucide-react";

const sources = ["Dataset metadata", "Knowledge graphs", "Ontologies", "Curated resources"];

const outputs = [
  { icon: FileSearch, label: "Guided queries" },
  { icon: Bot, label: "AI assistants" },
  { icon: ShieldCheck, label: "Auditable answers" },
];

export function FederationDiagram() {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800/60">
      <div className="text-xs font-semibold uppercase tracking-wider text-okn-primary">
        How WOBD works
      </div>
      <div className="mt-4 grid gap-3">
        <div className="grid grid-cols-2 gap-2">
          {sources.map((source) => (
            <div
              key={source}
              className="rounded-xl border border-slate-200 bg-white p-3 text-sm font-medium text-slate-700 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
            >
              {source}
            </div>
          ))}
        </div>

        <div className="flex items-center justify-center" aria-hidden>
          <div className="h-8 w-px bg-slate-300 dark:bg-slate-600" />
        </div>

        <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <div
            className="absolute inset-0 opacity-10"
            style={{
              background:
                "radial-gradient(circle at 20% 30%, var(--okn-primary), transparent 28%), radial-gradient(circle at 80% 70%, var(--okn-primary-light), transparent 30%)",
            }}
            aria-hidden
          />
          <div className="relative flex items-center gap-3">
            <span
              className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full text-white"
              style={{ backgroundColor: "var(--okn-primary)" }}
            >
              <Network className="h-5 w-5" aria-hidden />
            </span>
            <div>
              <div className="text-base font-semibold text-slate-950 dark:text-slate-100">
                WOBD federation layer
              </div>
              <p className="mt-1 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                Shared identifiers, graph metadata, query guardrails, ontology lookup, and
                provenance-aware execution.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-center" aria-hidden>
          <div className="h-8 w-px bg-slate-300 dark:bg-slate-600" />
        </div>

        <div className="grid gap-2 sm:grid-cols-3">
          {outputs.map((output) => {
            const Icon = output.icon;
            return (
              <div
                key={output.label}
                className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white p-3 text-sm font-medium text-slate-700 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
              >
                <Icon className="h-4 w-4 flex-shrink-0 text-okn-primary" aria-hidden />
                {output.label}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
