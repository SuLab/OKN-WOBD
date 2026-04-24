import Link from "next/link";
import { QueryCards } from "@/components/landing/QueryCards";

export default function QueriesPage() {
  return (
    <div
      className="flex flex-1 flex-col items-center px-4 pb-8 sm:pb-10"
      style={{ backgroundColor: "var(--niaid-page-bg)" }}
    >
      <div className="flex w-full max-w-5xl flex-1 flex-col items-center gap-12 pt-24 sm:gap-14 sm:pt-28 md:gap-16 md:pt-32">
        <div className="flex w-full flex-col items-center text-center">
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Templated queries
          </h1>
          <p className="mx-auto mt-5 w-[90%] max-w-full text-left text-base leading-relaxed text-slate-600 [text-wrap:pretty] dark:text-slate-400">
            Pick a template to run a predefined, validated SPARQL query pattern over the
            federated WOBD graphs. Fill in your search terms and the app assembles and executes
            the query for you &mdash; no SPARQL required.{" "}
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
