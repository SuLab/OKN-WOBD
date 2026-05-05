import type { Metadata } from "next";
import { Breadcrumbs } from "@/components/layout/Breadcrumbs";

export const metadata: Metadata = {
  title: "About",
  description:
    "WOBD is an NSF-funded prototype federating biomedical dataset metadata with the Proto-OKN knowledge graphs. Team, roadmap, and project context.",
};

export default function AboutPage() {
  return (
    <div
      className="flex flex-1 flex-col items-center px-4 pb-8 sm:pb-10"
      style={{ backgroundColor: "var(--niaid-page-bg)" }}
    >
      <div className="flex w-full max-w-5xl flex-1 flex-col gap-8 pt-6 sm:gap-10 sm:pt-8">
        <Breadcrumbs
          items={[
            { label: "Home", href: "/" },
            { label: "About" },
          ]}
        />

        <div className="mx-auto w-full max-w-3xl space-y-8 text-slate-700 dark:text-slate-300">
          <header className="space-y-4">
            <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
              About the Web of Biological Data
            </h1>
            <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm dark:border-slate-700 dark:bg-slate-900">
              <p className="text-slate-700 dark:text-slate-300">
                <strong>WOBD</strong> federates harmonized biomedical dataset metadata from the
                NIAID Data Ecosystem with the Proto-OKN biomedical knowledge graphs so a single
                query can move across dataset discovery, mechanism, and disease.
              </p>
              <p className="mt-2 text-slate-600 dark:text-slate-400">
                Supported by the U.S. National Science Foundation under award{" "}
                <a
                  className="font-medium text-niaid-link hover:underline"
                  href="https://www.nsf.gov/awardsearch/show-award/?AWD_ID=2535091"
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  #2535091
                </a>
                . Part of the NSF{" "}
                <a
                  className="font-medium text-niaid-link hover:underline"
                  href="https://www.proto-okn.net/"
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  Proto-OKN
                </a>{" "}
                federation.
              </p>
            </div>
            <p className="text-slate-600 dark:text-slate-400">
              The current implementation is a prototype: harmonized dataset metadata and gene
              expression analysis results are ingested, published, and queryable through a
              templated SPARQL UI, and the broader Proto-OKN federation is reachable through a
              unified Model Context Protocol server.
            </p>
          </header>

          <section className="space-y-3 border-t border-slate-200 pt-6 dark:border-slate-700">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              Roadmap
            </h2>
            <p>
              Two strands of future work would substantially expand what WOBD can answer:
            </p>
            <ul className="list-disc space-y-2 pl-6">
              <li>
                <strong>Broader dataset metadata ingestion.</strong> Today the dataset metadata
                layer is built primarily from NDE. Adding additional repositories (other
                domain-specific and generalist sources) would extend the federation&apos;s
                reach into clinical, environmental, and multi-omic data that NDE does not
                presently cover.
              </li>
              <li>
                <strong>Richer dataset metadata expressiveness.</strong> Current dataset records
                describe what a dataset is and where to find it. Expanding the schema to capture
                richer relationships &mdash; sample-level annotation, study-level provenance,
                contrast-level metadata &mdash; would let federated queries return more
                actionable results without requiring users to drop into per-dataset portals.
              </li>
            </ul>
            <p>
              Both directions require sustained engineering investment. Both also compound: each
              additional metadata source and each schema extension widens the set of
              cross-domain questions the unified MCP server can answer in a single chat.
            </p>
          </section>

          <section className="space-y-4 border-t border-slate-200 pt-6 dark:border-slate-700">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Team</h2>
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Scripps Research
                </h3>
                <ul className="mt-1 space-y-1 text-sm text-slate-700 dark:text-slate-300">
                  <li>Trish Whetzel</li>
                  <li>Ben Good</li>
                  <li>Andrew Su</li>
                  <li>Ginger Tsueng</li>
                </ul>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  RENCI
                </h3>
                <ul className="mt-1 space-y-1 text-sm text-slate-700 dark:text-slate-300">
                  <li>Chris Bizon</li>
                  <li>Jim Balhoff</li>
                  <li>Yaphet Kebede</li>
                </ul>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  UCSD / UCSF
                </h3>
                <ul className="mt-1 space-y-1 text-sm text-slate-700 dark:text-slate-300">
                  <li>Peter Rose</li>
                </ul>
              </div>
            </div>
          </section>

          <section className="space-y-3 border-t border-slate-200 pt-6 dark:border-slate-700">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              Relationship to Proto-OKN
            </h2>
            <p>
              The WOBD work extends ideas from the NSF{" "}
              <a
                className="font-medium text-niaid-link hover:underline"
                href="https://www.proto-okn.net/"
                rel="noopener noreferrer"
                target="_blank"
              >
                Proto-OKN
              </a>{" "}
              program: a publicly accessible, interconnected set of knowledge graphs and data
              services aimed at trustworthy, data-driven discovery. WOBD is a focused path
              within that broader fabric &mdash; the templated UI exposes the NDE and GXA graphs
              for reproducible workflows, and the unified MCP server reaches the entire
              federation, including curated biology in Wikidata, SPOKE-OKN, AOP-Wiki, and
              dozens of other graphs.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              Dataset metadata: the NIAID Data Ecosystem (NDE)
            </h2>
            <p>
              The primary structured metadata behind many graphs in this project comes from the{" "}
              <a
                className="font-medium text-niaid-link hover:underline"
                href="https://data.niaid.nih.gov"
                rel="noopener noreferrer"
                target="_blank"
              >
                NIAID Data Ecosystem Discovery Portal
              </a>{" "}
              (NDE). The NDE aggregates and harmonizes dataset records from domain-specific and
              generalist repositories, clinical, epidemiological, multi-omic, and more into a
              unified search index with a Schema.org&ndash;aligned schema, filters for host,
              pathogen, condition, and technique, and an API for programmatic access. Records
              point back to their source repositories rather than replacing them; the value is
              consistent discovery across sources.
            </p>
            <p>
              For a full description of the portal&apos;s design and scope, see Whetzel et&nbsp;al.,{" "}
              <a
                className="font-medium text-niaid-link hover:underline"
                href="https://journals.asm.org/doi/10.1128/msystems.01270-25"
                rel="noopener noreferrer"
                target="_blank"
              >
                The NIAID Discovery Portal: A Unified Search Engine for Infectious and
                Immune-Mediated Disease Datasets
              </a>{" "}
              (<em>mSystems</em>, 2026). Metadata harvested from the NDE pipeline is published as
              the NDE graph and loaded alongside other graphs in the federation used by this
              application.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              Gene Expression Atlas (GXA) data
            </h2>
            <p>
              Data for the GXA graph is built from experiments in the{" "}
              <a
                className="font-medium text-niaid-link hover:underline"
                href="https://www.ebi.ac.uk/gxa/home"
                rel="noopener noreferrer"
                target="_blank"
              >
                EMBL-EBI Gene Expression Atlas (GXA)
              </a>
              , public differential-expression and functional studies. Experiment packages are
              retrieved from the Atlas infrastructure, parsed, and emitted as Biolink-compatible
              linked data (study metadata, contrasts, genes, and pathway enrichment) so users
              can run queries that span NDE dataset metadata, GXA expression results, and other
              knowledge graphs in the federation, combining and interpreting those results in
              one workflow.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              FRINK registry and how things connect
            </h2>
            <p>
              Knowledge graphs are listed in the{" "}
              <a
                className="font-medium text-niaid-link hover:underline"
                href="https://registry.okn.us/"
                rel="noopener noreferrer"
                target="_blank"
              >
                FRINK registry
              </a>
              , each with a short name, title, description, and a link to its query endpoint. The{" "}
              <a
                className="font-medium text-niaid-link hover:underline"
                href="https://apps.okn.us/"
                rel="noopener noreferrer"
                target="_blank"
              >
                FRINK SPARQL federation
              </a>{" "}
              exposes those graphs so they can be queried individually or in combination. The
              NDE graph is published in that ecosystem; the GXA graph is published similarly. At
              a high level, WOBD links NDE metadata (what datasets exist, how they are
              annotated, and where to get them) to the same query plane as curated biological
              knowledge (genes, diseases, drugs, pathways, expression contrasts) already present
              in FRINK, so templated SPARQL queries and AI assistants can span dataset discovery
              and mechanistic context without siloed portals.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
