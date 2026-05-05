import type { Metadata } from "next";
import Link from "next/link";
import { QueryCards } from "@/components/landing/QueryCards";
import { Breadcrumbs } from "@/components/layout/Breadcrumbs";

export const metadata: Metadata = {
  title: "Guided queries",
  description:
    "Run guided WOBD query workflows over biomedical dataset metadata and gene-expression graphs. Pick a question, fill in terms, and inspect the generated graph query.",
};

export default function QueriesPage() {
  return (
    <div
      className="flex flex-1 flex-col items-center px-4 pb-8 sm:pb-10"
      style={{ backgroundColor: "var(--niaid-page-bg)" }}
    >
      <div className="flex w-full max-w-5xl flex-1 flex-col items-center gap-10 pt-6 sm:gap-12 sm:pt-8 md:gap-14">
        <Breadcrumbs
          items={[
            { label: "Home", href: "/" },
            { label: "Queries" },
          ]}
        />
        <div className="flex w-full flex-col items-center text-center">
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Guided queries
          </h1>
          <p className="mx-auto mt-5 w-[90%] max-w-full text-left text-base leading-relaxed text-slate-600 [text-wrap:pretty] dark:text-slate-400">
            Pick a research question, fill in the terms you care about, and WOBD assembles the
            graph query for you. These guided workflows are the safest way to learn what WOBD
            can currently do because every query pattern is curated, validated, and rerunnable.
          </p>
          <p className="mx-auto mt-3 w-[90%] max-w-full text-left text-sm leading-relaxed text-slate-600 dark:text-slate-400">
            Current guided queries focus on NIAID Data Ecosystem dataset metadata and Gene
            Expression Atlas evidence. For open-ended questions across all 30+ Proto-OKN graphs,
            use{" "}
            <Link href="/mcp" className="font-medium text-niaid-link hover:underline">
              AI assistant access
            </Link>
            .{" "}
            <Link href="/about" className="font-medium text-niaid-link hover:underline">
              Learn why the federation grows in value as more sources are added
            </Link>
          </p>
        </div>

        <section className="grid w-full grid-cols-1 gap-4 md:grid-cols-3" aria-label="How guided WOBD queries work">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-niaid-link">
              1. Choose a question
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
              Start from a tested workflow such as finding datasets by disease, datasets for a
              drug, or differential-expression evidence for genes.
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-niaid-link">
              2. Fill in terms
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
              Autocomplete helps resolve genes, diseases, species, tissues, and drugs to the
              identifiers used by the graphs.
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-niaid-link">
              3. Inspect results
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
              WOBD returns tables or dataset cards and can show the exact graph query that ran,
              so the workflow is auditable.
            </p>
          </div>
        </section>

        <QueryCards />
      </div>
    </div>
  );
}
