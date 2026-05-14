import Link from "next/link";
import { FederationDiagram } from "@/components/landing/FederationDiagram";
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

export default function LandingPage() {
  return (
    <div className="flex flex-1 flex-col items-center overflow-hidden px-4 pb-12 sm:pb-16">
      <div className="flex w-full max-w-[1200px] flex-1 flex-col items-center gap-12 pt-10 sm:gap-14 sm:pt-14 md:gap-16 md:pt-16">
        {/* Hero */}
        <section className="relative w-full rounded-[2rem] border border-okn-border bg-white p-6 shadow-sm sm:p-8 md:p-10">
          <div
            className="pointer-events-none absolute inset-x-6 top-0 h-28 rounded-b-full opacity-25 blur-3xl"
            style={{
              background:
                "linear-gradient(90deg, #6B4C9A, #8B6CB8, #9659FF)",
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
                  className="inline-flex items-center rounded-full border border-okn-border bg-okn-bgMuted px-3 py-1 font-medium text-okn-textStrong transition hover:border-okn-borderPurple hover:text-okn-primary"
                >
                  NSF #{NSF_AWARD_NUMBER}
                </a>
                <a
                  href={PROTO_OKN_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center rounded-full border border-okn-border bg-okn-bgMuted px-3 py-1 font-medium text-okn-textStrong transition hover:border-okn-borderPurple hover:text-okn-primary"
                >
                  Proto-OKN federation
                </a>
                <a
                  href={GITHUB_REPO_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center rounded-full border border-okn-border bg-okn-bgMuted px-3 py-1 font-medium text-okn-textStrong transition hover:border-okn-borderPurple hover:text-okn-primary"
                >
                  Open source
                </a>
              </div>

              <h1 className="mt-6 max-w-3xl text-4xl font-bold tracking-tight text-okn-navbar sm:text-5xl md:text-6xl">
                WOBD turns biomedical data silos into a queryable discovery network.
              </h1>
              <p className="mt-5 max-w-2xl text-lg leading-relaxed text-okn-textStrong">
                The Web of Biological Data connects harmonized dataset metadata from the{" "}
                <a
                  href="https://data.niaid.nih.gov/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-okn-primary hover:underline"
                >
                  NIAID Data Ecosystem
                </a>{" "}
                with 30+ Proto-OKN knowledge graphs, so researchers and AI assistants can move
                from a question to mechanisms, exposures, diseases, and supporting datasets in
                one reproducible workflow.
              </p>
              <p className="mt-4 max-w-2xl text-base leading-relaxed text-okn-textMuted">
                Continued support has compounding value: every new graph, repository, and
                metadata relationship widens the set of cross-domain questions WOBD can answer.
              </p>

              <div className="mt-7 flex flex-wrap gap-3">
                <Link
                  href="#impact"
                  className="inline-flex items-center rounded-[14px] bg-okn-primary px-6 py-3 text-sm font-semibold text-white shadow-sm transition hover:-translate-y-0.5 hover:bg-okn-navbar hover:shadow-md"
                >
                  See example analyses
                </Link>
                <Link
                  href="/queries"
                  className="inline-flex items-center rounded-[14px] border border-okn-border bg-white px-6 py-3 text-sm font-semibold text-okn-textStrong transition hover:-translate-y-0.5 hover:border-okn-borderPurple hover:text-okn-primary hover:shadow-md"
                >
                  Try a guided query
                </Link>
                <Link
                  href="/mcp"
                  className="inline-flex items-center rounded-[14px] border border-okn-border bg-white px-6 py-3 text-sm font-semibold text-okn-textStrong transition hover:-translate-y-0.5 hover:border-okn-borderPurple hover:text-okn-primary hover:shadow-md"
                >
                  Connect an AI assistant
                </Link>
              </div>
            </div>

            <FederationDiagram />
          </div>
        </section>

        <section className="grid w-full grid-cols-1 gap-3 sm:grid-cols-3" aria-label="WOBD impact summary">
          {impactStats.map((stat) => (
            <div
              key={stat.value}
              className="rounded-[10px] border border-okn-border bg-white p-5 text-center shadow-sm"
            >
              <div className="text-3xl font-bold text-okn-navbar">{stat.value}</div>
              <p className="mt-2 text-sm leading-relaxed text-okn-textMuted">{stat.label}</p>
            </div>
          ))}
        </section>

        <section className="w-full" aria-labelledby="audience-heading">
          <div className="mb-6 text-center">
            <h2
              id="audience-heading"
              className="text-xl font-semibold text-okn-navbar"
            >
              Choose the path that fits your role
            </h2>
            <p className="mx-auto mt-2 max-w-2xl text-sm leading-relaxed text-okn-textMuted">
              WOBD is both a practical discovery tool and a growing research infrastructure
              layer. These entry points separate hands-on use from strategic context.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {audiencePaths.map((path) => (
              <Link
                key={path.title}
                href={path.href}
                className="group flex min-h-full flex-col rounded-[10px] border border-okn-border bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-okn-borderPurple hover:shadow-[0_4px_16px_rgba(0,0,0,0.08)]"
              >
                <h3 className="text-lg font-semibold text-okn-navbar">{path.title}</h3>
                <p className="mt-3 flex-1 text-sm leading-relaxed text-okn-textMuted">
                  {path.description}
                </p>
                <span className="mt-5 inline-flex items-center text-sm font-semibold text-okn-primary group-hover:underline">
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
            className="text-center text-xl font-semibold text-okn-navbar"
          >
            How WOBD grows in value
          </h2>
          <p className="mx-auto mt-2 max-w-2xl text-center text-sm leading-relaxed text-okn-textMuted">
            The hard part of biomedical research is rarely a single database lookup. It is
            trusted synthesis across data that was funded, curated, and published separately.
          </p>
          <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-3">
            <div className="rounded-[10px] border border-okn-border bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-okn-primary">
                A shared query plane
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-okn-textStrong">
                WOBD publishes dataset metadata, expression evidence, and graph context into a
                federation that researchers and AI assistants can query consistently.
              </p>
            </div>
            <div className="rounded-[10px] border border-okn-border bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-okn-primary">
                Provenance by design
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-okn-textStrong">
                Results stay tied to source graphs, executed queries, identifiers, and dataset
                records, making AI-mediated discovery inspectable and rerunnable.
              </p>
            </div>
            <div className="rounded-[10px] border border-okn-border bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-okn-primary">
                Compounding growth
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-okn-textStrong">
                Each additional graph, repository, and metadata relationship expands the
                questions the network can answer without rebuilding one-off integrations.
              </p>
            </div>
          </div>
        </section>

        {/* Get started — two interfaces */}
        <section
          className="w-full max-w-5xl rounded-[10px] border border-okn-border bg-white p-6 shadow-sm"
          aria-labelledby="access-modes-heading"
        >
          <h2
            id="access-modes-heading"
            className="text-center text-xl font-semibold text-okn-navbar"
          >
            Start using WOBD
          </h2>
          <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
            <Link
              href="/queries"
              className="group flex flex-col rounded-[10px] border border-okn-border bg-okn-bgMuted p-5 transition hover:-translate-y-0.5 hover:border-okn-borderPurple hover:bg-white hover:shadow-md"
            >
              <h3 className="text-lg font-semibold text-okn-navbar">Guided query templates</h3>
              <p className="mt-3 text-sm leading-relaxed text-okn-textMuted">
                Fill in terms for datasets, drugs, genes, diseases, species, or tissues. WOBD
                generates the graph query and shows the results with query traces.
              </p>
              <span className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-okn-primary group-hover:underline">
                Try a guided query
                <span aria-hidden>&rarr;</span>
              </span>
            </Link>

            <Link
              href="/mcp"
              className="group flex flex-col rounded-[10px] border border-okn-border bg-okn-bgMuted p-5 transition hover:-translate-y-0.5 hover:border-okn-borderPurple hover:bg-white hover:shadow-md"
            >
              <h3 className="text-lg font-semibold text-okn-navbar">AI-assistant access</h3>
              <p className="mt-3 text-sm leading-relaxed text-okn-textMuted">
                Connect an MCP-capable assistant to ask open-ended questions across the whole
                Proto-OKN federation and inspect the graphs behind the answer.
              </p>
              <span className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-okn-primary group-hover:underline">
                Connect your assistant
                <span aria-hidden>&rarr;</span>
              </span>
            </Link>
          </div>
        </section>

        {/* Closing scope context */}
        <section className="w-full max-w-3xl text-center">
          <p className="text-sm leading-relaxed text-okn-textMuted">
            WOBD is part of the broader{" "}
            <a
              href={PROTO_OKN_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-okn-primary hover:underline"
            >
              Proto-OKN
            </a>{" "}
            effort to build interconnected, trustworthy knowledge graphs for data-driven
            discovery.{" "}
            <Link href="/about" className="font-medium text-okn-primary hover:underline">
              Review the growth plan and team &rarr;
            </Link>
          </p>
        </section>
      </div>
    </div>
  );
}
