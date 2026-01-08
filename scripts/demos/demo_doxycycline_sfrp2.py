#!/usr/bin/env python3
"""
Demo: Multi-Source Provenance Visualization

This script demonstrates the integration of multiple biomedical knowledge sources
to show connections between a drug, gene, diseases, and related pathways.

Data Sources:
1. GXA (local Fuseki) - Drug → gene expression relationships
2. SPOKE-OKN (FRINK) - Gene → disease markers and expression
3. Ubergraph (FRINK) - GO pathway → disease mappings
4. Wikidata - Gene annotations and pathway relationships

The output is an interactive HTML visualization with provenance shown on
both nodes and edges.

Usage:
    python demo_doxycycline_sfrp2.py
    python demo_doxycycline_sfrp2.py --output my_graph.html
    python demo_doxycycline_sfrp2.py --gene TP53 --drug metformin
"""

import argparse
from typing import List, Dict, Any, Optional

# Import existing infrastructure
from gene_disease_paths import GeneDiseasePathFinder
from plotly_visualizer import PlotlyVisualizer, COLORS

# Try to import Fuseki client for GXA queries
try:
    from fuseki_client import FusekiClient
    HAS_FUSEKI = True
except ImportError:
    HAS_FUSEKI = False


def query_gxa_drug_gene(
    drug_name: str,
    gene_symbol: str,
    fc_threshold: float = 0.5,
    pvalue_threshold: float = 0.1,
) -> List[Dict[str, Any]]:
    """
    Query GXA for drug treatment effects on a gene.

    Returns list of expression results with study metadata.
    """
    if not HAS_FUSEKI:
        print("  [GXA] Fuseki client not available, skipping GXA queries")
        return []

    print(f"\n[GXA] Querying for {drug_name} → {gene_symbol} expression...")

    try:
        client = FusekiClient(dataset='GXA-v2', timeout=120)
        if not client.is_available():
            print("  Warning: Fuseki server not available")
            return []
    except Exception as e:
        print(f"  Warning: Could not connect to Fuseki: {e}")
        return []

    # Query for drug treatment studies affecting the gene
    # Note: Drug names often appear in test_group_label, not project_title
    query = f'''
    SELECT DISTINCT ?study ?projectTitle ?geneSymbol ?log2fc ?pvalue
                    ?assayName ?testGroup ?refGroup
    WHERE {{
        # Start with expression data for the target gene
        ?exprUri a biolink:GeneExpressionMixin ;
                 biolink:subject ?assayUri ;
                 biolink:object ?gene ;
                 spokegenelab:log2fc ?log2fc ;
                 spokegenelab:adj_p_value ?pvalue .

        # Filter for target gene
        ?gene biolink:symbol ?geneSymbol .
        FILTER(?geneSymbol = "{gene_symbol}")

        # Get assay details - drug name is typically in test_group_label
        ?assayUri biolink:name ?assayName .
        OPTIONAL {{ ?assayUri spokegenelab:test_group_label ?testGroup }}
        OPTIONAL {{ ?assayUri spokegenelab:reference_group_label ?refGroup }}

        # Filter for drug name in test group OR assay name (case-insensitive)
        FILTER(
            CONTAINS(LCASE(COALESCE(?testGroup, "")), "{drug_name.lower()}") ||
            CONTAINS(LCASE(?assayName), "{drug_name.lower()}")
        )

        # Link to study with compound/treatment factor
        VALUES ?factor {{ "compound" "treatment" "dose" }}
        ?studyUri spokegenelab:experimental_factors ?factor ;
                  biolink:has_output ?assayUri ;
                  biolink:name ?study ;
                  spokegenelab:project_title ?projectTitle .
    }}
    LIMIT 50
    '''

    try:
        results = client.query_simple(query)
        print(f"  Found {len(results)} expression results")

        # Filter by thresholds in Python
        filtered = []
        for r in results:
            log2fc = float(r.get('log2fc', 0))
            pvalue = float(r.get('pvalue', 1)) if r.get('pvalue') else 1.0

            if abs(log2fc) >= fc_threshold and pvalue < pvalue_threshold:
                direction = "upregulates" if log2fc > 0 else "downregulates"
                filtered.append({
                    'drug': drug_name,
                    'gene': gene_symbol,
                    'log2fc': log2fc,
                    'pvalue': pvalue,
                    'direction': direction,
                    'study': r.get('study', ''),
                    'title': r.get('projectTitle', ''),
                    'assay': r.get('assayName', ''),
                    'test_group': r.get('testGroup', ''),
                    'ref_group': r.get('refGroup', ''),
                    'source': 'GXA',
                })

        print(f"  After filtering: {len(filtered)} significant results")
        return filtered

    except Exception as e:
        print(f"  Error querying GXA: {e}")
        return []


def query_gxa_disease_gene(
    gene_symbol: str,
    fc_threshold: float = 1.0,
    pvalue_threshold: float = 0.05,
) -> List[Dict[str, Any]]:
    """
    Query GXA for disease-related gene expression changes.

    Returns list of expression results linking genes to diseases.
    """
    if not HAS_FUSEKI:
        print("  [GXA] Fuseki client not available, skipping disease queries")
        return []

    print(f"\n[GXA] Querying for disease-related {gene_symbol} expression...")

    try:
        client = FusekiClient(dataset='GXA-v2', timeout=120)
        if not client.is_available():
            print("  Warning: Fuseki server not available")
            return []
    except Exception as e:
        print(f"  Warning: Could not connect to Fuseki: {e}")
        return []

    # Query for disease studies affecting the gene
    query = f'''
    SELECT DISTINCT ?study ?projectTitle ?geneSymbol ?log2fc ?pvalue
                    ?diseaseName ?diseaseId ?assayName ?testGroup ?refGroup
    WHERE {{
        # Start with expression data for the target gene
        ?exprUri a biolink:GeneExpressionMixin ;
                 biolink:subject ?assayUri ;
                 biolink:object ?gene ;
                 spokegenelab:log2fc ?log2fc ;
                 spokegenelab:adj_p_value ?pvalue .

        # Filter for target gene
        ?gene biolink:symbol ?geneSymbol .
        FILTER(?geneSymbol = "{gene_symbol}")

        # Get assay details
        ?assayUri biolink:name ?assayName .
        OPTIONAL {{ ?assayUri spokegenelab:test_group_label ?testGroup }}
        OPTIONAL {{ ?assayUri spokegenelab:reference_group_label ?refGroup }}

        # Link to disease study
        ?studyUri spokegenelab:experimental_factors "disease" ;
                  biolink:has_output ?assayUri ;
                  biolink:name ?study ;
                  spokegenelab:project_title ?projectTitle ;
                  biolink:studies ?disease .

        # Get disease info
        ?disease a biolink:Disease ;
                 biolink:name ?diseaseName .
        OPTIONAL {{ ?disease biolink:id ?diseaseId }}
    }}
    LIMIT 100
    '''

    try:
        results = client.query_simple(query)
        print(f"  Found {len(results)} disease expression results")

        # Filter by thresholds and exclude controls
        exclude_patterns = ['healthy', 'normal', 'control', 'reference', 'pato_', 'efo_0001461']
        filtered = []

        for r in results:
            log2fc = float(r.get('log2fc', 0))
            pvalue = float(r.get('pvalue', 1)) if r.get('pvalue') else 1.0
            disease_name = r.get('diseaseName', '')
            disease_id = r.get('diseaseId', '')

            # Skip controls/healthy
            if any(pat in disease_name.lower() or pat in disease_id.lower() for pat in exclude_patterns):
                continue

            if abs(log2fc) >= fc_threshold and pvalue < pvalue_threshold:
                direction = "upregulated" if log2fc > 0 else "downregulated"
                filtered.append({
                    'gene': gene_symbol,
                    'disease': disease_name,
                    'disease_id': disease_id,
                    'log2fc': log2fc,
                    'pvalue': pvalue,
                    'direction': direction,
                    'study': r.get('study', ''),
                    'title': r.get('projectTitle', ''),
                    'assay': r.get('assayName', ''),
                    'test_group': r.get('testGroup', ''),
                    'ref_group': r.get('refGroup', ''),
                    'source': 'GXA',
                })

        print(f"  After filtering: {len(filtered)} significant disease associations")
        return filtered

    except Exception as e:
        print(f"  Error querying GXA for diseases: {e}")
        return []


def build_graph(
    gxa_drug_results: List[Dict],
    gxa_disease_results: List[Dict],
    gene_disease_connections: List[Dict],
    drug_name: str,
    gene_symbol: str,
) -> tuple[List[Dict], List[Dict]]:
    """
    Build unified graph structure from multi-source query results.

    Returns (nodes, edges) for visualization.
    """
    nodes = {}
    edges = []

    # Always add central gene node
    gene_id = f"gene:{gene_symbol}"
    nodes[gene_id] = {
        "id": gene_id,
        "label": gene_symbol,
        "type": "gene",
        "title": f"Gene: {gene_symbol}",
    }

    # Add drug node and edges if we have GXA drug results
    if gxa_drug_results:
        drug_id = f"drug:{drug_name.lower().replace(' ', '_')}"
        nodes[drug_id] = {
            "id": drug_id,
            "label": drug_name,
            "type": "drug",
            "title": f"Drug: {drug_name}",
        }

        # Add drug → gene edges from GXA
        for r in gxa_drug_results:
            direction = r.get('direction', 'regulates')
            evidence = f"log2FC={r['log2fc']:.2f}, p={r['pvalue']:.3f}"
            study_id = r.get('study', 'N/A')
            assay_name = r.get('assay', r.get('test_group', 'N/A'))

            edges.append({
                "from": drug_id,
                "to": gene_id,
                "label": direction,
                "source": "GXA",
                "evidence": evidence,
                "study_id": study_id,
                "assay": assay_name,
                "title": f"{direction}<br>Study: {study_id}<br>Assay: {assay_name}<br>{evidence}",
            })

    # Add disease expression edges from GXA (gene upregulated/downregulated in disease)
    for r in gxa_disease_results:
        disease_name = r.get('disease', 'Unknown')
        disease_id_raw = r.get('disease_id', disease_name)
        disease_id = f"disease:{disease_id_raw.replace(' ', '_').replace(':', '_')}"

        # Add disease node if not exists
        if disease_id not in nodes:
            nodes[disease_id] = {
                "id": disease_id,
                "label": disease_name[:25],
                "type": "disease",
                "title": f"Disease: {disease_name}<br>ID: {disease_id_raw}",
            }

        # Add gene → disease edge (expression in disease context)
        direction = r.get('direction', 'expressed')
        evidence = f"log2FC={r['log2fc']:.2f}, p={r['pvalue']:.3f}"
        study_id = r.get('study', 'N/A')
        assay_name = r.get('assay', r.get('test_group', 'N/A'))

        edges.append({
            "from": gene_id,
            "to": disease_id,
            "label": direction,
            "source": "GXA",
            "evidence": evidence,
            "study_id": study_id,
            "assay": assay_name,
            "title": f"{direction} in {disease_name}<br>Study: {study_id}<br>Assay: {assay_name}<br>{evidence}",
        })

    # Process gene-disease connections (from SPOKE, Ubergraph, Wikidata)
    for conn in gene_disease_connections:
        source = conn.get('source', 'Unknown')
        path_type = conn.get('path_type', 'associated')
        intermediate = conn.get('intermediate')

        # Add disease node
        disease_id = f"disease:{conn.get('disease_id', conn['disease_name']).replace(' ', '_')}"
        if disease_id not in nodes:
            nodes[disease_id] = {
                "id": disease_id,
                "label": conn['disease_name'][:25],
                "type": "disease",
                "title": f"Disease: {conn['disease_name']}<br>ID: {conn.get('disease_id', 'N/A')}",
            }

        # Handle intermediate nodes (GO terms or related genes)
        if intermediate:
            if intermediate.startswith("GO:"):
                # GO term intermediate
                go_parts = intermediate.split(":")
                go_id = f"go:{go_parts[0]}_{go_parts[1].split()[0]}"
                go_label = intermediate.split(":")[0] + ":" + intermediate.split(":")[1].split()[0]
                go_full = intermediate

                if go_id not in nodes:
                    nodes[go_id] = {
                        "id": go_id,
                        "label": go_label,
                        "type": "go_term",
                        "title": f"GO Term: {go_full}",
                    }

                # Gene → GO edge
                if not any(e['from'] == gene_id and e['to'] == go_id for e in edges):
                    edges.append({
                        "from": gene_id,
                        "to": go_id,
                        "label": "involved in",
                        "source": source,
                    })

                # GO → Disease edge
                edges.append({
                    "from": go_id,
                    "to": disease_id,
                    "label": path_type.replace("_", " "),
                    "source": source,
                })
            else:
                # Related gene intermediate (shared pathway)
                related_gene = intermediate.split()[0]
                related_gene_id = f"gene:{related_gene}"

                if related_gene_id not in nodes:
                    nodes[related_gene_id] = {
                        "id": related_gene_id,
                        "label": related_gene,
                        "type": "gene",
                        "title": f"Related Gene: {intermediate}",
                    }

                # Gene → Related Gene edge (shared pathway)
                if not any(e['from'] == gene_id and e['to'] == related_gene_id for e in edges):
                    # Extract GO term from intermediate if present
                    go_info = ""
                    if "(shares:" in intermediate:
                        go_info = intermediate.split("(shares:")[1].rstrip(")")
                    edges.append({
                        "from": gene_id,
                        "to": related_gene_id,
                        "label": f"shares {go_info}" if go_info else "shared pathway",
                        "source": source,
                    })

                # Related Gene → Disease edge
                edges.append({
                    "from": related_gene_id,
                    "to": disease_id,
                    "label": "marker for",
                    "source": source,
                })
        else:
            # Direct gene → disease edge
            edges.append({
                "from": gene_id,
                "to": disease_id,
                "label": path_type.replace("_", " "),
                "source": source,
            })

    return list(nodes.values()), edges


def main():
    parser = argparse.ArgumentParser(
        description="Generate multi-source provenance visualization"
    )
    parser.add_argument(
        "--output", "-o",
        default="demo_provenance_graph.html",
        help="Output HTML file path"
    )
    parser.add_argument(
        "--drug",
        default="doxycycline",
        help="Drug name to search for in GXA (optional)"
    )
    parser.add_argument(
        "--gene",
        default="SFRP2",
        help="Gene symbol to analyze"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("MULTI-SOURCE PROVENANCE VISUALIZATION DEMO")
    print("=" * 70)
    print(f"\nGene: {args.gene}")
    print(f"Drug (GXA search): {args.drug}")
    print("\nData Sources:")
    print("  1. GXA (local Fuseki) - Drug & disease expression effects")
    print("  2. SPOKE-OKN (FRINK) - Gene-disease relationships")
    print("  3. Ubergraph (FRINK) - GO pathway connections")
    print("  4. Wikidata - Gene annotations and shared pathways")

    # Query GXA for drug → gene expression
    gxa_drug_results = query_gxa_drug_gene(args.drug, args.gene)

    # Query GXA for disease → gene expression
    gxa_disease_results = query_gxa_disease_gene(args.gene)

    # Query knowledge graphs for gene → disease connections
    print(f"\n[Knowledge Graphs] Finding {args.gene} → disease connections...")
    finder = GeneDiseasePathFinder(verbose=args.verbose)
    connections = finder.find_all_connections(args.gene)
    conn_dicts = [c.to_dict() for c in connections]
    print(f"  Found {len(connections)} connections")

    # Count by source
    source_counts = {}
    for c in connections:
        source_counts[c.source] = source_counts.get(c.source, 0) + 1
    for src, count in sorted(source_counts.items()):
        print(f"    {src}: {count}")

    # Build unified graph
    print("\n[Building Graph]")
    nodes, edges = build_graph(
        gxa_drug_results, gxa_disease_results, conn_dicts,
        drug_name=args.drug.title(),
        gene_symbol=args.gene,
    )

    print(f"  Total nodes: {len(nodes)}")
    print(f"  Total edges: {len(edges)}")

    # Count edges by source
    edge_source_counts = {}
    for e in edges:
        src = e.get('source', 'Unknown')
        edge_source_counts[src] = edge_source_counts.get(src, 0) + 1

    print("\n  Edges by source:")
    for src, count in sorted(edge_source_counts.items()):
        print(f"    {src}: {count}")

    # Generate visualization
    print(f"\n[Generating Visualization]")
    viz = PlotlyVisualizer()

    title = f"{args.gene} Knowledge Graph Integration"
    if gxa_drug_results:
        title = f"{args.drug.title()} → {args.gene} → Disease Connections"

    html = viz.provenance_network(
        nodes=nodes,
        edges=edges,
        title=title,
        central_node_id=f"gene:{args.gene}",
    )

    with open(args.output, 'w') as f:
        f.write(html)

    print(f"  Saved to: {args.output}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Generated visualization with {len(nodes)} nodes and {len(edges)} edges")
    print(f"Open {args.output} in a browser to explore the graph")
    print("\nThis demonstrates how integrating:")
    print("  - Expression data (GXA) - when available")
    print("  - Knowledge graphs (SPOKE)")
    print("  - Ontology relationships (Ubergraph)")
    print("  - Community knowledge (Wikidata)")
    print("can reveal connections between genes, pathways, and diseases.")


if __name__ == "__main__":
    main()
