# Biomedical Data Integration Demos

Reusable packages and question-driven investigations that integrate the **NIAID Data Ecosystem** with knowledge graphs (FRINK, Wikidata, Ubergraph), single-cell data (CellxGene Census), and bulk RNA-seq (ARCHS4).

## Quick Start

```bash
cd scripts/demos

# Run a single question
python -m questions.gene_disease_map
python -m questions.gene_neighborhood_map --gene TP53

# List all questions
python -m questions.run_all --list

# Run all questions (produces HTML reports in questions/output/)
python -m questions.run_all

# Run analysis tools directly
python -m analysis_tools.gene_paths SFRP2
python -m analysis_tools.gene_neighborhood CD19 --html cd19_network.html
python -m analysis_tools.go_disease_analysis --go-term GO:0030198 --disease "pulmonary fibrosis" --tissue lung

# Run ChatGEO differential expression
python -m chatgeo.cli "psoriasis in skin tissue"
```

## Biological Questions

Each question is a self-contained investigation that queries multiple data sources and produces an interactive HTML report with vis.js networks and Plotly charts.

| # | Question | Data Sources | Run With |
|---|----------|--------------|----------|
| Q1 | What diseases is SFRP2 connected to, and through what mechanisms? | SPOKE, Wikidata, Ubergraph | `python -m questions.gene_disease_map` |
| Q2 | What is the biological neighborhood of CD19 across FRINK knowledge graphs? | SPOKE-OKN, SPOKE-GeneLab, Wikidata, NDE, BioBricks | `python -m questions.gene_neighborhood_map` |
| Q3 | Which ECM genes are dysregulated in pulmonary fibrosis, and which cell types drive the changes? | Ubergraph, Wikidata, CellxGene, ARCHS4 | `python -m questions.go_process_in_disease` |
| Q4 | What genes are differentially expressed in psoriasis skin tissue vs normal? | ARCHS4, g:Profiler | `python -m questions.differential_expression` |
| Q5 | What genes show opposing drug vs disease expression? | GXA/Fuseki, SPOKE | `python -m questions.drug_disease_targets` |
| Q6 | What B cell activation genes have expression data in NIAID vaccination studies? | Wikidata, NIAID, ARCHS4 | `python -m questions.cross_layer_datasets` |
| Q7 | What is ACTA2's role in pulmonary fibrosis across cell types and data sources? | Wikidata, CellxGene, NIAID, ARCHS4 | `python -m questions.single_gene_deep_dive` |

Each question module accepts `--help` for parameter overrides (e.g., `--gene`, `--disease`, `--tissue`).

## Directory Structure

```
scripts/demos/
├── clients/          # Data source clients (SPARQL, NIAID, ARCHS4, CellxGene)
├── frink/            # FRINK KG integration (registry, context, NL-to-SPARQL)
├── analysis_tools/   # Reusable analysis tools
│   ├── gene_paths.py          # Gene-disease connections across KGs
│   ├── gene_neighborhood.py   # Gene neighborhood across FRINK graphs
│   ├── drug_disease.py        # Opposing drug/disease expression
│   ├── go_disease_analysis.py # Multi-layer GO term disease analysis
│   └── visualization.py       # vis.js network and Plotly visualizations
├── chatgeo/          # Natural language differential expression pipeline
├── questions/        # Biological question investigations (Q1-Q7)
│   ├── _report.py             # Shared HTML report framework
│   ├── run_all.py             # Runner for all questions
│   ├── reference_queries/     # SPARQL query examples
│   └── output/                # Generated HTML reports (gitignored)
├── tests/            # Tests
├── config.py         # Shared configuration (.env loading)
└── .env.example      # Environment variable template
```

## Packages

### clients/

Unified data source clients. Import from the package:

```python
from clients import SPARQLClient, NIAIDClient, ARCHS4Client, CellxGeneClient
```

| Module | Data Layer | Description |
|--------|-----------|-------------|
| `sparql.py` | Wikidata, FRINK, Ubergraph | SPARQL client with named endpoints |
| `niaid.py` | NIAID Discovery Portal | Dataset search with ontology annotations |
| `archs4.py` | ARCHS4 (local HDF5) | Bulk RNA-seq expression from GEO |
| `cellxgene.py` | CellxGene Census | Single-cell RNA-seq expression |

### analysis_tools/

Reusable analysis tools. Import from the package:

```python
from analysis_tools import GeneDiseasePathFinder, GeneNeighborhoodQuery, PlotlyVisualizer
```

| Module | Description |
|--------|-------------|
| `gene_paths.py` | Gene-disease connections via SPOKE, Wikidata, Ubergraph |
| `gene_neighborhood.py` | Gene neighborhood across FRINK graphs |
| `drug_disease.py` | Opposing drug/disease expression (requires local GXA Fuseki) |
| `go_disease_analysis.py` | Multi-layer GO term analysis (KG + single-cell + bulk) |
| `visualization.py` | vis.js networks and Plotly charts |

### frink/

FRINK knowledge graph integration:

```python
from frink import FrinkContext, FrinkNL2SPARQL, FrinkRegistryClient
```

### chatgeo/

Natural language differential expression pipeline:

```bash
python -m chatgeo.cli "psoriasis in skin tissue" --verbose
```

## Environment Setup

```bash
cp .env.example .env
```

Required variables:

| Variable | Required For | Description |
|----------|-------------|-------------|
| `ARCHS4_DATA_DIR` | ARCHS4/ChatGEO | Path to ARCHS4 HDF5 files (~15GB each) |
| `ANTHROPIC_API_KEY` | LLM summaries | Anthropic API key |
| `DATA_DIR` | Caching | Directory for intermediate result caching |

## Dependencies

```bash
# Core clients
pip install requests SPARQLWrapper

# Single-cell
pip install cellxgene-census

# Bulk RNA-seq
pip install h5py pandas numpy

# ChatGEO / DE analysis
pip install scipy pydeseq2 gprofiler-official

# Visualizations
pip install plotly

# LLM summaries
pip install anthropic
```

## External Integrations

| Service | URL | Used By |
|---------|-----|---------|
| FRINK | https://frink.apps.renci.org/ | Q1, Q2, Q3 |
| Wikidata | https://query.wikidata.org/sparql | Q1, Q2, Q3, Q6 |
| CellxGene Census | via `cellxgene-census` | Q3, Q7 |
| ARCHS4 | Local HDF5 files | Q3, Q4, Q6, Q7 |
| NIAID | https://api.data.niaid.nih.gov/ | Q6, Q7 |
| GXA/Fuseki | http://localhost:3030/GXA-v2/sparql | Q5 |
| g:Profiler | https://biit.cs.ut.ee/gprofiler/ | Q4 |
