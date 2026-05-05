import Link from "next/link";
import { ArrowRight, Database, FileSearch, Lightbulb } from "lucide-react";
import { getVignetteMeta } from "@/lib/landing/vignette-meta";
import { Breadcrumbs } from "@/components/layout/Breadcrumbs";

const SLUG = "diabetic-nephropathy";

export default function DiabeticNephropathyVignettePage() {
  const meta = getVignetteMeta(SLUG)!;
  const Icon = meta.icon;

  return (
    <div
      className="flex flex-1 flex-col items-center px-4 pb-8 sm:pb-10"
      style={{ backgroundColor: "var(--niaid-page-bg)" }}
    >
      <div className="flex w-full max-w-5xl flex-1 flex-col items-center gap-10 pt-6 sm:gap-12 sm:pt-8 md:gap-14">
        <Breadcrumbs
          items={[
            { label: "Home", href: "/" },
            { label: "MCP", href: "/mcp" },
            { label: meta.title },
          ]}
        />
        <div className="flex w-full flex-col items-center text-center">
          <span
            className={`mb-4 inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium dark:bg-slate-800 ${meta.iconColor}`}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden />
            {meta.tag}
          </span>
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            End-to-end differential expression from a single question
          </h1>
          <p className="mx-auto mt-5 w-[90%] max-w-full text-left text-base leading-relaxed text-slate-600 [text-wrap:pretty] dark:text-slate-400">
            One natural-language ask, an orchestrated bioinformatics pipeline (ontology
            resolution &rarr; sample discovery &rarr; differential expression &rarr; enrichment),
            and a method comparison that surfaced biology a simpler analysis would have missed.
          </p>
        </div>

        <section className="w-full max-w-3xl">
          <div
            className="rounded-lg border border-slate-200 border-l-4 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900"
            style={{ borderLeftColor: "var(--niaid-link)" }}
          >
            <div className="text-xs font-semibold uppercase tracking-wider text-niaid-link">
              Key finding
            </div>
            <p className="mt-2 text-base leading-relaxed text-slate-800 dark:text-slate-200">
              An <strong>end-to-end DE workflow</strong> &mdash; disease ontology resolution,
              ARCHS4 sample classification, statistical testing, enrichment &mdash; executed
              from one chat. Comparing pooled and study-matched modes revealed an{" "}
              <strong>interferon signaling signal</strong> (OAS2, RSAD2) that the simpler
              pooled analysis would have missed.
            </p>
          </div>
        </section>

        <section className="w-full max-w-3xl space-y-3 text-slate-700 dark:text-slate-300">
          <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            The question
          </h2>
          <blockquote className="border-l-4 border-slate-300 pl-4 italic text-slate-600 dark:border-slate-600 dark:text-slate-400">
            Run a differential expression analysis of diabetic nephropathy using the public
            ARCHS4 bulk RNA-seq archive. Find disease and control samples, compute DE, and
            interpret the results.
          </blockquote>
          <p>
            Without an OKN-backed MCP server, this is days of manual work for a bioinformatics
            postdoc: resolve the disease term to a MONDO concept, download ARCHS4 metadata,
            classify thousands of samples as test or control, write the statistical pipeline,
            decide between pooled and per-study designs, and run enrichment. The MCP server
            does it in one chat &mdash; <em>and</em> runs both methods so the user sees what
            the simpler analysis would have missed.
          </p>
        </section>

        <section className="w-full">
          <h2 className="mb-6 text-center text-xl font-semibold text-slate-900 dark:text-slate-100">
            One question, orchestrated pipeline
          </h2>
          <div className="grid grid-cols-1 items-stretch gap-3 md:grid-cols-[1fr_auto_1.5fr_auto_1fr]">
            <div className="flex flex-col rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
              <div className="flex items-center gap-2 text-niaid-link">
                <Lightbulb className="h-5 w-5" aria-hidden />
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Natural-language query
                </h3>
              </div>
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
                Run a pooled differential expression analysis of diabetic nephropathy using
                ARCHS4. Then try the study-matched meta-analysis.
              </p>
            </div>
            <FlowArrow />
            <div className="flex flex-col rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
              <div className="flex items-center gap-2 text-niaid-link">
                <Database className="h-5 w-5" aria-hidden />
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  MCP server orchestrates four tools
                </h3>
              </div>
              <ul className="mt-2 space-y-1 text-sm text-slate-600 dark:text-slate-400">
                <li>
                  <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-slate-800">
                    resolve_disease_ontology
                  </code>{" "}
                  &mdash; MONDO term lookup
                </li>
                <li>
                  <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-slate-800">
                    find_samples
                  </code>{" "}
                  &mdash; ARCHS4 metadata + LLM sample classification
                </li>
                <li>
                  <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-slate-800">
                    differential_expression
                  </code>{" "}
                  &mdash; pooled and study-matched meta-analysis
                </li>
                <li>
                  <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-slate-800">
                    enrichment_analysis
                  </code>{" "}
                  &mdash; g:Profiler over GO, KEGG, Reactome
                </li>
              </ul>
            </div>
            <FlowArrow />
            <div className="flex flex-col rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
              <div className="flex items-center gap-2 text-niaid-link">
                <FileSearch className="h-5 w-5" aria-hidden />
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Integrated answer
                </h3>
              </div>
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
                Five immediate-early response transcription factors strongly downregulated;
                study-matched mode additionally reveals two upregulated interferon-stimulated
                genes (OAS2, RSAD2) that pooling missed &mdash; pointing at two coordinated
                biological processes in DN kidney.
              </p>
            </div>
          </div>
        </section>

        <section className="w-full">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat number="174" label="DN samples discovered" />
            <Stat number="13" label="ARCHS4 studies" />
            <Stat number="7" label="significant genes" />
            <Stat number="2" label="DE methods compared" />
          </div>
        </section>

        <section className="w-full max-w-3xl space-y-3 text-slate-700 dark:text-slate-300">
          <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            What this query unlocks
          </h2>
          <ul className="list-disc space-y-2 pl-6">
            <li>
              <strong>End-to-end automation.</strong> Disease ontology resolution, sample
              discovery and per-study LLM classification, statistical testing, and enrichment
              all run in a single chat session &mdash; the kind of workflow that previously
              demanded a bioinformatics postdoc with R/Bioconductor experience.
            </li>
            <li>
              <strong>Method comparison by default.</strong> The MCP runs both pooled (fast,
              cross-study) and study-matched meta-analysis (controls for batch effects per
              study), making the methodology choice transparent and surfacing signal that one
              method alone would miss.
            </li>
            <li>
              <strong>Reproducibility built in.</strong> Every parameter &mdash; FDR threshold,
              fold-change cutoff, sample IDs, contributing studies, statistical test &mdash; is
              recorded in the answer; rerunning the analysis is a copy-paste, not a
              re-derivation.
            </li>
            <li>
              <strong>Biology, not just statistics.</strong> The combined picture &mdash;
              suppressed immediate-early gene response plus activated interferon signaling
              &mdash; matches established disease biology, anchored to specific GEO accessions
              the user can drill into.
            </li>
          </ul>
        </section>

        <section className="w-full max-w-3xl space-y-3 border-t border-slate-200 pt-6 text-slate-700 dark:border-slate-700 dark:text-slate-300">
          <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            Why this matters &mdash; research productivity
          </h2>
          <p>
            Differential expression is the single most common bioinformatics analysis in
            biomedical research. Every disease produces its own variant, every variant takes
            weeks of postdoc time to assemble, and the methodological choices (pooled vs.
            matched, FDR cutoffs, sample inclusion) are buried in supplementary methods that
            rarely make it back into the next study. An MCP server that runs the workflow
            end-to-end &mdash; with both methods, with classification logged, with parameters
            preserved &mdash; turns the analysis itself into a portable, comparable artifact
            instead of an undocumented one-off.
          </p>
          <p>
            Diabetic nephropathy is one disease in ARCHS4&apos;s ~1M-sample archive. The same
            tool stack runs an analogous analysis for any condition with samples in the
            archive, and the underlying pattern &mdash; ontology resolution, automated sample
            classification, two-method DE, enrichment &mdash; transfers to other transcriptomic
            archives as they are integrated. The compounding investment is in the workflow
            scaffolding, not the per-disease scripting.
          </p>
        </section>

        <section className="w-full max-w-3xl">
          <Link
            href="/mcp/diabetic-nephropathy/details"
            className="group flex items-center justify-between gap-4 rounded-lg border border-slate-200 bg-white p-5 shadow-sm transition-all hover:border-slate-300 hover:shadow-md dark:border-slate-700 dark:bg-slate-900 dark:hover:border-slate-600"
          >
            <div>
              <div className="font-medium text-niaid-link group-hover:underline">
                Read the full analysis
              </div>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                Sample discovery, pooled and study-matched DE results, enrichment, and the
                pooled-vs-matched comparison.
              </p>
            </div>
            <ArrowRight
              className="h-5 w-5 flex-shrink-0 text-niaid-link"
              aria-hidden
            />
          </Link>
        </section>
      </div>
    </div>
  );
}

function FlowArrow() {
  return (
    <div className="flex items-center justify-center text-slate-400">
      <ArrowRight className="hidden h-5 w-5 md:block" aria-hidden />
      <ArrowRight className="h-5 w-5 rotate-90 md:hidden" aria-hidden />
    </div>
  );
}

function Stat({ number, label }: { number: string; label: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 text-center shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <div className="text-2xl font-bold text-slate-900 dark:text-slate-100">{number}</div>
      <div className="mt-1 text-xs text-slate-600 dark:text-slate-400">{label}</div>
    </div>
  );
}
