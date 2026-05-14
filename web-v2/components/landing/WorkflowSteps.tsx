import type { LucideIcon } from "lucide-react";

export interface WorkflowStep {
  title: string;
  body: string;
  icon?: LucideIcon;
}

export function WorkflowSteps({
  steps,
  ariaLabel,
}: {
  steps: WorkflowStep[];
  ariaLabel: string;
}) {
  return (
    <section className="w-full" aria-label={ariaLabel}>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {steps.map((step, index) => {
          const Icon = step.icon;
          return (
            <div
              key={step.title}
              className="relative overflow-hidden rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900"
            >
              <div
                className="absolute -right-6 -top-6 h-20 w-20 rounded-full opacity-10"
                style={{ backgroundColor: "var(--okn-primary)" }}
                aria-hidden
              />
              <div className="relative flex items-center gap-3">
                <span
                  className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full text-sm font-bold text-white"
                  style={{ backgroundColor: "var(--okn-primary)" }}
                >
                  {Icon ? <Icon className="h-4 w-4" aria-hidden /> : index + 1}
                </span>
                <h2 className="text-sm font-semibold uppercase tracking-wider text-okn-primary">
                  {index + 1}. {step.title}
                </h2>
              </div>
              <p className="relative mt-3 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                {step.body}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
