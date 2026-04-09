export default function AboutPage() {
  return (
    <div
      className="px-4 py-6 sm:py-8"
      style={{ backgroundColor: "var(--niaid-page-bg)" }}
    >
      <div className="mx-auto max-w-3xl space-y-8 text-slate-700">
        <header>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            About the Web of Biological Data
          </h1>
          <p className="mt-3 text-slate-600 dark:text-slate-400">
            This is a prototype Web of Biological Data (WOBD), a
            research effort to make infectious and immune-related datasets and knowledge easier
            to find, query, reuse, and connect with other data sources in an AI-ready open
            knowledge network.
          </p>
          <p className="mt-3 text-slate-600 dark:text-slate-400">
            This work is supported by the U.S. National Science Foundation under award{" "}
            <a
              className="text-blue-700 underline decoration-blue-700/30 underline-offset-2 hover:decoration-blue-700"
              href="https://www.nsf.gov/awardsearch/show-award/?AWD_ID=2535091"
              rel="noopener noreferrer"
              target="_blank"
            >
              2535091
            </a>
            .
          </p>
        </header>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            Relationship to Proto-OKN
          </h2>
          <p>
            The WOBD work extends ideas from the NSF{" "}
            <a
              className="text-blue-700 underline decoration-blue-700/30 underline-offset-2 hover:decoration-blue-700"
              href="https://www.proto-okn.net/"
              rel="noopener noreferrer"
              target="_blank"
            >
              Proto-OKN
            </a>{" "}
            program: a publicly accessible, interconnected set of knowledge graphs and data
            services aimed at trustworthy, data-driven discovery. WOBD is conceived as a focused
            path within that broader fabric, connecting harmonized biomedical dataset metadata
            from the{" "}
            <a
              className="text-blue-700 underline decoration-blue-700/30 underline-offset-2 hover:decoration-blue-700"
              href="https://data.niaid.nih.gov/"
              rel="noopener noreferrer"
              target="_blank"
            >
              NIAID Data Ecosystem Portal
            </a>{" "}
            with gene expression data from the{" "}
            <a
              className="text-blue-700 underline decoration-blue-700/30 underline-offset-2 hover:decoration-blue-700"
              href="https://www.ebi.ac.uk/gxa/home"
              rel="noopener noreferrer"
              target="_blank"
            >
              Gene Expression Atlas
            </a>
            ,{" "}
            <a
              className="text-blue-700 underline decoration-blue-700/30 underline-offset-2 hover:decoration-blue-700"
              href="https://www.wikidata.org/wiki/Wikidata:Main_Page"
              rel="noopener noreferrer"
              target="_blank"
            >
              Wikidata
            </a>
            , and other knowledge graphs so researchers can move from questions to datasets and
            related biological context in fewer steps.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            Dataset metadata: the NIAID Data Ecosystem (NDE)
          </h2>
          <p>
            The primary structured metadata behind many graphs in this project comes from the{" "}
            <a
              className="text-blue-700 underline decoration-blue-700/30 underline-offset-2 hover:decoration-blue-700"
              href="https://data.niaid.nih.gov"
              rel="noopener noreferrer"
              target="_blank"
            >
              NIAID Data Ecosystem Discovery Portal
            </a>{" "}
            (NDE). The NDE aggregates and harmonizes dataset records from domain-specific and
            generalist repositories, clinical, epidemiological, multi-omic, and more into a
            unified search index with a Schema.org–aligned schema, filters for host, pathogen,
            condition, and technique, and an API for programmatic access. Records point back to
            their source repositories rather than replacing them; the value is consistent discovery
            across sources.
          </p>
          <p>
            For a full description of the portal&apos;s design and scope, see the resource report:{" "}
            <a
              className="text-blue-700 underline decoration-blue-700/30 underline-offset-2 hover:decoration-blue-700"
              href="https://arxiv.org/abs/2509.13524"
              rel="noopener noreferrer"
              target="_blank"
            >
              The NIAID Discovery Portal: A Unified Search Engine for Infectious and
              Immune-Mediated Disease Datasets
            </a>{" "}
            (arXiv:2509.13524). Metadata harvested from the NDE pipeline is published as the NDE
            graph and loaded alongside other graphs in the federation used by this application.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            Gene Expression Atlas (GXA) data
          </h2>
          <p>
            Data for the GXA graph is built from experiments in the{" "}
            <a
              className="text-blue-700 underline decoration-blue-700/30 underline-offset-2 hover:decoration-blue-700"
              href="https://www.ebi.ac.uk/gxa/home"
              rel="noopener noreferrer"
              target="_blank"
            >
              EMBL-EBI Gene Expression Atlas (GXA)
            </a>
            , public differential-expression and functional studies. Experiment packages are
            retrieved from the Atlas infrastructure, parsed, and emitted as Biolink-compatible
            linked data (study metadata, contrasts, genes, and pathway enrichment) so users can
            run queries that span NDE dataset metadata, GXA expression results, and other
            knowledge graphs in the federation, combining and interpreting those results in one
            workflow.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            FRINK registry and how things connect
          </h2>
          <p>
            Knowledge graphs are listed in the{" "}
            <a
              className="text-blue-700 underline decoration-blue-700/30 underline-offset-2 hover:decoration-blue-700"
              href="https://frink.renci.org/registry/"
              rel="noopener noreferrer"
              target="_blank"
            >
              FRINK registry
            </a>
            , each with a short name, title, description, and a link to its query endpoint. The{" "}
            <a
              className="text-blue-700 underline decoration-blue-700/30 underline-offset-2 hover:decoration-blue-700"
              href="https://frink.apps.renci.org/"
              rel="noopener noreferrer"
              target="_blank"
            >
              FRINK SPARQL federation
            </a>{" "}
            exposes those graphs so they can be queried, individually or in combination, depending
            on setup. The NDE graph is published in that ecosystem; the GXA graph is published
            similarly. At a high level, WOBD links NDE metadata (what datasets exist, how
            they are annotated, and where to get them) to the same query plane as curated
            biological knowledge (genes, diseases, drugs, pathways, expression contrasts) already
            present in FRINK, so templated SPARQL queries can span dataset discovery and mechanistic
            context without siloed portals.
          </p>
        </section>

        <section className="space-y-3 border-t border-slate-200 pt-6 dark:border-slate-700">
          <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            This application
          </h2>
          <p>
            This site offers a template-based front end to that federated layer: each workflow is
            a predefined, validated SPARQL query pattern you can run with your own search terms or
            parameters. You choose a template, the app fills in the corresponding SPARQL and executes
            it against the registered graph endpoints so you can explore the NDE dataset layer and
            related biological knowledge in FRINK without writing queries by hand.
          </p>
        </section>

        <section className="space-y-3 border-t border-slate-200 pt-6 dark:border-slate-700">
          <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Team</h2>
          <ul className="list-disc space-y-1 pl-5 text-slate-700 dark:text-slate-300">
            <li>Trish Whetzel</li>
            <li>Ben Good</li>
            <li>Andrew Su</li>
            <li>Chris Bizon</li>
            <li>Ginger Tsueng</li>
            <li>Jim Balhoff</li>
            <li>Yaphet Kebede</li>
          </ul>
        </section>
      </div>
    </div>
  );
}
