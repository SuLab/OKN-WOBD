#!/usr/bin/env python3
"""
Q2: What is the biological neighborhood of a gene across FRINK knowledge graphs?

Data Sources: SPOKE-OKN, SPOKE-GeneLab, Wikidata, NDE, BioBricks-AOPWiki
Primary Tools: GeneNeighborhoodQuery, PlotlyVisualizer

Queries the immediate neighborhood of a gene across multiple knowledge graphs,
returning related entities (diseases, GO terms, datasets, pathways) with their
provenance.

Usage:
    python -m questions.gene_neighborhood_map
    python -m questions.gene_neighborhood_map --gene TP53
"""

import argparse
from collections import defaultdict
from pathlib import Path

QUESTION = "What is the biological neighborhood of {gene} across FRINK knowledge graphs?"
GENE = "CD19"


def run(gene: str = GENE, output_dir: str = "questions/output"):
    """Run the investigation and produce an HTML report."""
    from analysis_tools import GeneNeighborhoodQuery, PlotlyVisualizer
    from questions._report import QuestionReport, results_table, summary_stats

    question = QUESTION.format(gene=gene)
    report = QuestionReport(
        question=question,
        sources=["SPOKE-OKN", "SPOKE-GeneLab", "Wikidata", "NDE", "BioBricks"],
        module_name="gene_neighborhood_map",
    )

    # --- Step 1: Resolve gene and query all graphs ---
    print(f"Querying neighborhood for {gene}...")
    querier = GeneNeighborhoodQuery(timeout=60)
    neighborhood = querier.query_all(symbol=gene)

    report.add_step(
        f"Resolve {gene} identifiers",
        summary_stats("Gene Symbol", neighborhood.gene_symbol)
        + summary_stats("NCBI Gene ID", neighborhood.ncbi_gene_id or "N/A")
        + summary_stats("Gene IRI", f"<code>{neighborhood.gene_iri}</code>" if neighborhood.gene_iri else "N/A"),
    )

    # --- Step 2: Per-graph results ---
    graph_rows = []
    for g in neighborhood.graphs:
        status = f"{len(g.entities)} entities" if not g.error else f"Error: {g.error[:60]}"
        graph_rows.append({
            "Graph": g.graph_name,
            "Entities": str(len(g.entities)),
            "Query Time": f"{g.query_time_ms:.0f}ms",
            "Status": status,
        })

    total_entities = sum(len(g.entities) for g in neighborhood.graphs)
    report.add_step(
        "Query all knowledge graphs in parallel",
        summary_stats("Total entities found", total_entities)
        + results_table(graph_rows),
    )

    # --- Step 3: Entity type breakdown ---
    type_counts = defaultdict(int)
    for g in neighborhood.graphs:
        for e in g.entities:
            type_label = e.type_label or "Unknown"
            type_counts[type_label] += 1

    type_rows = [
        {"Entity Type": t, "Count": str(c)}
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1])
    ]
    if type_rows:
        report.add_step(
            "Categorize related entities by type",
            results_table(type_rows),
        )

    # --- Step 4: Sample entities per graph ---
    for g in neighborhood.graphs:
        if not g.entities:
            continue
        entity_rows = []
        for e in g.entities[:8]:
            arrow = "->" if e.direction == "outgoing" else "<-"
            entity_rows.append({
                "Direction": arrow,
                "Entity": e.label[:50],
                "Type": e.type_label or "",
                "Predicate": e.predicate_label,
            })
        report.add_step(
            f"Entities from {g.graph_name} ({len(g.entities)} total)",
            results_table(entity_rows),
        )

    # --- Visualization: Network ---
    if total_entities > 0:
        viz = PlotlyVisualizer()
        network_html = viz.neighborhood_network(neighborhood)
        report.add_visualization(
            f"Neighborhood Network of {gene}",
            network_html,
        )

    # --- Answer ---
    active_graphs = [g.graph_name for g in neighborhood.graphs if g.entities]
    report.set_answer(
        f"{gene} has {total_entities} related entities across "
        f"{len(active_graphs)} knowledge graphs ({', '.join(active_graphs)}).\n\n"
        f"Entity types include: {', '.join(sorted(type_counts.keys()))}."
    )

    for g in neighborhood.graphs:
        report.add_provenance(f"endpoint_{g.graph_name}", g.endpoint)

    # SPARQL queries used (representative templates)
    gene_iri = neighborhood.gene_iri or "<gene_iri>"
    report.add_query(
        "SPOKE-OKN: Gene neighborhood",
        f'''PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX biolink: <https://w3id.org/biolink/vocab/>

SELECT DISTINCT ?entity ?entityLabel ?entityType ?entityTypeLabel ?predicate ?predicateLabel ?direction
WHERE {{
  {{
    <{gene_iri}> ?predicate ?entity .
    BIND("outgoing" AS ?direction)
    OPTIONAL {{ ?entity rdfs:label ?entityLabel }}
    OPTIONAL {{ ?entity a ?entityType . OPTIONAL {{ ?entityType rdfs:label ?entityTypeLabel }} }}
    OPTIONAL {{ ?predicate rdfs:label ?predicateLabel }}
    FILTER(?predicate != rdf:type && ?predicate != rdfs:label && ?predicate != rdfs:comment)
  }}
  UNION
  {{
    ?entity ?predicate <{gene_iri}> .
    BIND("incoming" AS ?direction)
    OPTIONAL {{ ?entity rdfs:label ?entityLabel }}
    OPTIONAL {{ ?entity a ?entityType . OPTIONAL {{ ?entityType rdfs:label ?entityTypeLabel }} }}
    OPTIONAL {{ ?predicate rdfs:label ?predicateLabel }}
    FILTER(?predicate != rdf:type && ?predicate != rdfs:label)
  }}
}}
LIMIT 20''',
        "https://frink.apps.renci.org/spoke-okn/sparql",
    )
    report.add_query(
        "Wikidata: Gene properties and GO terms",
        f'''SELECT DISTINCT ?entity ?entityLabel ?entityType ?entityTypeLabel ?property ?propertyLabel ?direction
WHERE {{
  {{
    ?gene wdt:P353 "{gene}" .
    ?gene wdt:P703 wd:Q15978631 .
  }}
  {{
    ?gene ?prop ?entity .
    ?property wikibase:directClaim ?prop .
    BIND("outgoing" AS ?direction)
    FILTER(isIRI(?entity) && ?entity != wd:Q15978631)
    OPTIONAL {{ ?entity wdt:P31 ?entityType }}
  }}
  UNION
  {{
    ?gene wdt:P688 ?protein .
    ?protein ?prop ?entity .
    ?property wikibase:directClaim ?prop .
    BIND("outgoing" AS ?direction)
    FILTER(isIRI(?entity))
    OPTIONAL {{ ?entity wdt:P31 ?entityType }}
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT 30''',
        "https://query.wikidata.org/sparql",
    )
    report.add_query(
        "NDE: Datasets mentioning gene",
        f'''PREFIX schema: <http://schema.org/>

SELECT DISTINCT ?entity ?entityLabel ?entityType ?predicate ?direction
WHERE {{
  ?entity a schema:Dataset .
  BIND(schema:Dataset AS ?entityType)
  BIND("incoming" AS ?direction)
  BIND(schema:mentions AS ?predicate)
  {{
    ?entity schema:name ?name .
    FILTER(CONTAINS(LCASE(?name), LCASE("{gene}")))
    BIND(?name AS ?entityLabel)
  }}
  UNION
  {{
    ?entity schema:description ?desc .
    FILTER(CONTAINS(LCASE(?desc), LCASE("{gene}")))
    ?entity schema:name ?entityLabel .
  }}
}}
LIMIT 10''',
        "https://frink.apps.renci.org/nde/sparql",
    )

    filepath = str(Path(output_dir) / "gene_neighborhood_map.html")
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
