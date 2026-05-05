import type { Metadata } from "next";
import { getVignetteMeta } from "@/lib/landing/vignette-meta";
import { Breadcrumbs } from "@/components/layout/Breadcrumbs";

const SLUG = "diabetic-nephropathy";

export const metadata: Metadata = {
  title: "Diabetic nephropathy: full analysis",
  description:
    "Full vignette: sample discovery, pooled and study-matched DE results, enrichment analysis, and the methodology comparison that surfaced interferon signaling.",
};

export default function DiabeticNephropathyDetailsPage() {
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
            { label: meta.title, href: "/mcp/diabetic-nephropathy" },
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
            End-to-end differential expression from a single question
          </h1>
          <p className="mx-auto mt-5 w-[90%] max-w-full text-left text-base leading-relaxed text-slate-600 [text-wrap:pretty] dark:text-slate-400">
            A walk-through of how the unified MCP server runs a complete differential
            expression analysis of diabetic nephropathy in ARCHS4 from one chat &mdash;
            including running both pooled and study-matched meta-analysis modes so the user can
            see what each method reveals.
          </p>
        </div>

        <div className="w-full max-w-3xl space-y-10 text-slate-700 dark:text-slate-300">
          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              The scenario
            </h2>
            <blockquote className="border-l-4 border-slate-300 pl-4 italic text-slate-600 dark:border-slate-600 dark:text-slate-400">
              Run a pooled differential expression analysis of diabetic nephropathy using
              ARCHS4. Then try the study-matched meta-analysis. Tell me your steps as you go
              and finish with a report on the results.
            </blockquote>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              How the assistant approached it
            </h2>
            <p>
              The MCP server orchestrated four tools in sequence:
            </p>
            <ol className="list-decimal space-y-2 pl-6">
              <li>
                <strong>Disease ontology resolution.</strong>{" "}
                <code className="rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">
                  resolve_disease_ontology
                </code>{" "}
                mapped &ldquo;diabetic nephropathy&rdquo; to{" "}
                <strong>MONDO:0005016</strong> (diabetic kidney disease) with exact confidence,
                no subtype expansion.
              </li>
              <li>
                <strong>Sample discovery.</strong>{" "}
                <code className="rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">
                  find_samples
                </code>{" "}
                queried ARCHS4 metadata with ontology-enhanced search and applied LLM-generated
                regex patterns (diabetic nephropathy, DKD, DN, diabetic glomerulopathy, STZ
                kidney, db/db kidney) filtered to kidney/renal/glomerular/tubular/podocyte
                tissue. Per-study LLM classification labeled each sample as test or control.
              </li>
              <li>
                <strong>Differential expression.</strong>{" "}
                <code className="rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">
                  differential_expression
                </code>{" "}
                ran first in <em>pooled</em> mode (Mann-Whitney U with Benjamini-Hochberg FDR),
                then in <em>study-matched</em> mode (per-study DE combined via Stouffer&apos;s
                weighted Z), with FDR &lt; 0.01 and |log2FC| &gt; 2.0.
              </li>
              <li>
                <strong>Enrichment.</strong>{" "}
                <code className="rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">
                  enrichment_analysis
                </code>{" "}
                ran g:Profiler over GO, KEGG, and Reactome on the pooled DE gene set.
              </li>
            </ol>
          </section>

          <section className="space-y-4">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              Findings
            </h2>

            <div className="space-y-2">
              <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                Sample discovery
              </h3>
              <ul className="list-disc space-y-1 pl-6">
                <li>
                  <strong>174</strong> DN test samples across <strong>13 ARCHS4 studies</strong>
                </li>
                <li>
                  <strong>555</strong> kidney control samples across <strong>161 studies</strong>
                </li>
                <li>
                  <strong>9 studies</strong> contributed both test and control samples
                </li>
              </ul>
              <p>
                Top contributing studies (test / control samples):
              </p>
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 dark:border-slate-700">
                      <th className="px-3 py-2 text-left font-semibold">Study</th>
                      <th className="px-3 py-2 text-right font-semibold">Test</th>
                      <th className="px-3 py-2 text-right font-semibold">Control</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                    <tr><td className="px-3 py-2">GSE175759</td><td className="px-3 py-2 text-right">62</td><td className="px-3 py-2 text-right">19</td></tr>
                    <tr><td className="px-3 py-2">GSE142025</td><td className="px-3 py-2 text-right">35</td><td className="px-3 py-2 text-right">0</td></tr>
                    <tr><td className="px-3 py-2">GSE162830</td><td className="px-3 py-2 text-right">22</td><td className="px-3 py-2 text-right">8</td></tr>
                    <tr><td className="px-3 py-2">GSE185011</td><td className="px-3 py-2 text-right">20</td><td className="px-3 py-2 text-right">5</td></tr>
                    <tr><td className="px-3 py-2">GSE204880</td><td className="px-3 py-2 text-right">6</td><td className="px-3 py-2 text-right">5</td></tr>
                    <tr><td className="px-3 py-2">GSE199437</td><td className="px-3 py-2 text-right">6</td><td className="px-3 py-2 text-right">3</td></tr>
                  </tbody>
                </table>
              </div>
              <p>
                The system flagged study-matched mode as the recommended methodology but
                executed pooled first as requested, then ran study-matched for comparison.
              </p>
            </div>

            <div className="space-y-2">
              <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                Pooled differential expression
              </h3>
              <p>
                100 test samples (10 studies) vs. 53 control samples (8 studies), 19,282 genes
                tested. <strong>Five genes significant, all downregulated:</strong>
              </p>
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 dark:border-slate-700">
                      <th className="px-3 py-2 text-left font-semibold">Gene</th>
                      <th className="px-3 py-2 text-right font-semibold">log2FC</th>
                      <th className="px-3 py-2 text-right font-semibold">Adj. p</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                    <tr><td className="px-3 py-2 font-medium">DUSP1</td><td className="px-3 py-2 text-right">&minus;2.78</td><td className="px-3 py-2 text-right">2.5e-10</td></tr>
                    <tr><td className="px-3 py-2 font-medium">FOS</td><td className="px-3 py-2 text-right">&minus;3.39</td><td className="px-3 py-2 text-right">1.9e-7</td></tr>
                    <tr><td className="px-3 py-2 font-medium">FOSB</td><td className="px-3 py-2 text-right">&minus;2.66</td><td className="px-3 py-2 text-right">1.8e-7</td></tr>
                    <tr><td className="px-3 py-2 font-medium">NR4A1</td><td className="px-3 py-2 text-right">&minus;2.61</td><td className="px-3 py-2 text-right">5.0e-7</td></tr>
                    <tr><td className="px-3 py-2 font-medium">EGR1</td><td className="px-3 py-2 text-right">&minus;2.35</td><td className="px-3 py-2 text-right">2.4e-6</td></tr>
                  </tbody>
                </table>
              </div>
              <p>
                All five are immediate-early response transcription factors. The coordinated
                downregulation suggests suppression of immediate-early transcriptional
                responses in DN kidney &mdash; loss of adaptive stress signaling and MAPK/AP-1
                deregulation.
              </p>
            </div>

            <div className="space-y-2">
              <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                Enrichment (pooled DE genes)
              </h3>
              <ul className="list-disc space-y-1 pl-6">
                <li>
                  <strong>Reactome:</strong> NGF-stimulated transcription (p = 7.5e-5); nuclear
                  events: kinase and TF activation (p = 3.0e-4); NTRK1/TRKA signaling (p = 2.0e-3)
                </li>
                <li>
                  <strong>GO Molecular Function:</strong> DNA-binding transcription activator
                  activity, RNA Pol II-specific (p = 3.1e-4)
                </li>
                <li>
                  <strong>GO Biological Process:</strong> cellular response to chemical stimulus
                  (p = 0.010); response to hormone (p = 0.013)
                </li>
                <li>
                  <strong>KEGG:</strong> MAPK signaling pathway (p = 0.021)
                </li>
              </ul>
            </div>

            <div className="space-y-2">
              <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                Study-matched meta-analysis
              </h3>
              <p>
                Only three studies had both test and control samples meeting the minimum
                threshold (GSE175759, GSE199437, GSE204880; 71 test / 27 control; 15,943 genes
                tested in the intersection). <strong>Seven genes significant &mdash; five down,
                two up:</strong>
              </p>
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 dark:border-slate-700">
                      <th className="px-3 py-2 text-left font-semibold">Gene</th>
                      <th className="px-3 py-2 text-right font-semibold">log2FC</th>
                      <th className="px-3 py-2 text-right font-semibold">Adj. p</th>
                      <th className="px-3 py-2 text-left font-semibold">Direction</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                    <tr><td className="px-3 py-2 font-medium">FOSB</td><td className="px-3 py-2 text-right">&minus;2.73</td><td className="px-3 py-2 text-right">4.7e-8</td><td className="px-3 py-2">down</td></tr>
                    <tr><td className="px-3 py-2 font-medium">EGR1</td><td className="px-3 py-2 text-right">&minus;2.47</td><td className="px-3 py-2 text-right">4.5e-8</td><td className="px-3 py-2">down</td></tr>
                    <tr><td className="px-3 py-2 font-medium">FOS</td><td className="px-3 py-2 text-right">&minus;3.24</td><td className="px-3 py-2 text-right">9.1e-6</td><td className="px-3 py-2">down</td></tr>
                    <tr><td className="px-3 py-2 font-medium">DUSP1</td><td className="px-3 py-2 text-right">&minus;2.16</td><td className="px-3 py-2 text-right">5.0e-6</td><td className="px-3 py-2">down</td></tr>
                    <tr><td className="px-3 py-2 font-medium">NR4A1</td><td className="px-3 py-2 text-right">&minus;2.33</td><td className="px-3 py-2 text-right">8.0e-6</td><td className="px-3 py-2">down</td></tr>
                    <tr className="bg-slate-50 dark:bg-slate-800/50"><td className="px-3 py-2 font-medium">OAS2</td><td className="px-3 py-2 text-right">+2.29</td><td className="px-3 py-2 text-right">0.002</td><td className="px-3 py-2 font-medium">up</td></tr>
                    <tr className="bg-slate-50 dark:bg-slate-800/50"><td className="px-3 py-2 font-medium">RSAD2</td><td className="px-3 py-2 text-right">+2.09</td><td className="px-3 py-2 text-right">0.005</td><td className="px-3 py-2 font-medium">up</td></tr>
                  </tbody>
                </table>
              </div>
              <p>
                The two upregulated hits are interferon-stimulated genes: <strong>OAS2</strong>{" "}
                (2&prime;-5&prime;-oligoadenylate synthetase 2) and <strong>RSAD2</strong>{" "}
                (Viperin), both canonical antiviral / type I interferon response genes &mdash;
                a signal completely missed by the pooled analysis.
              </p>
            </div>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              Pooled vs. study-matched
            </h2>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 dark:border-slate-700">
                    <th className="px-3 py-2 text-left font-semibold">Feature</th>
                    <th className="px-3 py-2 text-left font-semibold">Pooled</th>
                    <th className="px-3 py-2 text-left font-semibold">Study-matched</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                  <tr><td className="px-3 py-2">Test samples</td><td className="px-3 py-2">100 (10 studies)</td><td className="px-3 py-2">71 (3 studies)</td></tr>
                  <tr><td className="px-3 py-2">Control samples</td><td className="px-3 py-2">53 (8 studies)</td><td className="px-3 py-2">27 (3 studies)</td></tr>
                  <tr><td className="px-3 py-2">Genes tested</td><td className="px-3 py-2">19,282</td><td className="px-3 py-2">15,943</td></tr>
                  <tr><td className="px-3 py-2">Significant genes</td><td className="px-3 py-2">5</td><td className="px-3 py-2 font-medium">7</td></tr>
                  <tr><td className="px-3 py-2">All downregulated?</td><td className="px-3 py-2">yes (5/5)</td><td className="px-3 py-2 font-medium">no &mdash; 2 upregulated</td></tr>
                </tbody>
              </table>
            </div>
            <p>
              Both methods recover the same five immediate-early genes with consistent effect
              sizes. Study-matched additionally surfaces OAS2 and RSAD2 by controlling for
              batch effects within each study before combining via Stouffer&apos;s weighted Z
              &mdash; a signal obscured when samples are pooled across 10 platforms.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              Biological interpretation
            </h2>
            <p>
              The combined picture suggests two coordinated processes in DN kidney:
            </p>
            <ol className="list-decimal space-y-2 pl-6">
              <li>
                <strong>Suppression of the immediate-early transcriptional response</strong>{" "}
                (FOS, FOSB, EGR1, NR4A1, DUSP1) &mdash; loss of adaptive stress signaling and
                MAPK pathway dampening.
              </li>
              <li>
                <strong>Activation of innate immune / interferon signaling</strong> (OAS2,
                RSAD2) &mdash; consistent with established inflammatory mechanisms in DN
                progression.
              </li>
            </ol>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              Caveats
            </h2>
            <ul className="list-disc space-y-1 pl-6">
              <li>
                Stringent thresholds (FDR &lt; 0.01, |log2FC| &gt; 2.0) yield small gene lists.
              </li>
              <li>
                Pooled mode mixes samples across 10 platforms, introducing potential batch
                effects.
              </li>
              <li>
                Only three studies met the matched-controls minimum for study-matched mode;
                GSE175759 dominates (62/71 test, 21/27 control).
              </li>
              <li>
                Immediate-early genes (FOS, EGR1) are sensitive to tissue processing delays
                &mdash; care is needed in interpreting their downregulation as DN-specific.
              </li>
              <li>
                Enrichment analysis returned empty for the study-matched gene set (too few
                genes split across directions).
              </li>
            </ul>
          </section>

          <section className="space-y-3 border-t border-slate-200 pt-6 dark:border-slate-700">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              Bottom line
            </h2>
            <p>
              The MCP server resolved a disease term, classified hundreds of ARCHS4 samples,
              ran two complementary DE methods, and produced a coherent biological
              interpretation &mdash; in one chat. The pooled-vs-matched comparison illustrates
              the broader value: the right method choice is rarely obvious in advance, and an
              orchestrated pipeline that runs both lets the user see the methodology trade-off
              instead of guessing at it.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
