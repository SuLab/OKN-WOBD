"""
Shared HTML report generator for question modules.

Produces self-contained HTML files with embedded vis.js networks,
Plotly charts, and collapsible investigation steps.

Usage:
    from questions._report import QuestionReport

    report = QuestionReport(
        question="What diseases is SFRP2 connected to?",
        sources=["SPOKE-OKN", "Wikidata", "Ubergraph"],
    )
    report.add_step("Query SPOKE for direct associations", html_content)
    report.add_visualization("Network", vis_js_html)
    report.set_answer("SFRP2 connects to 15 diseases through 4 mechanisms.")
    report.save("output/gene_disease_map.html")
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class QuestionReport:
    """Builder for self-contained HTML investigation reports."""

    def __init__(
        self,
        question: str,
        sources: List[str],
        module_name: str = "",
    ):
        self.question = question
        self.sources = sources
        self.module_name = module_name
        self.steps: List[Dict[str, Any]] = []
        self.visualizations: List[Dict[str, str]] = []
        self.answer: Optional[str] = None
        self.provenance: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sources": sources,
        }
        self.raw_data: Dict[str, Any] = {}

    def add_step(
        self,
        title: str,
        content: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> "QuestionReport":
        """Add a numbered investigation step with HTML content."""
        self.steps.append({
            "number": len(self.steps) + 1,
            "title": title,
            "content": content,
        })
        if data:
            self.raw_data[f"step_{len(self.steps)}"] = data
        return self

    def add_visualization(
        self,
        title: str,
        html: str,
    ) -> "QuestionReport":
        """Add an embedded visualization (vis.js network or Plotly chart)."""
        self.visualizations.append({"title": title, "html": html})
        return self

    def set_answer(self, answer: str) -> "QuestionReport":
        """Set the concluding answer summary."""
        self.answer = answer
        return self

    def add_provenance(self, key: str, value: Any) -> "QuestionReport":
        """Add provenance metadata (endpoint URLs, query params, etc.)."""
        self.provenance[key] = value
        return self

    def save(self, filepath: str) -> str:
        """Render and save the HTML report. Returns the absolute path."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        html = self._render()
        path.write_text(html)
        return str(path.resolve())

    def _render(self) -> str:
        """Render the full HTML report."""
        steps_html = self._render_steps()
        viz_html = self._render_visualizations()
        answer_html = self._render_answer()
        provenance_html = self._render_provenance()
        source_badges = " ".join(
            f'<span class="badge">{s}</span>' for s in self.sources
        )

        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.question}</title>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f8f9fa;
            color: #2c3e50;
            line-height: 1.6;
            padding: 0 20px 40px;
            max-width: 1100px;
            margin: 0 auto;
        }}
        header {{
            text-align: center;
            padding: 40px 0 20px;
            border-bottom: 2px solid #e9ecef;
            margin-bottom: 30px;
        }}
        header h1 {{
            font-size: 1.6em;
            color: #2c3e50;
            font-style: italic;
            font-weight: 500;
            margin-bottom: 12px;
        }}
        .badge {{
            display: inline-block;
            background: #3498db;
            color: white;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.8em;
            margin: 2px;
        }}
        .step {{
            background: white;
            border-radius: 8px;
            padding: 20px 24px;
            margin-bottom: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }}
        .step-header {{
            display: flex;
            align-items: center;
            cursor: pointer;
            user-select: none;
        }}
        .step-number {{
            background: #3498db;
            color: white;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.85em;
            font-weight: 600;
            margin-right: 12px;
            flex-shrink: 0;
        }}
        .step-title {{
            font-weight: 600;
            font-size: 1.05em;
        }}
        .step-toggle {{
            margin-left: auto;
            color: #aaa;
            font-size: 1.2em;
            transition: transform 0.2s;
        }}
        .step-toggle.collapsed {{ transform: rotate(-90deg); }}
        .step-body {{
            margin-top: 14px;
            padding-left: 40px;
            overflow: hidden;
            transition: max-height 0.3s ease;
        }}
        .step-body.collapsed {{ max-height: 0; margin-top: 0; }}
        .step-body table {{
            border-collapse: collapse;
            width: 100%;
            margin: 10px 0;
        }}
        .step-body th, .step-body td {{
            padding: 6px 12px;
            border: 1px solid #e9ecef;
            text-align: left;
            font-size: 0.9em;
        }}
        .step-body th {{ background: #f8f9fa; font-weight: 600; }}
        .viz-section {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }}
        .viz-section h3 {{ margin-bottom: 14px; }}
        .answer-section {{
            background: #eaf7ed;
            border-left: 4px solid #27ae60;
            border-radius: 0 8px 8px 0;
            padding: 20px 24px;
            margin: 24px 0;
        }}
        .answer-section h2 {{
            color: #27ae60;
            font-size: 1.1em;
            margin-bottom: 8px;
        }}
        .provenance {{
            background: white;
            border-radius: 8px;
            padding: 16px 24px;
            margin-top: 24px;
            font-size: 0.85em;
            color: #666;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }}
        .provenance h3 {{
            font-size: 0.95em;
            color: #888;
            margin-bottom: 8px;
            cursor: pointer;
        }}
        .provenance-body {{ display: none; }}
        .provenance-body.expanded {{ display: block; }}
        .provenance dt {{ font-weight: 600; margin-top: 6px; }}
        .provenance dd {{ margin-left: 16px; word-break: break-all; }}
        code {{ background: #f0f0f0; padding: 1px 5px; border-radius: 3px; font-size: 0.9em; }}
        .no-data {{ color: #999; font-style: italic; }}
    </style>
</head>
<body>
    <header>
        <h1>"{self.question}"</h1>
        <div>{source_badges}</div>
    </header>

    {steps_html}
    {viz_html}
    {answer_html}
    {provenance_html}

    <script>
        document.querySelectorAll('.step-header').forEach(function(header) {{
            header.addEventListener('click', function() {{
                var body = this.nextElementSibling;
                var toggle = this.querySelector('.step-toggle');
                body.classList.toggle('collapsed');
                toggle.classList.toggle('collapsed');
            }});
        }});
        document.querySelectorAll('.provenance h3').forEach(function(h) {{
            h.addEventListener('click', function() {{
                this.nextElementSibling.classList.toggle('expanded');
            }});
        }});
    </script>
</body>
</html>'''

    def _render_steps(self) -> str:
        parts = []
        for step in self.steps:
            parts.append(f'''
    <div class="step">
        <div class="step-header">
            <div class="step-number">{step["number"]}</div>
            <div class="step-title">{step["title"]}</div>
            <div class="step-toggle">&#9660;</div>
        </div>
        <div class="step-body">
            {step["content"]}
        </div>
    </div>''')
        return "\n".join(parts)

    def _render_visualizations(self) -> str:
        parts = []
        for viz in self.visualizations:
            parts.append(f'''
    <div class="viz-section">
        <h3>{viz["title"]}</h3>
        {viz["html"]}
    </div>''')
        return "\n".join(parts)

    def _render_answer(self) -> str:
        if not self.answer:
            return ""
        paragraphs = self.answer.strip().split("\n\n")
        body = "".join(f"<p>{p.strip()}</p>" for p in paragraphs if p.strip())
        return f'''
    <div class="answer-section">
        <h2>Answer</h2>
        {body}
    </div>'''

    def _render_provenance(self) -> str:
        items = []
        for key, value in self.provenance.items():
            if isinstance(value, list):
                val_str = ", ".join(str(v) for v in value)
            elif isinstance(value, dict):
                val_str = "<br>".join(f"{k}: {v}" for k, v in value.items())
            else:
                val_str = str(value)
            items.append(f"<dt>{key}</dt><dd>{val_str}</dd>")
        dl = "\n            ".join(items)
        return f'''
    <div class="provenance">
        <h3>Provenance &#9660;</h3>
        <div class="provenance-body">
            <dl>
            {dl}
            </dl>
        </div>
    </div>'''


def results_table(rows: List[Dict[str, str]], columns: Optional[List[str]] = None) -> str:
    """Render a list of dicts as an HTML table."""
    if not rows:
        return '<p class="no-data">No results</p>'
    cols = columns or list(rows[0].keys())
    header = "".join(f"<th>{c}</th>" for c in cols)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{row.get(c, '')}</td>" for c in cols)
        body_rows.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def summary_stats(label: str, value: Any) -> str:
    """Render a single key-value statistic."""
    return f"<p><strong>{label}:</strong> {value}</p>"
