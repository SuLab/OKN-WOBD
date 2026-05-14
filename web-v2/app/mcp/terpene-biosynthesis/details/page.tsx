import type { Metadata } from "next";
import Link from "next/link";
import { getVignetteMeta } from "@/lib/landing/vignette-meta";
import { Breadcrumbs } from "@/components/layout/Breadcrumbs";

const SLUG = "terpene-biosynthesis";

export const metadata: Metadata = {
  title: "Terpene biosynthesis: full analysis",
  description:
    "Full vignette: federated approach across pathway and expression KGs plus the NDE/WOBD metadata layer, plant + microbial dataset findings, candidate enzyme panel, and ranking criteria.",
};

export default function TerpeneBiosynthesisVignettePage() {
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
            { label: meta.title, href: "/mcp/terpene-biosynthesis" },
            { label: "Details" },
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
            Designing a microbial host for terpene biomanufacturing
          </h1>
          <p className="mx-auto mt-5 w-[90%] max-w-full text-left text-base leading-relaxed text-slate-600 [text-wrap:pretty] dark:text-slate-400">
            A walk-through of how the unified MCP server supports a plant and microbial terpene
            engineering question. The assistant pulls candidate enzymes from pathway and
            expression graphs, then leans on the NDE/WOBD metadata layer to surface the
            experimental datasets that make engineering decisions defensible.
          </p>
        </div>

        <section className="w-full max-w-3xl">
          <div
            className="rounded-lg border border-slate-200 border-l-4 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900"
            style={{ borderLeftColor: "var(--okn-navbar)" }}
          >
            <div className="text-xs font-semibold uppercase tracking-wider text-okn-primary">
              Key finding
            </div>
            <p className="mt-2 text-base leading-relaxed text-slate-800 dark:text-slate-200">
              <strong>20+ datasets</strong> surfaced spanning <strong>seven plant species</strong>
              {" "}and <strong>three microbial hosts</strong>, with a candidate enzyme panel
              anchored across pathway and expression evidence &mdash; usable starting material
              for a synthetic biology team within minutes.
            </p>
          </div>
        </section>

        <div className="w-full max-w-3xl space-y-10 text-slate-700 dark:text-slate-300">
          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              The scenario
            </h2>
            <blockquote className="border-l-4 border-slate-300 pl-4 italic text-slate-600 dark:border-slate-600 dark:text-slate-400">
              A team of synthetic biologists is designing a microbial host for sustainable
              biomanufacturing of a high-value terpene. They want to identify promising genetic
              parts (enzymes from plant and microbial systems) and the experimental datasets
              &mdash; RNA-seq, proteomics, fermentation studies &mdash; that would support those
              choices.
            </blockquote>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              How the assistant approached it
            </h2>
            <p>
              The proto-OKN stack does not have a single &ldquo;terpene pathway graph.&rdquo; The
              effective workflow is a federation of three layers:
            </p>
            <ol className="list-decimal space-y-2 pl-6">
              <li>
                <strong>Pathway and gene-part discovery</strong> &mdash; <code className="rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">prokn</code>,{" "}
                <code className="rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">gene-expression-atlas-okn</code>,{" "}
                <code className="rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">spoke-genelab</code>
              </li>
              <li>
                <strong>Experimental metadata discovery</strong> &mdash;{" "}
                <code className="rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">nde</code>
                , the WOBD metadata layer, with dataset records under{" "}
                <code className="break-all rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">okn.wobd.org/dataset/...</code>
              </li>
              <li>
                <strong>Cross-graph integration</strong> &mdash; joins between
                gene-expression-atlas-okn and spoke-genelab on{" "}
                <code className="rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">NCBI_Gene</code>,{" "}
                <code className="rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">GeneSymbol</code>, and{" "}
                <code className="rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">UBERON</code>
              </li>
            </ol>
          </section>

          <section className="space-y-4">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              Findings
            </h2>

            <div className="space-y-2">
              <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                The terpene ontology space is well covered
              </h3>
              <p>
                Search expansion grounds in <strong>terpenoid biosynthetic process</strong>{" "}
                (GO:0016114) and <strong>isoprenoid biosynthetic process</strong> (GO:0008299).
                Descendants include monoterpenoid, diterpenoid, sesquiterpenoid, triterpenoid,
                carotenoid, hopanoid, paclitaxel, and menthol biosynthetic processes &mdash;
                enough scaffolding to scope queries by terpene class.
              </p>
            </div>

            <div className="space-y-2">
              <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                Plant and microbial coverage in the expression graphs
              </h3>
              <p>
                Taxon coverage relevant to terpene engineering:
              </p>
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 dark:border-slate-700">
                      <th className="px-3 py-2 text-left font-semibold">Taxon</th>
                      <th className="px-3 py-2 text-left font-semibold">gene-expression-atlas-okn</th>
                      <th className="px-3 py-2 text-left font-semibold">spoke-genelab</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                    <tr><td className="px-3 py-2">human</td><td className="px-3 py-2">1671</td><td className="px-3 py-2">43 / 1530</td></tr>
                    <tr><td className="px-3 py-2">mouse</td><td className="px-3 py-2">1323</td><td className="px-3 py-2">104 / 4898</td></tr>
                    <tr><td className="px-3 py-2"><em>Arabidopsis thaliana</em></td><td className="px-3 py-2">638</td><td className="px-3 py-2">40 / 3356</td></tr>
                    <tr><td className="px-3 py-2"><em>Saccharomyces cerevisiae</em></td><td className="px-3 py-2">54</td><td className="px-3 py-2">1 / 26</td></tr>
                  </tbody>
                </table>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  spoke-genelab counts are studies / assays.
                </p>
              </div>
            </div>

            <div className="space-y-2">
              <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                Canonical pathway genes are present
              </h3>
              <p>
                gene-expression-atlas-okn returns the precursor-supply panel:{" "}
                <strong>DXS, DXR, HDR, HMG1/HMG2/HMGR, IDI1/IDI2, ERG20/FDPS, GGPS1, PSY</strong>.
                spoke-genelab adds <em>Arabidopsis</em>-specific hits including{" "}
                <strong>PSY</strong> and <strong>LCYB</strong>. Not enough on its own to
                reconstruct a full specialized-terpene branch, but enough to anchor candidate-part
                searches around precursor-supply modules.
              </p>
            </div>

            <div className="space-y-2">
              <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                Plant datasets surfaced via NDE
              </h3>
              <ul className="list-disc space-y-1 pl-6">
                <li>
                  <strong>GSE102404</strong> &mdash; <em>Artemisia argyi</em> transcriptome
                  naming HMGR, MVD, DXS, DXR, HDS, HDR
                </li>
                <li>
                  <strong>GSE175645, GSE28539, GSE121523, GSE121831</strong> &mdash; <em>Taxus</em>{" "}
                  taxoid / paclitaxel biosynthesis (incl. female-specific MYB-bHLH regulation)
                </li>
                <li>
                  <strong>GSE103181</strong> &mdash; <em>Crocus sativus</em> apocarotenoid
                  biosynthesis: 41 pathway genes + 5 TF hubs
                </li>
                <li>
                  <strong>GSE120135</strong>, <strong>GSE96954</strong> &mdash; maize / Isodon
                  diterpenoid defense pathways (kauralexin, kaurene synthase-like)
                </li>
                <li>
                  <strong>GSE243419</strong> &mdash; single-cell RNA-seq of cotton secretory
                  glandular cells
                </li>
                <li>
                  <strong>GSE109299 / GSE109303 / GSE288025 / GSE287659</strong> &mdash; rice
                  diterpenoid phytoalexin biosynthesis
                </li>
              </ul>
            </div>

            <div className="space-y-2">
              <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                Microbial / host-engineering datasets
              </h3>
              <ul className="list-disc space-y-1 pl-6">
                <li>
                  <strong>GSE102672</strong> &mdash; IPP toxicity in isoprenoid-producing{" "}
                  <em>E. coli</em>; RNA-seq + proteomics through onset and recovery, with PMK
                  reduction implicated as a recovery mechanism
                </li>
                <li>
                  <strong>GSE84255</strong> &mdash; balancing IspG / IspH to reduce toxic HMBPP
                  accumulation in <em>E. coli</em>
                </li>
                <li>
                  <strong>GSE29267</strong>, <strong>GSE30403</strong> &mdash; FPP toxicity in{" "}
                  <em>E. coli</em> (LB and M9), showing rescue by channeling FPP into product
                </li>
                <li>
                  <strong>GSE34665</strong> &mdash; D-limonene response in <em>S. cerevisiae</em>
                  (monoterpene tolerance)
                </li>
                <li>
                  <strong>GSE225783</strong> &mdash; taxadiene-producing <em>S. cerevisiae</em>{" "}
                  evolved for oxidative robustness
                </li>
                <li>
                  <strong>GSE10712</strong> &mdash; <em>Aspergillus nidulans</em> response to
                  farnesol (fungal isoprenoid-alcohol stress)
                </li>
              </ul>
            </div>
          </section>

          <section className="space-y-4">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              A starting candidate panel
            </h2>
            <p>
              Combining the discovery layers gives a first-pass plant and microbial terpene
              engineering panel organized in three modules:
            </p>

            <div className="space-y-2">
              <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                Core precursor-supply module
              </h3>
              <p>
                HMGR / HMG1 / HMG2, MVD, DXS, DXR, HDS, HDR, IDI1 / IDI2, FDPS / ERG20, GGPS1
              </p>
            </div>

            <div className="space-y-2">
              <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                Product-branch module (pick by target class)
              </h3>
              <ul className="list-disc space-y-1 pl-6">
                <li>
                  <strong>Taxoid / taxane:</strong> <em>Taxus</em> datasets (GSE175645, GSE28539,
                  GSE121523, GSE121831) plus the taxadiene yeast adaptation set (GSE225783)
                </li>
                <li>
                  <strong>Defense diterpene:</strong> maize and <em>Isodon</em> (GSE120135,
                  GSE96954) for kaurene/kauralexin scaffolds and recruited P450 chemistry
                </li>
                <li>
                  <strong>Carotenoid / apocarotenoid:</strong> <em>Crocus</em>, cotton single
                  cell, <em>Arabidopsis</em> (GSE103181, GSE243419), driving PSY/LCYB and
                  downstream regulators
                </li>
              </ul>
            </div>

            <div className="space-y-2">
              <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                Host-hardening module
              </h3>
              <ul className="list-disc space-y-1 pl-6">
                <li>PMK balancing from IPP toxicity (GSE102672)</li>
                <li>IspG / IspH balancing from HMBPP accumulation (GSE84255)</li>
                <li>FPP-to-product sink logic (GSE29267, GSE30403)</li>
                <li>Monoterpene tolerance programs (GSE34665)</li>
                <li>Oxidative robustness in taxadiene yeast (GSE225783)</li>
              </ul>
            </div>

            <div className="space-y-2">
              <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                Suggested ranking
              </h3>
              <p>
                A practical priority score combines{" "}
                <strong>pathway centrality</strong> (precursor-supply outranks peripheral
                responders),{" "}
                <strong>plant and microbial evidence</strong> (Arabidopsis, Taxus, Artemisia,
                maize, yeast, E. coli),{" "}
                <strong>dataset richness</strong> (multi-omics, perturbation, time course over
                static single-condition), and{" "}
                <strong>engineering transferability</strong> (microbial toxicity / tolerance gets
                extra weight because it de-risks host design).
              </p>
            </div>
          </section>

          <section className="space-y-3 border-t border-slate-200 pt-6 dark:border-slate-700">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              Bottom line
            </h2>
            <p>
              The proto-OKN environment supports the scenario, but the most effective execution
              splits the work across layers: ontology terms define the terpene biology space, the
              expression KGs confirm plant and microbial coverage and candidate-gene presence,
              and the
              NDE/WOBD metadata layer carries the plant and microbial datasets that make
              engineering decisions defensible. The natural next step is a ranked candidate table
              with graph-specific query templates for one terpene class &mdash; taxanes,
              carotenoid/apocarotenoids, or defense diterpenes.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
