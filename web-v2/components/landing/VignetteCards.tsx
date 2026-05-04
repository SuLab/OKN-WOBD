import Link from "next/link";
import { VIGNETTE_META } from "@/lib/landing/vignette-meta";

export function VignetteCards() {
  return (
    <section
      className="w-full max-w-5xl mx-auto"
      aria-labelledby="vignette-cards-heading"
    >
      <h2
        id="vignette-cards-heading"
        className="text-center text-lg sm:text-xl font-semibold text-slate-900 dark:text-slate-100 mb-4"
      >
        Example vignettes
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {VIGNETTE_META.map((card) => {
          const Icon = card.icon;
          return (
            <Link
              key={card.slug}
              href={`/mcp/${card.slug}`}
              className="group flex flex-col rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 shadow-sm hover:shadow-md hover:border-slate-300 dark:hover:border-slate-600 transition-all text-left"
            >
              <div className="flex items-start gap-3">
                <span
                  className={`flex-shrink-0 ${card.iconColor}`}
                  aria-hidden
                >
                  <Icon className="w-6 h-6" />
                </span>
                <div className="min-w-0 flex-1">
                  <h3 className="font-semibold text-slate-900 dark:text-slate-100">
                    {card.title}
                  </h3>
                  <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                    {card.description}
                  </p>
                  <span className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-slate-700 dark:text-slate-300 group-hover:text-niaid-link">
                    See vignette
                    <span aria-hidden>→</span>
                  </span>
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
