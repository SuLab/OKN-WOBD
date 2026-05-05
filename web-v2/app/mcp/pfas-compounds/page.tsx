import Link from "next/link";
import { ArrowRight, Database, FileSearch, Lightbulb } from "lucide-react";
import { getVignetteMeta } from "@/lib/landing/vignette-meta";
import { Breadcrumbs } from "@/components/layout/Breadcrumbs";

const SLUG = "pfas-compounds";

export default function PFASVignettePage() {
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
            Are replacement PFAS chemicals actually safer?
          </h1>
          <p className="mx-auto mt-5 w-[90%] max-w-full text-left text-base leading-relaxed text-slate-600 [text-wrap:pretty] dark:text-slate-400">
            One natural-language query, seven federated knowledge graphs, an answer that joins
            water-system monitoring, adverse outcome pathways, gene-disease associations, and
            transcriptomic datasets &mdash; work that no single database can do.
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
              <strong>GenX</strong>, the chemical that replaced PFOA, is detected at{" "}
              <strong>73% the frequency of legacy PFOS</strong> in U.S. water systems and was
              the <strong>most potent PPAR&alpha; activator</strong> of 16 PFAS tested by the
              EPA &mdash; convergent evidence across seven graphs that compound-by-compound
              substitution is not reducing risk.
            </p>
          </div>
        </section>

        <section className="w-full max-w-3xl space-y-3 text-slate-700 dark:text-slate-300">
          <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            The question
          </h2>
          <blockquote className="border-l-4 border-slate-300 pl-4 italic text-slate-600 dark:border-slate-600 dark:text-slate-400">
            Manufacturers replaced PFOA with GenX (HFPO-DA) and ADONA, marketed as safer
            alternatives. Are the replacements actually safer? Answering that requires linking
            water-system contamination data to molecular mechanism, then to gene-disease
            associations, then to experimental datasets &mdash; across four disciplines that
            traditionally live in different databases.
          </blockquote>
          <p>
            Without an OKN-backed federation, this kind of question lands on a research team
            that has to manually search EPA monitoring data, then mechanistic toxicology
            literature, then transcriptomic repositories like GEO, then disease association
            databases &mdash; weeks to months of cross-disciplinary work, with the synthesis
            still done by hand. The MCP server returns convergent evidence in minutes.
          </p>
        </section>

        <section className="w-full">
          <h2 className="mb-6 text-center text-xl font-semibold text-slate-900 dark:text-slate-100">
            One query, federated answer
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
                Are replacement PFAS chemicals (GenX, ADONA) actually safer than the legacy
                compounds they replaced?
              </p>
            </div>
            <FlowArrow />
            <div className="flex flex-col rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
              <div className="flex items-center gap-2 text-niaid-link">
                <Database className="h-5 w-5" aria-hidden />
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Unified MCP server federates seven KGs
                </h3>
              </div>
              <ul className="mt-2 space-y-1 text-sm text-slate-600 dark:text-slate-400">
                <li>
                  <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-slate-800">
                    sawgraph
                  </code>{" "}
                  &mdash; water-system contamination monitoring
                </li>
                <li>
                  <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-slate-800">
                    biobricks-aopwiki
                  </code>{" "}
                  &mdash; adverse outcome pathways
                </li>
                <li>
                  <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-slate-800">
                    spoke-okn
                  </code>{" "}
                  &mdash; gene-disease associations
                </li>
                <li>
                  <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-slate-800">
                    nde
                  </code>{" "}
                  &mdash; transcriptomic dataset metadata
                </li>
                <li>
                  <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-slate-800">
                    wikidata
                  </code>
                  ,{" "}
                  <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-slate-800">
                    spoke-genelab
                  </code>
                  ,{" "}
                  <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-slate-800">
                    ubergraph
                  </code>{" "}
                  &mdash; functional annotation and ontology
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
                GenX is already detected at 73% the frequency of legacy PFOS in U.S. water
                systems and is the most potent PPAR&alpha; activator of 16 PFAS tested &mdash;
                converging evidence across seven graphs that compound-by-compound regulation is
                not reducing risk.
              </p>
            </div>
          </div>
        </section>

        <section className="w-full">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat number="7" label="federated KGs" />
            <Stat number="25" label="PFAS in water systems" />
            <Stat number="11" label="GenX transcriptomic datasets" />
            <Stat number="168" label="enriched pathways" />
          </div>
        </section>

        <section className="w-full max-w-3xl space-y-3 text-slate-700 dark:text-slate-300">
          <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            What this query unlocks
          </h2>
          <ul className="list-disc space-y-2 pl-6">
            <li>
              <strong>Cross-domain joins.</strong> The query spans environmental monitoring
              (SAWGraph), mechanistic toxicology (AOP-Wiki), gene-disease associations
              (SPOKE-OKN), and experimental datasets (NDE) &mdash; four disciplines that
              traditionally live in separate portals.
            </li>
            <li>
              <strong>Convergent evidence, not single-source claims.</strong> The conclusion
              that replacement PFAS hit the same molecular target as legacy compounds rests on
              independent lines from environmental data, EPA receptor assays, knockout-mouse
              transcriptomics, and pathway enrichment &mdash; each from a different graph.
            </li>
            <li>
              <strong>Mechanism grounded in shared identifiers.</strong> Joins on gene symbols,
              Ensembl IDs, and chemical compound IDs let the assistant move from a chemical in
              water (SAWGraph) to a target receptor (PubMed + NDE) to a disease outcome
              (SPOKE-OKN, AOP-Wiki) without losing provenance.
            </li>
            <li>
              <strong>Policy-relevant synthesis.</strong> The same federated answer that
              identifies a hazard also surfaces the candidate biomarkers (PPARA, ACOX1, FABP1,
              SREBF1) needed to monitor it &mdash; closing the loop from question to actionable
              recommendation.
            </li>
          </ul>
        </section>

        <section className="w-full max-w-3xl space-y-3 border-t border-slate-200 pt-6 text-slate-700 dark:border-slate-700 dark:text-slate-300">
          <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            Why this matters &mdash; public-health policy
          </h2>
          <p>
            Class-based chemical regulation has been a long-standing aim of public-health
            agencies, but the evidence required &mdash; environmental fate, toxicity mechanism,
            and disease association, all linked to specific compounds &mdash; has historically
            lived in separately funded, separately curated databases. Assembling it has meant
            standing up a multi-disciplinary working group for months. The federated MCP
            server makes a question of that shape a chat session, with provenance preserved
            back to each source graph.
          </p>
          <p>
            The implication for emerging-contaminant policy is direct: as the next generation
            of PFAS replacements (and bisphenols, microplastics, and other chemical classes)
            enters the regulatory pipeline, the substrate to evaluate them is already in
            place. The federation also turns single-event policy questions into recurring
            queries &mdash; a regulator can rerun the analysis as new datasets land in the
            knowledge graphs, without rebuilding the workflow.
          </p>
        </section>

        <section className="w-full max-w-3xl">
          <Link
            href="/mcp/pfas-compounds/details"
            className="group flex items-center justify-between gap-4 rounded-lg border border-slate-200 bg-white p-5 shadow-sm transition-all hover:border-slate-300 hover:shadow-md dark:border-slate-700 dark:bg-slate-900 dark:hover:border-slate-600"
          >
            <div>
              <div className="font-medium text-niaid-link group-hover:underline">
                Read the full analysis
              </div>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                Specific datasets, mechanistic findings, disease pathways, and the convergence
                argument in detail.
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
