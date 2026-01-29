#!/usr/bin/env python3
"""
Interactive network visualization for terpenoid biosynthetic process.

Creates a vis.js network with nodes for:
- GO terms (terpenoid biosynthetic process and children)
- Genes (from UniProt annotations)
- Assays (from GXA expression data)
- Studies (from GXA)

Usage:
    cd scripts/demos && python biosynthesis/visualize_terpenoid_network.py

Output:
    biosynthesis/terpenoid_network.html
"""

import sys
from pathlib import Path
from typing import List, Dict, Set, Any
import requests
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sparql_client import SPARQLClient
from fuseki_client import FusekiClient
from plotly_visualizer import PlotlyVisualizer

# Color scheme for node types
COLORS = {
    "go_term": "#2ecc71",      # Green
    "gene": "#3498db",         # Blue
    "assay": "#e67e22",        # Orange
    "study": "#9b59b6",        # Purple
}

# Color scheme for edge sources
SOURCE_COLORS = {
    "Ubergraph": "#2ecc71",    # Green
    "UniProt": "#f39c12",      # Gold
    "GXA": "#e74c3c",          # Red
}


def get_terpenoid_go_terms(client: SPARQLClient) -> List[Dict[str, str]]:
    """Get terpenoid biosynthetic process (GO:0016114) and child terms."""
    print("Step 1: Querying Ubergraph for terpenoid GO terms...")

    query = """
    SELECT DISTINCT ?goId ?label WHERE {
        ?subclass rdfs:subClassOf* obo:GO_0016114 .
        ?subclass a owl:Class .
        ?subclass rdfs:label ?label .
        BIND(REPLACE(STR(?subclass), "http://purl.obolibrary.org/obo/GO_", "GO:") AS ?goId)
        FILTER(STRSTARTS(STR(?subclass), "http://purl.obolibrary.org/obo/GO_"))
    }
    ORDER BY ?label
    """

    results = client.query_simple(query, endpoint="ubergraph")
    print(f"  Found {len(results)} GO terms")
    return results


def get_go_hierarchy(client: SPARQLClient, go_ids: Set[str]) -> List[Dict[str, str]]:
    """Get direct parent-child relationships for GO terms (simplified)."""
    # Skip hierarchy query to avoid rate limits - just connect all terms to root
    print("\n  Using simplified GO term structure (no hierarchy query)")
    return []


def get_arabidopsis_genes_from_uniprot(go_ids: Set[str]) -> List[Dict[str, str]]:
    """Get Arabidopsis genes annotated to GO terms from UniProt."""
    print("\nStep 2: Querying UniProt for Arabidopsis genes...")

    go_uris = " ".join(
        f'<http://purl.obolibrary.org/obo/{gid.replace(":", "_")}>'
        for gid in go_ids
    )

    query = f'''
    PREFIX up: <http://purl.uniprot.org/core/>
    PREFIX taxon: <http://purl.uniprot.org/taxonomy/>

    SELECT DISTINCT ?gene ?go ?geneName WHERE {{
        VALUES ?go {{ {go_uris} }}
        ?protein a up:Protein ;
                 up:organism taxon:3702 ;
                 up:classifiedWith ?go ;
                 up:encodedBy ?geneResource .
        ?geneResource up:locusName ?gene .
        OPTIONAL {{ ?protein up:recommendedName/up:fullName ?geneName }}
    }}
    '''

    try:
        resp = requests.post(
            "https://sparql.uniprot.org/sparql",
            data={"query": query},
            headers={"Accept": "application/sparql-results+json"},
            timeout=180,
        )
        resp.raise_for_status()
        data = resp.json()
        bindings = data.get("results", {}).get("bindings", [])

        results = []
        for b in bindings:
            gene = b.get("gene", {}).get("value", "")
            go_uri = b.get("go", {}).get("value", "")
            gene_name = b.get("geneName", {}).get("value", "")
            go_id = go_uri.split("/")[-1].replace("_", ":")

            results.append({
                "gene": gene.upper(),
                "goId": go_id,
                "geneName": gene_name,
            })

        print(f"  Found {len(results)} gene-GO associations")
        return results

    except Exception as e:
        print(f"  Error querying UniProt: {e}")
        return []


def get_gene_expression(
    fuseki: FusekiClient,
    gene_symbols: Set[str],
) -> List[Dict[str, str]]:
    """Get expression data for genes in Arabidopsis studies."""
    print("\nStep 3: Querying GXA for gene expression...")

    gene_uris = " ".join(
        f'<https://www.ncbi.nlm.nih.gov/gene/{sym}>'
        for sym in gene_symbols
    )

    query = f'''
    SELECT DISTINCT ?studyId ?studyTitle ?assayId ?geneSymbol ?log2fc ?pvalue
    WHERE {{
        VALUES ?gene {{ {gene_uris} }}

        ?expr a biolink:GeneExpressionMixin ;
              biolink:subject ?assay ;
              biolink:object ?gene ;
              spokegenelab:log2fc ?log2fc ;
              spokegenelab:adj_p_value ?pvalue .

        FILTER(?log2fc > 1.0)
        FILTER(?pvalue < 0.05)

        ?study biolink:has_output ?assay ;
               biolink:name ?studyId ;
               biolink:in_taxon ?taxon .
        FILTER(?taxon = "Arabidopsis thaliana" || ?taxon = "3702")

        OPTIONAL {{ ?study spokegenelab:project_title ?studyTitle }}

        BIND(REPLACE(STR(?gene), ".*[/#]", "") AS ?geneSymbol)
        BIND(REPLACE(STR(?assay), ".*[/#]", "") AS ?assayId)
    }}
    ORDER BY ?studyId DESC(?log2fc)
    '''

    results = fuseki.query_simple(query)
    print(f"  Found {len(results)} expression results")
    return results


def build_network(
    go_terms: List[Dict[str, str]],
    go_hierarchy: List[Dict[str, str]],
    gene_results: List[Dict[str, str]],
    expression_results: List[Dict[str, str]],
) -> tuple[List[Dict], List[Dict]]:
    """Build nodes and edges for the network visualization."""
    print("\nStep 4: Building network...")

    nodes = []
    edges = []
    node_ids = set()

    # GO term labels lookup
    go_labels = {r["goId"]: r.get("label", r["goId"]) for r in go_terms}

    # Gene-GO mapping
    gene_go_map: Dict[str, Set[str]] = {}
    gene_names: Dict[str, str] = {}
    for r in gene_results:
        gene = r.get("gene", "")
        go_id = r.get("goId", "")
        if gene:
            if gene not in gene_go_map:
                gene_go_map[gene] = set()
            if go_id:
                gene_go_map[gene].add(go_id)
            if r.get("geneName"):
                gene_names[gene] = r["geneName"]

    # Track which GO terms and genes have expression data
    genes_with_expression = {r.get("geneSymbol") for r in expression_results}
    go_terms_with_genes = set()
    for gene in genes_with_expression:
        go_terms_with_genes.update(gene_go_map.get(gene, set()))

    # 1. Add GO term nodes (only those connected to expressed genes)
    for go_id in go_terms_with_genes:
        node_id = f"go:{go_id}"
        if node_id not in node_ids:
            label = go_labels.get(go_id, go_id)
            nodes.append({
                "id": node_id,
                "label": go_id,
                "type": "go_term",
                "title": f"<b>{go_id}</b><br>{label}<br>Source: Gene Ontology (via Ubergraph)",
            })
            node_ids.add(node_id)

    # 2. Add GO hierarchy edges
    for rel in go_hierarchy:
        child_id = f"go:{rel['child']}"
        parent_id = f"go:{rel['parent']}"
        if child_id in node_ids and parent_id in node_ids:
            edges.append({
                "from": child_id,
                "to": parent_id,
                "label": "is_a",
                "source": "Ubergraph",
                "title": f"<b>is_a</b><br>Source: Ubergraph<br>{rel['child']} is a subclass of {rel['parent']}",
            })

    # 3. Add gene nodes (only those with expression)
    for gene in genes_with_expression:
        node_id = f"gene:{gene}"
        if node_id not in node_ids:
            gene_name = gene_names.get(gene, "")
            title_parts = [f"<b>{gene}</b>"]
            if gene_name:
                title_parts.append(f"{gene_name}")
            go_ids = gene_go_map.get(gene, set())
            if go_ids:
                go_list = ", ".join(sorted(go_ids))
                title_parts.append(f"GO terms: {go_list}")
            title_parts.append("Source: UniProt")

            nodes.append({
                "id": node_id,
                "label": gene,
                "type": "gene",
                "title": "<br>".join(title_parts),
            })
            node_ids.add(node_id)

    # 4. Add gene-GO edges
    for gene in genes_with_expression:
        gene_node = f"gene:{gene}"
        for go_id in gene_go_map.get(gene, set()):
            go_node = f"go:{go_id}"
            if go_node in node_ids:
                edges.append({
                    "from": gene_node,
                    "to": go_node,
                    "label": "annotated_to",
                    "source": "UniProt",
                    "title": f"<b>annotated_to</b><br>Source: UniProt<br>{gene} is annotated to {go_id}",
                })

    # 5. Add study and assay nodes, and expression edges
    studies_added = set()
    assays_added = set()

    for r in expression_results:
        study_id = r.get("studyId", "")
        assay_id = r.get("assayId", "")
        gene = r.get("geneSymbol", "")
        log2fc = r.get("log2fc", "")
        pvalue = r.get("pvalue", "")
        study_title = r.get("studyTitle", study_id)

        # Add study node
        study_node = f"study:{study_id}"
        if study_node not in node_ids:
            nodes.append({
                "id": study_node,
                "label": study_id,
                "type": "study",
                "title": f"<b>{study_id}</b><br>{study_title}<br>Source: GXA (Gene Expression Atlas)",
            })
            node_ids.add(study_node)
            studies_added.add(study_id)

        # Add assay node
        assay_node = f"assay:{assay_id}"
        if assay_node not in node_ids:
            nodes.append({
                "id": assay_node,
                "label": assay_id.split("-")[-1] if "-" in assay_id else assay_id,
                "type": "assay",
                "title": f"<b>{assay_id}</b><br>Study: {study_id}<br>Source: GXA",
            })
            node_ids.add(assay_node)
            assays_added.add(assay_id)

            # Study -> Assay edge
            edges.append({
                "from": study_node,
                "to": assay_node,
                "label": "has_assay",
                "source": "GXA",
                "title": f"<b>has_assay</b><br>Source: GXA<br>Study {study_id} contains assay {assay_id}",
            })

        # Assay -> Gene expression edge
        gene_node = f"gene:{gene}"
        if gene_node in node_ids:
            try:
                log2fc_val = float(log2fc) if log2fc else 0
                label = f"↑{log2fc_val:.1f}"
            except (ValueError, TypeError):
                label = "upregulated"
            edges.append({
                "from": assay_node,
                "to": gene_node,
                "label": label,
                "source": "GXA",
                "title": f"<b>upregulated</b><br>log2FC: {log2fc}<br>adj. p-value: {pvalue}<br>Source: GXA",
            })

    print(f"  Network: {len(nodes)} nodes, {len(edges)} edges")
    print(f"    GO terms: {len([n for n in nodes if n['type'] == 'go_term'])}")
    print(f"    Genes: {len([n for n in nodes if n['type'] == 'gene'])}")
    print(f"    Assays: {len(assays_added)}")
    print(f"    Studies: {len(studies_added)}")

    return nodes, edges


def generate_html(
    nodes: List[Dict],
    edges: List[Dict],
    title: str,
    output_path: Path,
) -> None:
    """Generate the interactive HTML visualization."""
    print("\nStep 5: Generating HTML visualization...")

    # Prepare vis.js node data
    vis_nodes = []
    for node in nodes:
        node_type = node.get("type", "gene")
        color = COLORS.get(node_type, "#95a5a6")

        # Different shapes for different types
        shape_map = {
            "go_term": "diamond",
            "gene": "dot",
            "assay": "square",
            "study": "triangle",
        }

        # Different sizes
        size_map = {
            "go_term": 20,
            "gene": 15,
            "assay": 12,
            "study": 25,
        }

        vis_nodes.append({
            "id": node["id"],
            "label": node["label"],
            "color": {
                "background": color,
                "border": color,
                "highlight": {"background": "#f1c40f", "border": "#f39c12"},
            },
            "shape": shape_map.get(node_type, "dot"),
            "size": size_map.get(node_type, 15),
            "font": {"size": 11, "color": "#2c3e50"},
            "title": node.get("title", node["label"]),
        })

    # Prepare vis.js edge data
    vis_edges = []
    for edge in edges:
        source = edge.get("source", "Unknown")
        edge_color = SOURCE_COLORS.get(source, "#95a5a6")

        vis_edges.append({
            "from": edge["from"],
            "to": edge["to"],
            "label": edge.get("label", ""),
            "color": {"color": edge_color, "highlight": "#f1c40f"},
            "title": edge.get("title", ""),
            "width": 2,
            "font": {
                "size": 9,
                "color": "#555",
                "strokeWidth": 2,
                "strokeColor": "#ffffff",
            },
            "smooth": {"type": "continuous"},
        })

    nodes_json = json.dumps(vis_nodes)
    edges_json = json.dumps(vis_edges)

    # Build legend
    node_legend = " ".join([
        f'<span style="display:inline-flex;align-items:center;margin-right:15px;">'
        f'<span style="display:inline-block;width:14px;height:14px;background:{color};'
        f'border-radius:{"50%" if typ in ["gene"] else "3px"};margin-right:5px;"></span>{typ.replace("_", " ").title()}</span>'
        for typ, color in COLORS.items()
    ])

    source_legend = " ".join([
        f'<span style="display:inline-flex;align-items:center;margin-right:15px;">'
        f'<span style="display:inline-block;width:20px;height:3px;background:{color};margin-right:5px;"></span>{src}</span>'
        for src, color in SOURCE_COLORS.items()
    ])

    html = f'''<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }}
        h1 {{
            text-align: center;
            color: #2c3e50;
            margin-bottom: 10px;
        }}
        .legend {{
            text-align: center;
            margin-bottom: 10px;
            font-size: 13px;
            color: #555;
        }}
        .legend div {{
            margin: 5px 0;
        }}
        .instructions {{
            text-align: center;
            font-size: 12px;
            color: #888;
            margin-bottom: 10px;
        }}
        #network {{
            width: 100%;
            height: 700px;
            border: 1px solid #ddd;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .controls {{
            text-align: center;
            margin-bottom: 10px;
        }}
        .toggle-btn {{
            padding: 8px 16px;
            font-size: 13px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            margin: 0 5px;
            transition: all 0.2s;
        }}
        .toggle-btn.active {{ background: #27ae60; color: white; }}
        .toggle-btn.inactive {{ background: #e0e0e0; color: #555; }}
        .toggle-btn:hover {{ opacity: 0.85; }}
        .summary {{
            text-align: center;
            margin-top: 15px;
            font-size: 13px;
            color: #666;
        }}
        #custom-tooltip {{
            position: fixed;
            background: rgba(45, 52, 54, 0.95);
            color: white;
            padding: 10px 14px;
            border-radius: 6px;
            font-size: 13px;
            line-height: 1.5;
            max-width: 400px;
            pointer-events: none;
            z-index: 10000;
            display: none;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }}
        #custom-tooltip b {{ color: #f1c40f; }}
        .vis-tooltip {{ display: none !important; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div class="legend">
        <div><b>Nodes:</b> {node_legend}</div>
        <div><b>Edge Sources:</b> {source_legend}</div>
    </div>
    <div class="controls">
        <button id="physicsToggle" class="toggle-btn inactive" onclick="togglePhysics()">
            ⚡ Auto-Layout: OFF
        </button>
        <button class="toggle-btn inactive" onclick="resetLayout()">
            🔄 Reset Layout
        </button>
        <button class="toggle-btn inactive" onclick="fitNetwork()">
            🔍 Fit to View
        </button>
    </div>
    <div class="instructions">Drag nodes to rearrange • Scroll to zoom • Hover for details</div>
    <div id="network"></div>
    <div id="custom-tooltip"></div>
    <div class="summary">
        {len(nodes)} nodes • {len(edges)} connections<br>
        Data sources: Ubergraph (GO hierarchy), UniProt (gene annotations), GXA (expression)
    </div>

    <script type="text/javascript">
        var nodes = new vis.DataSet({nodes_json});
        var edges = new vis.DataSet({edges_json});

        var container = document.getElementById('network');
        var data = {{ nodes: nodes, edges: edges }};

        var options = {{
            nodes: {{
                borderWidth: 2,
                shadow: true,
                font: {{ color: '#2c3e50', face: 'arial' }}
            }},
            edges: {{
                shadow: true,
                smooth: {{ type: 'continuous' }},
                arrows: {{ to: {{ enabled: true, scaleFactor: 0.5 }} }}
            }},
            physics: {{
                enabled: true,
                barnesHut: {{
                    gravitationalConstant: -4000,
                    centralGravity: 0.3,
                    springLength: 120,
                    springConstant: 0.04,
                    damping: 0.09,
                }},
                stabilization: {{ iterations: 200, fit: true }}
            }},
            interaction: {{
                hover: true,
                tooltipDelay: 100,
                dragNodes: true,
                dragView: true,
                zoomView: true,
            }}
        }};

        var network = new vis.Network(container, data, options);
        var physicsEnabled = false;

        network.on("stabilizationIterationsDone", function () {{
            physicsEnabled = false;
            network.setOptions({{ physics: {{ enabled: false }} }});
            updatePhysicsButton();
        }});

        function togglePhysics() {{
            physicsEnabled = !physicsEnabled;
            network.setOptions({{ physics: {{ enabled: physicsEnabled }} }});
            updatePhysicsButton();
        }}

        function updatePhysicsButton() {{
            var btn = document.getElementById('physicsToggle');
            btn.textContent = physicsEnabled ? '⚡ Auto-Layout: ON' : '⚡ Auto-Layout: OFF';
            btn.className = physicsEnabled ? 'toggle-btn active' : 'toggle-btn inactive';
        }}

        function resetLayout() {{
            physicsEnabled = true;
            network.setOptions({{ physics: {{ enabled: true }} }});
            updatePhysicsButton();
            var positions = network.getPositions();
            var updates = [];
            for (var nodeId in positions) {{
                updates.push({{ id: nodeId, x: undefined, y: undefined }});
            }}
            nodes.update(updates);
            network.stabilize(200);
        }}

        function fitNetwork() {{
            network.fit({{ animation: true }});
        }}

        // Custom tooltip
        var tooltip = document.getElementById('custom-tooltip');

        function showTooltip(content, params) {{
            if (!content) return;
            tooltip.innerHTML = content;
            tooltip.style.display = 'block';
            var x, y;
            if (params.event && params.event.srcEvent) {{
                x = params.event.srcEvent.clientX;
                y = params.event.srcEvent.clientY;
            }} else if (params.pointer && params.pointer.DOM) {{
                var rect = container.getBoundingClientRect();
                x = rect.left + params.pointer.DOM.x;
                y = rect.top + params.pointer.DOM.y;
            }} else return;
            tooltip.style.left = (x + 15) + 'px';
            tooltip.style.top = (y + 15) + 'px';
            var rect = tooltip.getBoundingClientRect();
            if (rect.right > window.innerWidth) tooltip.style.left = (x - rect.width - 15) + 'px';
            if (rect.bottom > window.innerHeight) tooltip.style.top = (y - rect.height - 15) + 'px';
        }}

        function hideTooltip() {{ tooltip.style.display = 'none'; }}

        network.on('hoverEdge', function(params) {{
            var edge = edges.get(params.edge);
            if (edge && edge.title) showTooltip(edge.title, params);
        }});
        network.on('blurEdge', hideTooltip);
        network.on('hoverNode', function(params) {{
            var node = nodes.get(params.node);
            if (node && node.title) showTooltip(node.title, params);
        }});
        network.on('blurNode', hideTooltip);
        network.on('dragStart', hideTooltip);
        network.on('click', hideTooltip);
    </script>
</body>
</html>'''

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  Saved: {output_path}")


def main():
    """Main entry point."""
    print("=" * 70)
    print("Terpenoid Biosynthesis Network Visualization")
    print("=" * 70)

    # Initialize clients
    sparql_client = SPARQLClient()
    fuseki_client = FusekiClient(dataset="GXA-v2")

    # Check Fuseki
    print("\nChecking Fuseki server...")
    if not fuseki_client.is_available():
        print("ERROR: Fuseki server not available.")
        sys.exit(1)
    print("  Fuseki is available!")

    # Step 1: Get GO terms
    go_terms = get_terpenoid_go_terms(sparql_client)
    if not go_terms:
        print("ERROR: No GO terms found.")
        sys.exit(1)

    go_ids = {r["goId"] for r in go_terms if r.get("goId")}

    # Get GO hierarchy
    go_hierarchy = get_go_hierarchy(sparql_client, go_ids)

    # Step 2: Get genes from UniProt
    gene_results = get_arabidopsis_genes_from_uniprot(go_ids)
    if not gene_results:
        print("No genes found.")
        sys.exit(0)

    gene_symbols = {r["gene"] for r in gene_results if r.get("gene")}

    # Step 3: Get expression data
    expression_results = get_gene_expression(fuseki_client, gene_symbols)
    if not expression_results:
        print("No expression data found.")
        sys.exit(0)

    # Step 4: Build network
    nodes, edges = build_network(go_terms, go_hierarchy, gene_results, expression_results)

    # Step 5: Generate HTML
    output_path = Path(__file__).parent / "terpenoid_network.html"
    generate_html(
        nodes, edges,
        "Terpenoid Biosynthesis Network (Arabidopsis)",
        output_path,
    )

    print("\n" + "=" * 70)
    print("Done! Open the HTML file in a browser to view the network.")
    print("=" * 70)


if __name__ == "__main__":
    main()
