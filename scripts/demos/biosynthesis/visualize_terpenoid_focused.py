#!/usr/bin/env python3
"""
Focused network visualization for terpenoid biosynthesis genes.

A simplified view showing only:
- Genes directly annotated to terpenoid biosynthesis GO terms
- Assays where those genes are upregulated
- Direct connections (no study nodes, cleaner layout)

Usage:
    cd scripts/demos && python biosynthesis/visualize_terpenoid_focused.py

Output:
    biosynthesis/terpenoid_focused.html
"""

import sys
from pathlib import Path
from typing import List, Dict, Set
import requests
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sparql_client import SPARQLClient
from fuseki_client import FusekiClient

# Color scheme
COLORS = {
    "go_term": "#27ae60",      # Green
    "gene": "#3498db",         # Blue
    "assay": "#e67e22",        # Orange
    "study": "#9b59b6",        # Purple
}

SOURCE_COLORS = {
    "Ubergraph": "#27ae60",
    "UniProt": "#f39c12",
    "GXA": "#e74c3c",
}


def get_terpenoid_go_terms(client: SPARQLClient) -> List[Dict[str, str]]:
    """Get terpenoid biosynthetic process and direct children only."""
    print("Step 1: Querying Ubergraph for terpenoid GO terms...")

    # Get direct subclasses only (not transitive)
    query = """
    SELECT DISTINCT ?goId ?label WHERE {
        {
            # The root term itself
            BIND(obo:GO_0016114 AS ?term)
            ?term rdfs:label ?label .
            BIND("GO:0016114" AS ?goId)
        }
        UNION
        {
            # Direct children only
            ?term rdfs:subClassOf obo:GO_0016114 .
            ?term a owl:Class .
            ?term rdfs:label ?label .
            BIND(REPLACE(STR(?term), "http://purl.obolibrary.org/obo/GO_", "GO:") AS ?goId)
            FILTER(STRSTARTS(STR(?term), "http://purl.obolibrary.org/obo/GO_"))
        }
    }
    ORDER BY ?label
    """

    results = client.query_simple(query, endpoint="ubergraph")
    print(f"  Found {len(results)} GO terms (terpenoid biosynthetic process + direct children)")
    return results


def get_genes_from_uniprot(go_ids: Set[str]) -> List[Dict[str, str]]:
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
        print(f"  Error: {e}")
        return []


def get_gene_expression(fuseki: FusekiClient, gene_symbols: Set[str]) -> List[Dict[str, str]]:
    """Get expression data for genes - highly filtered for compact visualization."""
    print("\nStep 3: Querying GXA for gene expression...")

    gene_uris = " ".join(
        f'<https://www.ncbi.nlm.nih.gov/gene/{sym}>'
        for sym in gene_symbols
    )

    # Very stringent filters for compact network
    query = f'''
    SELECT DISTINCT ?studyId ?studyTitle ?assayId ?geneSymbol ?log2fc ?pvalue
    WHERE {{
        VALUES ?gene {{ {gene_uris} }}

        ?expr a biolink:GeneExpressionMixin ;
              biolink:subject ?assay ;
              biolink:object ?gene ;
              spokegenelab:log2fc ?log2fc ;
              spokegenelab:adj_p_value ?pvalue .

        FILTER(?log2fc > 3.0)
        FILTER(?pvalue < 0.001)

        ?study biolink:has_output ?assay ;
               biolink:name ?studyId ;
               biolink:in_taxon ?taxon .
        FILTER(?taxon = "Arabidopsis thaliana" || ?taxon = "3702")

        OPTIONAL {{ ?study spokegenelab:project_title ?studyTitle }}

        BIND(REPLACE(STR(?gene), ".*[/#]", "") AS ?geneSymbol)
        BIND(REPLACE(STR(?assay), ".*[/#]", "") AS ?assayId)
    }}
    ORDER BY DESC(?log2fc)
    '''

    results = fuseki.query_simple(query)
    print(f"  Found {len(results)} highly significant events (log2fc>3.0, p<0.001)")
    return results


def build_focused_network(
    go_terms: List[Dict[str, str]],
    gene_results: List[Dict[str, str]],
    expression_results: List[Dict[str, str]],
    max_assays_per_gene: int = 1,
    max_genes: int = 10,
) -> tuple[List[Dict], List[Dict]]:
    """Build a focused network with genes at center, limited for clarity."""
    print("\nStep 4: Building focused network...")

    nodes = []
    edges = []
    node_ids = set()

    # Lookups
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

    # Get genes with expression and their assays
    gene_assays: Dict[str, List[Dict]] = {}
    for r in expression_results:
        gene = r.get("geneSymbol", "")
        if gene:
            if gene not in gene_assays:
                gene_assays[gene] = []
            gene_assays[gene].append(r)

    # Sort genes by max fold change and limit
    gene_max_fc = {g: max(float(a.get("log2fc", 0)) for a in assays)
                   for g, assays in gene_assays.items()}
    top_genes = sorted(gene_max_fc.keys(), key=lambda g: gene_max_fc[g], reverse=True)[:max_genes]
    genes_with_expr = set(top_genes)

    # Limit assays per gene (keep highest fold changes)
    for gene in gene_assays:
        assays = gene_assays[gene]
        assays.sort(key=lambda a: float(a.get("log2fc", 0)), reverse=True)
        gene_assays[gene] = assays[:max_assays_per_gene]

    print(f"  Limiting to top {max_genes} genes, max {max_assays_per_gene} assays each")

    # Only include GO terms that have expressed genes
    go_terms_to_show = set()
    for gene in genes_with_expr:
        go_terms_to_show.update(gene_go_map.get(gene, set()))

    # 1. Add GO term nodes
    for go_id in go_terms_to_show:
        node_id = f"go:{go_id}"
        label = go_labels.get(go_id, go_id)
        # Shorten label for display
        short_label = label[:25] + "..." if len(label) > 25 else label
        nodes.append({
            "id": node_id,
            "label": f"{go_id}\n{short_label}",
            "type": "go_term",
            "title": f"<b>{go_id}</b><br>{label}<br><br>Source: Gene Ontology",
            "fullDescription": label,
            "source": "Gene Ontology (via Ubergraph)",
        })
        node_ids.add(node_id)

    # 2. Add gene nodes and gene->GO edges
    for gene in genes_with_expr:
        node_id = f"gene:{gene}"
        gene_name = gene_names.get(gene, "")
        go_ids_for_gene = gene_go_map.get(gene, set())

        title_parts = [f"<b>{gene}</b>"]
        if gene_name:
            title_parts.append(gene_name)
        if go_ids_for_gene:
            title_parts.append(f"<br>GO: {', '.join(sorted(go_ids_for_gene))}")
        title_parts.append("<br>Source: UniProt")

        desc_parts = []
        if gene_name:
            desc_parts.append(gene_name)
        if go_ids_for_gene:
            desc_parts.append(f"Annotated to: {', '.join(sorted(go_ids_for_gene))}")

        nodes.append({
            "id": node_id,
            "label": gene,
            "type": "gene",
            "title": "".join(title_parts),
            "fullDescription": " | ".join(desc_parts) if desc_parts else f"Arabidopsis gene {gene}",
            "source": "UniProt",
        })
        node_ids.add(node_id)

        # Gene -> GO edges
        for go_id in go_ids_for_gene:
            go_node = f"go:{go_id}"
            if go_node in node_ids:
                edges.append({
                    "from": node_id,
                    "to": go_node,
                    "label": "annotated_to",
                    "source": "UniProt",
                    "title": f"<b>annotated_to</b><br>{gene} → {go_id}<br>Source: UniProt",
                })

    # 3. Add study, assay nodes and edges (only for selected genes)
    studies_added = set()
    assays_added = set()
    for gene in genes_with_expr:
        gene_node = f"gene:{gene}"
        assay_list = gene_assays.get(gene, [])

        for r in assay_list:
            assay_id = r.get("assayId", "")
            study_id = r.get("studyId", "")
            study_title = r.get("studyTitle", "") or study_id
            log2fc = r.get("log2fc", "")
            pvalue = r.get("pvalue", "")

            study_node = f"study:{study_id}"
            assay_node = f"assay:{assay_id}"

            # Add study node
            if study_node not in node_ids:
                # Show study ID and truncated title in label
                short_title = study_title[:35] + "..." if len(study_title) > 35 else study_title
                nodes.append({
                    "id": study_node,
                    "label": f"{study_id}\n{short_title}",
                    "type": "study",
                    "title": f"<b>{study_id}</b><br>{study_title}<br><br>Source: GXA (Gene Expression Atlas)",
                    "fullDescription": study_title,  # Store full description for details panel
                    "source": "GXA (Gene Expression Atlas)",
                })
                node_ids.add(study_node)
                studies_added.add(study_id)

            # Add assay node
            if assay_node not in node_ids:
                short_assay = assay_id.split("-")[-1] if "-" in assay_id else assay_id
                nodes.append({
                    "id": assay_node,
                    "label": short_assay,
                    "type": "assay",
                    "title": f"<b>{assay_id}</b><br>Study: {study_id}<br><br>Source: GXA",
                    "fullDescription": f"Experimental contrast from study {study_id}",
                    "source": "GXA (Gene Expression Atlas)",
                    "studyId": study_id,
                })
                node_ids.add(assay_node)
                assays_added.add(assay_id)

                # Study -> Assay edge
                edges.append({
                    "from": study_node,
                    "to": assay_node,
                    "label": "has_assay",
                    "source": "GXA",
                    "title": f"<b>has_assay</b><br>{study_id} → {assay_id}<br>Source: GXA",
                })

            # Assay -> Gene edge with fold change and p-value
            try:
                fc_val = float(log2fc)
                pval = float(pvalue)
                label = f"↑{fc_val:.1f} (p={pval:.1e})"
            except:
                label = f"↑ (p={pvalue})"

            edges.append({
                "from": assay_node,
                "to": gene_node,
                "label": label,
                "source": "GXA",
                "title": f"<b>upregulated</b><br>log2FC: {log2fc}<br>adj. p-value: {pvalue}<br><br>Source: GXA",
            })

    # Filter to only include nodes with connections
    connected_node_ids = set()
    for edge in edges:
        connected_node_ids.add(edge["from"])
        connected_node_ids.add(edge["to"])

    nodes = [n for n in nodes if n["id"] in connected_node_ids]
    node_ids = {n["id"] for n in nodes}

    # Also filter edges to only connected nodes (should be all, but safety check)
    edges = [e for e in edges if e["from"] in node_ids and e["to"] in node_ids]

    # Recount by type
    go_count = len([n for n in nodes if n["type"] == "go_term"])
    gene_count = len([n for n in nodes if n["type"] == "gene"])
    study_count = len([n for n in nodes if n["type"] == "study"])
    assay_count = len([n for n in nodes if n["type"] == "assay"])

    print(f"  Network: {len(nodes)} nodes, {len(edges)} edges (connected only)")
    print(f"    GO terms: {go_count}")
    print(f"    Genes: {gene_count}")
    print(f"    Studies: {study_count}")
    print(f"    Assays: {assay_count}")

    return nodes, edges


def generate_html(nodes: List[Dict], edges: List[Dict], title: str, output_path: Path) -> None:
    """Generate the HTML visualization."""
    print("\nStep 5: Generating HTML...")

    # Prepare vis.js nodes
    vis_nodes = []
    for node in nodes:
        node_type = node.get("type", "gene")
        color = COLORS.get(node_type, "#95a5a6")

        shape_map = {"go_term": "diamond", "gene": "dot", "study": "triangle", "assay": "box"}
        size_map = {"go_term": 25, "gene": 20, "study": 22, "assay": 12}

        vis_nodes.append({
            "id": node["id"],
            "label": node["label"],
            "color": {"background": color, "border": color,
                      "highlight": {"background": "#f1c40f", "border": "#f39c12"}},
            "shape": shape_map.get(node_type, "dot"),
            "size": size_map.get(node_type, 15),
            "font": {"size": 11, "color": "#2c3e50", "multi": True},
            "title": node.get("title", node["label"]),
            "fullDescription": node.get("fullDescription", ""),
            "source": node.get("source", ""),
            "nodeType": node_type,
        })

    # Prepare vis.js edges
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
            "font": {"size": 10, "color": "#333", "strokeWidth": 2, "strokeColor": "#fff"},
            "smooth": {"type": "continuous"},
            "arrows": {"to": {"enabled": True, "scaleFactor": 0.5}},
        })

    nodes_json = json.dumps(vis_nodes)
    edges_json = json.dumps(vis_edges)

    # Legend
    node_legend = " ".join([
        f'<span style="display:inline-flex;align-items:center;margin-right:20px;">'
        f'<span style="display:inline-block;width:16px;height:16px;background:{color};'
        f'border-radius:{"50%" if typ == "gene" else "3px"};margin-right:6px;"></span>'
        f'{typ.replace("_", " ").title()}</span>'
        for typ, color in COLORS.items()
    ])

    source_legend = " ".join([
        f'<span style="display:inline-flex;align-items:center;margin-right:20px;">'
        f'<span style="display:inline-block;width:24px;height:3px;background:{color};margin-right:6px;"></span>'
        f'{src}</span>'
        for src, color in SOURCE_COLORS.items()
    ])

    html = f'''<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0; padding: 20px; background: #f8f9fa;
        }}
        h1 {{ text-align: center; color: #2c3e50; margin-bottom: 8px; font-size: 24px; }}
        .subtitle {{ text-align: center; color: #666; margin-bottom: 15px; font-size: 14px; }}
        .legend {{ text-align: center; margin-bottom: 12px; font-size: 13px; color: #555; }}
        .legend div {{ margin: 4px 0; }}
        .controls {{ text-align: center; margin-bottom: 10px; }}
        .btn {{
            padding: 8px 16px; font-size: 13px; border: none; border-radius: 5px;
            cursor: pointer; margin: 0 5px; transition: all 0.2s;
        }}
        .btn.active {{ background: #27ae60; color: white; }}
        .btn.inactive {{ background: #e0e0e0; color: #555; }}
        .btn:hover {{ opacity: 0.85; }}
        .instructions {{ text-align: center; font-size: 12px; color: #888; margin-bottom: 8px; }}
        .main-container {{
            display: flex; gap: 20px; align-items: flex-start;
        }}
        #network {{
            flex: 1; height: 650px; border: 1px solid #ddd;
            background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        #details-panel {{
            width: 320px; min-height: 200px; max-height: 650px; overflow-y: auto;
            background: white; border: 1px solid #ddd; border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1); padding: 15px;
        }}
        #details-panel h3 {{
            margin: 0 0 10px 0; color: #2c3e50; font-size: 16px;
            border-bottom: 2px solid #3498db; padding-bottom: 8px;
        }}
        #details-panel .detail-type {{
            display: inline-block; padding: 3px 8px; border-radius: 4px;
            font-size: 11px; font-weight: bold; text-transform: uppercase;
            margin-bottom: 10px;
        }}
        #details-panel .detail-type.go_term {{ background: #27ae60; color: white; }}
        #details-panel .detail-type.gene {{ background: #3498db; color: white; }}
        #details-panel .detail-type.study {{ background: #9b59b6; color: white; }}
        #details-panel .detail-type.assay {{ background: #e67e22; color: white; }}
        #details-panel .detail-label {{
            font-size: 12px; color: #888; margin-top: 12px; margin-bottom: 4px;
        }}
        #details-panel .detail-value {{
            font-size: 14px; color: #2c3e50; line-height: 1.5;
        }}
        #details-panel .detail-value.description {{
            background: #f8f9fa; padding: 10px; border-radius: 4px;
            border-left: 3px solid #3498db;
        }}
        #details-panel .placeholder {{
            color: #aaa; font-style: italic; text-align: center; padding: 40px 20px;
        }}
        .summary {{ text-align: center; margin-top: 12px; font-size: 13px; color: #666; }}
        #tooltip {{
            position: fixed; background: rgba(40,44,52,0.95); color: white;
            padding: 10px 14px; border-radius: 6px; font-size: 13px; line-height: 1.5;
            max-width: 350px; pointer-events: none; z-index: 10000; display: none;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }}
        #tooltip b {{ color: #f1c40f; }}
        .vis-tooltip {{ display: none !important; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div class="subtitle">Genes annotated to terpenoid biosynthesis showing significant upregulation</div>
    <div class="legend">
        <div><b>Nodes:</b> {node_legend}</div>
        <div><b>Data Sources:</b> {source_legend}</div>
    </div>
    <div class="controls">
        <button id="physicsBtn" class="btn inactive" onclick="togglePhysics()">⚡ Auto-Layout: OFF</button>
        <button class="btn inactive" onclick="resetLayout()">🔄 Reset</button>
        <button class="btn inactive" onclick="network.fit({{animation:true}})">🔍 Fit</button>
    </div>
    <div class="instructions">Drag nodes • Scroll to zoom • Click node for details</div>
    <div class="main-container">
        <div id="network"></div>
        <div id="details-panel">
            <div class="placeholder">Click a node to see details</div>
        </div>
    </div>
    <div id="tooltip"></div>
    <div class="summary">
        {len(nodes)} nodes • {len(edges)} connections<br>
        Gene Ontology (Ubergraph) → UniProt annotations → GXA expression
    </div>
    <script>
        var nodes = new vis.DataSet({nodes_json});
        var edges = new vis.DataSet({edges_json});
        var container = document.getElementById('network');
        var options = {{
            nodes: {{ borderWidth: 2, shadow: true }},
            edges: {{ shadow: true, smooth: {{ type: 'continuous' }} }},
            physics: {{
                enabled: true,
                barnesHut: {{ gravitationalConstant: -5000, springLength: 150, springConstant: 0.04 }},
                stabilization: {{ iterations: 200, fit: true }}
            }},
            interaction: {{ hover: true, tooltipDelay: 100 }}
        }};
        var network = new vis.Network(container, {{ nodes: nodes, edges: edges }}, options);
        var physicsOn = false;

        network.on("stabilizationIterationsDone", function() {{
            physicsOn = false;
            network.setOptions({{ physics: {{ enabled: false }} }});
            updateBtn();
        }});

        function togglePhysics() {{
            physicsOn = !physicsOn;
            network.setOptions({{ physics: {{ enabled: physicsOn }} }});
            updateBtn();
        }}
        function updateBtn() {{
            var b = document.getElementById('physicsBtn');
            b.textContent = physicsOn ? '⚡ Auto-Layout: ON' : '⚡ Auto-Layout: OFF';
            b.className = physicsOn ? 'btn active' : 'btn inactive';
        }}
        function resetLayout() {{
            physicsOn = true;
            network.setOptions({{ physics: {{ enabled: true }} }});
            updateBtn();
            var pos = network.getPositions();
            var upd = [];
            for (var id in pos) upd.push({{ id: id, x: undefined, y: undefined }});
            nodes.update(upd);
            network.stabilize(200);
        }}

        var tooltip = document.getElementById('tooltip');
        function showTip(content, e) {{
            if (!content) return;
            tooltip.innerHTML = content;
            tooltip.style.display = 'block';
            tooltip.style.left = (e.event.srcEvent.clientX + 15) + 'px';
            tooltip.style.top = (e.event.srcEvent.clientY + 15) + 'px';
        }}
        function hideTip() {{ tooltip.style.display = 'none'; }}

        network.on('hoverNode', function(e) {{ var n = nodes.get(e.node); if (n) showTip(n.title, e); }});
        network.on('blurNode', hideTip);
        network.on('hoverEdge', function(e) {{ var ed = edges.get(e.edge); if (ed) showTip(ed.title, e); }});
        network.on('blurEdge', hideTip);
        network.on('dragStart', hideTip);

        // Click handler for details panel
        var detailsPanel = document.getElementById('details-panel');

        network.on('click', function(params) {{
            hideTip();
            if (params.nodes.length > 0) {{
                var nodeId = params.nodes[0];
                var node = nodes.get(nodeId);
                if (node) {{
                    showDetails(node);
                }}
            }} else {{
                clearDetails();
            }}
        }});

        function showDetails(node) {{
            var typeLabel = node.nodeType.replace('_', ' ');
            var idParts = node.id.split(':');
            var displayId = idParts.length > 1 ? idParts.slice(1).join(':') : node.id;

            var html = '<span class="detail-type ' + node.nodeType + '">' + typeLabel + '</span>';
            html += '<h3>' + displayId + '</h3>';

            if (node.fullDescription) {{
                html += '<div class="detail-label">Description</div>';
                html += '<div class="detail-value description">' + node.fullDescription + '</div>';
            }}

            if (node.source) {{
                html += '<div class="detail-label">Data Source</div>';
                html += '<div class="detail-value">' + node.source + '</div>';
            }}

            // Show connected nodes
            var connectedEdges = network.getConnectedEdges(node.id);
            var connectedNodes = network.getConnectedNodes(node.id);
            if (connectedNodes.length > 0) {{
                html += '<div class="detail-label">Connections (' + connectedNodes.length + ')</div>';
                html += '<div class="detail-value">';
                connectedNodes.forEach(function(connId) {{
                    var connNode = nodes.get(connId);
                    if (connNode) {{
                        var connIdParts = connId.split(':');
                        var connDisplay = connIdParts.length > 1 ? connIdParts.slice(1).join(':') : connId;
                        html += '<div style="margin:3px 0;">• ' + connDisplay + ' <span style="color:#888;">(' + connNode.nodeType.replace('_',' ') + ')</span></div>';
                    }}
                }});
                html += '</div>';
            }}

            detailsPanel.innerHTML = html;
        }}

        function clearDetails() {{
            detailsPanel.innerHTML = '<div class="placeholder">Click a node to see details</div>';
        }}
    </script>
</body>
</html>'''

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Saved: {output_path}")


def main():
    print("=" * 70)
    print("Focused Terpenoid Biosynthesis Network")
    print("=" * 70)

    sparql = SPARQLClient()
    fuseki = FusekiClient(dataset="GXA-v2")

    print("\nChecking Fuseki...")
    if not fuseki.is_available():
        print("ERROR: Fuseki not available")
        sys.exit(1)
    print("  OK!")

    # Step 1: GO terms
    go_terms = get_terpenoid_go_terms(sparql)
    if not go_terms:
        sys.exit(1)
    go_ids = {r["goId"] for r in go_terms}

    # Step 2: Genes
    gene_results = get_genes_from_uniprot(go_ids)
    if not gene_results:
        sys.exit(0)
    gene_symbols = {r["gene"] for r in gene_results}

    # Step 3: Expression
    expression_results = get_gene_expression(fuseki, gene_symbols)
    if not expression_results:
        print("No significant expression found.")
        sys.exit(0)

    # Step 4: Build network
    nodes, edges = build_focused_network(go_terms, gene_results, expression_results)

    # Step 5: Generate HTML
    output_path = Path(__file__).parent / "terpenoid_focused.html"
    generate_html(nodes, edges, "Terpenoid Biosynthesis: Gene-Assay Network", output_path)

    print("\n" + "=" * 70)
    print("Done! Open terpenoid_focused.html in a browser.")
    print("=" * 70)


if __name__ == "__main__":
    main()
