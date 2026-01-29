#!/usr/bin/env python3
"""
Generate Interactive Visualization for a Single GXA Experiment

This script creates an interactive HTML visualization showing:
1. Study metadata (title, organism, experimental factors)
2. Diseases and treatments studied
3. Top differentially expressed genes (up and down regulated)
4. GO/pathway enrichments

Usage:
    python generate_experiment_visualization.py --study E-GEOD-54711 --output examples/
    python generate_experiment_visualization.py --study E-GEOD-54711 --top-genes 30 --output examples/
"""

import argparse
import os
from typing import List, Dict, Any, Optional

# Import existing infrastructure
from fuseki_client import FusekiClient
from plotly_visualizer import PlotlyVisualizer, COLORS


def query_study_metadata(client: FusekiClient, study_id: str) -> Dict[str, Any]:
    """
    Query metadata for a specific study.

    Returns dict with title, description, organism, experimental_factors, etc.
    """
    query = f'''
    SELECT ?p ?o
    WHERE {{
        spokegenelab:{study_id} ?p ?o .
    }}
    '''
    results = client.query_simple(query)

    metadata = {
        'study_id': study_id,
        'title': '',
        'description': '',
        'organism': '',
        'experimental_factors': [],
        'source': '',
        'submitter': '',
        'secondary_accessions': [],
    }

    for r in results:
        pred = r.get('p', '')
        obj = r.get('o', '')

        if 'project_title' in pred:
            metadata['title'] = obj
        elif pred.endswith('description'):
            metadata['description'] = obj
        elif 'in_taxon' in pred and not obj.isdigit():
            metadata['organism'] = obj
        elif 'experimental_factors' in pred:
            metadata['experimental_factors'].append(obj)
        elif 'source' in pred:
            metadata['source'] = obj
        elif 'submitter_name' in pred:
            metadata['submitter'] = obj
        elif 'secondary_accessions' in pred:
            metadata['secondary_accessions'].append(obj)

    return metadata


def query_study_entities(client: FusekiClient, study_id: str) -> Dict[str, List[Dict]]:
    """
    Query diseases and chemical entities studied.

    Returns dict with 'diseases' and 'compounds' lists.
    """
    query = f'''
    SELECT ?entity ?type ?name ?id
    WHERE {{
        spokegenelab:{study_id} biolink:studies ?entity .
        ?entity a ?type ;
                biolink:name ?name .
        OPTIONAL {{ ?entity biolink:id ?id }}
    }}
    '''
    results = client.query_simple(query)

    entities = {'diseases': [], 'compounds': []}

    for r in results:
        entity_type = r.get('type', '').split('/')[-1]
        entity_data = {
            'uri': r.get('entity', ''),
            'name': r.get('name', ''),
            'id': r.get('id', ''),
        }

        if entity_type == 'Disease':
            entities['diseases'].append(entity_data)
        elif entity_type == 'ChemicalEntity':
            entities['compounds'].append(entity_data)

    return entities


def query_study_assays(client: FusekiClient, study_id: str) -> List[Dict[str, Any]]:
    """
    Query assays for a study.

    Returns list of assay dicts with name, test_group, ref_group.
    """
    query = f'''
    SELECT ?assay ?name ?testGroup ?refGroup
    WHERE {{
        spokegenelab:{study_id} biolink:has_output ?assay .
        ?assay biolink:name ?name .
        OPTIONAL {{ ?assay spokegenelab:test_group_label ?testGroup }}
        OPTIONAL {{ ?assay spokegenelab:reference_group_label ?refGroup }}
    }}
    '''
    results = client.query_simple(query)

    assays = []
    for r in results:
        assays.append({
            'uri': r.get('assay', ''),
            'name': r.get('name', ''),
            'test_group': r.get('testGroup', ''),
            'ref_group': r.get('refGroup', ''),
        })

    return assays


def query_differentially_expressed_genes(
    client: FusekiClient,
    study_id: str,
    top_n: int = 20,
    pvalue_threshold: float = 0.05,
) -> List[Dict[str, Any]]:
    """
    Query top differentially expressed genes for a study.

    Returns list of gene dicts with symbol, log2fc, pvalue, direction.
    """
    query = f'''
    SELECT ?geneSymbol ?log2fc ?pvalue ?assayName
    WHERE {{
        ?expr a biolink:GeneExpressionMixin ;
              biolink:subject ?assay ;
              biolink:object ?gene ;
              spokegenelab:log2fc ?log2fc ;
              spokegenelab:adj_p_value ?pvalue .

        spokegenelab:{study_id} biolink:has_output ?assay .
        ?assay biolink:name ?assayName .
        ?gene biolink:symbol ?geneSymbol .

        FILTER(?pvalue < {pvalue_threshold})
    }}
    ORDER BY DESC(ABS(?log2fc))
    LIMIT {top_n * 2}
    '''
    results = client.query_simple(query)

    genes = []
    seen = set()
    for r in results:
        symbol = r.get('geneSymbol', '')
        if symbol in seen:
            continue
        seen.add(symbol)

        log2fc = float(r.get('log2fc', 0))
        genes.append({
            'symbol': symbol,
            'log2fc': log2fc,
            'pvalue': float(r.get('pvalue', 1)),
            'assay': r.get('assayName', ''),
            'direction': 'up' if log2fc > 0 else 'down',
        })

        if len(genes) >= top_n:
            break

    return genes


def query_go_enrichments(
    client: FusekiClient,
    study_id: str,
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """
    Query GO/pathway enrichments for a study.

    Returns list of enrichment dicts with go_id, go_name, pvalue.
    """
    query = f'''
    SELECT DISTINCT ?goId ?goName ?pvalue
    WHERE {{
        ?enrichment biolink:participates_in ?goTerm ;
                    spokegenelab:adj_p_value ?pvalue .
        ?goTerm biolink:name ?goId .
        OPTIONAL {{ ?goTerm biolink:id ?goName }}

        ?assay biolink:has_output ?enrichment .
        spokegenelab:{study_id} biolink:has_output ?assay .
    }}
    ORDER BY ?pvalue
    LIMIT {top_n}
    '''
    results = client.query_simple(query)

    enrichments = []
    seen_ids = set()
    for r in results:
        go_id = r.get('goId', '')
        # Skip duplicate pathway IDs (e.g., R-HSA, R-MMU variants)
        base_id = go_id.split('-')[-1] if '-' in go_id else go_id
        if base_id in seen_ids:
            continue
        seen_ids.add(base_id)

        enrichments.append({
            'go_id': go_id,
            'go_name': r.get('goName', go_id),
            'pvalue': float(r.get('pvalue', 1)),
        })

    return enrichments


def build_experiment_graph(
    metadata: Dict[str, Any],
    entities: Dict[str, List[Dict]],
    assays: List[Dict],
    genes: List[Dict],
    enrichments: List[Dict],
) -> tuple[List[Dict], List[Dict]]:
    """
    Build graph structure for experiment visualization.

    Returns (nodes, edges) lists for vis.js.
    """
    nodes = {}
    edges = []

    study_id = metadata['study_id']

    # Central study node
    study_node_id = f"study:{study_id}"
    study_label = metadata['title'][:40] + '...' if len(metadata['title']) > 40 else metadata['title']
    nodes[study_node_id] = {
        "id": study_node_id,
        "label": study_label or study_id,
        "type": "study",
        "title": f"<b>Study: {study_id}</b><br>"
                 f"Title: {metadata['title']}<br>"
                 f"Organism: {metadata['organism']}<br>"
                 f"Factors: {', '.join(metadata['experimental_factors'])}",
    }

    # Disease nodes
    for disease in entities['diseases']:
        disease_id = f"disease:{disease['name'].lower().replace(' ', '_')}"
        if disease_id not in nodes:
            nodes[disease_id] = {
                "id": disease_id,
                "label": disease['name'][:20],
                "type": "disease",
                "title": f"<b>Disease:</b> {disease['name']}<br>ID: {disease.get('id', 'N/A')}",
            }
            edges.append({
                "from": study_node_id,
                "to": disease_id,
                "label": "studies",
                "source": "GXA",
                "title": "Study investigates this disease",
            })

    # Compound nodes
    for compound in entities['compounds']:
        compound_id = f"drug:{compound['name'].lower().replace(' ', '_')[:30]}"
        if compound_id not in nodes:
            nodes[compound_id] = {
                "id": compound_id,
                "label": compound['name'][:20],
                "type": "drug",
                "title": f"<b>Compound:</b> {compound['name']}<br>ID: {compound.get('id', 'N/A')}",
            }
            edges.append({
                "from": study_node_id,
                "to": compound_id,
                "label": "tests",
                "source": "GXA",
                "title": "Study tests this compound",
            })

    # Assay nodes (if multiple assays, show them)
    for i, assay in enumerate(assays):
        assay_id = f"assay:{i}"
        assay_label = assay['name'][:25] if assay['name'] else f"Assay {i+1}"
        nodes[assay_id] = {
            "id": assay_id,
            "label": assay_label,
            "type": "assay",
            "title": f"<b>Assay:</b> {assay['name']}<br>"
                     f"Test: {assay['test_group']}<br>"
                     f"Reference: {assay['ref_group']}",
        }
        edges.append({
            "from": study_node_id,
            "to": assay_id,
            "label": "has assay",
            "source": "GXA",
            "title": f"Test: {assay['test_group']} vs Ref: {assay['ref_group']}",
        })

    # Gene nodes - split by up/down regulation
    up_genes = [g for g in genes if g['direction'] == 'up']
    down_genes = [g for g in genes if g['direction'] == 'down']

    # Add upregulated genes
    for gene in up_genes[:10]:  # Limit to top 10 each direction
        gene_id = f"gene:{gene['symbol']}"
        if gene_id not in nodes:
            nodes[gene_id] = {
                "id": gene_id,
                "label": gene['symbol'],
                "type": "gene_up",
                "title": f"<b>Gene:</b> {gene['symbol']}<br>"
                         f"log2FC: {gene['log2fc']:.2f}<br>"
                         f"p-value: {gene['pvalue']:.2e}<br>"
                         f"Direction: UPREGULATED",
            }
            # Connect to assay(s)
            assay_id = "assay:0" if assays else study_node_id
            edges.append({
                "from": assay_id,
                "to": gene_id,
                "label": f"+{gene['log2fc']:.1f}",
                "source": "GXA",
                "title": f"Upregulated (log2FC={gene['log2fc']:.2f}, p={gene['pvalue']:.2e})",
            })

    # Add downregulated genes
    for gene in down_genes[:10]:
        gene_id = f"gene:{gene['symbol']}"
        if gene_id not in nodes:
            nodes[gene_id] = {
                "id": gene_id,
                "label": gene['symbol'],
                "type": "gene_down",
                "title": f"<b>Gene:</b> {gene['symbol']}<br>"
                         f"log2FC: {gene['log2fc']:.2f}<br>"
                         f"p-value: {gene['pvalue']:.2e}<br>"
                         f"Direction: DOWNREGULATED",
            }
            assay_id = "assay:0" if assays else study_node_id
            edges.append({
                "from": assay_id,
                "to": gene_id,
                "label": f"{gene['log2fc']:.1f}",
                "source": "GXA",
                "title": f"Downregulated (log2FC={gene['log2fc']:.2f}, p={gene['pvalue']:.2e})",
            })

    # GO/pathway enrichment nodes
    for enrichment in enrichments[:8]:  # Limit to top 8
        go_id = enrichment['go_id']
        go_node_id = f"go:{go_id.replace(':', '_')}"

        # Determine label - prefer readable name
        label = enrichment['go_name'] if enrichment['go_name'] != go_id else go_id
        if len(label) > 25:
            label = label[:22] + '...'

        if go_node_id not in nodes:
            nodes[go_node_id] = {
                "id": go_node_id,
                "label": label,
                "type": "go_term",
                "title": f"<b>Pathway/GO Term:</b> {enrichment['go_name']}<br>"
                         f"ID: {go_id}<br>"
                         f"p-value: {enrichment['pvalue']:.2e}",
            }
            assay_id = "assay:0" if assays else study_node_id
            edges.append({
                "from": assay_id,
                "to": go_node_id,
                "label": "enriched",
                "source": "GXA",
                "title": f"Enriched pathway (p={enrichment['pvalue']:.2e})",
            })

    return list(nodes.values()), edges


def generate_visjs_html(
    nodes: List[Dict],
    edges: List[Dict],
    title: str,
    metadata: Dict[str, Any],
    height: int = 700,
    width: int = 1100,
) -> str:
    """Generate standalone HTML with vis.js network for experiment visualization."""
    import json

    # Extended color scheme for experiment visualization
    node_colors = {
        "study": "#2c3e50",      # Dark blue-gray
        "disease": "#e74c3c",    # Red
        "drug": "#9b59b6",       # Purple
        "assay": "#3498db",      # Blue
        "gene_up": "#e74c3c",    # Red (upregulated)
        "gene_down": "#3498db",  # Blue (downregulated)
        "go_term": "#2ecc71",    # Green
    }

    # Prepare vis.js node data
    vis_nodes = []
    for node in nodes:
        node_type = node.get("type", "gene")
        color = node_colors.get(node_type, "#95a5a6")

        # Determine size based on type
        if node_type == "study":
            size = 45
        elif node_type == "assay":
            size = 35
        elif node_type in ("disease", "drug"):
            size = 30
        else:
            size = 22

        # Determine shape
        if node_type == "study":
            shape = "box"
        elif node_type == "drug":
            shape = "diamond"
        elif node_type == "go_term":
            shape = "triangle"
        else:
            shape = "dot"

        vis_node = {
            "id": node["id"],
            "label": node.get("label", node["id"]),
            "color": {
                "background": color,
                "border": color,
                "highlight": {"background": "#f1c40f", "border": "#f39c12"},
            },
            "size": size,
            "font": {"size": 12 if node_type == "study" else 11, "color": "#ffffff"},
            "title": node.get("title", node.get("label", node["id"])),
            "shape": shape,
        }

        # Make study node fixed initially
        if node_type == "study":
            vis_node["fixed"] = {"x": False, "y": False}
            vis_node["physics"] = False
            vis_node["font"]["bold"] = True

        vis_nodes.append(vis_node)

    # Prepare vis.js edge data
    vis_edges = []
    for edge in edges:
        edge_data = {
            "from": edge["from"],
            "to": edge["to"],
            "color": {"color": "#7f8c8d", "highlight": "#f1c40f"},
            "title": edge.get("title", ""),
            "width": 2,
            "smooth": {"type": "continuous"},
        }

        if edge.get("label"):
            edge_data["label"] = edge["label"]
            edge_data["font"] = {
                "size": 9,
                "color": "#555",
                "strokeWidth": 2,
                "strokeColor": "#ffffff",
                "align": "middle",
            }

        vis_edges.append(edge_data)

    nodes_json = json.dumps(vis_nodes)
    edges_json = json.dumps(vis_edges)

    # Build legend HTML
    legend_items = [
        ("Study", node_colors["study"], "■"),
        ("Disease", node_colors["disease"], "●"),
        ("Drug/Compound", node_colors["drug"], "◆"),
        ("Assay", node_colors["assay"], "●"),
        ("Gene (up)", node_colors["gene_up"], "●"),
        ("Gene (down)", node_colors["gene_down"], "●"),
        ("GO/Pathway", node_colors["go_term"], "▲"),
    ]
    legend_html = " ".join([
        f'<span style="display:inline-block;margin-right:12px;">'
        f'<span style="color:{color};font-size:14px;margin-right:4px;">{symbol}</span>{label}</span>'
        for label, color, symbol in legend_items
    ])

    # Build study info box
    factors = ', '.join(metadata.get('experimental_factors', []))
    gse = ', '.join(metadata.get('secondary_accessions', []))
    study_info = f"""
    <div style="background:#f8f9fa;padding:12px 15px;border-radius:6px;margin-bottom:15px;font-size:13px;max-width:{width}px;margin:0 auto 15px auto;">
        <div style="font-weight:bold;color:#2c3e50;margin-bottom:5px;">{metadata.get('title', metadata.get('study_id', 'Unknown'))}</div>
        <div style="color:#666;">
            <b>Study ID:</b> {metadata.get('study_id', 'N/A')} |
            <b>GEO:</b> {gse or 'N/A'} |
            <b>Organism:</b> {metadata.get('organism', 'N/A')} |
            <b>Factors:</b> {factors or 'N/A'}
        </div>
    </div>
    """

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
        .study-info {{
            max-width: {width}px;
            margin: 0 auto;
        }}
        .legend {{
            text-align: center;
            margin-bottom: 10px;
            font-size: 13px;
            color: #555;
        }}
        .instructions {{
            text-align: center;
            font-size: 12px;
            color: #888;
            margin-bottom: 10px;
        }}
        #network {{
            width: {width}px;
            height: {height}px;
            border: 1px solid #ddd;
            background: white;
            margin: 0 auto;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .summary {{
            text-align: center;
            margin-top: 15px;
            font-size: 13px;
            color: #666;
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
        .toggle-btn.active {{
            background: #27ae60;
            color: white;
        }}
        .toggle-btn.inactive {{
            background: #e0e0e0;
            color: #555;
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
        #custom-tooltip b {{
            color: #f1c40f;
        }}
        .vis-tooltip {{
            display: none !important;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    {study_info}
    <div class="legend">{legend_html}</div>
    <div class="controls">
        <button id="physicsToggle" class="toggle-btn inactive" onclick="togglePhysics()">
            ⚡ Auto-Layout: OFF
        </button>
        <button class="toggle-btn inactive" onclick="resetLayout()">
            🔄 Reset Layout
        </button>
    </div>
    <div class="instructions">Drag nodes to rearrange • Scroll to zoom • Hover for details</div>
    <div id="network"></div>
    <div id="custom-tooltip"></div>
    <div class="summary">
        {len(nodes)} nodes • {len(edges)} connections
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
                font: {{
                    color: '#ffffff',
                    face: 'arial',
                }}
            }},
            edges: {{
                shadow: true,
                smooth: {{
                    type: 'continuous'
                }}
            }},
            physics: {{
                enabled: true,
                barnesHut: {{
                    gravitationalConstant: -2500,
                    centralGravity: 0.25,
                    springLength: 120,
                    springConstant: 0.04,
                    damping: 0.09,
                }},
                stabilization: {{
                    iterations: 200,
                    fit: true
                }}
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
            if (physicsEnabled) {{
                btn.textContent = '⚡ Auto-Layout: ON';
                btn.className = 'toggle-btn active';
            }} else {{
                btn.textContent = '⚡ Auto-Layout: OFF';
                btn.className = 'toggle-btn inactive';
            }}
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
            }} else {{
                return;
            }}
            tooltip.style.left = (x + 15) + 'px';
            tooltip.style.top = (y + 15) + 'px';
            var rect = tooltip.getBoundingClientRect();
            if (rect.right > window.innerWidth) {{
                tooltip.style.left = (x - rect.width - 15) + 'px';
            }}
            if (rect.bottom > window.innerHeight) {{
                tooltip.style.top = (y - rect.height - 15) + 'px';
            }}
        }}

        function hideTooltip() {{
            tooltip.style.display = 'none';
        }}

        network.on('hoverEdge', function(params) {{
            var edgeId = params.edge;
            var edge = edges.get(edgeId);
            var content = edge ? edge.title : null;
            if (content) showTooltip(content, params);
        }});

        network.on('blurEdge', hideTooltip);

        network.on('hoverNode', function(params) {{
            var nodeId = params.node;
            var node = nodes.get(nodeId);
            var content = node ? node.title : null;
            if (content) showTooltip(content, params);
        }});

        network.on('blurNode', hideTooltip);
        network.on('dragStart', hideTooltip);
        network.on('click', hideTooltip);
    </script>
</body>
</html>'''
    return html


def generate_experiment_visualization(
    study_id: str,
    output_dir: str,
    top_genes: int = 20,
    verbose: bool = False,
) -> str:
    """
    Generate a complete visualization for a study/experiment.

    Args:
        study_id: Study identifier (e.g., 'E-GEOD-54711')
        output_dir: Output directory for HTML file
        top_genes: Number of top DEGs to include
        verbose: Verbose output

    Returns:
        Path to the generated HTML file.
    """
    print("=" * 70)
    print(f"GENERATING VISUALIZATION FOR EXPERIMENT: {study_id}")
    print("=" * 70)

    # Initialize Fuseki client
    print("\n[Connecting to Fuseki...]")
    try:
        client = FusekiClient(dataset='GXA-v2', timeout=120)
        if not client.is_available():
            print("  ERROR: Fuseki server not available")
            return ""
    except Exception as e:
        print(f"  ERROR: Could not connect to Fuseki: {e}")
        return ""
    print("  Connected!")

    # Query study metadata
    print("\n[Querying Study Metadata...]")
    metadata = query_study_metadata(client, study_id)
    print(f"  Title: {metadata['title'][:60]}...")
    print(f"  Organism: {metadata['organism']}")
    print(f"  Factors: {', '.join(metadata['experimental_factors'])}")

    # Query entities (diseases, compounds)
    print("\n[Querying Diseases and Compounds...]")
    entities = query_study_entities(client, study_id)
    print(f"  Diseases: {len(entities['diseases'])}")
    print(f"  Compounds: {len(entities['compounds'])}")

    # Query assays
    print("\n[Querying Assays...]")
    assays = query_study_assays(client, study_id)
    print(f"  Found {len(assays)} assay(s)")
    for assay in assays:
        print(f"    - {assay['name']}")

    # Query differentially expressed genes
    print(f"\n[Querying Top {top_genes} Differentially Expressed Genes...]")
    genes = query_differentially_expressed_genes(client, study_id, top_n=top_genes)
    up_count = len([g for g in genes if g['direction'] == 'up'])
    down_count = len([g for g in genes if g['direction'] == 'down'])
    print(f"  Found {len(genes)} genes ({up_count} up, {down_count} down)")

    # Query GO enrichments
    print("\n[Querying GO/Pathway Enrichments...]")
    enrichments = query_go_enrichments(client, study_id, top_n=10)
    print(f"  Found {len(enrichments)} enriched pathways")

    # Build graph
    print("\n[Building Graph...]")
    nodes, edges = build_experiment_graph(metadata, entities, assays, genes, enrichments)
    print(f"  Total nodes: {len(nodes)}")
    print(f"  Total edges: {len(edges)}")

    # Generate visualization
    print("\n[Generating Visualization...]")
    title = f"Experiment: {study_id}"
    html = generate_visjs_html(nodes, edges, title, metadata)

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Build filename
    filename = f"experiment_{study_id.lower().replace('-', '_')}.html"
    output_file = os.path.join(output_dir, filename)

    with open(output_file, 'w') as f:
        f.write(html)

    print(f"  Saved to: {output_file}")
    return output_file


def main():
    parser = argparse.ArgumentParser(
        description="Generate interactive visualization for a GXA experiment"
    )
    parser.add_argument(
        "--study", "-s",
        required=True,
        help="Study ID (e.g., E-GEOD-54711)"
    )
    parser.add_argument(
        "--output", "-o",
        default="./examples",
        help="Output directory for HTML files"
    )
    parser.add_argument(
        "--top-genes", "-n",
        type=int,
        default=20,
        help="Number of top DEGs to show (default: 20)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    args = parser.parse_args()

    output_file = generate_experiment_visualization(
        study_id=args.study,
        output_dir=args.output,
        top_genes=args.top_genes,
        verbose=args.verbose,
    )

    if output_file:
        print("\n" + "=" * 70)
        print("GENERATION COMPLETE")
        print("=" * 70)
        print(f"Output: {output_file}")
    else:
        print("\nGeneration failed.")


if __name__ == "__main__":
    main()