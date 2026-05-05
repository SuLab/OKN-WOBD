import Link from "next/link";
import { ArrowRight, Database, FileSearch, Lightbulb } from "lucide-react";
import { getVignetteMeta } from "@/lib/landing/vignette-meta";
import { Breadcrumbs } from "@/components/layout/Breadcrumbs";

const SLUG = "terpene-biosynthesis";

export default function TerpeneBiosynthesisVignettePage() {
  const meta = getVignetteMeta(SLUG)!;
  const Icon = meta.icon;

  return (
    <div
      className="flex flex-1 flex-col items-center px-4 pb-8 sm:pb-10"
      style={{ backgroundColor: "var(--niaid-page-bg)" }}
    >
      <div className="flex w-full max-w-5xl flex-1 flex-col items-center gap-10 pt-6 sm:gap-12 sm:pt-8 md:gap-14">
        <Breadcrumbs
          items={[
            { label: "Home", href: "/" },
            { label: "MCP", href: "/mcp" },
            { label: meta.title },
          ]}
        />
        <div className="flex w-full flex-col items-center text-center">
          <span
            className={`mb-4 inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium dark:bg-slate-800 ${meta.iconColor}`}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden />
            {meta.tag}
          </span>
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Designing a microbial host for terpene biomanufacturing
          </h1>
          <p className="mx-auto mt-5 w-[90%] max-w-full text-left text-base leading-relaxed text-slate-600 [text-wrap:pretty] dark:text-slate-400">
            One natural-language query, four federated knowledge graphs, an integrated answer that
            would otherwise take days of cross-portal search.
          </p>
        </div>

        <section className="w-full max-w-3xl space-y-3 text-slate-700 dark:text-slate-300">
          <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            The question
          </h2>
          <blockquote className="border-l-4 border-slate-300 pl-4 italic text-slate-600 dark:border-slate-600 dark:text-slate-400">
            A team of synthetic biologists is designing a microbial host for sustainable
            biomanufacturing of a high-value terpene. They need plant and microbial enzymes that
            drive terpene biosynthesis, and the experimental datasets &mdash; RNA-seq, proteomics,
            fermentation studies &mdash; that justify specific gene parts and predict how a
            production strain will behave.
          </blockquote>
          <p>
            Answering that well requires three different kinds of evidence at once: pathway-level
            gene relationships, organism-specific expression data across plant and microbial
            systems, and curated dataset metadata that ties each candidate gene to the experiments
            that justify it. Without an OKN-backed federation, that means days of fragmented
            searching across pathway portals, GEO, ArrayExpress, and species-specific resources
            &mdash; with the cross-organism synthesis still done by hand.
          </p>
        </section>

        <section className="w-full">
          <h2 className="mb-6 text-center text-xl font-semibold text-slate-900 dark:text-slate-100">
            One query, federated answer
          </h2>
          <div className="grid grid-cols-1 items-stretch gap-3 md:grid-cols-[1fr_auto_1.5fr_auto_1fr]">
            <div className="flex flex-col rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
              <div className="flex items-center gap-2 text-niaid-link">
                <Lightbulb className="h-5 w-5" aria-hidden />
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Natural-language query
                </h3>
              </div>
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
                Which plant and microbial genes drive terpene biosynthesis, and which datasets
                support engineering a microbial host?
              </p>
            </div>
            <FlowArrow />
            <div className="flex flex-col rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
              <div className="flex items-center gap-2 text-niaid-link">
                <Database className="h-5 w-5" aria-hidden />
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Unified MCP server federates four KGs
                </h3>
              </div>
              <ul className="mt-2 space-y-1 text-sm text-slate-600 dark:text-slate-400">
                <li>
                  <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-slate-800">
                    prokn
                  </code>{" "}
                  &mdash; pathway and gene-part discovery
                </li>
                <li>
                  <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-slate-800">
                    gene-expression-atlas-okn
                  </code>{" "}
                  &mdash; differential expression across organisms
                </li>
                <li>
                  <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-slate-800">
                    spoke-genelab
                  </code>{" "}
                  &mdash; organism-specific studies and assays
                </li>
                <li>
                  <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-slate-800">
                    nde
                  </code>{" "}
                  &mdash; NDE/WOBD dataset metadata layer
                </li>
              </ul>
            </div>
            <FlowArrow />
            <div className="flex flex-col rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
              <div className="flex items-center gap-2 text-niaid-link">
                <FileSearch className="h-5 w-5" aria-hidden />
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Integrated answer
                </h3>
              </div>
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
                Candidate gene panel anchored across plant and microbial organisms, with the
                experimental datasets that justify each choice &mdash; every result traceable to
                its source graph.
              </p>
            </div>
          </div>
        </section>

        <section className="w-full">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat number="4" label="federated KGs" />
            <Stat number="20+" label="datasets surfaced" />
            <Stat number="~15" label="candidate genes anchored" />
            <Stat number="7 / 3" label="plant species / microbial hosts" />
          </div>
        </section>

        <section className="w-full max-w-3xl space-y-3 text-slate-700 dark:text-slate-300">
          <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            What this query unlocks
          </h2>
          <ul className="list-disc space-y-2 pl-6">
            <li>
              <strong>Cross-graph synthesis on shared identifiers.</strong> Joins on{" "}
              <code className="rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">
                NCBI_Gene
              </code>
              ,{" "}
              <code className="rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">
                GeneSymbol
              </code>
              , and{" "}
              <code className="rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">
                UBERON
              </code>{" "}
              link organism-specific pathway evidence to organism-spanning expression data.
            </li>
            <li>
              <strong>Pathway and dataset discovery in a single step.</strong> The NDE/WOBD
              metadata graph surfaces real experiments &mdash; <em>Artemisia</em> transcriptomes,{" "}
              <em>Taxus</em> paclitaxel biosynthesis, <em>E. coli</em> precursor toxicity,
              taxadiene-producing yeast &mdash; that justify each candidate gene.
            </li>
            <li>
              <strong>Plant and microbial scope from one ask.</strong> No separate queries against
              plant pathway resources, microbial host-engineering datasets, and tolerance studies,
              and no manual stitching across them.
            </li>
            <li>
              <strong>Provenance preserved.</strong> Every gene, dataset, and edge in the answer
              traces back to a specific KG and source record &mdash; auditable, reproducible, and
              re-runnable.
            </li>
          </ul>
        </section>

        <section className="w-full max-w-3xl space-y-3 border-t border-slate-200 pt-6 text-slate-700 dark:border-slate-700 dark:text-slate-300">
          <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            Why this matters
          </h2>
          <p>
            Terpene biomanufacturing is one example. The same unified MCP server federates over 30
            Proto-OKN knowledge graphs spanning biology and health, environment, justice, and
            technology and manufacturing. Investment in shared knowledge-graph infrastructure
            compounds across domains: a query pattern that works for terpene engineering also
            works for tracing PFAS exposure pathways, mapping disease mechanisms, or correlating
            socioeconomic factors with environmental risk.
          </p>
          <p>
            The point is not any single answer. It is that an entire class of cross-domain
            questions &mdash; previously intractable without a team of domain experts and weeks of
            manual integration &mdash; becomes tractable in a single chat.
          </p>
        </section>

        <section className="w-full max-w-3xl">
          <Link
            href="/mcp/terpene-biosynthesis/details"
            className="group flex items-center justify-between gap-4 rounded-lg border border-slate-200 bg-white p-5 shadow-sm transition-all hover:border-slate-300 hover:shadow-md dark:border-slate-700 dark:bg-slate-900 dark:hover:border-slate-600"
          >
            <div>
              <div className="font-medium text-niaid-link group-hover:underline">
                Read the full analysis
              </div>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                Specific datasets, gene panels, ranking criteria, and the proposed engineering
                workflow.
              </p>
            </div>
            <ArrowRight
              className="h-5 w-5 flex-shrink-0 text-niaid-link"
              aria-hidden
            />
          </Link>
        </section>
      </div>
    </div>
  );
}

function FlowArrow() {
  return (
    <div className="flex items-center justify-center text-slate-400">
      <ArrowRight className="hidden h-5 w-5 md:block" aria-hidden />
      <ArrowRight className="h-5 w-5 rotate-90 md:hidden" aria-hidden />
    </div>
  );
}

function Stat({ number, label }: { number: string; label: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 text-center shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <div className="text-2xl font-bold text-slate-900 dark:text-slate-100">{number}</div>
      <div className="mt-1 text-xs text-slate-600 dark:text-slate-400">{label}</div>
    </div>
  );
}
