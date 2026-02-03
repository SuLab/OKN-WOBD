#!/usr/bin/env python3
"""
Q1: What diseases is a gene connected to, and through what mechanisms?

Data Sources: SPOKE-OKN, Wikidata, Ubergraph
Primary Tools: GeneDiseasePathFinder, PlotlyVisualizer

Finds gene-disease connections via direct markers, genetic associations,
GO pathway links, and shared pathway intermediates across three knowledge graphs.

Usage:
    python -m questions.gene_disease_map
    python -m questions.gene_disease_map --gene TP53
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

QUESTION = "What diseases is {gene} connected to, and through what mechanisms?"
GENE = "SFRP2"


def run(gene: str = GENE, output_dir: str = "questions/output"):
    """Run the investigation and produce an HTML report."""
    from analysis_tools import GeneDiseasePathFinder, PlotlyVisualizer
    from questions._report import QuestionReport, results_table, summary_stats

    question = QUESTION.format(gene=gene)
    report = QuestionReport(
        question=question,
        sources=["SPOKE-OKN", "Wikidata", "Ubergraph"],
        module_name="gene_disease_map",
    )

    # --- Step 1: Find all connections ---
    print(f"Finding disease connections for {gene}...")
    finder = GeneDiseasePathFinder(verbose=False)
    connections = finder.find_all_connections(gene)
    conn_dicts = [c.to_dict() for c in connections]

    # Group by source
    by_source = defaultdict(list)
    for c in connections:
        by_source[c.source].append(c)

    source_rows = [
        {"Source": src, "Connections": str(len(conns)),
         "Path Types": ", ".join(sorted(set(c.path_type for c in conns)))}
        for src, conns in by_source.items()
    ]
    report.add_step(
        "Query knowledge graphs for gene-disease connections",
        summary_stats("Total connections", len(connections))
        + summary_stats("Unique diseases", len(set(c.disease_name for c in connections)))
        + results_table(source_rows),
        data={"n_connections": len(connections)},
    )

    # --- Step 2: Summarize by path type ---
    by_type = defaultdict(list)
    for c in connections:
        by_type[c.path_type].append(c)

    type_rows = []
    for ptype, conns in sorted(by_type.items(), key=lambda x: -len(x[1])):
        sample = ", ".join(sorted(set(c.disease_name for c in conns))[:5])
        type_rows.append({
            "Mechanism": ptype.replace("_", " ").title(),
            "Count": str(len(conns)),
            "Sample Diseases": sample,
        })

    report.add_step(
        "Categorize connection mechanisms",
        results_table(type_rows),
    )

    # --- Step 3: Top diseases ---
    disease_counts = defaultdict(lambda: {"sources": set(), "types": set()})
    for c in connections:
        disease_counts[c.disease_name]["sources"].add(c.source)
        disease_counts[c.disease_name]["types"].add(c.path_type)

    top_diseases = sorted(disease_counts.items(), key=lambda x: -len(x[1]["sources"]))[:15]
    disease_rows = [
        {"Disease": name, "Sources": ", ".join(sorted(info["sources"])),
         "Mechanisms": ", ".join(sorted(info["types"]))}
        for name, info in top_diseases
    ]
    report.add_step(
        "Rank diseases by evidence breadth",
        results_table(disease_rows),
    )

    # --- Visualization: Network ---
    if connections:
        viz = PlotlyVisualizer()
        network_html = viz.gene_disease_network(
            conn_dicts,
            title=f"{gene} Disease Connections",
            gene_symbol=gene,
        )
        report.add_visualization(f"{gene} Disease Network", network_html)

    # --- Answer ---
    n_diseases = len(set(c.disease_name for c in connections))
    n_mechanisms = len(by_type)
    sources_used = sorted(by_source.keys())
    report.set_answer(
        f"{gene} is connected to {n_diseases} diseases through {n_mechanisms} "
        f"distinct mechanisms across {len(sources_used)} knowledge graphs "
        f"({', '.join(sources_used)}).\n\n"
        f"The connection types include: {', '.join(sorted(by_type.keys()))}."
    )

    # Provenance
    report.add_provenance("endpoints", {
        "SPOKE-OKN": "https://frink.apps.renci.org/spoke-okn/sparql",
        "Wikidata": "https://query.wikidata.org/sparql",
        "Ubergraph": "https://ubergraph.apps.renci.org/sparql",
    })
    report.add_provenance("gene_symbol", gene)

    # SPARQL queries used
    report.add_query(
        "SPOKE: Direct gene-disease associations",
        f'''PREFIX biolink: <https://w3id.org/biolink/vocab/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX spoke: <https://purl.org/okn/frink/kg/spoke/schema/>

SELECT ?gene ?predicate ?disease
WHERE {{
    ?gene a biolink:Gene ;
          rdfs:label "{gene}" .
    VALUES ?predicate {{
        spoke:MARKER_POS_GmpD
        spoke:MARKER_NEG_GmnD
        spoke:EXPRESSEDIN_GeiD
    }}
    ?gene ?predicate ?disease .
}}''',
        "https://frink.apps.renci.org/spoke-okn/sparql",
    )
    report.add_query(
        "Wikidata: Gene-disease associations",
        f'''PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?disease ?diseaseLabel ?doid ?mondo
WHERE {{
    ?gene wdt:P353 "{gene}" ;
          wdt:P703 wd:Q15978631 .
    ?gene wdt:P2293 ?disease .
    ?disease rdfs:label ?diseaseLabel .
    FILTER(LANG(?diseaseLabel) = "en")
    OPTIONAL {{ ?disease wdt:P699 ?doid . }}
    OPTIONAL {{ ?disease wdt:P5270 ?mondo . }}
}}''',
        "https://query.wikidata.org/sparql",
    )
    report.add_query(
        "Wikidata: Gene GO terms (via protein)",
        f'''PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?goId ?goLabel
WHERE {{
    ?gene wdt:P353 "{gene}" ;
          wdt:P703 wd:Q15978631 ;
          wdt:P688 ?protein .
    ?protein wdt:P680|wdt:P681|wdt:P682 ?goTerm .
    ?goTerm wdt:P686 ?goId .
    ?goTerm rdfs:label ?goLabel .
    FILTER(LANG(?goLabel) = "en")
}}''',
        "https://query.wikidata.org/sparql",
    )
    report.add_query(
        "Ubergraph: GO term to disease (per GO term)",
        '''PREFIX obo: <http://purl.obolibrary.org/obo/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

SELECT DISTINCT ?disease ?diseaseLabel
WHERE {
    BIND(obo:<GO_ID> AS ?goTerm)
    {
        ?disease rdfs:subClassOf* obo:MONDO_0000001 .
        ?disease rdfs:subClassOf ?restriction .
        ?restriction owl:onProperty ?prop ;
                     owl:someValuesFrom ?goTerm .
    }
    UNION
    {
        ?disease rdfs:subClassOf* obo:MONDO_0000001 .
        ?disease obo:RO_0004027 ?goTerm .
    }
    ?disease rdfs:label ?diseaseLabel .
}
LIMIT 20''',
        "https://ubergraph.apps.renci.org/sparql",
    )

    filepath = str(Path(output_dir) / "gene_disease_map.html")
    saved = report.save(filepath)
    print(f"Report saved to: {saved}")
    return report


def main():
    parser = argparse.ArgumentParser(description=QUESTION.format(gene="<GENE>"))
    parser.add_argument("--gene", "-g", default=GENE, help=f"Gene symbol (default: {GENE})")
    parser.add_argument("--output-dir", "-o", default="questions/output")
    args = parser.parse_args()
    run(gene=args.gene.upper(), output_dir=args.output_dir)


if __name__ == "__main__":
    main()
