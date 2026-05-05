import type { Metadata } from "next";
import Link from "next/link";
import { VignetteCards } from "@/components/landing/VignetteCards";
import { Breadcrumbs } from "@/components/layout/Breadcrumbs";

export const metadata: Metadata = {
  title: "Unified MCP server",
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
            Ask 30+ knowledge graphs from your AI assistant
          </h1>
          <p className="mt-3 text-base font-medium text-slate-700 dark:text-slate-300">
            The unified MCP server &mdash; one endpoint, the entire Proto-OKN federation
          </p>
          <div className="mx-auto mt-5 w-[90%] max-w-full space-y-3 text-left text-base leading-relaxed text-slate-600 [text-wrap:pretty] dark:text-slate-400">
            <p>
              Connect Claude, ChatGPT, or any MCP-capable client to a single{" "}
              <a
                className="font-medium text-niaid-link hover:underline"
                href="https://modelcontextprotocol.io/"
                rel="noopener noreferrer"
                target="_blank"
              >
                Model Context Protocol
              </a>{" "}
              endpoint that spans over 30 Proto-OKN knowledge graphs &mdash; including the NDE
              and GXA graphs that power WOBD. The assistant discovers relevant graphs, inspects
              schemas, runs SPARQL with automatic ontology expansion, bridges identifiers across
              graphs, and synthesizes results in a single conversation.
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

        <VignetteCards />

        <section className="w-full max-w-3xl border-t border-slate-200 pt-6 text-center text-sm text-slate-600 dark:border-slate-700 dark:text-slate-400">
          <p>
            More worked analyses across the Proto-OKN federation are available in the upstream{" "}
            <a
              className="font-medium text-niaid-link hover:underline"
              href="https://github.com/sbl-sdsc/mcp-proto-okn#example-queries"
              rel="noopener noreferrer"
              target="_blank"
            >
              mcp-proto-okn example library
            </a>{" "}
            &mdash; spanning environmental justice, criminal-justice patterns, spaceflight
            biology, drug-target discovery, and more.
          </p>
        </section>
      </div>
    </div>
  );
}
