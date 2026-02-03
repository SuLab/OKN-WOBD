# analysis_tools

Reusable analysis tools for biomedical data exploration. Each module can be used as a Python library or run directly from the command line.

## Modules

| Module | Description | Data Sources |
|--------|-------------|--------------|
| `gene_paths.py` | Find gene-disease connections and the mechanisms linking them | SPOKE-OKN, Wikidata, Ubergraph |
| `gene_neighborhood.py` | Query the biological neighborhood of a gene across FRINK knowledge graphs | SPOKE-OKN, SPOKE-GeneLab, Wikidata, NDE, BioBricks |
| `go_disease_analysis.py` | Multi-layer analysis: which genes in a GO process are dysregulated in a disease, and which cell types drive the changes? | Ubergraph, Wikidata, CellxGene Census, ARCHS4 |
| `drug_disease.py` | Find genes with opposing expression between drug treatment and disease | GXA/Fuseki (local) |
| `visualization.py` | Interactive vis.js network graphs and Plotly charts | — |

## Quick Start

```bash
cd scripts/demos

# Gene-disease connections
python -m analysis_tools.gene_paths SFRP2
python -m analysis_tools.gene_paths --gene ACTA2 --verbose --html acta2_network.html

# Gene neighborhood
python -m analysis_tools.gene_neighborhood CD19
python -m analysis_tools.gene_neighborhood CD19 --html cd19_network.html
python -m analysis_tools.gene_neighborhood --ncbi 930 --format json

# GO term disease analysis (multi-layer)
python -m analysis_tools.go_disease_analysis \
    --go-term GO:0030198 \
    --disease "pulmonary fibrosis" \
    --tissue lung \
    --output ecm_fibrosis.json

# Drug-disease opposing expression (requires local GXA Fuseki)
python -m analysis_tools.drug_disease
```

## Python API

```python
from analysis_tools import (
    GeneDiseasePathFinder,
    GeneNeighborhoodQuery,
    find_drug_disease_genes,
    run_go_disease_analysis,
    PlotlyVisualizer,
)

# Gene-disease paths
finder = GeneDiseasePathFinder(verbose=True)
connections = finder.find_all_connections("SFRP2")

# Gene neighborhood
querier = GeneNeighborhoodQuery()
neighborhood = querier.query_all(symbol="CD19")

# GO term disease analysis
results = run_go_disease_analysis(
    go_term="GO:0030198",
    disease="pulmonary fibrosis",
    tissue="lung",
)

# Drug-disease opposing expression
results = find_drug_disease_genes(drug_direction="down", disease_direction="up")

# Visualizations
viz = PlotlyVisualizer()
html = viz.gene_disease_network(connections, title="SFRP2 Diseases")
html = viz.neighborhood_network(neighborhood)
```

## Module Details

### gene_paths.py

Finds connections between a gene and diseases across three knowledge graphs:

- **SPOKE-OKN**: Direct marker associations (positive/negative), expression links
- **Wikidata**: Genetic associations, protein-GO term-disease paths
- **Ubergraph**: GO term to disease relationships via ontology reasoning

Path types: `MARKER_POS`, `MARKER_NEG`, `EXPRESSEDIN`, `ASSOCIATES`, `GO_PROCESS`.

Outputs a vis.js interactive network when `--html` is specified.

### gene_neighborhood.py

Queries the immediate neighborhood of a gene across multiple FRINK knowledge graphs. Returns related entities (diseases, GO terms, datasets, pathways) grouped by source graph.

Supports lookup by gene symbol or NCBI Gene ID. Output formats: text summary, JSON, table. Generates a vis.js network with `--html`.

### go_disease_analysis.py

Three-layer analysis answering: *"Which genes involved in [BIOLOGICAL PROCESS] are dysregulated in [DISEASE], and which cell types drive those changes?"*

1. **Knowledge Graph layer** (Ubergraph/Wikidata) -- discovers genes annotated to the GO term
2. **Single-cell layer** (CellxGene Census) -- analyzes cell-type-specific expression in disease vs normal
3. **Bulk RNA-seq layer** (ARCHS4) -- validates findings with differential expression across GEO studies

Produces a JSON report with all three layers plus an optional LLM-generated summary.

### drug_disease.py

Finds genes where drug treatment and disease push expression in opposite directions:

1. **Drug DOWN / Disease UP** -- drug suppresses a pathologically elevated gene
2. **Drug UP / Disease DOWN** -- drug activates a pathologically suppressed gene

Requires a local GXA Fuseki server at `http://localhost:3030/GXA-v2/sparql`.

### visualization.py

Interactive visualizations built on Plotly and vis.js:

- `gene_disease_network()` -- vis.js network of gene-disease connections
- `neighborhood_network()` -- vis.js network of a gene's biological neighborhood
- `expression_comparison()` -- Plotly bar chart comparing fold changes
- `drug_disease_patterns()` -- Plotly chart of opposing drug/disease expression
- `save_html()` -- save any Plotly figure as a self-contained HTML file

## Dependencies

```bash
pip install SPARQLWrapper requests   # SPARQL queries
pip install cellxgene-census         # Single-cell (go_disease_analysis)
pip install h5py pandas numpy        # ARCHS4 bulk RNA-seq (go_disease_analysis)
pip install plotly                   # Visualizations
pip install anthropic                # LLM summaries (go_disease_analysis)
```

## Environment Variables

Set in `scripts/demos/.env`:

| Variable | Required By | Description |
|----------|------------|-------------|
| `ARCHS4_DATA_DIR` | `go_disease_analysis` | Path to ARCHS4 HDF5 files |
| `ANTHROPIC_API_KEY` | `go_disease_analysis` | Anthropic API key for LLM summaries |
| `DATA_DIR` | `go_disease_analysis` | Directory for intermediate result caching |
