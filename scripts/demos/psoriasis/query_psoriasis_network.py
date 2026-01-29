#!/usr/bin/env python3
"""
Psoriasis Gene Expression Network Analysis

Integrates data from multiple sources to create a comprehensive view of
genes differentially expressed in psoriasis:

1. GXA (Gene Expression Atlas): Psoriasis studies and upregulated genes
2. Ubergraph: GO terms associated with biological processes
3. Wikidata: Gene-disease associations and annotations

This demonstrates cross-layer knowledge graph integration for disease analysis.

Usage:
    cd scripts/demos && python psoriasis/query_psoriasis_network.py

Output:
    psoriasis/psoriasis_network.html - Interactive visualization
    psoriasis/psoriasis_genes.csv - Gene expression data
"""

import csv
import json
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sparql_client import SPARQLClient
from fuseki_client import FusekiClient


# Color scheme for visualization
COLORS = {
    "disease": "#e74c3c",      # Red
    "study": "#9b59b6",        # Purple
    "assay": "#3498db",        # Blue
    "gene": "#2ecc71",         # Green
    "go_term": "#f39c12",      # Orange
}

SOURCE_COLORS = {
    "GXA": "#e74c3c",
    "Gene Ontology": "#27ae60",
}


def get_psoriasis_studies(fuseki: FusekiClient) -> List[Dict[str, str]]:
    """Get psoriasis studies from GXA."""
    print("Step 1: Querying GXA for psoriasis studies...")

    query = '''
    SELECT DISTINCT ?studyId ?studyTitle ?diseaseName
    WHERE {
        ?study a biolink:Study ;
               biolink:name ?studyId ;
               biolink:studies ?disease .

        ?disease a biolink:Disease ;
                 biolink:name ?diseaseName .

        FILTER(CONTAINS(LCASE(?diseaseName), 'psoriasis'))

        OPTIONAL { ?study spokegenelab:project_title ?studyTitle }
    }
    ORDER BY ?studyId
    '''

    results = fuseki.query_simple(query)
    print(f"  Found {len(results)} psoriasis studies")
    return results


def get_psoriasis_upregulated_genes(
    fuseki: FusekiClient,
    study_ids: List[str],
    min_log2fc: float = 1.5,
    max_pvalue: float = 0.01,
    limit_per_study: int = 50,
) -> List[Dict[str, Any]]:
    """
    Get significantly upregulated genes in psoriasis studies.

    Args:
        fuseki: FusekiClient instance
        study_ids: List of study IDs to query
        min_log2fc: Minimum log2 fold change (positive for upregulation)
        max_pvalue: Maximum adjusted p-value
        limit_per_study: Max genes per study to prevent overload
    """
    print(f"\nStep 2: Querying upregulated genes (log2fc>{min_log2fc}, p<{max_pvalue})...")

    # Build study filter
    study_values = " ".join(f'spokegenelab:{sid}' for sid in study_ids)

    query = f'''
    SELECT DISTINCT ?studyId ?assayId ?geneSymbol ?log2fc ?pvalue ?testGroup ?refGroup
    WHERE {{
        VALUES ?study {{ {study_values} }}

        ?study biolink:name ?studyId ;
               biolink:has_output ?assay .

        ?assay biolink:name ?assayId .
        OPTIONAL {{ ?assay spokegenelab:test_group_label ?testGroup }}
        OPTIONAL {{ ?assay spokegenelab:reference_group_label ?refGroup }}

        ?expr a biolink:GeneExpressionMixin ;
              biolink:subject ?assay ;
              biolink:object ?gene ;
              spokegenelab:log2fc ?log2fc ;
              spokegenelab:adj_p_value ?pvalue .

        ?gene biolink:symbol ?geneSymbol .

        FILTER(?log2fc > {min_log2fc})
        FILTER(?pvalue < {max_pvalue})
    }}
    ORDER BY DESC(?log2fc)
    LIMIT {limit_per_study * len(study_ids)}
    '''

    results = fuseki.query_simple(query)

    # Convert to proper types
    processed = []
    for r in results:
        try:
            processed.append({
                "studyId": r.get("studyId", ""),
                "assayId": r.get("assayId", ""),
                "geneSymbol": r.get("geneSymbol", ""),
                "log2fc": float(r.get("log2fc", 0)),
                "pvalue": float(r.get("pvalue", 1)),
                "testGroup": r.get("testGroup", ""),
                "refGroup": r.get("refGroup", ""),
            })
        except (ValueError, TypeError):
            continue

    print(f"  Found {len(processed)} upregulated gene-assay pairs")
    return processed


def get_go_terms_from_enrichments(
    enrichments: List[Dict[str, str]],
) -> Dict[str, Dict[str, str]]:
    """
    Extract GO terms from enrichment results.
    Returns dict mapping GO ID to label.
    """
    go_terms: Dict[str, Dict[str, str]] = {}

    for e in enrichments:
        go_id = e.get("goId", "")
        go_name = e.get("goName", "")
        if go_id and go_id.startswith("GO:"):
            go_terms[go_id] = {
                "goId": go_id,
                "goLabel": go_name if go_name != go_id else go_id,
            }

    return go_terms


def get_genes_for_enriched_go_terms(
    fuseki: FusekiClient,
    study_ids: List[str],
    go_terms: Dict[str, Dict[str, str]],
) -> Dict[str, List[Dict[str, str]]]:
    """
    Get genes associated with enriched GO terms from GXA.
    This links genes to GO terms based on which terms were enriched in their assays.
    """
    print(f"\nStep 3b: Linking genes to enriched GO terms...")

    if not go_terms:
        return {}

    # Build GO term filter
    go_ids = list(go_terms.keys())[:20]  # Limit for performance
    go_values = " ".join(f'"{gid}"' for gid in go_ids)
    study_values = " ".join(f'spokegenelab:{sid}' for sid in study_ids)

    # Find which genes are in assays that have specific GO enrichments
    query = f'''
    SELECT DISTINCT ?geneSymbol ?goId
    WHERE {{
        VALUES ?study {{ {study_values} }}
        VALUES ?goIdVal {{ {go_values} }}

        ?study biolink:has_output ?assay .

        # Gene expression in this assay
        ?expr a biolink:GeneExpressionMixin ;
              biolink:subject ?assay ;
              biolink:object ?gene ;
              spokegenelab:log2fc ?log2fc ;
              spokegenelab:adj_p_value ?pvalue .

        ?gene biolink:symbol ?geneSymbol .
        FILTER(?log2fc > 1.5)
        FILTER(?pvalue < 0.01)

        # GO enrichment in same assay
        ?assay biolink:has_output ?enrichment .
        ?enrichment biolink:participates_in ?goTerm .
        ?goTerm biolink:name ?goId .
        FILTER(?goId = ?goIdVal)
    }}
    LIMIT 500
    '''

    try:
        results = fuseki.query_simple(query)

        gene_go_map: Dict[str, List[Dict[str, str]]] = {}
        for r in results:
            symbol = r.get("geneSymbol", "")
            go_id = r.get("goId", "")
            if symbol and go_id:
                if symbol not in gene_go_map:
                    gene_go_map[symbol] = []
                # Add GO term info
                go_info = go_terms.get(go_id, {"goId": go_id, "goLabel": go_id})
                if go_info not in gene_go_map[symbol]:
                    gene_go_map[symbol].append(go_info)

        total_associations = sum(len(terms) for terms in gene_go_map.values())
        print(f"  Found {total_associations} gene-GO associations for {len(gene_go_map)} genes")
        return gene_go_map

    except Exception as e:
        print(f"  Warning: GO-gene linking failed: {e}")
        return {}


def get_psoriasis_go_enrichments(
    fuseki: FusekiClient,
    study_ids: List[str],
    max_pvalue: float = 0.05,
) -> List[Dict[str, str]]:
    """Get GO term enrichments from psoriasis studies."""
    print(f"\nStep 4: Querying GO enrichments for psoriasis studies...")

    study_values = " ".join(f'spokegenelab:{sid}' for sid in study_ids)

    query = f'''
    SELECT DISTINCT ?studyId ?goId ?goName ?pvalue
    WHERE {{
        VALUES ?study {{ {study_values} }}

        ?study biolink:name ?studyId ;
               biolink:has_output ?assay .

        ?assay biolink:has_output ?enrichment .

        ?enrichment biolink:participates_in ?goTerm ;
                    spokegenelab:adj_p_value ?pvalue .

        ?goTerm biolink:name ?goId .
        OPTIONAL {{ ?goTerm biolink:id ?goName }}

        FILTER(?pvalue < {max_pvalue})
    }}
    ORDER BY ?pvalue
    LIMIT 100
    '''

    results = fuseki.query_simple(query)
    print(f"  Found {len(results)} GO enrichments")
    return results


def build_network(
    studies: List[Dict[str, str]],
    genes: List[Dict[str, Any]],
    gene_go_map: Dict[str, List[Dict[str, str]]],
    enrichments: List[Dict[str, str]],
    max_genes: int = 30,
    max_go_terms: int = 15,
) -> Tuple[List[Dict], List[Dict]]:
    """Build network graph for visualization."""
    print(f"\nStep 5: Building network (max {max_genes} genes, {max_go_terms} GO terms)...")

    nodes = []
    edges = []
    node_ids = set()

    # Study lookup
    study_titles = {s["studyId"]: s.get("studyTitle", s["studyId"]) for s in studies}

    # 1. Disease node (central)
    disease_node = "disease:psoriasis"
    nodes.append({
        "id": disease_node,
        "label": "Psoriasis",
        "type": "disease",
        "title": "<b>Psoriasis</b><br>EFO:0000676<br><br>Chronic inflammatory skin condition",
        "fullDescription": "Psoriasis - chronic autoimmune skin disease characterized by patches of abnormal skin",
        "source": "GXA",
    })
    node_ids.add(disease_node)

    # 2. Study nodes
    study_ids_added = set()
    for study in studies[:8]:  # Limit studies for clarity
        study_id = study["studyId"]
        if study_id in study_ids_added:
            continue
        study_ids_added.add(study_id)

        node_id = f"study:{study_id}"
        title = study_titles.get(study_id, study_id)
        short_title = title[:40] + "..." if len(title) > 40 else title

        nodes.append({
            "id": node_id,
            "label": f"{study_id}\n{short_title}",
            "type": "study",
            "title": f"<b>{study_id}</b><br>{title}<br><br>Source: GXA",
            "fullDescription": title,
            "source": "GXA",
        })
        node_ids.add(node_id)

        # Disease -> Study edge
        edges.append({
            "from": disease_node,
            "to": node_id,
            "label": "studied_in",
            "source": "GXA",
            "title": f"<b>studied_in</b><br>Psoriasis studied in {study_id}",
        })

    # 3. Gene nodes (top N by fold change)
    # Group genes by symbol, keep best result
    gene_best: Dict[str, Dict[str, Any]] = {}
    for g in genes:
        symbol = g["geneSymbol"]
        if symbol not in gene_best or g["log2fc"] > gene_best[symbol]["log2fc"]:
            gene_best[symbol] = g

    # Sort by fold change and take top N
    sorted_genes = sorted(gene_best.values(), key=lambda x: x["log2fc"], reverse=True)
    top_genes = sorted_genes[:max_genes]

    assays_added = set()
    for gene in top_genes:
        symbol = gene["geneSymbol"]
        study_id = gene["studyId"]
        assay_id = gene["assayId"]

        # Sanitize assay ID for use as node ID (remove special chars)
        assay_id_safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in assay_id)

        # Gene node
        gene_node = f"gene:{symbol}"
        if gene_node not in node_ids:
            go_terms = gene_go_map.get(symbol, [])
            go_str = ", ".join(t["goId"] for t in go_terms[:3])

            nodes.append({
                "id": gene_node,
                "label": symbol,
                "type": "gene",
                "title": f"<b>{symbol}</b><br>log2FC: {gene['log2fc']:.2f}<br>p-value: {gene['pvalue']:.2e}<br>GO: {go_str or 'N/A'}<br><br>Source: GXA",
                "fullDescription": f"Gene {symbol} - upregulated in psoriasis (log2FC={gene['log2fc']:.2f})",
                "source": "GXA",
                "log2fc": gene["log2fc"],
            })
            node_ids.add(gene_node)

        # Assay node (simplified)
        if assay_id and study_id in study_ids_added:
            assay_node = f"assay:{assay_id_safe}"
            if assay_node not in assays_added:
                short_assay = assay_id.split("-")[-1] if "-" in assay_id else assay_id
                # Truncate long assay labels
                if len(short_assay) > 20:
                    short_assay = short_assay[:17] + "..."
                test_group = gene.get("testGroup", "")
                ref_group = gene.get("refGroup", "")

                nodes.append({
                    "id": assay_node,
                    "label": short_assay,
                    "type": "assay",
                    "title": f"<b>{assay_id}</b><br>Test: {test_group}<br>Ref: {ref_group}<br><br>Source: GXA",
                    "fullDescription": f"Experimental contrast: {test_group} vs {ref_group}",
                    "source": "GXA",
                })
                node_ids.add(assay_node)
                assays_added.add(assay_node)

                # Study -> Assay edge
                study_node = f"study:{study_id}"
                if study_node in node_ids:
                    edges.append({
                        "from": study_node,
                        "to": assay_node,
                        "label": "has_assay",
                        "source": "GXA",
                        "title": f"<b>has_assay</b><br>Study produces experimental contrast",
                    })

            # Assay -> Gene edge
            assay_node = f"assay:{assay_id_safe}"
            if assay_node in node_ids:
                edges.append({
                    "from": assay_node,
                    "to": gene_node,
                    "label": f"↑{gene['log2fc']:.1f}",
                    "source": "GXA",
                    "title": f"<b>upregulated</b><br>log2FC: {gene['log2fc']:.2f}<br>p-value: {gene['pvalue']:.2e}",
                })

    # 4. GO term nodes
    go_term_counts: Dict[str, Dict[str, Any]] = {}
    for symbol, terms in gene_go_map.items():
        if f"gene:{symbol}" in node_ids:  # Only for genes in network
            for term in terms:
                go_id = term["goId"]
                if go_id not in go_term_counts:
                    go_term_counts[go_id] = {
                        "goId": go_id,
                        "goLabel": term["goLabel"],
                        "genes": [],
                    }
                go_term_counts[go_id]["genes"].append(symbol)

    # Sort by number of genes and take top N
    sorted_go = sorted(go_term_counts.values(), key=lambda x: len(x["genes"]), reverse=True)
    top_go = sorted_go[:max_go_terms]

    for go in top_go:
        if len(go["genes"]) < 2:  # Skip GO terms with only 1 gene
            continue

        go_id = go["goId"]
        go_node = f"go:{go_id}"
        label = go["goLabel"]
        short_label = label[:25] + "..." if len(label) > 25 else label

        nodes.append({
            "id": go_node,
            "label": f"{go_id}\n{short_label}",
            "type": "go_term",
            "title": f"<b>{go_id}</b><br>{label}<br><br>Associated genes: {', '.join(go['genes'])}<br><br>Source: GXA Enrichment",
            "fullDescription": label,
            "source": "Gene Ontology",
        })
        node_ids.add(go_node)

        # Gene -> GO edges
        for symbol in go["genes"]:
            gene_node = f"gene:{symbol}"
            if gene_node in node_ids:
                edges.append({
                    "from": gene_node,
                    "to": go_node,
                    "label": "participates_in",
                    "source": "Gene Ontology",
                    "title": f"<b>participates_in</b><br>{symbol} → {go_id}<br>Source: Wikidata/GO",
                })

    # Summary
    node_counts = {}
    for n in nodes:
        t = n["type"]
        node_counts[t] = node_counts.get(t, 0) + 1

    print(f"  Network: {len(nodes)} nodes, {len(edges)} edges")
    for t, c in sorted(node_counts.items()):
        print(f"    {t}: {c}")

    return nodes, edges


def generate_html(
    nodes: List[Dict],
    edges: List[Dict],
    title: str,
    output_path: Path,
) -> None:
    """Generate interactive HTML visualization."""
    print(f"\nStep 6: Generating HTML...")

    # Prepare vis.js nodes
    vis_nodes = []
    for node in nodes:
        node_type = node.get("type", "gene")
        color = COLORS.get(node_type, "#95a5a6")

        shape_map = {
            "disease": "star",
            "study": "triangle",
            "assay": "box",
            "gene": "dot",
            "go_term": "diamond",
        }
        size_map = {
            "disease": 35,
            "study": 22,
            "assay": 12,
            "gene": 18,
            "go_term": 20,
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
            "font": {"size": 9, "color": "#333", "strokeWidth": 2, "strokeColor": "#fff"},
            "smooth": {"type": "continuous"},
            "arrows": {"to": {"enabled": True, "scaleFactor": 0.5}},
        })

    nodes_json = json.dumps(vis_nodes)
    edges_json = json.dumps(vis_edges)

    # Legend HTML
    node_legend = " ".join([
        f'<span style="display:inline-flex;align-items:center;margin-right:15px;">'
        f'<span style="display:inline-block;width:14px;height:14px;background:{color};'
        f'border-radius:{"50%" if typ == "gene" else "3px"};margin-right:5px;"></span>'
        f'{typ.replace("_", " ").title()}</span>'
        for typ, color in COLORS.items()
    ])

    source_legend = " ".join([
        f'<span style="display:inline-flex;align-items:center;margin-right:15px;">'
        f'<span style="display:inline-block;width:20px;height:3px;background:{color};margin-right:5px;"></span>'
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
        .legend {{ text-align: center; margin-bottom: 10px; font-size: 12px; color: #555; }}
        .legend div {{ margin: 4px 0; }}
        .controls {{ text-align: center; margin-bottom: 8px; }}
        .btn {{
            padding: 8px 14px; font-size: 12px; border: none; border-radius: 5px;
            cursor: pointer; margin: 0 4px; transition: all 0.2s;
        }}
        .btn.active {{ background: #27ae60; color: white; }}
        .btn.inactive {{ background: #e0e0e0; color: #555; }}
        .instructions {{ text-align: center; font-size: 11px; color: #888; margin-bottom: 8px; }}
        .main-container {{ display: flex; gap: 20px; align-items: flex-start; }}
        #network {{
            flex: 1; height: 650px; border: 1px solid #ddd;
            background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        #details-panel {{
            width: 300px; min-height: 200px; max-height: 650px; overflow-y: auto;
            background: white; border: 1px solid #ddd; border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1); padding: 15px;
        }}
        #details-panel h3 {{
            margin: 0 0 10px 0; color: #2c3e50; font-size: 15px;
            border-bottom: 2px solid #3498db; padding-bottom: 8px;
        }}
        #details-panel .detail-type {{
            display: inline-block; padding: 2px 8px; border-radius: 4px;
            font-size: 10px; font-weight: bold; text-transform: uppercase; margin-bottom: 8px;
        }}
        #details-panel .detail-type.disease {{ background: #e74c3c; color: white; }}
        #details-panel .detail-type.study {{ background: #9b59b6; color: white; }}
        #details-panel .detail-type.assay {{ background: #3498db; color: white; }}
        #details-panel .detail-type.gene {{ background: #2ecc71; color: white; }}
        #details-panel .detail-type.go_term {{ background: #f39c12; color: white; }}
        #details-panel .detail-label {{ font-size: 11px; color: #888; margin-top: 10px; margin-bottom: 3px; }}
        #details-panel .detail-value {{ font-size: 13px; color: #2c3e50; line-height: 1.4; }}
        #details-panel .detail-value.description {{
            background: #f8f9fa; padding: 8px; border-radius: 4px;
            border-left: 3px solid #3498db;
        }}
        #details-panel .placeholder {{ color: #aaa; font-style: italic; text-align: center; padding: 30px 15px; }}
        .summary {{ text-align: center; margin-top: 10px; font-size: 12px; color: #666; }}
        #tooltip {{
            position: fixed; background: rgba(40,44,52,0.95); color: white;
            padding: 10px 14px; border-radius: 6px; font-size: 12px; line-height: 1.4;
            max-width: 320px; pointer-events: none; z-index: 10000; display: none;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }}
        #tooltip b {{ color: #f1c40f; }}
        .vis-tooltip {{ display: none !important; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div class="subtitle">Multi-source integration: GXA Expression + GO Enrichment Analysis</div>
    <div class="legend">
        <div><b>Nodes:</b> {node_legend}</div>
        <div><b>Data Sources:</b> {source_legend}</div>
    </div>
    <div class="controls">
        <button id="physicsBtn" class="btn inactive" onclick="togglePhysics()">Auto-Layout: OFF</button>
        <button class="btn inactive" onclick="resetLayout()">Reset</button>
        <button class="btn inactive" onclick="network.fit({{animation:true}})">Fit</button>
    </div>
    <div class="instructions">Drag nodes to rearrange | Scroll to zoom | Click for details</div>
    <div class="main-container">
        <div id="network"></div>
        <div id="details-panel">
            <div class="placeholder">Click a node to see details</div>
        </div>
    </div>
    <div id="tooltip"></div>
    <div class="summary">
        {len(nodes)} nodes | {len(edges)} connections<br>
        GXA (Expression + GO Enrichment)
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
                barnesHut: {{ gravitationalConstant: -4000, springLength: 140, springConstant: 0.04 }},
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
            b.textContent = physicsOn ? 'Auto-Layout: ON' : 'Auto-Layout: OFF';
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

        var detailsPanel = document.getElementById('details-panel');

        network.on('click', function(params) {{
            hideTip();
            if (params.nodes.length > 0) {{
                var nodeId = params.nodes[0];
                var node = nodes.get(nodeId);
                if (node) showDetails(node);
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

            var connectedNodes = network.getConnectedNodes(node.id);
            if (connectedNodes.length > 0) {{
                html += '<div class="detail-label">Connections (' + connectedNodes.length + ')</div>';
                html += '<div class="detail-value">';
                connectedNodes.forEach(function(connId) {{
                    var connNode = nodes.get(connId);
                    if (connNode) {{
                        var connIdParts = connId.split(':');
                        var connDisplay = connIdParts.length > 1 ? connIdParts.slice(1).join(':') : connId;
                        html += '<div style="margin:2px 0;">• ' + connDisplay + ' <span style="color:#888;font-size:10px;">(' + connNode.nodeType.replace('_',' ') + ')</span></div>';
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


def export_genes_csv(
    genes: List[Dict[str, Any]],
    gene_go_map: Dict[str, List[Dict[str, str]]],
    output_path: Path,
) -> None:
    """Export gene data to CSV."""
    print(f"\nExporting gene data to CSV...")

    fieldnames = [
        "gene_symbol", "study_id", "assay_id", "log2fc", "adj_pvalue",
        "test_group", "ref_group", "go_terms"
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for gene in genes:
            symbol = gene["geneSymbol"]
            go_terms = gene_go_map.get(symbol, [])
            go_str = "; ".join(t["goId"] for t in go_terms)

            writer.writerow({
                "gene_symbol": symbol,
                "study_id": gene["studyId"],
                "assay_id": gene["assayId"],
                "log2fc": f"{gene['log2fc']:.3f}",
                "adj_pvalue": f"{gene['pvalue']:.2e}",
                "test_group": gene.get("testGroup", ""),
                "ref_group": gene.get("refGroup", ""),
                "go_terms": go_str,
            })

    print(f"  Saved: {output_path}")


def main():
    """Main entry point."""
    print("=" * 70)
    print("Psoriasis Gene Expression Network Analysis")
    print("=" * 70)

    # Initialize clients
    sparql = SPARQLClient(timeout=60)
    fuseki = FusekiClient(dataset="GXA-v2")

    # Check Fuseki availability
    print("\nChecking Fuseki availability...")
    if not fuseki.is_available():
        print("ERROR: Fuseki server not available")
        sys.exit(1)
    print("  OK!")

    # Step 1: Get psoriasis studies
    studies = get_psoriasis_studies(fuseki)
    if not studies:
        print("No psoriasis studies found")
        sys.exit(0)

    study_ids = list({s["studyId"] for s in studies})
    print(f"  Studies: {', '.join(study_ids[:5])}...")

    # Step 2: Get upregulated genes
    genes = get_psoriasis_upregulated_genes(fuseki, study_ids)
    if not genes:
        print("No upregulated genes found")
        sys.exit(0)

    gene_symbols = {g["geneSymbol"] for g in genes}
    print(f"  Top genes: {', '.join(list(gene_symbols)[:10])}...")

    # Step 3: Get GO enrichments from GXA
    enrichments = get_psoriasis_go_enrichments(fuseki, study_ids)

    # Step 3b: Extract GO terms and link to genes
    go_terms = get_go_terms_from_enrichments(enrichments)
    gene_go_map = get_genes_for_enriched_go_terms(fuseki, study_ids, go_terms)

    # Step 5: Build network
    nodes, edges = build_network(studies, genes, gene_go_map, enrichments)

    # Step 6: Generate visualization
    output_path = Path(__file__).parent / "psoriasis_network.html"
    generate_html(nodes, edges, "Psoriasis Gene Expression Network", output_path)

    # Export CSV
    csv_path = Path(__file__).parent / "psoriasis_genes.csv"
    export_genes_csv(genes, gene_go_map, csv_path)

    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"  Psoriasis studies: {len(study_ids)}")
    print(f"  Upregulated genes: {len(gene_symbols)}")
    print(f"  Genes with GO terms: {len(gene_go_map)}")
    print(f"  GO enrichments: {len(enrichments)}")
    print(f"\n  Visualization: {output_path}")
    print(f"  Gene data: {csv_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
