import Link from "next/link";

export default function LandingPage() {
  return (
    <div
      className="flex flex-1 flex-col items-center px-4 pb-12 sm:pb-16"
      style={{ backgroundColor: "var(--niaid-page-bg)" }}
    >
      <div className="flex w-full max-w-5xl flex-1 flex-col items-center gap-12 pt-20 sm:gap-14 sm:pt-24 md:gap-16 md:pt-28">
        <div className="flex w-full max-w-3xl flex-col items-center text-center">
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Web of Biological Data
          </h1>
          <p className="mt-3 text-base text-slate-700 dark:text-slate-300">
            A queryable layer connecting biomedical knowledge graphs and dataset metadata.
          </p>
          <div className="mt-6 space-y-4 text-left text-base leading-relaxed text-slate-600 [text-wrap:pretty] dark:text-slate-400">
            <p>
              WOBD links biomedical knowledge graphs so a single query can move across them. One
              member &mdash; the{" "}
              <a
                href="https://data.niaid.nih.gov/"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-niaid-link underline-offset-2 hover:underline"
              >
                NIAID Data Ecosystem
              </a>{" "}
              (NDE) &mdash; is unusual in that it indexes <em>datasets</em> rather than biology
              directly. That lets a query start from a mechanistic finding in one graph and end
              at the datasets you could analyze to investigate it further.
            </p>
            <p>
              Other members supply the biology. The{" "}
              <a
                href="https://www.ebi.ac.uk/gxa/home"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-niaid-link underline-offset-2 hover:underline"
              >
                Gene Expression Atlas
              </a>{" "}
              (GXA), for example, contributes differential-expression results across many
              diseases and tissues. WOBD is part of the wider{" "}
              <a
                href="https://www.proto-okn.net/"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-niaid-link underline-offset-2 hover:underline"
              >
                Proto-OKN
              </a>{" "}
              federation; today's templated queries cover NDE and GXA, while the unified MCP
              server reaches all 27 Proto-OKN graphs.{" "}
              <Link href="/about" className="font-medium text-niaid-link hover:underline">
                Learn more
              </Link>
            </p>
          </div>
        </div>

        <section className="w-full" aria-labelledby="access-modes-heading">
          <h2
            id="access-modes-heading"
            className="text-center text-lg sm:text-xl font-semibold text-slate-900 dark:text-slate-100 mb-6"
          >
            Two ways to query WOBD
          </h2>
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
                Browse templates
                <span aria-hidden>&rarr;</span>
              </span>
            </Link>

            <Link
              href="/about#mcp"
              className="group flex flex-col rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6 shadow-sm hover:shadow-md hover:border-slate-300 dark:hover:border-slate-600 transition-all text-left"
            >
              <h3 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
                Unified MCP server
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                Connect an AI assistant &mdash; Claude, ChatGPT, VS Code &mdash; to a single
                Model Context Protocol server spanning all 27 Proto-OKN graphs. The assistant
                discovers graphs, inspects schemas, runs SPARQL, bridges identifiers, and
                combines results in conversation. Good for open-ended, cross-graph questions.
              </p>
              <span className="mt-5 inline-flex items-center gap-1 text-sm font-medium text-slate-700 dark:text-slate-300 group-hover:text-niaid-link">
                How to connect
                <span aria-hidden>&rarr;</span>
              </span>
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}
