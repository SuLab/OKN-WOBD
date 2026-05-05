import type { Metadata } from "next";
import { getVignetteMeta } from "@/lib/landing/vignette-meta";
import { Breadcrumbs } from "@/components/layout/Breadcrumbs";

const SLUG = "pfas-compounds";

export const metadata: Metadata = {
  title: "PFAS compounds: full analysis",
  description:
    "Full vignette: SAWGraph contamination data, EPA potency study, AOP-Wiki + g:Profiler enrichment, SPOKE-OKN disease convergence, and the convergence argument across seven knowledge graphs.",
};

export default function PFASDetailsPage() {
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
            { label: meta.title, href: "/mcp/pfas-compounds" },
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
            Are replacement PFAS chemicals actually safer?
          </h1>
          <p className="mx-auto mt-5 w-[90%] max-w-full text-left text-base leading-relaxed text-slate-600 [text-wrap:pretty] dark:text-slate-400">
            A walk-through of how the unified MCP server answers a cross-domain public-health
            question by federating environmental monitoring, adverse outcome pathways,
            gene-disease associations, and transcriptomic datasets across seven knowledge
            graphs.
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

        <div className="w-full max-w-3xl space-y-10 text-slate-700 dark:text-slate-300">
          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              The scenario
            </h2>
            <blockquote className="border-l-4 border-slate-300 pl-4 italic text-slate-600 dark:border-slate-600 dark:text-slate-400">
              PFAS (per- and polyfluoroalkyl substances) are &ldquo;forever chemicals&rdquo;
              used since the 1950s in non-stick coatings, waterproof textiles, firefighting
              foams, and food packaging. As evidence of harm from PFOS and PFOA mounted,
              manufacturers introduced replacements like GenX (HFPO-DA) and ADONA, marketed as
              safer. Whether the replacements are actually safer, or whether they hit the same
              biological targets, is the question.
            </blockquote>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              How the assistant approached it
            </h2>
            <p>
              The answer requires linking four different kinds of evidence. The MCP server
              federated seven Proto-OKN knowledge graphs plus three external tools to produce
              it:
            </p>
            <ol className="list-decimal space-y-2 pl-6">
              <li>
                <strong>Environmental contamination</strong> &mdash;{" "}
                <code className="rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">
                  sawgraph
                </code>{" "}
                for water-system monitoring of monitored PFAS compounds.
              </li>
              <li>
                <strong>Mechanistic toxicology</strong> &mdash;{" "}
                <code className="rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">
                  biobricks-aopwiki
                </code>{" "}
                for adverse outcome pathways, plus PubMed for the EPA's 16-PFAS receptor-binding
                study.
              </li>
              <li>
                <strong>Disease and pathway evidence</strong> &mdash;{" "}
                <code className="rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">
                  spoke-okn
                </code>
                ,{" "}
                <code className="rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">
                  ubergraph
                </code>
                , and{" "}
                <code className="rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">
                  wikidata
                </code>{" "}
                for gene-disease associations and functional annotation; g:Profiler for pathway
                enrichment of the 10 most-implicated PFAS genes.
              </li>
              <li>
                <strong>Experimental datasets</strong> &mdash;{" "}
                <code className="rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">
                  nde
                </code>{" "}
                for transcriptomic studies, plus{" "}
                <code className="rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">
                  spoke-genelab
                </code>{" "}
                for differential-expression validation across spaceflight and other stress
                contexts.
              </li>
            </ol>
            <p>
              Cross-graph joins used gene symbols, Ensembl IDs, and chemical compound identities
              as shared identifiers. The same chemical (GenX) and the same gene (PPARA) can be
              referenced consistently across SAWGraph, NDE, SPOKE-OKN, and PubMed because of
              that shared identifier substrate.
            </p>
          </section>

          <section className="space-y-4">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              Findings
            </h2>

            <div className="space-y-2">
              <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                Replacement PFAS are already ubiquitous
              </h3>
              <p>
                SAWGraph tracks <strong>25 distinct PFAS compounds</strong> across U.S. water
                systems. Replacement chemicals are not trace contaminants &mdash; they are
                already present at frequencies comparable to the legacy compounds they were
                meant to replace.
              </p>
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 dark:border-slate-700">
                      <th className="px-3 py-2 text-left font-semibold">Compound</th>
                      <th className="px-3 py-2 text-right font-semibold">Observations</th>
                      <th className="px-3 py-2 text-left font-semibold">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                    <tr><td className="px-3 py-2">PFOS</td><td className="px-3 py-2 text-right">23,086</td><td className="px-3 py-2">legacy &mdash; restricted</td></tr>
                    <tr><td className="px-3 py-2">PFHxS</td><td className="px-3 py-2 text-right">22,132</td><td className="px-3 py-2">legacy</td></tr>
                    <tr><td className="px-3 py-2">PFBA</td><td className="px-3 py-2 text-right">21,470</td><td className="px-3 py-2">legacy</td></tr>
                    <tr><td className="px-3 py-2">PFOA</td><td className="px-3 py-2 text-right">20,399</td><td className="px-3 py-2">legacy &mdash; restricted</td></tr>
                    <tr className="bg-slate-50 dark:bg-slate-800/50"><td className="px-3 py-2 font-medium">PFPE-diacid</td><td className="px-3 py-2 text-right">17,694</td><td className="px-3 py-2">emerging &mdash; in current use</td></tr>
                    <tr className="bg-slate-50 dark:bg-slate-800/50"><td className="px-3 py-2 font-medium">GenX (HFPO-DA)</td><td className="px-3 py-2 text-right">16,954</td><td className="px-3 py-2">replacement &mdash; in current use</td></tr>
                    <tr className="bg-slate-50 dark:bg-slate-800/50"><td className="px-3 py-2 font-medium">ADONA</td><td className="px-3 py-2 text-right">15,804</td><td className="px-3 py-2">replacement &mdash; in current use</td></tr>
                  </tbody>
                </table>
              </div>
              <p>
                GenX appears at <strong>73%</strong> the frequency of PFOS, ADONA at{" "}
                <strong>68%</strong>. Exposed populations encounter complex PFAS mixtures, not
                individual chemicals.
              </p>
            </div>

            <div className="space-y-2">
              <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                The replacement is more potent at the same target
              </h3>
              <p>
                The strongest mechanistic finding draws from PubMed literature and NDE
                transcriptomic datasets together:
              </p>
              <ul className="list-disc space-y-2 pl-6">
                <li>
                  <strong>16-PFAS comparison (Evans et al., EPA 2022).</strong> In PPAR&alpha;
                  receptor-binding assays across 16 PFAS, GenX was the <strong>most potent
                  PPAR&alpha; activator</strong> &mdash; lowest effective concentration, highest
                  fold induction, highest area under the curve.
                </li>
                <li>
                  <strong>PPAR&alpha; knockout proof (NDE GSE212294).</strong> In PPAR&alpha;-KO
                  mice, GenX&apos;s hepatic effects disappear completely; PFOA retains some
                  effects through alternative receptors. GenX is a <em>purer</em> PPAR&alpha;
                  activator than the legacy compound it replaced.
                </li>
                <li>
                  <strong>Transcriptomic concordance (Heintz et al. 2024; NDE GSE248251).</strong>{" "}
                  GenX&apos;s transcriptomic profile most closely matches the prototypical
                  PPAR&alpha; agonist drug GW7647 across mouse, rat, and human hepatocytes
                  &mdash; not a general toxicant signature.
                </li>
                <li>
                  <strong>Effects at drinking-water concentrations (Shi et al. 2023).</strong>{" "}
                  GenX disrupts hepatic lipid metabolism via PPAR&alpha; signaling at 0.1 and 10
                  &micro;g/L &mdash; concentrations already documented in SAWGraph.
                </li>
                <li>
                  <strong>The pattern repeats (Jackson et al. 2024).</strong> Next-generation
                  perfluoroether acids PFO4DA and PFO5DoA also activate PPAR&alpha;. The
                  substitution cycle continues.
                </li>
              </ul>
              <p>
                NDE returned <strong>11 GenX-specific transcriptomic studies</strong> spanning
                mouse, rat, human hepatocytes, marsupial blood, Drosophila brain, and zebrafish
                embryos &mdash; consistent PPAR&alpha; signaling and lipid-metabolism enrichment
                across systems.
              </p>
            </div>

            <div className="space-y-2">
              <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                AOPs and pathway enrichment confirm the mechanism
              </h3>
              <p>
                AOP-Wiki encodes <strong>40 liver-related adverse outcome pathways</strong>;
                three are directly PFAS-relevant:
              </p>
              <ul className="list-disc space-y-1 pl-6">
                <li>
                  <strong>AOP 166</strong> &mdash; PPAR&alpha; activation &rarr; hepatocellular
                  adenomas/carcinomas
                </li>
                <li>
                  <strong>AOP 220</strong> &mdash; CYP2E1 activation &rarr; liver cancer via
                  oxidative stress
                </li>
                <li>
                  <strong>AOP 213</strong> &mdash; inhibition of &beta;-oxidation &rarr;
                  non-alcoholic steatohepatitis (NASH)
                </li>
              </ul>
              <p>
                g:Profiler enrichment of the 10 most-implicated PFAS genes (PPARA, CYP2E1,
                ACOX1, FABP1, SREBF1, NR1I2, CYP1A1, CYP3A4, NR1H4, ABCB11) returned{" "}
                <strong>168 significantly enriched terms</strong>, converging sharply on lipid
                metabolism and PPAR signaling:
              </p>
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 dark:border-slate-700">
                      <th className="px-3 py-2 text-left font-semibold">Pathway (source)</th>
                      <th className="px-3 py-2 text-left font-semibold">p-value</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                    <tr><td className="px-3 py-2">Metabolism of lipids (Reactome)</td><td className="px-3 py-2">1.0e-13</td></tr>
                    <tr><td className="px-3 py-2">PPAR&alpha; activates gene expression (Reactome)</td><td className="px-3 py-2">6.9e-12</td></tr>
                    <tr><td className="px-3 py-2">PPAR signaling pathway (KEGG)</td><td className="px-3 py-2">3.5e-9</td></tr>
                    <tr><td className="px-3 py-2">Alcoholic liver disease (KEGG)</td><td className="px-3 py-2">3.3e-7</td></tr>
                    <tr><td className="px-3 py-2">Chemical carcinogenesis &mdash; DNA adducts (KEGG)</td><td className="px-3 py-2">9.3e-6</td></tr>
                    <tr><td className="px-3 py-2">Non-alcoholic fatty liver disease (KEGG)</td><td className="px-3 py-2">2.4e-3</td></tr>
                    <tr><td className="px-3 py-2">Fatty acid metabolic process (GO:BP)</td><td className="px-3 py-2">1.2e-15</td></tr>
                  </tbody>
                </table>
              </div>
              <p>
                The 10 PFAS target genes form a coherent functional module. Any chemical that
                activates PPAR&alpha; &mdash; legacy or replacement &mdash; enters this same
                molecular network.
              </p>
            </div>

            <div className="space-y-2">
              <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                Two genes, two mechanisms, converging on the same diseases
              </h3>
              <p>
                SPOKE-OKN gene-disease associations for the two key PFAS targets:
              </p>
              <ul className="list-disc space-y-1 pl-6">
                <li>
                  <strong>PPARA</strong> &rarr; liver disease (direct), kidney cancer,
                  hypertension, diabetes mellitus, obesity
                </li>
                <li>
                  <strong>CYP2E1</strong> &rarr; liver cancer (direct DE), mitochondrial
                  disease, steroid metabolism disease, kidney cancer (8 independent paths via
                  shared mitochondrial pathways)
                </li>
              </ul>
              <p>
                PPAR&alpha; (lipid metabolism) and CYP2E1 (oxidative stress) converge on
                <strong> liver cancer</strong> and <strong>kidney cancer</strong> through
                distinct mechanistic routes confirmed in separate knowledge graphs &mdash;
                exactly the kind of independent-paths convergence that supports causal
                inference.
              </p>
            </div>

            <div className="space-y-2">
              <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                Cross-species datasets validate the picture
              </h3>
              <p>
                A broader NDE query returned <strong>20+ PFAS transcriptomic datasets</strong>{" "}
                spanning carp, zebrafish, mouse, rat, and human models &mdash; including the
                PFOA-induced NAFLD mouse model, PFAS human liver spheroids (TempO-Seq), and the
                GenX hepatic effects dataset that experimentally confirms a replacement PFAS
                produces the same liver-tissue transcriptomic signature as legacy compounds.
              </p>
              <p>
                Wikidata independently annotates PPARA with cholesterol homeostasis, lipid
                response, and fatty-acid metabolic process. SPOKE-GeneLab shows PPARA
                differential expression across 10 NASA spaceflight assays, confirming it as a
                bona fide stress-responsive gene rather than an artifact of PFAS-specific
                experimental design.
              </p>
            </div>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              Synthesis: convergence across independent lines
            </h2>
            <p>
              The case against compound-by-compound regulation rests on independent lines of
              evidence pointing at the same conclusion:
            </p>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 dark:border-slate-700">
                    <th className="px-3 py-2 text-left font-semibold">Evidence</th>
                    <th className="px-3 py-2 text-left font-semibold">Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                  <tr><td className="px-3 py-2">GenX at 73% the detection frequency of PFOS</td><td className="px-3 py-2">SAWGraph</td></tr>
                  <tr><td className="px-3 py-2">GenX is the most potent PPAR&alpha; activator of 16 PFAS tested</td><td className="px-3 py-2">PubMed (Evans et al.)</td></tr>
                  <tr><td className="px-3 py-2">GenX effects entirely PPAR&alpha;-dependent</td><td className="px-3 py-2">NDE (GSE212294)</td></tr>
                  <tr><td className="px-3 py-2">GenX profile matches PPAR&alpha; agonist across 3 species</td><td className="px-3 py-2">PubMed + NDE</td></tr>
                  <tr><td className="px-3 py-2">GenX disrupts lipid metabolism at drinking-water concentrations</td><td className="px-3 py-2">PubMed (Shi et al.)</td></tr>
                  <tr><td className="px-3 py-2">PPAR&alpha; activation &rarr; liver tumors</td><td className="px-3 py-2">AOP-Wiki</td></tr>
                  <tr><td className="px-3 py-2">10 PFAS genes enriched for PPAR signaling (p=3.5e-9)</td><td className="px-3 py-2">g:Profiler</td></tr>
                  <tr><td className="px-3 py-2">PPARA and CYP2E1 both link to liver and kidney cancer</td><td className="px-3 py-2">SPOKE-OKN, Ubergraph</td></tr>
                  <tr><td className="px-3 py-2">20+ PFAS datasets spanning fish to human hepatocytes</td><td className="px-3 py-2">NDE</td></tr>
                  <tr><td className="px-3 py-2">PPAR&alpha; annotated for lipid/cholesterol metabolism</td><td className="px-3 py-2">Wikidata</td></tr>
                  <tr><td className="px-3 py-2">Next-gen replacements (PFO4DA, PFO5DoA) also activate PPAR&alpha;</td><td className="px-3 py-2">PubMed (Jackson et al.)</td></tr>
                </tbody>
              </table>
            </div>
            <p>
              No single database holds this picture. SAWGraph knows contamination but not
              biology; PubMed has the potency comparison but not the prevalence; NDE provides
              transcriptomic proof but not disease outcomes; AOP-Wiki maps the pathway but not
              which chemicals trigger it; SPOKE-OKN knows disease associations but not exposure.
              Only by querying across the federation can the full argument come together.
            </p>
          </section>

          <section className="space-y-3 border-t border-slate-200 pt-6 dark:border-slate-700">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              Bottom line
            </h2>
            <p>
              The federated answer supports class-based regulation of PFAS rather than
              compound-by-compound substitution: the replacement is more potent at the same
              molecular target, effects occur at existing environmental concentrations, the
              next generation already repeats the pattern, and biomarker candidates from the
              PPAR&alpha; gene network would detect harm from any PPAR&alpha;-activating PFAS.
              Each of those claims rests on a different graph, but the conclusion is the
              convergence.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
