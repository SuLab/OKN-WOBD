import type { Metadata } from "next";
import { Breadcrumbs } from "@/components/layout/Breadcrumbs";
import {
  CONTACT_EMAIL,
  CONTACT_SUBJECT,
  FRINK_OKN_URL,
  FRINK_REGISTRY_URL,
  NSF_AWARD_NUMBER,
  NSF_AWARD_URL,
  PROTO_OKN_URL,
} from "@/lib/site-config";

export const metadata: Metadata = {
  title: "About and growth plan",
  description:
    "WOBD is NSF-funded research infrastructure connecting biomedical dataset metadata with Proto-OKN knowledge graphs. Learn what it does, why it compounds, and what continued support unlocks.",
};

const growthPriorities = [
  {
    title: "Broader metadata ingestion",
    body:
      "Extend beyond the current NDE-centered layer into additional domain-specific and generalist repositories, especially clinical, environmental, and multi-omic resources that users otherwise search separately.",
  },
  {
    title: "Richer dataset descriptions",
    body:
      "Capture sample-level annotation, study provenance, assay context, contrasts, and analysis-ready relationships so WOBD can return more actionable answers without pushing users back into every source portal.",
  },
  {
    title: "Cross-graph identifiers and evaluation",
    body:
      "Strengthen mappings across genes, diseases, chemicals, organisms, datasets, and publications, then benchmark recurring workflows so AI-mediated answers remain auditable and reproducible as the federation grows.",
  },
];

const supportOutcomes = [
  "More repositories become discoverable through one query plane.",
  "More scientific questions become reusable workflows instead of one-off integrations.",
  "More AI-assistant answers carry graph provenance, query traces, and source records.",
  "More program investments become interoperable with the broader Proto-OKN ecosystem.",
];

export default function AboutPage() {
  return (
    <div className="flex flex-1 flex-col items-center px-4 pb-10 sm:pb-12">
      <div className="flex w-full max-w-[1200px] flex-1 flex-col gap-8 pt-6 sm:gap-10 sm:pt-8">
        <Breadcrumbs
          items={[
            { label: "Home", href: "/" },
            { label: "About" },
          ]}
        />

        <div className="mx-auto w-full max-w-[740px] space-y-8 text-okn-textStrong">
          <header className="rounded-[10px] border border-okn-border bg-white p-6 shadow-sm sm:p-8">
            <div className="text-xs font-semibold uppercase tracking-wider text-okn-primary">
              About WOBD
            </div>
            <h1 className="mt-3 text-3xl font-bold tracking-tight text-okn-navbar sm:text-4xl">
              Research infrastructure for queryable, AI-ready biomedical data.
            </h1>
            <p className="mt-5 border-l-4 border-okn-navbar pl-4 text-base leading-relaxed text-okn-textStrong">
              The Web of Biological Data federates harmonized biomedical dataset metadata with
              Proto-OKN knowledge graphs so researchers can move from a question to mechanisms,
              diseases, exposures, genes, and supporting datasets in one reproducible workflow.
            </p>
            <p className="mt-3 text-base leading-relaxed text-okn-textMuted">
              WOBD is supported by the U.S. National Science Foundation under award{" "}
              <a
                className="font-medium text-okn-primary hover:underline"
                href={NSF_AWARD_URL}
                rel="noopener noreferrer"
                target="_blank"
              >
                #{NSF_AWARD_NUMBER}
              </a>{" "}
              and is part of the{" "}
              <a
                className="font-medium text-okn-primary hover:underline"
                href={PROTO_OKN_URL}
                rel="noopener noreferrer"
                target="_blank"
              >
                Proto-OKN
              </a>{" "}
              federation.
            </p>
          </header>

          <section className="grid gap-4 md:grid-cols-[0.9fr_1.1fr]">
            <div className="rounded-[10px] border border-okn-border bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
              <h2 className="text-xl font-semibold text-okn-navbar">
                The value proposition
              </h2>
              <p className="mt-3 text-sm leading-relaxed text-okn-textStrong">
                Biomedical data resources are often funded, curated, and queried separately.
                WOBD makes those investments work together by giving datasets and knowledge
                graphs a shared query plane that both humans and AI assistants can use.
              </p>
            </div>
            <div className="rounded-[10px] border border-okn-border bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
              <h2 className="text-xl font-semibold text-okn-navbar">
                Why continued support compounds
              </h2>
              <p className="mt-3 text-sm leading-relaxed text-okn-textStrong">
                WOBD is not a single-purpose application. Each graph, repository, identifier
                bridge, and metadata extension expands the set of questions that can be asked
                across the entire federation without rebuilding a bespoke integration.
              </p>
            </div>
          </section>

          <section className="rounded-[10px] border border-okn-border bg-white p-6 shadow-sm">
            <h2 className="text-xl font-semibold text-okn-navbar">Growth plan</h2>
            <p className="mt-3 max-w-3xl text-sm leading-relaxed text-okn-textMuted">
              The next stage of WOBD should focus on durable infrastructure: more sources,
              richer metadata, stronger cross-graph identity, and evaluation that keeps
              AI-assisted discovery inspectable.
            </p>
            <div className="mt-5 grid gap-4 md:grid-cols-3">
              {growthPriorities.map((priority) => (
                <div
                  key={priority.title}
                  className="rounded-[10px] border border-okn-border bg-okn-bgMuted p-4"
                >
                  <h3 className="text-sm font-semibold text-okn-primary">
                    {priority.title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-okn-textStrong">
                    {priority.body}
                  </p>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-[10px] border border-okn-border bg-white p-6 shadow-sm">
            <h2 className="text-xl font-semibold text-okn-navbar">What support unlocks</h2>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {supportOutcomes.map((outcome) => (
                <div
                  key={outcome}
                  className="rounded-[10px] border border-okn-border bg-okn-bgMuted p-4 text-sm leading-relaxed text-okn-textStrong"
                >
                  {outcome}
                </div>
              ))}
            </div>
          </section>

          <section className="space-y-4 border-t border-okn-border pt-6">
            <h2 className="text-xl font-semibold text-okn-navbar">
              Current user-facing surfaces
            </h2>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-[10px] border border-okn-border bg-white p-5">
                <h3 className="text-sm font-semibold uppercase tracking-wider text-okn-primary">
                  Guided query templates
                </h3>
                <p className="mt-2 text-sm leading-relaxed">
                  Researchers fill in terms for dataset discovery, drug-related datasets, and
                  gene-expression questions. WOBD generates validated graph queries and returns
                  table or dataset-card results with query traces.
                </p>
              </div>
              <div className="rounded-[10px] border border-okn-border bg-white p-5">
                <h3 className="text-sm font-semibold uppercase tracking-wider text-okn-primary">
                  Unified MCP server
                </h3>
                <p className="mt-2 text-sm leading-relaxed">
                  AI assistants can discover relevant graphs, inspect schemas, bridge
                  identifiers, run SPARQL, and synthesize answers across the wider Proto-OKN
                  federation from one conversation.
                </p>
              </div>
            </div>
          </section>

          <section className="space-y-4 border-t border-okn-border pt-6">
            <h2 className="text-xl font-semibold text-okn-navbar">Team</h2>
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <h3 className="text-sm font-semibold text-okn-textStrong">Scripps Research</h3>
                <ul className="mt-1 space-y-1 text-sm text-okn-textStrong">
                  <li>Trish Whetzel</li>
                  <li>Ben Good</li>
                  <li>Andrew Su</li>
                  <li>Ginger Tsueng</li>
                </ul>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-okn-textStrong">RENCI</h3>
                <ul className="mt-1 space-y-1 text-sm text-okn-textStrong">
                  <li>Chris Bizon</li>
                  <li>Jim Balhoff</li>
                  <li>Yaphet Kebede</li>
                </ul>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-okn-textStrong">UCSD / UCSF</h3>
                <ul className="mt-1 space-y-1 text-sm text-okn-textStrong">
                  <li>Peter Rose</li>
                </ul>
              </div>
            </div>
          </section>

          <section className="space-y-3 border-t border-okn-border pt-6">
            <h2 className="text-xl font-semibold text-okn-navbar">Technical foundation</h2>
            <p>
              The primary structured dataset metadata layer comes from the{" "}
              <a
                className="font-medium text-okn-primary hover:underline"
                href="https://data.niaid.nih.gov"
                rel="noopener noreferrer"
                target="_blank"
              >
                NIAID Data Ecosystem Discovery Portal
              </a>{" "}
              (NDE), which harmonizes dataset records from domain-specific and generalist
              repositories. Metadata harvested from that pipeline is published as the NDE graph
              and loaded alongside other graphs in the federation.
            </p>
            <p>
              WOBD also uses data from the{" "}
              <a
                className="font-medium text-okn-primary hover:underline"
                href="https://www.ebi.ac.uk/gxa/home"
                rel="noopener noreferrer"
                target="_blank"
              >
                EMBL-EBI Gene Expression Atlas
              </a>{" "}
              (GXA), emitting study metadata, contrasts, genes, and pathway enrichment as linked
              data so expression evidence can be queried with dataset metadata and other
              knowledge graphs.
            </p>
            <p>
              Knowledge graphs are listed in the{" "}
              <a
                className="font-medium text-okn-primary hover:underline"
                href={FRINK_REGISTRY_URL}
                rel="noopener noreferrer"
                target="_blank"
              >
                FRINK registry
              </a>
              , and the{" "}
              <a
                className="font-medium text-okn-primary hover:underline"
                href={FRINK_OKN_URL}
                rel="noopener noreferrer"
                target="_blank"
              >
                FRINK SPARQL federation
              </a>{" "}
              exposes those graphs so they can be queried individually or together.
            </p>
          </section>

          <section className="rounded-[10px] border border-okn-border bg-white p-6 text-center shadow-sm">
            <h2 className="text-xl font-semibold text-okn-navbar">
              Discuss WOBD growth or collaboration
            </h2>
            <p className="mx-auto mt-3 max-w-2xl text-sm leading-relaxed text-okn-textMuted">
              For programmatic questions, collaboration opportunities, or support discussions,
              contact the WOBD team.
            </p>
            <a
              href={`mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(CONTACT_SUBJECT)}`}
              className="mt-5 inline-flex items-center rounded-[14px] bg-okn-primary px-6 py-3 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-okn-navbar hover:shadow-md"
            >
              Contact the team
            </a>
          </section>
        </div>
      </div>
    </div>
  );
}
