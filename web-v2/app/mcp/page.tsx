import Link from "next/link";
import { VignetteCards } from "@/components/landing/VignetteCards";
import { Breadcrumbs } from "@/components/layout/Breadcrumbs";

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
            Unified MCP server
          </h1>
          <p className="mx-auto mt-5 w-[90%] max-w-full text-left text-base leading-relaxed text-slate-600 [text-wrap:pretty] dark:text-slate-400">
            Connect an AI assistant &mdash; Claude, ChatGPT, VS Code &mdash; to the{" "}
            <a
              className="font-medium text-niaid-link hover:underline"
              href="https://github.com/sbl-sdsc/mcp-proto-okn"
              rel="noopener noreferrer"
              target="_blank"
            >
              mcp-proto-okn
            </a>{" "}
            <a
              className="font-medium text-niaid-link hover:underline"
              href="https://modelcontextprotocol.io/"
              rel="noopener noreferrer"
              target="_blank"
            >
              Model Context Protocol
            </a>{" "}
            server, a single endpoint spanning over 30 Proto-OKN KGs &mdash;
            including the NDE and GXA graphs that power WOBD. The assistant discovers relevant
            graphs, inspects schemas, runs SPARQL with automatic ontology expansion, bridges
            identifiers across graphs, and synthesizes results in a single conversation; see
            the{" "}
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
              Learn to connect your client to our MCP server &rarr;
            </Link>
          </p>
        </div>

        <VignetteCards />
      </div>
    </div>
  );
}
