#!/usr/bin/env python3
"""
Generate Multi-Source Provenance Visualization for a Gene

This script creates an interactive HTML visualization showing:
1. Drug treatments that affect the gene (from GXA)
2. Diseases where the gene is differentially expressed (from GXA)
3. Gene-disease connections from knowledge graphs (SPOKE, Ubergraph, Wikidata)

Usage:
    python generate_gene_visualization.py --gene S100A12 --output examples/
    python generate_gene_visualization.py --gene IL1B --drug JQ1 --output examples/

    # Batch mode for multiple genes:
    python generate_gene_visualization.py --genes S100A12,IL1B,LIF --output examples/
"""

import argparse
import os
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


def query_gxa_drug_effects(
    gene_symbol: str,
    drug_name: Optional[str] = None,
    fc_threshold: float = 1.0,
    pvalue_threshold: float = 0.05,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Query GXA for drug/compound treatment effects on a gene.

    If drug_name is provided, filter to that drug. Otherwise, return all
    drug treatments affecting the gene.
    """
    if not HAS_FUSEKI:
        print("  [GXA] Fuseki client not available")
        return []

    print(f"\n[GXA] Querying drug effects on {gene_symbol}...")

    try:
        client = FusekiClient(dataset='GXA-v2', timeout=120)
        if not client.is_available():
            print("  Warning: Fuseki server not available")
            return []
    except Exception as e:
        print(f"  Warning: Could not connect to Fuseki: {e}")
        return []

    # Build optional drug filter
    drug_filter = ""
    if drug_name:
        drug_filter = f'''
            FILTER(
                CONTAINS(LCASE(COALESCE(?testGroup, "")), "{drug_name.lower()}") ||
                CONTAINS(LCASE(?assayName), "{drug_name.lower()}")
            )
        '''

    query = f'''
    SELECT DISTINCT ?study ?projectTitle ?geneSymbol ?log2fc ?pvalue
                    ?assayName ?testGroup ?refGroup ?drugName ?drugId
    WHERE {{
        # Expression data for the target gene
        ?exprUri a biolink:GeneExpressionMixin ;
                 biolink:subject ?assayUri ;
                 biolink:object ?gene ;
                 spokegenelab:log2fc ?log2fc ;
                 spokegenelab:adj_p_value ?pvalue .

        ?gene biolink:symbol ?geneSymbol .
        FILTER(?geneSymbol = "{gene_symbol}")

        # Get assay details
        ?assayUri biolink:name ?assayName .
        OPTIONAL {{ ?assayUri spokegenelab:test_group_label ?testGroup }}
        OPTIONAL {{ ?assayUri spokegenelab:reference_group_label ?refGroup }}

        {drug_filter}

        # Link to study with compound/treatment factor
        VALUES ?factor {{ "compound" "treatment" "dose" }}
        ?studyUri spokegenelab:experimental_factors ?factor ;
                  biolink:has_output ?assayUri ;
                  biolink:name ?study ;
                  spokegenelab:project_title ?projectTitle .

        # Get drug entity if available
        OPTIONAL {{
            ?studyUri biolink:studies ?drug .
            ?drug a biolink:ChemicalEntity ;
                  biolink:name ?drugName ;
                  biolink:id ?drugId .
        }}
    }}
    LIMIT {limit}
    '''

    try:
        results = client.query_simple(query)
        print(f"  Found {len(results)} drug treatment results")

        # Filter by thresholds
        filtered = []
        for r in results:
            log2fc = float(r.get('log2fc', 0))
            pvalue = float(r.get('pvalue', 1)) if r.get('pvalue') else 1.0

            if abs(log2fc) >= fc_threshold and pvalue < pvalue_threshold:
                direction = "upregulates" if log2fc > 0 else "downregulates"
                drug_label = r.get('drugName') or r.get('testGroup') or 'Unknown treatment'

                filtered.append({
                    'gene': gene_symbol,
                    'drug': drug_label,
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


def query_gxa_disease_expression(
    gene_symbol: str,
    fc_threshold: float = 1.0,
    pvalue_threshold: float = 0.05,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Query GXA for disease-related gene expression changes.
    """
    if not HAS_FUSEKI:
        print("  [GXA] Fuseki client not available")
        return []

    print(f"\n[GXA] Querying disease expression for {gene_symbol}...")

    try:
        client = FusekiClient(dataset='GXA-v2', timeout=120)
        if not client.is_available():
            print("  Warning: Fuseki server not available")
            return []
    except Exception as e:
        print(f"  Warning: Could not connect to Fuseki: {e}")
        return []

    query = f'''
    SELECT DISTINCT ?study ?projectTitle ?geneSymbol ?log2fc ?pvalue
                    ?diseaseName ?diseaseId ?assayName ?testGroup ?refGroup
    WHERE {{
        ?exprUri a biolink:GeneExpressionMixin ;
                 biolink:subject ?assayUri ;
                 biolink:object ?gene ;
                 spokegenelab:log2fc ?log2fc ;
                 spokegenelab:adj_p_value ?pvalue .

        ?gene biolink:symbol ?geneSymbol .
        FILTER(?geneSymbol = "{gene_symbol}")

        ?assayUri biolink:name ?assayName .
        OPTIONAL {{ ?assayUri spokegenelab:test_group_label ?testGroup }}
        OPTIONAL {{ ?assayUri spokegenelab:reference_group_label ?refGroup }}

        ?studyUri spokegenelab:experimental_factors "disease" ;
                  biolink:has_output ?assayUri ;
                  biolink:name ?study ;
                  spokegenelab:project_title ?projectTitle ;
                  biolink:studies ?disease .

        ?disease a biolink:Disease ;
                 biolink:name ?diseaseName .
        OPTIONAL {{ ?disease biolink:id ?diseaseId }}
    }}
    LIMIT {limit}
    '''

    try:
        results = client.query_simple(query)
        print(f"  Found {len(results)} disease expression results")

        # Filter and exclude controls
        exclude_patterns = ['healthy', 'normal', 'control', 'reference', 'pato_', 'efo_0001461']
        filtered = []

        for r in results:
            log2fc = float(r.get('log2fc', 0))
            pvalue = float(r.get('pvalue', 1)) if r.get('pvalue') else 1.0
            disease_name = r.get('diseaseName', '')
            disease_id = r.get('diseaseId', '')

            # Skip controls
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
    drug_results: List[Dict],
    disease_results: List[Dict],
    kg_connections: List[Dict],
    gene_symbol: str,
) -> tuple[List[Dict], List[Dict]]:
    """
    Build unified graph structure from multi-source query results.
    """
    nodes = {}
    edges = []

    # Central gene node
    gene_id = f"gene:{gene_symbol}"
    nodes[gene_id] = {
        "id": gene_id,
        "label": gene_symbol,
        "type": "gene",
        "title": f"Gene: {gene_symbol}",
    }

    # Add drug nodes and edges
    seen_drug_edges = set()
    for r in drug_results:
        drug_name = r.get('drug', 'Unknown')
        drug_id = f"drug:{drug_name.lower().replace(' ', '_')[:30]}"

        if drug_id not in nodes:
            nodes[drug_id] = {
                "id": drug_id,
                "label": drug_name[:25],
                "type": "drug",
                "title": f"Drug: {drug_name}",
            }

        edge_key = (drug_id, gene_id, r.get('study', ''))
        if edge_key not in seen_drug_edges:
            seen_drug_edges.add(edge_key)
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

    # Add disease expression edges from GXA
    seen_disease_edges = set()
    for r in disease_results:
        disease_name = r.get('disease', 'Unknown')
        disease_id_raw = r.get('disease_id', disease_name)
        disease_id = f"disease:{disease_id_raw.replace(' ', '_').replace(':', '_')[:40]}"

        if disease_id not in nodes:
            nodes[disease_id] = {
                "id": disease_id,
                "label": disease_name[:25],
                "type": "disease",
                "title": f"Disease: {disease_name}<br>ID: {disease_id_raw}",
            }

        edge_key = (gene_id, disease_id, r.get('study', ''))
        if edge_key not in seen_disease_edges:
            seen_disease_edges.add(edge_key)
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

    # Process knowledge graph connections
    for conn in kg_connections:
        source = conn.get('source', 'Unknown')
        path_type = conn.get('path_type', 'associated')
        intermediate = conn.get('intermediate')

        disease_id = f"disease:{conn.get('disease_id', conn['disease_name']).replace(' ', '_')[:40]}"
        if disease_id not in nodes:
            nodes[disease_id] = {
                "id": disease_id,
                "label": conn['disease_name'][:25],
                "type": "disease",
                "title": f"Disease: {conn['disease_name']}<br>ID: {conn.get('disease_id', 'N/A')}",
            }

        if intermediate:
            if intermediate.startswith("GO:"):
                go_parts = intermediate.split(":")
                go_id = f"go:{go_parts[0]}_{go_parts[1].split()[0]}"
                go_label = intermediate.split(":")[0] + ":" + intermediate.split(":")[1].split()[0]

                if go_id not in nodes:
                    nodes[go_id] = {
                        "id": go_id,
                        "label": go_label,
                        "type": "go_term",
                        "title": f"GO Term: {intermediate}",
                    }

                if not any(e['from'] == gene_id and e['to'] == go_id for e in edges):
                    edges.append({
                        "from": gene_id,
                        "to": go_id,
                        "label": "involved in",
                        "source": source,
                    })

                edges.append({
                    "from": go_id,
                    "to": disease_id,
                    "label": path_type.replace("_", " "),
                    "source": source,
                })
            else:
                related_gene = intermediate.split()[0]
                related_gene_id = f"gene:{related_gene}"

                if related_gene_id not in nodes:
                    nodes[related_gene_id] = {
                        "id": related_gene_id,
                        "label": related_gene,
                        "type": "gene",
                        "title": f"Related Gene: {intermediate}",
                    }

                if not any(e['from'] == gene_id and e['to'] == related_gene_id for e in edges):
                    go_info = ""
                    if "(shares:" in intermediate:
                        go_info = intermediate.split("(shares:")[1].rstrip(")")
                    edges.append({
                        "from": gene_id,
                        "to": related_gene_id,
                        "label": f"shares {go_info}" if go_info else "shared pathway",
                        "source": source,
                    })

                edges.append({
                    "from": related_gene_id,
                    "to": disease_id,
                    "label": "marker for",
                    "source": source,
                })
        else:
            edges.append({
                "from": gene_id,
                "to": disease_id,
                "label": path_type.replace("_", " "),
                "source": source,
            })

    return list(nodes.values()), edges


def generate_visualization(
    gene_symbol: str,
    output_dir: str,
    drug_name: Optional[str] = None,
    disease_name: Optional[str] = None,
    verbose: bool = False,
) -> str:
    """
    Generate a complete visualization for a gene.

    Returns the path to the generated HTML file.
    """
    print("=" * 70)
    print(f"GENERATING VISUALIZATION FOR: {gene_symbol}")
    print("=" * 70)

    # Query GXA for drug effects
    drug_results = query_gxa_drug_effects(gene_symbol, drug_name)

    # Query GXA for disease expression
    disease_results = query_gxa_disease_expression(gene_symbol)

    # Query knowledge graphs
    print(f"\n[Knowledge Graphs] Finding {gene_symbol} → disease connections...")
    finder = GeneDiseasePathFinder(verbose=verbose)
    connections = finder.find_all_connections(gene_symbol)
    kg_connections = [c.to_dict() for c in connections]
    print(f"  Found {len(connections)} connections")

    # Build graph
    print("\n[Building Graph]")
    nodes, edges = build_graph(drug_results, disease_results, kg_connections, gene_symbol)
    print(f"  Total nodes: {len(nodes)}")
    print(f"  Total edges: {len(edges)}")

    # Generate visualization
    print(f"\n[Generating Visualization]")
    viz = PlotlyVisualizer()

    # Create descriptive title
    drug_count = len(set(r.get('drug', '') for r in drug_results))
    disease_count = len(set(r.get('disease', '') for r in disease_results)) + len(set(c.get('disease_name', '') for c in kg_connections))
    title = f"{gene_symbol}: {drug_count} Drug Effects, {disease_count} Disease Associations"

    html = viz.provenance_network(
        nodes=nodes,
        edges=edges,
        title=title,
        central_node_id=f"gene:{gene_symbol}",
    )

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Build filename from gene, primary drug, and primary disease
    def slugify(s: str, max_len: int = 20) -> str:
        """Convert string to filename-safe slug."""
        return s.lower().replace(' ', '_').replace('-', '_').replace(';', '').replace(',', '').replace('/', '_')[:max_len]

    # Get primary drug
    if drug_name:
        drug_slug = slugify(drug_name)
    elif drug_results:
        primary_drug = drug_results[0].get('drug', 'unknown')
        drug_slug = slugify(primary_drug)
    else:
        drug_slug = None

    # Get primary disease (prefer explicit, then GXA disease results, fallback to KG connections)
    if disease_name:
        disease_slug = slugify(disease_name)
    elif disease_results:
        primary_disease = disease_results[0].get('disease', 'unknown')
        disease_slug = slugify(primary_disease)
    elif kg_connections:
        primary_disease = kg_connections[0].get('disease_name', 'unknown')
        disease_slug = slugify(primary_disease)
    else:
        disease_slug = None

    # Build filename: gene_drug_disease.html
    parts = [gene_symbol.lower()]
    if drug_slug:
        parts.append(drug_slug)
    if disease_slug:
        parts.append(disease_slug)
    filename = "_".join(parts) + ".html"

    output_file = os.path.join(output_dir, filename)
    with open(output_file, 'w') as f:
        f.write(html)

    print(f"  Saved to: {output_file}")
    return output_file


def main():
    parser = argparse.ArgumentParser(
        description="Generate multi-source provenance visualization for gene(s)"
    )
    parser.add_argument(
        "--gene",
        help="Single gene symbol to analyze"
    )
    parser.add_argument(
        "--genes",
        help="Comma-separated list of gene symbols"
    )
    parser.add_argument(
        "--drug",
        help="Optional: filter to specific drug name"
    )
    parser.add_argument(
        "--disease",
        help="Optional: disease name for filename (does not filter results)"
    )
    parser.add_argument(
        "--output", "-o",
        default="./examples",
        help="Output directory for HTML files"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    args = parser.parse_args()

    # Determine genes to process
    if args.genes:
        genes = [g.strip() for g in args.genes.split(',')]
    elif args.gene:
        genes = [args.gene]
    else:
        parser.error("Either --gene or --genes is required")

    # Generate visualizations
    output_files = []
    for gene in genes:
        output_file = generate_visualization(
            gene_symbol=gene,
            output_dir=args.output,
            drug_name=args.drug if len(genes) == 1 else None,
            disease_name=args.disease if len(genes) == 1 else None,
            verbose=args.verbose,
        )
        output_files.append(output_file)
        print()

    # Summary
    print("=" * 70)
    print("GENERATION COMPLETE")
    print("=" * 70)
    print(f"Generated {len(output_files)} visualizations:")
    for f in output_files:
        print(f"  - {f}")


if __name__ == "__main__":
    main()
