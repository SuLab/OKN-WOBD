import Link from "next/link";
import { notFound } from "next/navigation";
import { VIGNETTE_META, getVignetteMeta } from "@/lib/landing/vignette-meta";

export function generateStaticParams() {
  return VIGNETTE_META.map((v) => ({ slug: v.slug }));
}

export default function VignettePage({ params }: { params: { slug: string } }) {
  const meta = getVignetteMeta(params.slug);
  if (!meta) notFound();

  const Icon = meta.icon;

  return (
    <div
      className="flex flex-1 flex-col items-center px-4 pb-8 sm:pb-10"
      style={{ backgroundColor: "var(--niaid-page-bg)" }}
    >
      <div className="flex w-full max-w-5xl flex-1 flex-col items-center gap-12 pt-24 sm:gap-14 sm:pt-28 md:gap-16 md:pt-32">
        <div className="flex w-full flex-col items-center text-center">
          <span
            className={`mb-4 inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300 ${meta.iconColor}`}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden />
            {meta.tag}
          </span>
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            {meta.title}
          </h1>
          <p className="mx-auto mt-5 w-[90%] max-w-full text-left text-base leading-relaxed text-slate-600 [text-wrap:pretty] dark:text-slate-400">
            {meta.description}{" "}
            <Link href="/mcp" className="font-medium text-niaid-link hover:underline">
              Back to MCP server
            </Link>
          </p>
        </div>

        <div className="w-full max-w-3xl space-y-4 text-slate-700 dark:text-slate-300">
          <section className="rounded-lg border border-dashed border-slate-300 bg-white p-6 dark:border-slate-700 dark:bg-slate-900">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
              Vignette coming soon
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
              This vignette is a placeholder. It will walk through an example of using the
              unified MCP server to investigate <strong>{meta.tag.toLowerCase()}</strong> across
              Proto-OKN graphs &mdash; the prompts used, the graphs the assistant chose, the
              SPARQL it generated, and the synthesized answer.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
