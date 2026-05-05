import type { Metadata } from "next";
import Link from "next/link";
import { QueryCards } from "@/components/landing/QueryCards";
import { Breadcrumbs } from "@/components/layout/Breadcrumbs";

export const metadata: Metadata = {
  title: "Templated queries",
  description:
    "Run predefined, validated SPARQL queries over the federated WOBD graphs (NDE + GXA). Pick a template, fill in your search terms — no SPARQL required.",
};

export default function QueriesPage() {
  return (
    <div
      className="flex flex-1 flex-col items-center px-4 pb-8 sm:pb-10"
      style={{ backgroundColor: "var(--niaid-page-bg)" }}
    >
      <div className="flex w-full max-w-5xl flex-1 flex-col items-center gap-10 pt-6 sm:gap-12 sm:pt-8 md:gap-14">
        <Breadcrumbs
          items={[
            { label: "Home", href: "/" },
            { label: "Queries" },
          ]}
        />
        <div className="flex w-full flex-col items-center text-center">
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Templated queries
          </h1>
          <p className="mx-auto mt-5 w-[90%] max-w-full text-left text-base leading-relaxed text-slate-600 [text-wrap:pretty] dark:text-slate-400">
            Pick a template to run a predefined, validated SPARQL query pattern over the
            federated WOBD graphs. Fill in your search terms and the app assembles and executes
            the query for you &mdash; no SPARQL required. The current templated UI covers the
            NDE and GXA graphs; for open-ended cross-graph questions across all 30+ Proto-OKN
            graphs, use the{" "}
            <Link href="/mcp" className="font-medium text-niaid-link hover:underline">
              unified MCP server
            </Link>
            .{" "}
            <Link href="/about" className="font-medium text-niaid-link hover:underline">
              Learn more about WOBD
            </Link>
          </p>
        </div>

        <QueryCards />
      </div>
    </div>
  );
}
