import Link from "next/link";
import { VignetteCards } from "@/components/landing/VignetteCards";
import {
  NSF_AWARD_NUMBER,
  NSF_AWARD_URL,
  PROTO_OKN_URL,
  GITHUB_REPO_URL,
} from "@/lib/site-config";

export default function LandingPage() {
  return (
    <div
      className="flex flex-1 flex-col items-center px-4 pb-12 sm:pb-16"
      style={{ backgroundColor: "var(--niaid-page-bg)" }}
    >
      <div className="flex w-full max-w-5xl flex-1 flex-col items-center gap-12 pt-12 sm:gap-14 sm:pt-16 md:gap-16 md:pt-20">
        {/* Hero */}
        <div className="flex w-full max-w-3xl flex-col items-center text-center">
          <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Web of Biological Data
          </h1>
          <p className="mt-3 text-lg sm:text-xl font-medium text-slate-700 dark:text-slate-300 [text-wrap:balance]">
            Federated queries across biomedical knowledge graphs and dataset metadata
          </p>

          {/* Credibility chips */}
          <div className="mt-5 flex flex-wrap items-center justify-center gap-2 text-xs">
            <a
              href={NSF_AWARD_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-3 py-1 font-medium text-slate-700 hover:border-slate-300 hover:text-niaid-link dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-600"
            >
              Funded by NSF #{NSF_AWARD_NUMBER}
            </a>
            <a
              href={PROTO_OKN_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-3 py-1 font-medium text-slate-700 hover:border-slate-300 hover:text-niaid-link dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-600"
            >
              Proto-OKN federation member
            </a>
            <a
              href={GITHUB_REPO_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-3 py-1 font-medium text-slate-700 hover:border-slate-300 hover:text-niaid-link dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-600"
            >
              Open source on GitHub
            </a>
          </div>

          <p className="mt-6 text-base leading-relaxed text-slate-600 [text-wrap:pretty] dark:text-slate-400">
            WOBD federates the{" "}
            <a
              href="https://data.niaid.nih.gov/"
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-niaid-link hover:underline"
            >
              NIAID Data Ecosystem
            </a>
            &apos;s harmonized biomedical dataset metadata with{" "}
            <strong>30+ Proto-OKN knowledge graphs</strong> so a single query can move from a
            research question through mechanism, exposure, or disease to the datasets that
            support analysis. Built for working researchers and AI assistants alike.
          </p>
        </div>

        {/* Featured vignettes — proof of impact */}
        <VignetteCards
          heading="See it in action"
          lead="Three worked analyses across biomanufacturing, public-health policy, and disease genomics — questions that previously required cross-disciplinary working groups, answered in a single chat."
        />

        {/* Why WOBD — value proposition */}
        <section
          className="w-full max-w-5xl"
          aria-labelledby="why-wobd-heading"
        >
          <h2
            id="why-wobd-heading"
            className="text-center text-lg sm:text-xl font-semibold text-slate-900 dark:text-slate-100 mb-2"
          >
            Why WOBD
          </h2>
          <p className="mx-auto mb-8 max-w-2xl text-center text-sm text-slate-600 dark:text-slate-400">
            The hard part of biomedical research is rarely a single question &mdash; it is the
            synthesis across data silos. WOBD targets that synthesis directly.
          </p>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
            <div className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-niaid-link">
                The problem
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-700 dark:text-slate-300">
                Cross-domain questions &mdash; linking environmental exposure to molecular
                mechanism to disease outcome to supporting datasets &mdash; require synthesis
                across databases that were separately funded, separately curated, and rarely
                designed to interoperate. That synthesis has historically taken cross-
                disciplinary working groups months to assemble.
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-niaid-link">
                The approach
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-700 dark:text-slate-300">
                WOBD ingests harmonized biomedical dataset metadata (the NIAID Data Ecosystem)
                and connects it to the Proto-OKN family of knowledge graphs through a shared
                identifier substrate. Researchers reach the federation through a templated
                SPARQL UI; AI assistants reach the same graphs through a unified MCP server.
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-niaid-link">
                The outcome
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-700 dark:text-slate-300">
                Cross-domain questions become single-chat workflows. The results trace back to
                their source graphs (auditable, reproducible, re-runnable), and every
                additional graph or metadata source ingested into the federation widens the set
                of questions the system can answer.
              </p>
            </div>
          </div>
        </section>

        {/* Two ways to use WOBD */}
        <section className="w-full" aria-labelledby="access-modes-heading">
          <h2
            id="access-modes-heading"
            className="text-center text-lg sm:text-xl font-semibold text-slate-900 dark:text-slate-100 mb-2"
          >
            Two ways to use WOBD
          </h2>
          <p className="mx-auto mb-6 max-w-2xl text-center text-sm text-slate-600 dark:text-slate-400">
            A focused templated UI for reproducible workflows, or a unified MCP server for
            open-ended cross-graph exploration with your AI assistant of choice.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Link
              href="/queries"
              className="group flex flex-col rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6 shadow-sm hover:shadow-md hover:border-slate-300 dark:hover:border-slate-600 transition-all text-left"
            >
              <h3 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
                Templated queries
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                Pick a template and fill in your search terms &mdash; genes, diseases, datasets,
                contrasts. The app assembles and executes the SPARQL for you. Currently covers
                NDE and GXA. Good for focused, reproducible workflows; no SPARQL required.
              </p>
              <span className="mt-5 inline-flex items-center gap-1 text-sm font-medium text-slate-700 dark:text-slate-300 group-hover:text-niaid-link">
                Try a query
                <span aria-hidden>&rarr;</span>
              </span>
            </Link>

            <Link
              href="/mcp"
              className="group flex flex-col rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6 shadow-sm hover:shadow-md hover:border-slate-300 dark:hover:border-slate-600 transition-all text-left"
            >
              <h3 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
                Unified MCP server
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                Connect an AI assistant &mdash; Claude, ChatGPT, VS Code &mdash; to a single
                Model Context Protocol server spanning over 30 Proto-OKN KGs. The assistant
                discovers graphs, inspects schemas, runs SPARQL, bridges identifiers, and
                combines results in conversation. Good for open-ended, cross-graph questions.
              </p>
              <span className="mt-5 inline-flex items-center gap-1 text-sm font-medium text-slate-700 dark:text-slate-300 group-hover:text-niaid-link">
                Connect your AI assistant
                <span aria-hidden>&rarr;</span>
              </span>
            </Link>
          </div>
        </section>

        {/* Closing scope context */}
        <section className="w-full max-w-3xl text-center">
          <p className="text-sm text-slate-600 dark:text-slate-400">
            WOBD is part of the broader{" "}
            <a
              href={PROTO_OKN_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-niaid-link hover:underline"
            >
              Proto-OKN
            </a>{" "}
            federation, an NSF-funded effort to build interconnected knowledge graphs for
            data-driven discovery.{" "}
            <Link href="/about" className="font-medium text-niaid-link hover:underline">
              About WOBD &amp; the team &rarr;
            </Link>
          </p>
        </section>
      </div>
    </div>
  );
}
