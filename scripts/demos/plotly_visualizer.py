#!/usr/bin/env python3
"""
Interactive Plotly Visualizations for Gene-Disease Analysis

This module provides reusable visualization components for:
- Gene-disease network graphs
- Expression fold change comparisons
- Multi-source connection summaries
- Drug-disease therapeutic patterns

All visualizations are interactive and can be saved as HTML files
or displayed in Jupyter notebooks.

Usage:
    from plotly_visualizer import PlotlyVisualizer

    viz = PlotlyVisualizer()

    # Network graph
    fig = viz.gene_disease_network(connections)
    fig.show()

    # Save to HTML
    viz.save_html(fig, "network.html")
"""
from __future__ import annotations

import json
from typing import Dict, List, Any, Optional, Tuple, TYPE_CHECKING
from collections import defaultdict
from pathlib import Path

try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False
    go = None  # type: ignore
    px = None  # type: ignore
    make_subplots = None  # type: ignore

# Type alias for plotly figures (works even when plotly not installed)
if HAS_PLOTLY:
    Figure = go.Figure
else:
    Figure = Any  # type: ignore


# Color schemes
COLORS = {
    # Sources
    "SPOKE-OKN": "#1f77b4",      # Blue
    "Wikidata": "#ff7f0e",       # Orange
    "Ubergraph": "#2ca02c",      # Green
    "SPOKE+Wikidata": "#9467bd", # Purple
    "GXA": "#d62728",            # Red

    # Path types
    "positive_marker": "#2ecc71",    # Green
    "negative_marker": "#e74c3c",    # Red
    "expressed_in": "#3498db",       # Blue
    "genetic_association": "#9b59b6", # Purple
    "go_pathway": "#f39c12",         # Orange
    "shared_pathway": "#1abc9c",     # Teal

    # Expression direction
    "up": "#e74c3c",      # Red (up-regulated)
    "down": "#3498db",    # Blue (down-regulated)
    "neutral": "#95a5a6", # Gray

    # Node types
    "gene": "#3498db",
    "disease": "#e74c3c",
    "go_term": "#2ecc71",
    "drug": "#9b59b6",
}


class PlotlyVisualizer:
    """Interactive visualization components for gene-disease analysis."""

    def __init__(self, template: str = "plotly_white"):
        """
        Initialize visualizer.

        Args:
            template: Plotly template (plotly_white, plotly_dark, ggplot2, etc.)
        """
        if not HAS_PLOTLY:
            raise ImportError("plotly is required. Install with: pip install plotly")
        self.template = template

    def gene_disease_network(
        self,
        connections: List[Dict[str, Any]],
        title: str = "Gene-Disease Connections",
        gene_symbol: Optional[str] = None,
        show_intermediates: bool = True,
        height: int = 700,
        width: int = 1000,
    ) -> str:
        """
        Create an interactive network graph with draggable nodes using vis.js.

        Args:
            connections: List of connection dicts with gene, disease, path_type, source, intermediate
            title: Chart title
            gene_symbol: Central gene (extracted from connections if not provided)
            show_intermediates: Whether to show intermediate nodes (GO terms, related genes)
            height: Figure height in pixels
            width: Figure width in pixels

        Returns:
            HTML string containing the vis.js network
        """
        if not connections:
            return "<p>No connections to display</p>"

        # Extract gene symbol if not provided
        if gene_symbol is None:
            gene_symbol = connections[0].get("gene", "Gene")

        # Build network data
        nodes = {}  # node_id -> {label, type, ...}
        edges = []  # [(source, target, edge_data), ...]

        # Central gene node
        gene_id = f"gene:{gene_symbol}"
        nodes[gene_id] = {
            "id": gene_id,
            "label": gene_symbol,
            "type": "gene",
            "color": COLORS["gene"],
            "size": 40,
            "font": {"size": 14, "color": "#ffffff"},
            "title": f"Gene: {gene_symbol}",
        }

        # Process connections
        for conn in connections:
            disease_name = conn.get("disease_name", conn.get("disease", "Unknown"))
            disease_id = conn.get("disease_id", disease_name)
            path_type = conn.get("path_type", "associated")
            source = conn.get("source", "Unknown")
            intermediate = conn.get("intermediate")

            # Disease node
            disease_node_id = f"disease:{disease_id}"
            if disease_node_id not in nodes:
                nodes[disease_node_id] = {
                    "id": disease_node_id,
                    "label": self._truncate_label(disease_name, 20),
                    "type": "disease",
                    "color": COLORS["disease"],
                    "size": 25,
                    "font": {"size": 11, "color": "#ffffff"},
                    "title": f"Disease: {disease_name}\nID: {disease_id}",
                }

            # Handle intermediate nodes
            if show_intermediates and intermediate:
                if intermediate.startswith("GO:"):
                    inter_id = f"go:{intermediate.split(':')[1].split()[0]}"
                    inter_label = intermediate.split(":")[0] + ":" + intermediate.split(":")[1].split()[0]
                    inter_type = "go_term"
                    inter_title = intermediate
                else:
                    inter_id = f"gene:{intermediate.split()[0]}"
                    inter_label = intermediate.split()[0]
                    inter_type = "gene"
                    inter_title = intermediate

                if inter_id not in nodes:
                    nodes[inter_id] = {
                        "id": inter_id,
                        "label": inter_label,
                        "type": inter_type,
                        "color": COLORS.get(inter_type, "#95a5a6"),
                        "size": 18,
                        "font": {"size": 10, "color": "#ffffff"},
                        "title": inter_title,
                    }

                edges.append({
                    "from": gene_id,
                    "to": inter_id,
                    "color": COLORS.get(path_type, "#95a5a6"),
                    "title": f"{path_type} ({source})",
                })
                edges.append({
                    "from": inter_id,
                    "to": disease_node_id,
                    "color": COLORS.get(path_type, "#95a5a6"),
                    "title": f"{path_type} ({source})",
                })
            else:
                edges.append({
                    "from": gene_id,
                    "to": disease_node_id,
                    "color": COLORS.get(path_type, "#95a5a6"),
                    "title": f"{path_type} ({source})",
                })

        # Convert to vis.js format
        vis_nodes = list(nodes.values())
        vis_edges = edges

        # Generate HTML with vis.js
        html = self._generate_visjs_html(vis_nodes, vis_edges, title, height, width, gene_symbol)
        return html

    def _truncate_label(self, label: str, max_len: int) -> str:
        """Truncate label for display."""
        if len(label) <= max_len:
            return label
        return label[:max_len-2] + "..."

    def _generate_visjs_html(
        self,
        nodes: List[Dict],
        edges: List[Dict],
        title: str,
        height: int,
        width: int,
        gene_symbol: str,
    ) -> str:
        """Generate standalone HTML with vis.js network."""
        import json

        # Prepare node data for vis.js
        vis_nodes = []
        for node in nodes:
            vis_node = {
                "id": node["id"],
                "label": node["label"],
                "color": {
                    "background": node["color"],
                    "border": node["color"],
                    "highlight": {"background": "#f1c40f", "border": "#f39c12"},
                },
                "size": node["size"],
                "font": node.get("font", {"size": 12, "color": "#ffffff"}),
                "title": node.get("title", node["label"]),
                "shape": "dot" if node["type"] != "gene" else "dot",
            }
            # Make central gene node fixed initially but draggable
            if node["id"] == f"gene:{gene_symbol}":
                vis_node["fixed"] = {"x": False, "y": False}
                vis_node["physics"] = False  # Start stable
            vis_nodes.append(vis_node)

        # Prepare edge data
        vis_edges = []
        for edge in edges:
            vis_edges.append({
                "from": edge["from"],
                "to": edge["to"],
                "color": {"color": edge["color"], "highlight": "#f1c40f"},
                "title": edge.get("title", ""),
                "width": 2,
                "smooth": {"type": "continuous"},
            })

        nodes_json = json.dumps(vis_nodes)
        edges_json = json.dumps(vis_edges)

        # Build legend HTML
        legend_items = [
            ("Gene", COLORS["gene"]),
            ("Disease", COLORS["disease"]),
            ("GO Term", COLORS["go_term"]),
        ]
        legend_html = " ".join([
            f'<span style="display:inline-block;margin-right:15px;">'
            f'<span style="display:inline-block;width:12px;height:12px;'
            f'background:{color};border-radius:50%;margin-right:5px;"></span>{label}</span>'
            for label, color in legend_items
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
            margin-bottom: 15px;
            font-size: 14px;
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
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div class="legend">{legend_html}</div>
    <div class="instructions">Drag nodes to rearrange • Scroll to zoom • Hover for details</div>
    <div id="network"></div>
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
                    gravitationalConstant: -3000,
                    centralGravity: 0.3,
                    springLength: 150,
                    springConstant: 0.04,
                    damping: 0.09,
                }},
                stabilization: {{
                    iterations: 150,
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

        // Stop physics after initial stabilization for smoother dragging
        network.on("stabilizationIterationsDone", function () {{
            network.setOptions({{ physics: {{ enabled: false }} }});
        }});

        // Re-enable physics briefly when dragging ends to settle
        network.on("dragEnd", function (params) {{
            if (params.nodes.length > 0) {{
                network.setOptions({{ physics: {{ enabled: true }} }});
                setTimeout(function() {{
                    network.setOptions({{ physics: {{ enabled: false }} }});
                }}, 500);
            }}
        }});
    </script>
</body>
</html>'''
        return html

    def expression_comparison(
        self,
        results: List[Dict[str, Any]],
        title: str = "Drug vs Disease Expression",
        max_genes: int = 20,
        height: int = 600,
        width: int = 900,
    ) -> go.Figure:
        """
        Create a bar chart comparing drug and disease expression fold changes.

        Args:
            results: List of dicts with gene, drug_log2fc, disease_log2fc
            title: Chart title
            max_genes: Maximum number of genes to show
            height: Figure height
            width: Figure width

        Returns:
            Plotly Figure object
        """
        if not results:
            return self._empty_figure("No expression data to display")

        # Limit and sort by absolute disease fold change
        results = sorted(results, key=lambda x: abs(x.get("disease_log2fc", 0)), reverse=True)
        results = results[:max_genes]

        genes = [r.get("gene", "Unknown") for r in results]
        drug_fc = [r.get("drug_log2fc", 0) for r in results]
        disease_fc = [r.get("disease_log2fc", 0) for r in results]

        # Create grouped bar chart
        fig = go.Figure()

        fig.add_trace(go.Bar(
            name="Drug Effect",
            x=genes,
            y=drug_fc,
            marker_color=[COLORS["down"] if fc < 0 else COLORS["up"] for fc in drug_fc],
            text=[f"{fc:.1f}" for fc in drug_fc],
            textposition="outside",
        ))

        fig.add_trace(go.Bar(
            name="Disease Effect",
            x=genes,
            y=disease_fc,
            marker_color=[COLORS["up"] if fc > 0 else COLORS["down"] for fc in disease_fc],
            text=[f"{fc:.1f}" for fc in disease_fc],
            textposition="outside",
            opacity=0.7,
        ))

        fig.update_layout(
            title=dict(text=title, x=0.5, font=dict(size=18)),
            barmode="group",
            xaxis_title="Gene",
            yaxis_title="Log2 Fold Change",
            template=self.template,
            height=height,
            width=width,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5,
            ),
            hovermode="x unified",
        )

        # Add zero line
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)

        return fig

    def source_summary(
        self,
        connections: List[Dict[str, Any]],
        title: str = "Connections by Source",
        height: int = 400,
        width: int = 600,
    ) -> go.Figure:
        """
        Create a sunburst chart showing connections by source and path type.

        Args:
            connections: List of connection dicts
            title: Chart title
            height: Figure height
            width: Figure width

        Returns:
            Plotly Figure object
        """
        if not connections:
            return self._empty_figure("No connections to display")

        # Count by source and path type
        counts = defaultdict(lambda: defaultdict(int))
        for conn in connections:
            source = conn.get("source", "Unknown")
            path_type = conn.get("path_type", "associated")
            counts[source][path_type] += 1

        # Build sunburst data
        labels = ["Total"]
        parents = [""]
        values = [len(connections)]
        colors = ["#ecf0f1"]

        for source, path_types in counts.items():
            # Source level
            source_total = sum(path_types.values())
            labels.append(source)
            parents.append("Total")
            values.append(source_total)
            colors.append(COLORS.get(source, "#95a5a6"))

            # Path type level
            for path_type, count in path_types.items():
                labels.append(f"{path_type} ({count})")
                parents.append(source)
                values.append(count)
                colors.append(COLORS.get(path_type, "#bdc3c7"))

        fig = go.Figure(go.Sunburst(
            labels=labels,
            parents=parents,
            values=values,
            marker=dict(colors=colors),
            branchvalues="total",
            hovertemplate="<b>%{label}</b><br>Count: %{value}<extra></extra>",
        ))

        fig.update_layout(
            title=dict(text=title, x=0.5, font=dict(size=18)),
            template=self.template,
            height=height,
            width=width,
            margin=dict(l=20, r=20, t=60, b=20),
        )

        return fig

    def disease_heatmap(
        self,
        connections: List[Dict[str, Any]],
        title: str = "Gene-Disease Association Matrix",
        height: int = 500,
        width: int = 800,
    ) -> go.Figure:
        """
        Create a heatmap of gene-disease associations by path type.

        Args:
            connections: List of connection dicts
            title: Chart title
            height: Figure height
            width: Figure width

        Returns:
            Plotly Figure object
        """
        if not connections:
            return self._empty_figure("No connections to display")

        # Build matrix: diseases x path_types
        diseases = list(set(conn.get("disease_name", "Unknown") for conn in connections))
        path_types = list(set(conn.get("path_type", "associated") for conn in connections))

        # Count connections
        matrix = [[0] * len(path_types) for _ in diseases]
        for conn in connections:
            disease = conn.get("disease_name", "Unknown")
            path_type = conn.get("path_type", "associated")
            if disease in diseases and path_type in path_types:
                matrix[diseases.index(disease)][path_types.index(path_type)] += 1

        fig = go.Figure(go.Heatmap(
            z=matrix,
            x=[pt.replace("_", " ").title() for pt in path_types],
            y=diseases,
            colorscale="Blues",
            hovertemplate="Disease: %{y}<br>Path Type: %{x}<br>Count: %{z}<extra></extra>",
        ))

        fig.update_layout(
            title=dict(text=title, x=0.5, font=dict(size=18)),
            xaxis_title="Connection Type",
            yaxis_title="Disease",
            template=self.template,
            height=height,
            width=width,
        )

        return fig

    def drug_disease_patterns(
        self,
        pattern1_results: List[Dict[str, Any]],
        pattern2_results: List[Dict[str, Any]],
        title: str = "Drug-Disease Expression Patterns",
        height: int = 600,
        width: int = 1000,
    ) -> go.Figure:
        """
        Create a visualization of both drug-disease expression patterns.

        Args:
            pattern1_results: Drug DOWN / Disease UP results
            pattern2_results: Drug UP / Disease DOWN results
            title: Chart title
            height: Figure height
            width: Figure width

        Returns:
            Plotly Figure object
        """
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=["Drug ↓ / Disease ↑", "Drug ↑ / Disease ↓"],
            horizontal_spacing=0.12,
        )

        # Pattern 1: Drug DOWN, Disease UP
        if pattern1_results:
            p1_sorted = sorted(pattern1_results, key=lambda x: x.get("disease_log2fc", 0), reverse=True)[:15]
            genes1 = [r.get("gene", "?") for r in p1_sorted]
            disease_fc1 = [r.get("disease_log2fc", 0) for r in p1_sorted]

            fig.add_trace(go.Bar(
                y=genes1,
                x=disease_fc1,
                orientation="h",
                marker_color=COLORS["up"],
                name="Disease UP",
                text=[f"+{fc:.1f}" for fc in disease_fc1],
                textposition="outside",
                showlegend=True,
            ), row=1, col=1)

        # Pattern 2: Drug UP, Disease DOWN
        if pattern2_results:
            p2_sorted = sorted(pattern2_results, key=lambda x: x.get("disease_log2fc", 0))[:15]
            genes2 = [r.get("gene", "?") for r in p2_sorted]
            disease_fc2 = [abs(r.get("disease_log2fc", 0)) for r in p2_sorted]

            fig.add_trace(go.Bar(
                y=genes2,
                x=disease_fc2,
                orientation="h",
                marker_color=COLORS["down"],
                name="Disease DOWN",
                text=[f"-{fc:.1f}" for fc in disease_fc2],
                textposition="outside",
                showlegend=True,
            ), row=1, col=2)

        fig.update_layout(
            title=dict(text=title, x=0.5, font=dict(size=18)),
            template=self.template,
            height=height,
            width=width,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.08,
                xanchor="center",
                x=0.5,
            ),
        )

        fig.update_xaxes(title_text="Disease |log2FC|", row=1, col=1)
        fig.update_xaxes(title_text="Disease |log2FC|", row=1, col=2)

        return fig

    def multi_panel_summary(
        self,
        gene_symbol: str,
        connections: List[Dict[str, Any]],
        expression_results: Optional[List[Dict[str, Any]]] = None,
        height: int = 800,
        width: int = 1200,
    ) -> go.Figure:
        """
        Create a multi-panel summary visualization.

        Args:
            gene_symbol: Gene symbol
            connections: Gene-disease connections
            expression_results: Optional expression comparison data
            height: Figure height
            width: Figure width

        Returns:
            Plotly Figure object
        """
        # Determine layout
        has_expression = expression_results and len(expression_results) > 0

        if has_expression:
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=[
                    f"{gene_symbol} Disease Connections",
                    "Connections by Source",
                    "Expression Comparison",
                    "Disease Association Matrix",
                ],
                specs=[
                    [{"type": "scatter"}, {"type": "sunburst"}],
                    [{"type": "bar"}, {"type": "heatmap"}],
                ],
                vertical_spacing=0.12,
                horizontal_spacing=0.1,
            )
        else:
            fig = make_subplots(
                rows=1, cols=2,
                subplot_titles=[
                    f"{gene_symbol} Disease Connections",
                    "Connections by Source",
                ],
                specs=[[{"type": "scatter"}, {"type": "sunburst"}]],
                horizontal_spacing=0.1,
            )

        # This is a simplified version - full implementation would
        # integrate the individual chart components

        fig.update_layout(
            title=dict(text=f"Gene Analysis: {gene_symbol}", x=0.5, font=dict(size=20)),
            template=self.template,
            height=height,
            width=width,
            showlegend=True,
        )

        return fig

    def _empty_figure(self, message: str) -> go.Figure:
        """Create an empty figure with a message."""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="gray"),
        )
        fig.update_layout(
            template=self.template,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
        )
        return fig

    def save_html(self, fig: go.Figure, filepath: str, include_plotlyjs: bool = True):
        """
        Save figure to an HTML file.

        Args:
            fig: Plotly Figure object
            filepath: Output file path
            include_plotlyjs: Whether to include plotly.js in the file
        """
        fig.write_html(
            filepath,
            include_plotlyjs=include_plotlyjs,
            full_html=True,
        )
        print(f"Saved: {filepath}")


def demo():
    """Demonstrate visualization capabilities."""
    if not HAS_PLOTLY:
        print("plotly is required for this demo")
        return

    viz = PlotlyVisualizer()

    # Sample data
    connections = [
        {"gene": "SFRP2", "disease_id": "DOID_263", "disease_name": "kidney cancer",
         "path_type": "negative_marker", "source": "SPOKE-OKN", "intermediate": None},
        {"gene": "SFRP2", "disease_id": "DOID_1793", "disease_name": "pancreatic cancer",
         "path_type": "expressed_in", "source": "SPOKE-OKN", "intermediate": None},
        {"gene": "SFRP2", "disease_id": "MONDO_0020779", "disease_name": "cartilage disorder",
         "path_type": "go_pathway", "source": "Ubergraph", "intermediate": "GO:0051216: cartilage development"},
        {"gene": "SFRP2", "disease_id": "DOID_4362", "disease_name": "cervical cancer",
         "path_type": "shared_pathway", "source": "SPOKE+Wikidata", "intermediate": "S100A9 (shares: GO:0031012)"},
        {"gene": "SFRP2", "disease_id": "DOID_1781", "disease_name": "thyroid cancer",
         "path_type": "shared_pathway", "source": "SPOKE+Wikidata", "intermediate": "COL8A1 (shares: GO:0031012)"},
    ]

    expression_results = [
        {"gene": "SFRP2", "drug_log2fc": -6.5, "disease_log2fc": 4.3},
        {"gene": "Wdr95", "drug_log2fc": -2.4, "disease_log2fc": 6.2},
        {"gene": "H2ac24", "drug_log2fc": -2.1, "disease_log2fc": 5.4},
        {"gene": "Gbp8", "drug_log2fc": -2.6, "disease_log2fc": 5.0},
    ]

    print("Creating visualizations...")

    # Network graph
    fig1 = viz.gene_disease_network(connections, title="SFRP2 Disease Connections")
    viz.save_html(fig1, "demo_network.html")

    # Source summary
    fig2 = viz.source_summary(connections)
    viz.save_html(fig2, "demo_sources.html")

    # Expression comparison
    fig3 = viz.expression_comparison(expression_results)
    viz.save_html(fig3, "demo_expression.html")

    # Disease heatmap
    fig4 = viz.disease_heatmap(connections)
    viz.save_html(fig4, "demo_heatmap.html")

    print("\nDemo complete! Open the HTML files in a browser to view.")


if __name__ == "__main__":
    demo()
