# GO Disease Analyzer

A multi-layer gene expression analysis tool that answers questions of the form:

> **"Which genes involved in [BIOLOGICAL PROCESS] are dysregulated in [DISEASE], and which cell types drive those changes?"**

## Workflow Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GO DISEASE ANALYZER                               │
│                                                                             │
│  INPUT: GO Term + Disease + Tissue                                          │
│  Example: GO:0042113 (B cell activation) + SLE + blood                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 1: KNOWLEDGE GRAPH DISCOVERY                                         │
│  ┌─────────────────┐         ┌─────────────────┐                           │
│  │    Ubergraph    │         │    Wikidata     │                           │
│  │  (GO Ontology)  │         │ (Gene-GO links) │                           │
│  └────────┬────────┘         └────────┬────────┘                           │
│           │                           │                                     │
│           ▼                           ▼                                     │
│  ┌─────────────────┐         ┌─────────────────┐                           │
│  │ GO:0042113 +    │  ───►   │ Human genes     │                           │
│  │ 28 subclasses   │         │ annotated to    │                           │
│  │ (B cell activ., │         │ these GO terms  │                           │
│  │  BCR signaling, │         │                 │                           │
│  │  etc.)          │         │ → 149 genes     │                           │
│  └─────────────────┘         └─────────────────┘                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 2: SINGLE-CELL EXPRESSION (CellxGene Census)                         │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  For each gene, compare expression:                                   │  │
│  │                                                                       │  │
│  │    NORMAL blood cells  ◄─────────────►  SLE blood cells              │  │
│  │    (13.8M cells)                        (777K cells)                  │  │
│  │                                                                       │  │
│  │  Calculate per cell type:                                             │  │
│  │    • Fold change (disease/normal)                                     │  │
│  │    • Mean expression in each condition                                │  │
│  │    • Number of cells analyzed                                         │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  OUTPUT:                                                                    │
│    • Top upregulated genes (FC > 1.5)                                       │
│    • Top downregulated genes (FC < 0.67)                                    │
│    • Cell types driving expression changes                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 3: BULK RNA-SEQ VALIDATION (ARCHS4)                                  │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  Search GEO studies:                                                  │  │
│  │                                                                       │  │
│  │    Disease samples          Control samples                           │  │
│  │    ┌─────────────┐          ┌─────────────┐                          │  │
│  │    │ GSE123456   │          │ "normal     │                          │  │
│  │    │ GSE789012   │          │  blood"     │                          │  │
│  │    │ ...         │          │ samples     │                          │  │
│  │    └─────────────┘          └─────────────┘                          │  │
│  │           │                        │                                  │  │
│  │           └────────┬───────────────┘                                  │  │
│  │                    ▼                                                  │  │
│  │         Calculate differential expression                             │  │
│  │         for top genes from Layer 2                                    │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  OUTPUT:                                                                    │
│    • Fold changes validated across independent studies                      │
│    • GEO series IDs for data provenance                                     │
│    • Concordance score                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 4: LLM SUMMARY (Claude)                                              │
│                                                                             │
│  Generates natural language summary with:                                   │
│    • Key findings                                                           │
│    • Biological interpretation                                              │
│    • Data provenance (GO terms, datasets, GEO IDs)                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  OUTPUT: JSON + Console Report                                              │
│                                                                             │
│  {                                                                          │
│    "query": { "go_term": "GO:0042113", "disease": "SLE", ... },            │
│    "layer1_knowledge": { "n_genes": 149, "genes": [...] },                  │
│    "layer2_singlecell": { "top_upregulated": [...], "cell_types": [...] }, │
│    "layer3_validation": { "differential_expression": [...] },               │
│    "llm_summary": "..."                                                     │
│  }                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Sources

| Layer | Source | What it provides |
|-------|--------|------------------|
| 1 | **Ubergraph** | GO term hierarchy (parent + subclasses) |
| 1 | **Wikidata** | Gene-to-GO term annotations for human genes |
| 2 | **CellxGene Census** | Single-cell RNA-seq across millions of cells |
| 3 | **ARCHS4** | Bulk RNA-seq from GEO (local HDF5 files) |
| 4 | **Claude API** | Natural language summary generation |

## Installation

```bash
# Required
pip install sparqlwrapper cellxgene-census

# Optional (for ARCHS4 validation)
pip install archs4py

# Optional (for LLM summaries)
pip install anthropic
```

## Environment Setup

Create a `.env` file in `scripts/demos/`:

```bash
# Required for caching
DATA_DIR=/path/to/cache/directory

# Required for ARCHS4 validation
ARCHS4_DATA_DIR=/path/to/archs4/hdf5/files

# Required for LLM summaries
ANTHROPIC_API_KEY=your-api-key
```

## Usage

### Basic Usage

```bash
# B cell activation genes in systemic lupus erythematosus
python go_disease_analyzer.py \
    --go-term GO:0042113 \
    --go-label "B cell activation" \
    --disease "systemic lupus erythematosus" \
    --tissue blood \
    --output lupus_bcell.json
```

### Example Queries

```bash
# ECM genes in pulmonary fibrosis (lung tissue)
python go_disease_analyzer.py \
    --go-term GO:0030198 \
    --go-label "extracellular matrix organization" \
    --disease "pulmonary fibrosis" \
    --tissue lung \
    --output ecm_fibrosis.json

# Inflammatory response in COVID-19 (lung)
python go_disease_analyzer.py \
    --go-term GO:0006954 \
    --go-label "inflammatory response" \
    --disease "COVID-19" \
    --tissue lung \
    --output inflammatory_covid.json

# Toll-like receptor signaling in lupus (blood)
python go_disease_analyzer.py \
    --go-term GO:0002224 \
    --go-label "toll-like receptor signaling pathway" \
    --disease "systemic lupus erythematosus" \
    --tissue blood \
    --output tlr_lupus.json

# Complement activation in lupus
python go_disease_analyzer.py \
    --go-term GO:0006956 \
    --go-label "complement activation" \
    --disease "systemic lupus erythematosus" \
    --tissue blood \
    --output complement_lupus.json
```

### Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--go-term` | GO term ID (required) | - |
| `--go-label` | Human-readable label | Auto-fetched |
| `--disease` | Disease name (must match CellxGene) | - |
| `--tissue` | Tissue name | - |
| `--uberon-id` | UBERON ID for precise tissue filtering | - |
| `--control-term` | ARCHS4 control search term | "normal {tissue}" |
| `--max-genes` | Maximum genes to analyze | 30 |
| `--output`, `-o` | Output JSON file | - |
| `--no-cache` | Disable caching | False |
| `--skip-cellxgene` | Skip single-cell analysis | False |
| `--skip-archs4` | Skip bulk RNA-seq validation | False |

## Finding Good Query Parameters

### Available Diseases in CellxGene

Diseases with good single-cell data coverage (check before running):

**Lung tissue:**
- `normal`, `COVID-19`, `pulmonary fibrosis`, `lung adenocarcinoma`
- `interstitial lung disease`, `chronic obstructive pulmonary disease`

**Blood:**
- `normal`, `COVID-19`, `systemic lupus erythematosus`
- `rheumatoid arthritis`, `cytomegalovirus infection`

### Finding GO Terms

Use the GO browser or search Ubergraph:

```python
from sparql_client import SPARQLClient

client = SPARQLClient('https://ubergraph.apps.renci.org/sparql')
results = client.query('''
    SELECT ?go_id ?label WHERE {
        ?go_term rdfs:label ?label .
        FILTER(CONTAINS(LCASE(?label), "interferon"))
        BIND(REPLACE(STR(?go_term), "http://purl.obolibrary.org/obo/GO_", "GO:") AS ?go_id)
    } LIMIT 20
''')
```

### Recommended GO Terms by Disease

| Disease | Relevant GO Terms |
|---------|-------------------|
| **SLE (Lupus)** | GO:0034340 (type I interferon response), GO:0042113 (B cell activation), GO:0006956 (complement activation), GO:0002224 (TLR signaling) |
| **Pulmonary Fibrosis** | GO:0030198 (ECM organization), GO:0006954 (inflammatory response), GO:0030199 (collagen fibril organization) |
| **COVID-19** | GO:0006954 (inflammatory response), GO:0045087 (innate immune response), GO:0034340 (type I interferon response) |
| **Rheumatoid Arthritis** | GO:0006954 (inflammatory response), GO:0042113 (B cell activation), GO:0006956 (complement activation) |

## Output Format

The tool produces a JSON file with the following structure:

```json
{
  "query": {
    "go_term": "GO:0042113",
    "go_label": "B cell activation",
    "disease": "systemic lupus erythematosus",
    "tissue": "blood"
  },
  "timestamp": "2024-01-15T10:30:00Z",

  "layer1_knowledge": {
    "n_genes": 149,
    "sample_genes": ["CD19", "CD79A", "BTK", ...],
    "genes_with_go_terms": [
      {"symbol": "CD19", "go_terms": ["B cell activation", "B cell receptor signaling"]}
    ]
  },

  "layer2_singlecell": {
    "n_genes_analyzed": 30,
    "n_upregulated": 12,
    "n_downregulated": 5,
    "top_upregulated": [
      {"symbol": "IGHG1", "fold_change": 3.2, "top_cell_type": "plasma cell"}
    ],
    "cell_type_drivers": [
      {"cell_type": "plasma cell", "n_upregulated": 8, "genes": [...]}
    ]
  },

  "layer3_validation": {
    "n_studies": 5,
    "n_disease_samples": 120,
    "n_control_samples": 85,
    "differential_expression": [
      {"gene": "IGHG1", "fold_change": 2.8, "log2_fc": 1.49, "mean_disease": 245.3, "mean_control": 87.6}
    ],
    "studies": [
      {"gse": "GSE123456", "study_title": "SLE blood transcriptome", "n_samples": 24}
    ]
  },

  "llm_summary": "Analysis of B cell activation genes in systemic lupus erythematosus reveals..."
}
```

## Caching

Results are cached in `$DATA_DIR/go_disease_cache/`:
- GO gene queries: `go_genes_{hash}.json`
- CellxGene results: `cellxgene_{hash}.json` and `gene_expr_{hash}_{gene}.json`

Use `--no-cache` to force fresh queries.

## Troubleshooting

### "No data found for disease X in tissue Y"

Check available diseases:
```python
from cellxgene_client import CellxGeneClient
import cellxgene_census

with CellxGeneClient() as client:
    obs = cellxgene_census.get_obs(
        client.census, 'homo_sapiens',
        value_filter="tissue_general == 'blood'",
        column_names=['disease']
    )
    print(obs['disease'].value_counts())
```

### "SPARQL query timeout"

The tool uses a two-step query approach (Ubergraph then Wikidata) to avoid federated query timeouts. If you still see timeouts, try:
- Reducing `--max-genes`
- Using `--no-cache` to retry

### "ARCHS4 not available"

Ensure `ARCHS4_DATA_DIR` points to a directory containing the ARCHS4 HDF5 files (human_gene_v2.2.h5 or similar, ~15GB each).

## Citation

If you use this tool, please cite:
- CellxGene Census: https://chanzuckerberg.github.io/cellxgene-census/
- ARCHS4: https://maayanlab.cloud/archs4/
- Ubergraph: https://github.com/INCATools/ubergraph
- Gene Ontology: http://geneontology.org/
