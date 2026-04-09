import Link from "next/link";
import { QueryCards } from "@/components/landing/QueryCards";

export default function LandingPage() {
  return (
    <div
      className="flex flex-1 flex-col items-center px-4 pb-8 sm:pb-10"
      style={{ backgroundColor: "var(--niaid-page-bg)" }}
    >
      <div className="flex w-full max-w-5xl flex-1 flex-col items-center gap-12 pt-24 sm:gap-14 sm:pt-28 md:gap-16 md:pt-32">
        <div className="flex w-full flex-col items-center text-center">
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Web of Biological Data
          </h1>
          <p className="mx-auto mt-5 w-[90%] max-w-full text-left text-base leading-relaxed text-slate-600 [text-wrap:pretty] dark:text-slate-400">
            The Web of Biological Data (WOBD) helps researchers discover
            infectious- and immune-related datasets and connect them to gene expression and other
            biological knowledge graphs. It brings together metadata from the{" "}
            <a
              href="https://data.niaid.nih.gov/"
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-niaid-link underline-offset-2 hover:underline"
            >
              NIAID Data Ecosystem
            </a>{" "}
            with results from resources such as the Gene Expression Atlas, using guided templates
            instead of writing SPARQL by hand. WOBD is part of broader{" "}
            <a
              href="https://www.proto-okn.net/"
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-niaid-link underline-offset-2 hover:underline"
            >
              Proto-OKN
            </a>{" "}
            effort to make biomedical discovery more open and AI-ready.{" "}
            <Link href="/about" className="font-medium text-niaid-link hover:underline">
              Learn more
            </Link>
          </p>
        </div>

        <QueryCards />
      </div>
    </div>
  );
}
