import Link from "next/link";
import { VignetteCards } from "@/components/landing/VignetteCards";
import {
  NSF_AWARD_NUMBER,
  NSF_AWARD_URL,
  PROTO_OKN_URL,
  GITHUB_REPO_URL,
} from "@/lib/site-config";

const impactStats = [
  { value: "30+", label: "Proto-OKN graphs reachable through the federation" },
  { value: "3", label: "worked cross-domain analyses shown on this site" },
  { value: "2", label: "ways to use WOBD: guided templates or AI assistants" },
];

const audiencePaths = [
  {
    title: "For researchers",
    href: "/queries",
    cta: "Run a guided query",
    description:
      "Use vetted forms to find biomedical datasets and gene-expression evidence without writing graph queries.",
  },
  {
    title: "For AI assistant users",
    href: "/mcp",
    cta: "Connect an assistant",
    description:
      "Ask open-ended questions across the Proto-OKN federation from Claude, ChatGPT, VS Code, or another MCP-capable client.",
  },
  {
    title: "For content partners",
    href: "/about",
    cta: "Explore integration opportunities",
    description:
      "See how datasets, knowledge graphs, ontologies, and curated resources can become part of a shared query layer.",
  },
];

const federationSteps = [
  {
    title: "Biomedical repositories",
    body: "NDE metadata, GXA expression data, GEO-linked studies, and future domain repositories.",
  },
  {
    title: "WOBD federation layer",
    body: "Shared identifiers, graph metadata, SPARQL guardrails, ontology lookup, and provenance-aware query execution.",
  },
  {
    title: "Reusable answers",
    body: "Templated searches and AI-assistant workflows with source graphs, query traces, and rerunnable results.",
  },
];

export default function LandingPage() {
  return (
    <div
      className="flex flex-1 flex-col items-center overflow-hidden px-4 pb-12 sm:pb-16"
      style={{ backgroundColor: "var(--niaid-page-bg)" }}
    >
      <div className="flex w-full max-w-6xl flex-1 flex-col items-center gap-12 pt-10 sm:gap-14 sm:pt-14 md:gap-16 md:pt-16">
        {/* Hero */}
        <section className="relative w-full rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900 sm:p-8 md:p-10">
          <div
            className="pointer-events-none absolute inset-x-6 top-0 h-28 rounded-b-full opacity-20 blur-3xl"
            style={{
              background:
                "linear-gradient(90deg, var(--niaid-link), var(--niaid-button), #2f6f9f)",
            }}
            aria-hidden
          />
          <div className="relative grid gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
            <div>
              <div className="flex flex-wrap gap-2 text-xs">
                <a
                  href={NSF_AWARD_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1 font-medium text-slate-700 hover:border-slate-300 hover:text-niaid-link dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:border-slate-600"
                >
                  NSF #{NSF_AWARD_NUMBER}
                </a>
                <a
                  href={PROTO_OKN_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1 font-medium text-slate-700 hover:border-slate-300 hover:text-niaid-link dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:border-slate-600"
                >
                  Proto-OKN federation
                </a>
                <a
                  href={GITHUB_REPO_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1 font-medium text-slate-700 hover:border-slate-300 hover:text-niaid-link dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:border-slate-600"
                >
                  Open source
                </a>
              </div>

              <h1 className="mt-6 max-w-3xl text-4xl font-bold tracking-tight text-slate-950 dark:text-slate-100 sm:text-5xl md:text-6xl">
                WOBD turns biomedical data silos into a queryable discovery network.
              </h1>
              <p className="mt-5 max-w-2xl text-lg leading-relaxed text-slate-700 dark:text-slate-300">
                The Web of Biological Data connects harmonized dataset metadata from the{" "}
                <a
                  href="https://data.niaid.nih.gov/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-niaid-link hover:underline"
                >
                  NIAID Data Ecosystem
                </a>{" "}
                with 30+ Proto-OKN knowledge graphs, so researchers and AI assistants can move
                from a question to mechanisms, exposures, diseases, and supporting datasets in
                one reproducible workflow.
              </p>
              <p className="mt-4 max-w-2xl text-base leading-relaxed text-slate-600 dark:text-slate-400">
                Continued support has compounding value: every new graph, repository, and
                metadata relationship widens the set of cross-domain questions WOBD can answer.
              </p>

              <div className="mt-7 flex flex-wrap gap-3">
                <Link
                  href="#impact"
                  className="inline-flex items-center rounded-md px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:opacity-90"
                  style={{ backgroundColor: "var(--niaid-button)" }}
                >
                  See example analyses
                </Link>
                <Link
                  href="/queries"
                  className="inline-flex items-center rounded-md border border-slate-300 bg-white px-5 py-2.5 text-sm font-semibold text-slate-800 transition hover:border-slate-400 hover:text-niaid-link dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
                >
                  Try a guided query
                </Link>
                <Link
                  href="/mcp"
                  className="inline-flex items-center rounded-md border border-slate-300 bg-white px-5 py-2.5 text-sm font-semibold text-slate-800 transition hover:border-slate-400 hover:text-niaid-link dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
                >
                  Connect an AI assistant
                </Link>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800/60">
              <div className="text-xs font-semibold uppercase tracking-wider text-niaid-link">
                How WOBD works
              </div>
              <div className="mt-4 space-y-3">
                {federationSteps.map((step, index) => (
                  <div
                    key={step.title}
                    className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900"
                  >
                    <div className="flex items-center gap-3">
                      <span
                        className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-sm font-bold text-white"
                        style={{ backgroundColor: "var(--niaid-link)" }}
                      >
                        {index + 1}
                      </span>
                      <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                        {step.title}
                      </h2>
                    </div>
                    <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                      {step.body}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="grid w-full grid-cols-1 gap-3 sm:grid-cols-3" aria-label="WOBD impact summary">
          {impactStats.map((stat) => (
            <div
              key={stat.value}
              className="rounded-2xl border border-slate-200 bg-white p-5 text-center shadow-sm dark:border-slate-700 dark:bg-slate-900"
            >
              <div className="text-3xl font-bold text-slate-950 dark:text-slate-100">
                {stat.value}
              </div>
              <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                {stat.label}
              </p>
            </div>
          ))}
        </section>

        <section className="w-full" aria-labelledby="audience-heading">
          <div className="mb-6 text-center">
            <h2
              id="audience-heading"
              className="text-xl font-semibold text-slate-900 dark:text-slate-100"
            >
              Choose the path that fits your role
            </h2>
            <p className="mx-auto mt-2 max-w-2xl text-sm leading-relaxed text-slate-600 dark:text-slate-400">
              WOBD is both a practical discovery tool and a growing research infrastructure
              layer. These entry points separate hands-on use from strategic context.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {audiencePaths.map((path) => (
              <Link
                key={path.title}
                href={path.href}
                className="group flex min-h-full flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md dark:border-slate-700 dark:bg-slate-900 dark:hover:border-slate-600"
              >
                <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                  {path.title}
                </h3>
                <p className="mt-3 flex-1 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                  {path.description}
                </p>
                <span className="mt-5 inline-flex items-center text-sm font-semibold text-niaid-link group-hover:underline">
                  {path.cta} <span aria-hidden className="ml-1">&rarr;</span>
                </span>
              </Link>
            ))}
          </div>
        </section>

        {/* Featured vignettes — proof of impact */}
        <VignetteCards
          heading="Impact case studies"
          lead="Three worked analyses show the same pattern: WOBD joins separately curated resources into auditable answers that would otherwise require cross-disciplinary teams and manual synthesis."
        />

        {/* Why WOBD — value proposition */}
        <section
          id="support-case"
          className="w-full max-w-5xl"
          aria-labelledby="support-case-heading"
        >
          <h2
            id="support-case-heading"
            className="text-center text-xl font-semibold text-slate-900 dark:text-slate-100"
          >
            Why continued support matters
          </h2>
          <p className="mx-auto mt-2 max-w-2xl text-center text-sm leading-relaxed text-slate-600 dark:text-slate-400">
            The hard part of biomedical research is rarely a single database lookup. It is
            trusted synthesis across data that was funded, curated, and published separately.
          </p>
          <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-3">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-niaid-link">
                A shared query plane
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-700 dark:text-slate-300">
                WOBD publishes dataset metadata, expression evidence, and graph context into a
                federation that researchers and AI assistants can query consistently.
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-niaid-link">
                Provenance by design
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-700 dark:text-slate-300">
                Results stay tied to source graphs, executed queries, identifiers, and dataset
                records, making AI-mediated discovery inspectable and rerunnable.
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-niaid-link">
                Compounding growth
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-700 dark:text-slate-300">
                Each additional graph, repository, and metadata relationship expands the
                questions the network can answer without rebuilding one-off integrations.
              </p>
            </div>
          </div>
        </section>

        {/* Get started — two interfaces */}
        <section className="w-full max-w-5xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900" aria-labelledby="access-modes-heading">
          <h2
            id="access-modes-heading"
            className="text-center text-xl font-semibold text-slate-900 dark:text-slate-100"
          >
            Start using WOBD
          </h2>
          <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
            <Link
              href="/queries"
              className="group flex flex-col rounded-xl border border-slate-200 bg-slate-50 p-5 transition hover:border-slate-300 hover:bg-white dark:border-slate-700 dark:bg-slate-800/60 dark:hover:border-slate-600"
            >
              <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                Guided query templates
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                Fill in terms for datasets, drugs, genes, diseases, species, or tissues. WOBD
                generates the graph query and shows the results with query traces.
              </p>
              <span className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-niaid-link group-hover:underline">
                Try a guided query
                <span aria-hidden>&rarr;</span>
              </span>
            </Link>

            <Link
              href="/mcp"
              className="group flex flex-col rounded-xl border border-slate-200 bg-slate-50 p-5 transition hover:border-slate-300 hover:bg-white dark:border-slate-700 dark:bg-slate-800/60 dark:hover:border-slate-600"
            >
              <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                AI-assistant access
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                Connect an MCP-capable assistant to ask open-ended questions across the whole
                Proto-OKN federation and inspect the graphs behind the answer.
              </p>
              <span className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-niaid-link group-hover:underline">
                Connect your assistant
                <span aria-hidden>&rarr;</span>
              </span>
            </Link>
          </div>
        </section>

        {/* Closing scope context */}
        <section className="w-full max-w-3xl text-center">
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400">
            WOBD is part of the broader{" "}
            <a
              href={PROTO_OKN_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-niaid-link hover:underline"
            >
              Proto-OKN
            </a>{" "}
            effort to build interconnected, trustworthy knowledge graphs for data-driven
            discovery.{" "}
            <Link href="/about" className="font-medium text-niaid-link hover:underline">
              Review the growth plan and team &rarr;
            </Link>
          </p>
        </section>
      </div>
    </div>
  );
}
