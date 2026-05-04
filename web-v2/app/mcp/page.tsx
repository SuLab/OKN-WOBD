import Link from "next/link";
import { VignetteCards } from "@/components/landing/VignetteCards";

export default function MCPPage() {
  return (
    <div
      className="flex flex-1 flex-col items-center px-4 pb-8 sm:pb-10"
      style={{ backgroundColor: "var(--niaid-page-bg)" }}
    >
      <div className="flex w-full max-w-5xl flex-1 flex-col items-center gap-12 pt-24 sm:gap-14 sm:pt-28 md:gap-16 md:pt-32">
        <div className="flex w-full flex-col items-center text-center">
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Unified MCP server
          </h1>
          <p className="mx-auto mt-5 w-[90%] max-w-full text-left text-base leading-relaxed text-slate-600 [text-wrap:pretty] dark:text-slate-400">
            Connect an AI assistant &mdash; Claude, ChatGPT, VS Code &mdash; to a single Model
            Context Protocol server spanning all 27 Proto-OKN graphs. The assistant discovers
            graphs, inspects schemas, runs SPARQL, bridges identifiers, and combines results in
            conversation.{" "}
            <Link href="/about" className="font-medium text-niaid-link hover:underline">
              Learn more about WOBD
            </Link>
          </p>
        </div>

        <VignetteCards />

        <div className="w-full max-w-3xl space-y-8 text-slate-700 dark:text-slate-300">
          <section className="space-y-3">
            <p>
              The{" "}
              <a
                className="text-blue-700 underline decoration-blue-700/30 underline-offset-2 hover:decoration-blue-700"
                href="https://github.com/sbl-sdsc/mcp-proto-okn"
                rel="noopener noreferrer"
                target="_blank"
              >
                mcp-proto-okn
              </a>{" "}
              project provides a single{" "}
              <a
                className="text-blue-700 underline decoration-blue-700/30 underline-offset-2 hover:decoration-blue-700"
                href="https://modelcontextprotocol.io/"
                rel="noopener noreferrer"
                target="_blank"
              >
                Model Context Protocol
              </a>{" "}
              server that consolidates over 30 Proto-OKN knowledge graphs &mdash; including the
              NDE and GXA graphs used by WOBD &mdash; into one interface. Through it, an AI
              assistant can discover relevant graphs, inspect their schemas, run SPARQL queries
              with automatic ontology expansion, bridge identifiers across graphs (genes,
              chemicals, diseases, locations, industry codes), and synthesize results from
              multiple sources in a single conversation. See the{" "}
              <a
                className="text-blue-700 underline decoration-blue-700/30 underline-offset-2 hover:decoration-blue-700"
                href="https://github.com/sbl-sdsc/mcp-proto-okn/blob/main/docs/unified-server.md"
                rel="noopener noreferrer"
                target="_blank"
              >
                unified server documentation
              </a>{" "}
              for the full tool list and design.
            </p>
          </section>

          <section className="space-y-3">
            <p>
              The server exposes tools in four groups: <strong>discovery</strong> (list graphs,
              route a question to likely graphs, get descriptions),{" "}
              <strong>schema and query</strong> (inspect schemas, run SPARQL, run federated
              multi-graph queries, pull reusable query templates),{" "}
              <strong>cross-graph</strong> (identifier bridging and ontology descendant
              expansion), and <strong>visualization</strong> (schema diagrams and chat
              transcripts).
            </p>
          </section>

          <section className="space-y-3 border-t border-slate-200 pt-6 dark:border-slate-700">
            <p>
              Ready to try it?{" "}
              <Link
                href="/mcp/installation"
                className="font-medium text-niaid-link underline-offset-2 hover:underline"
              >
                Connect a client to the public endpoint &rarr;
              </Link>
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
