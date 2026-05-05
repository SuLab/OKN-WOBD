import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Bot, Network, ShieldCheck } from "lucide-react";
import { VignetteCards } from "@/components/landing/VignetteCards";
import { WorkflowSteps } from "@/components/landing/WorkflowSteps";
import { Breadcrumbs } from "@/components/layout/Breadcrumbs";

export const metadata: Metadata = {
  title: "AI assistant access",
  description:
    "Connect Claude, ChatGPT, or any MCP-capable AI assistant to a single endpoint spanning over 30 Proto-OKN knowledge graphs. Three worked example analyses included.",
};

export default function MCPPage() {
  return (
    <div
      className="flex flex-1 flex-col items-center px-4 pb-8 sm:pb-10"
      style={{ backgroundColor: "var(--niaid-page-bg)" }}
    >
      <div className="flex w-full max-w-5xl flex-1 flex-col items-center gap-10 pt-6 sm:gap-12 sm:pt-8 md:gap-14">
        <Breadcrumbs
          items={[
            { label: "Home", href: "/" },
            { label: "MCP" },
          ]}
        />
        <div className="flex w-full flex-col items-center text-center">
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Ask 30+ knowledge graphs from an AI assistant
          </h1>
          <div className="mx-auto mt-5 w-[90%] max-w-full space-y-3 text-left text-base leading-relaxed text-slate-600 [text-wrap:pretty] dark:text-slate-400">
            <p>
              WOBD can be used through guided forms, but the broader federation is best explored
              conversationally. Connect Claude, ChatGPT, or any MCP-capable client to a single{" "}
              <a
                className="font-medium text-niaid-link hover:underline"
                href="https://modelcontextprotocol.io/"
                rel="noopener noreferrer"
                target="_blank"
              >
                Model Context Protocol
              </a>{" "}
              endpoint. The assistant can discover relevant graphs, inspect schemas, bridge
              identifiers, run graph queries, and synthesize results while preserving the source
              graphs behind the answer.
            </p>
            <p>
              Built on the{" "}
              <a
                className="font-medium text-niaid-link hover:underline"
                href="https://github.com/sbl-sdsc/mcp-proto-okn"
                rel="noopener noreferrer"
                target="_blank"
              >
                mcp-proto-okn
              </a>{" "}
              project; see the{" "}
              <a
                className="font-medium text-niaid-link hover:underline"
                href="https://github.com/sbl-sdsc/mcp-proto-okn/blob/main/docs/unified-server.md"
                rel="noopener noreferrer"
                target="_blank"
              >
                unified server documentation
              </a>{" "}
              for the full tool list and design.{" "}
              <Link
                href="/mcp/installation"
                className="font-medium text-niaid-link underline-offset-2 hover:underline"
              >
                Connect your AI assistant &rarr;
              </Link>
            </p>
          </div>
        </div>

        <WorkflowSteps
          ariaLabel="How AI assistant access works"
          steps={[
            {
              title: "Connect",
              icon: Bot,
              body:
                "Point Claude, ChatGPT, VS Code, or another MCP-capable client at the hosted Proto-OKN endpoint.",
            },
            {
              title: "Explore graphs",
              icon: Network,
              body:
                "The assistant can discover relevant graphs, inspect schemas, bridge identifiers, and run graph queries.",
            },
            {
              title: "Audit answers",
              icon: ShieldCheck,
              body:
                "Ask which graphs were used and request the query trace so synthesis stays grounded in source records.",
            },
          ]}
        />

        <section className="grid w-full grid-cols-1 gap-4 md:grid-cols-2" aria-label="AI assistant use cases">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-niaid-link">
              What to ask
            </h2>
            <ul className="mt-3 space-y-2 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
              <li>Find datasets that support a disease, exposure, gene, pathway, or drug question.</li>
              <li>Compare evidence across graphs that normally live in separate portals.</li>
              <li>Ask which source graphs were used and request the queries behind an answer.</li>
            </ul>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-niaid-link">
              Why it matters
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
              General chat can invent connections. WOBD-backed assistant workflows ground answers
              in queryable graphs, shared identifiers, and inspectable source records, making
              exploratory synthesis easier to audit.
            </p>
          </div>
        </section>

        <VignetteCards />

        <section className="w-full max-w-3xl">
          <Link
            href="/mcp/installation"
            className="group flex items-center justify-between gap-4 rounded-lg border border-slate-200 bg-white p-5 shadow-sm transition-all hover:border-slate-300 hover:shadow-md dark:border-slate-700 dark:bg-slate-900 dark:hover:border-slate-600"
          >
            <div>
              <div className="font-medium text-niaid-link group-hover:underline">
                Connect Claude Desktop or ChatGPT
              </div>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                Use the public endpoint and a short verification prompt to confirm the assistant
                can see the Proto-OKN graph tools.
              </p>
            </div>
            <ArrowRight
              className="h-5 w-5 flex-shrink-0 text-niaid-link"
              aria-hidden
            />
          </Link>
        </section>

        <section className="w-full max-w-3xl">
          <a
            href="https://github.com/sbl-sdsc/mcp-proto-okn#example-queries"
            target="_blank"
            rel="noopener noreferrer"
            className="group flex items-center justify-between gap-4 rounded-lg border border-slate-200 bg-white p-5 shadow-sm transition-all hover:border-slate-300 hover:shadow-md dark:border-slate-700 dark:bg-slate-900 dark:hover:border-slate-600"
          >
            <div>
              <div className="font-medium text-niaid-link group-hover:underline">
                More worked analyses across the Proto-OKN federation
              </div>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                Browse the upstream <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-slate-800">mcp-proto-okn</code> example library &mdash; spanning environmental
                justice, criminal-justice patterns, spaceflight biology, drug-target discovery,
                and more.
              </p>
            </div>
            <ArrowRight
              className="h-5 w-5 flex-shrink-0 text-niaid-link"
              aria-hidden
            />
          </a>
        </section>
      </div>
    </div>
  );
}
