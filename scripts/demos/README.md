# Demos: Integrating NIAID with Knowledge Graphs and Data Repositories

This folder contains reusable clients and demonstration scripts for integrating the **NIAID Data Ecosystem** with external knowledge graph resources and aggregated data repositories.

## Purpose

These tools enable discovery and analysis workflows that connect:

1. **NIAID Data Ecosystem** - Federated search across biomedical data repositories
2. **Knowledge Graphs** - FRINK (Wikidata, Ubergraph, SPOKE) for ontology and relationship queries
3. **Expression Repositories** - ARCHS4 for uniformly processed RNA-seq data

By combining these resources, researchers can:
- Find datasets using ontology-based queries (MONDO diseases, NCBI Taxonomy, GO terms)
- Enrich dataset metadata with knowledge graph relationships
- Link clinical/immunology datasets to gene expression profiles
- Validate and expand findings across multiple data sources

## Clients

### NIAIDClient (`niaid_client.py`)

Client for the [NIAID Data Ecosystem Discovery Portal](https://data.niaid.nih.gov/) API.

**Features:**
- Search across 20+ biomedical repositories (ImmPort, Vivli, GEO, Zenodo, etc.)
- Query by disease (MONDO), species (NCBI Taxonomy), pathogen, or keywords
- Faceted search with automatic pagination
- Ontology annotation extraction from results

```python
from niaid_client import NIAIDClient

client = NIAIDClient()

# Search by keyword
result = client.search("vaccine", size=10)

# Search by disease + keyword
result = client.search_by_disease("influenza", keywords="vaccine")

# Search by species (NCBI Taxonomy ID)
result = client.search_by_species("9606", keywords="immunotherapy")  # Human

# Filter by repository
result = client.search_by_catalog("ImmPort", query="malaria")

# Paginated fetch
all_datasets = client.fetch_all("COVID-19 vaccine", max_results=500)
```

### SPARQLClient (`sparql_client.py`)

Client for querying SPARQL endpoints, pre-configured for [FRINK](https://frink.apps.renci.org/) knowledge graphs.

**Supported Endpoints:**
- **Wikidata** - General knowledge graph with biomedical entities
- **Ubergraph** - Integrated OBO ontology graph (MONDO, HP, GO, CHEBI, etc.)
- **SPOKE** - Biomedical knowledge graph

```python
from sparql_client import SPARQLClient

client = SPARQLClient()

# Get subclasses of infectious disease from Ubergraph
subclasses = client.get_subclasses("MONDO:0005550", endpoint="ubergraph")

# Get genes associated with a GO term via Wikidata
genes = client.get_genes_for_go_term("GO:0006915")  # Apoptosis

# Get disease-gene associations
disease_genes = client.get_disease_genes("MONDO:0005812")  # Influenza

# Custom SPARQL query
result = client.query("""
    SELECT ?disease ?label WHERE {
        ?disease rdfs:subClassOf* MONDO:0005550 .
        ?disease rdfs:label ?label .
    } LIMIT 10
""", endpoint="ubergraph")
```

### ARCHS4Client (`archs4_client.py`)

Client for [ARCHS4](https://maayanlab.cloud/archs4/) uniformly processed RNA-seq data from GEO.

**Features:**
- Query by GEO series (GSE) or sample (GSM) IDs
- Metadata-based search (tissue, cell type, condition)
- Expression normalization (quantile, CPM, TMM)
- Gene filtering utilities

```python
from archs4_client import ARCHS4Client

# Initialize (requires downloaded H5 file)
client = ARCHS4Client(organism="human", data_dir="./data")

# Get expression for a GEO series
expr_df = client.get_expression_by_series("GSE64016")
meta_df = client.get_metadata_by_series("GSE64016")

# Search by metadata keywords
expr_df = client.search_expression("pancreatic beta cell")

# Get specific samples
expr_df = client.get_expression_by_samples(["GSM1158284", "GSM1482938"])

# Normalize expression data
normalized = client.normalize_expression(expr_df, method="log_quantile")
```

**Note:** ARCHS4 requires downloading large H5 files (~15-25GB):
```python
# Download via client
client = ARCHS4Client(organism="human", auto_download=True)

# Or download manually from: https://maayanlab.cloud/archs4/download.html
```

## Demos

### Vaccine Search Demo (`demo_niaid_vaccine.py`)

Demonstrates NIAID query patterns for vaccine-related datasets:

```bash
python demo_niaid_vaccine.py
```

Shows:
- Simple keyword search
- Disease-specific queries (influenza, malaria)
- Species filtering (human, mouse)
- Repository filtering (ImmPort, Vivli)
- Ontology annotation extraction
- Facet analysis

## Integration Patterns

### Pattern 1: Ontology-Enriched Dataset Discovery

Use knowledge graphs to expand disease queries, then search NIAID:

```python
from sparql_client import SPARQLClient
from niaid_client import NIAIDClient

sparql = SPARQLClient()
niaid = NIAIDClient()

# Get child diseases of "infectious disease" from Ubergraph
diseases = sparql.get_subclasses("MONDO:0005550", endpoint="ubergraph", limit=50)

# Search NIAID for datasets related to each
for disease in diseases:
    result = niaid.search_by_disease(disease['label'], keywords="vaccine")
    print(f"{disease['label']}: {result.total} datasets")
```

### Pattern 2: Gene Expression for NIAID Datasets

Link NIAID datasets to ARCHS4 expression data via GEO accessions:

```python
from niaid_client import NIAIDClient
from archs4_client import ARCHS4Client

niaid = NIAIDClient()
archs4 = ARCHS4Client(organism="human", data_dir="./data")

# Find GEO datasets in NIAID
result = niaid.search_by_catalog("NCBI GEO", query="influenza vaccine")

for hit in result:
    geo_id = hit.get("identifier", "")
    if geo_id.startswith("GSE") and archs4.has_series(geo_id):
        expr = archs4.get_expression_by_series(geo_id)
        print(f"{geo_id}: {expr.shape[0]} genes x {expr.shape[1]} samples")
```

### Pattern 3: Disease-Gene-Expression Pipeline

Combine all three resources:

```python
from sparql_client import SPARQLClient
from niaid_client import NIAIDClient
from archs4_client import ARCHS4Client

# 1. Get genes associated with a disease from Wikidata
sparql = SPARQLClient()
genes = sparql.get_disease_genes("MONDO:0005812")  # Influenza
gene_symbols = [g['symbol'] for g in genes]

# 2. Find related datasets in NIAID
niaid = NIAIDClient()
datasets = niaid.search_by_disease("influenza", keywords="transcriptome")

# 3. Get expression for disease genes from ARCHS4
archs4 = ARCHS4Client(organism="human", data_dir="./data")
for hit in datasets:
    geo_id = hit.get("identifier", "")
    if geo_id.startswith("GSE") and archs4.has_series(geo_id):
        expr = archs4.get_expression_by_series(geo_id, genes=gene_symbols)
        # Analyze disease gene expression...
```

## Installation

```bash
# Core dependencies
pip install requests pandas SPARQLWrapper

# For ARCHS4 client
pip install archs4py
```

## External Resources

- **NIAID Data Ecosystem**: https://data.niaid.nih.gov/
- **FRINK Knowledge Graphs**: https://frink.apps.renci.org/
- **ARCHS4**: https://maayanlab.cloud/archs4/
- **Wikidata SPARQL**: https://query.wikidata.org/
- **Ubergraph**: https://github.com/INCATools/ubergraph

### FusekiClient (`fuseki_client.py`)

Client for querying local Apache Fuseki SPARQL servers, particularly the GXA (Gene Expression Atlas) dataset.

**Features:**
- Query local Fuseki SPARQL endpoints
- Pre-configured for GXA-v2 gene expression data
- Automatic retry with exponential backoff
- Reuses QueryResult from sparql_client.py

```python
from fuseki_client import FusekiClient

client = FusekiClient(dataset='GXA-v2', timeout=120)

# Simple query returning list of dicts
results = client.query_simple('''
    SELECT ?study ?title WHERE {
        ?study a biolink:Study ;
               spokegenelab:project_title ?title .
    } LIMIT 10
''')

# Check if server is available
if client.is_available():
    print("Fuseki server is running")
```

### CellxGeneClient (`cellxgene_client.py`)

Client for [CellxGene Census](https://chanzuckerberg.github.io/cellxgene-census/) single-cell RNA-seq data.

**Features:**
- Query cell-type-specific gene expression
- Compare disease vs normal conditions
- Filter by tissue, cell type, disease

```python
from cellxgene_client import CellxGeneClient

with CellxGeneClient() as client:
    # Get cell-type comparison for a gene
    comparison = client.get_cell_type_comparison(
        gene_symbol="ACTA2",
        tissue="lung",
        condition_a="normal",
        condition_b="pulmonary fibrosis"
    )
```

## Analysis Scripts

### Gene-Disease Path Finder (`gene_disease_paths.py`)

Finds connections between a gene and diseases using multiple knowledge graphs.

**Data Sources:**
- SPOKE-OKN: Direct gene-disease associations (markers, expression)
- Wikidata: Genetic associations, GO term annotations
- Ubergraph: GO term to disease phenotype mappings

**Path Types:**
| Type | Description |
|------|-------------|
| positive_marker | Gene is a positive marker for disease (SPOKE) |
| negative_marker | Gene is a negative marker for disease (SPOKE) |
| expressed_in | Gene differentially expressed in disease (SPOKE) |
| genetic_association | Gene genetically associated with disease (Wikidata) |
| go_pathway | Gene's GO term linked to disease phenotype (Ubergraph) |
| shared_pathway | Gene shares GO term with disease-associated gene |

```bash
# Find disease connections for SFRP2
python gene_disease_paths.py SFRP2

# With verbose output and JSON export
python gene_disease_paths.py SFRP2 --verbose -o sfrp2_paths.json
```

### Drug-Disease Expression Query (`query_drug_down_disease_up.py`)

Finds genes with opposing expression patterns between drug treatment and disease using the local GXA Fuseki database.

**Two patterns identified:**
1. **Drug DOWN → Disease UP**: Drug suppresses a gene that is pathologically elevated
2. **Drug UP → Disease DOWN**: Drug activates a gene that is pathologically suppressed

**Requirements:** Local Fuseki server running with GXA-v2 dataset at `http://localhost:3030/GXA-v2/sparql`

```bash
python query_drug_down_disease_up.py
```

**Output includes:**
- Gene symbol and expression fold changes
- Drug study title and experimental comparison
- Disease name and comparison context
- Summary statistics

### GO Term Disease Analyzer (`go_disease_analyzer.py`)

Multi-layer analysis of gene expression for genes in a GO term within a disease context.

**Layers:**
1. **Knowledge Graph** (FRINK/Ubergraph): Discover genes annotated to GO term
2. **Single-Cell** (CellxGene): Cell-type-specific expression changes
3. **Bulk Validation** (ARCHS4): Independent validation in bulk RNA-seq
4. **LLM Summary**: Natural language synthesis (requires ANTHROPIC_API_KEY)

```bash
# ECM genes in pulmonary fibrosis
python go_disease_analyzer.py \
    --go-term GO:0030198 \
    --disease "pulmonary fibrosis" \
    --tissue lung \
    --output ecm_fibrosis.json

# Inflammatory response in rheumatoid arthritis
python go_disease_analyzer.py \
    --go-term GO:0006954 \
    --disease "rheumatoid arthritis" \
    --tissue "synovial tissue"
```

## Context and Utility Scripts

### FRINK Context Builder (`frink_context_builder.py`)

Builds context files documenting FRINK knowledge graph schemas for LLM-assisted query generation.

### FRINK NL2SPARQL (`frink_nl2sparql.py`)

Natural language to SPARQL query translation using LLMs and FRINK context.

### Gene Neighborhood (`gene_neighborhood.py`)

Finds genes in the genomic neighborhood of a target gene.

### Visualization (`visualize_results.py`)

Generates provenance visualizations for multi-layer analysis results.

## GXA Context File

The `gxa_context.json` file documents the GXA-v2 dataset schema:

```json
{
  "endpoint": "http://localhost:3030/GXA-v2/sparql",
  "statistics": {
    "total_triples": 10811134,
    "studies": 1774,
    "genes": 873159,
    "diseases": 305
  },
  "schema": {
    "classes": ["biolink:Study", "biolink:Assay", "biolink:Gene", ...],
    "key_relationships": [...]
  }
}
```

## Ontology References

| Resource | Ontology | Example ID |
|----------|----------|------------|
| Disease | MONDO | MONDO:0005812 (influenza) |
| Disease | DOID | DOID:1793 (pancreatic cancer) |
| Species | NCBI Taxonomy | 9606 (human) |
| Gene Function | GO | GO:0006915 (apoptosis) |
| Phenotype | HP | HP:0001945 (fever) |
| Chemical | CHEBI | CHEBI:15377 (water) |
| Anatomy | UBERON | UBERON:0002048 (lung) |
| Cell Type | CL | CL:0000084 (T cell) |

## Environment Setup

Some scripts require environment variables in a `.env` file:

```bash
# Copy example and edit
cp .env.example .env

# Required for ARCHS4
ARCHS4_DATA_DIR=/path/to/archs4/h5files

# Required for LLM summaries
ANTHROPIC_API_KEY=your-api-key

# Optional for caching
DATA_DIR=/path/to/cache/dir
```
