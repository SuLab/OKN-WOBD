# ChatGEO

Natural language differential expression analysis using ARCHS4 bulk RNA-seq data.

ChatGEO takes a plain-text disease query (e.g., "psoriasis in skin tissue"), finds matching disease and control samples in the ARCHS4 compendium, and runs a statistical differential expression analysis.

## Prerequisites

**Python dependencies** (beyond the core `okn-wobd` package):

```
numpy
pandas
scipy
pydeseq2          # DESeq2 statistical model (default method)
gprofiler-official  # optional, for gene set enrichment analysis
```

**ARCHS4 HDF5 data files** (~15 GB each):

Download from [ARCHS4](https://maayanlab.cloud/archs4/download.html) and place in a local directory:

```
/path/to/archs4/
  human_gene_v2.latest.h5
  mouse_gene_v2.latest.h5   # only needed for --species mouse
```

## Setup

Set the `ARCHS4_DATA_DIR` environment variable to point to your HDF5 files:

```bash
export ARCHS4_DATA_DIR=/path/to/archs4
```

## Running

**Important**: Run from the `scripts/demos/` directory so that Python can find the `chatgeo` and `archs4_client` packages:

```bash
cd scripts/demos
python -m chatgeo.cli "psoriasis in skin tissue" --verbose
```

## Command Line Usage

```
python -m chatgeo.cli QUERY [OPTIONS]
```

### Positional Argument

| Argument | Description |
|----------|-------------|
| `QUERY` | Natural language query string (see Query Syntax below) |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--disease DISEASE` | (parsed from query) | Override the disease term from query parsing |
| `--tissue TISSUE` | (parsed from query) | Override or specify tissue constraint |
| `--species {human,mouse,both}` | `human` | Species to analyze |
| `--mode {pooled,study_matched,auto}` | `pooled` | Analysis mode |
| `--method {deseq2,mann-whitney,welch-t}` | `deseq2` | Statistical method for DE |
| `--fdr FLOAT` | `0.05` | FDR significance threshold |
| `--log2fc FLOAT` | `1.0` | Minimum absolute log2 fold change |
| `--max-test INT` | `500` | Maximum test (disease) samples |
| `--max-control INT` | `500` | Maximum control (healthy) samples |
| `--gene-filter {protein_coding,all}` | `protein_coding` | Gene biotype filter |
| `--include-mt-genes` | off | Include mitochondrial genes (MT-) |
| `--exclude-ribosomal` | off | Exclude ribosomal protein genes (RPS/RPL) |
| `--min-library-size INT` | `1000000` | Minimum library size to keep a sample |
| `--output PATH` | (none) | Output file path (.json or .tsv) |
| `--format {summary,json,tsv}` | `summary` | Output format |
| `--verbose, -v` | off | Print progress and diagnostic info |

## Query Syntax

ChatGEO parses natural language queries into a disease term and an optional tissue:

| Query | Parsed Disease | Parsed Tissue |
|-------|---------------|---------------|
| `"psoriasis in skin tissue"` | psoriasis | skin |
| `"breast cancer in mammary tissue"` | breast cancer | mammary |
| `"lung fibrosis"` | lung fibrosis | lung |
| `"alzheimer disease"` | alzheimer disease | (none) |

Recognized tissue prefixes: lung, liver, kidney, brain, heart, skin, blood, bone, muscle, intestine, colon, breast, prostate, ovarian, pancreatic, gastric, hepatic, renal, cardiac, pulmonary, dermal, neural.

Use `--tissue` to override or supply a tissue when query parsing does not detect one.

## Examples

```bash
# Basic psoriasis analysis with JSON output
python -m chatgeo.cli "psoriasis in skin tissue" \
    --output results.json --verbose

# Lung fibrosis with explicit tissue and stricter thresholds
python -m chatgeo.cli "lung fibrosis" \
    --tissue lung \
    --fdr 0.01 --log2fc 1.5 \
    --output fibrosis_results.json

# Rheumatoid arthritis, legacy Mann-Whitney test, limit samples
python -m chatgeo.cli "rheumatoid arthritis" \
    --tissue synovial \
    --method mann-whitney \
    --max-test 100 --max-control 100 \
    --output ra_results.json

# Mitochondrial myopathy, include MT genes (relevant to disease)
python -m chatgeo.cli "mitochondrial myopathy" \
    --tissue muscle \
    --include-mt-genes \
    --output mito_results.json

# Quick summary to stdout (no file output)
python -m chatgeo.cli "alzheimer disease" --tissue brain
```

Pre-built examples with saved results are in `examples/`. Run them all with:

```bash
cd scripts/demos/chatgeo/examples
python run_all_examples.py
```

## How It Works

1. **Query parsing** -- The natural language query is split into disease and tissue terms.

2. **Query expansion** -- Tissue/disease synonyms are added (e.g., "skin" expands to skin|dermal|cutaneous|epidermal) to broaden the ARCHS4 metadata search.

3. **Sample discovery** -- ARCHS4 metadata is searched for test samples matching the disease term, and control samples matching the tissue + control keywords (healthy, control, normal). Overlap between groups is removed.

4. **Expression retrieval** -- Raw gene expression counts are loaded from the ARCHS4 HDF5 file for both sample groups.

5. **Pre-processing** -- Samples with low library sizes (< 1M reads by default) are removed. Genes are filtered to protein-coding biotypes, duplicate gene symbols are collapsed, and low-count genes (< 10 total reads across all samples) are removed. Mitochondrial (MT-) and ribosomal (RPS/RPL) genes are optionally excluded.

6. **DE testing (DESeq2)** -- By default, the combined count matrix is analyzed using PyDESeq2, which applies median-of-ratios normalization, estimates per-gene dispersions via a negative binomial model, performs Wald tests for differential expression, and applies Benjamini-Hochberg FDR correction. Legacy Mann-Whitney U and Welch t-test methods are available as fallbacks.

7. **Enrichment analysis** -- Significant upregulated and downregulated gene lists are submitted to g:Profiler for Gene Ontology (BP, CC, MF), KEGG, and Reactome enrichment analysis.

8. **Output** -- Significant genes (FDR < threshold, |log2FC| >= threshold) are reported as upregulated or downregulated, with full provenance for reproducibility.

## Output Formats

**JSON** (`--output results.json`): Complete results including provenance (query parameters, sample IDs, study IDs, statistical settings) and per-gene statistics. Suitable for programmatic consumption.

**TSV** (`--output genes.tsv`): Tab-separated gene table with columns: gene_symbol, log2_fold_change, mean_test, mean_control, pvalue, pvalue_adjusted, direction, significant. Suitable for spreadsheet analysis.

**Summary** (default to stdout): Human-readable report with sample counts, method details, and top up/downregulated genes.

## Module Structure

```
chatgeo/
  cli.py                  # Entry point and argument parsing
  sample_finder.py        # ARCHS4 sample search (pooled and study-matched modes)
  query_builder.py        # Query expansion strategies (pattern-based, ontology placeholder)
  de_analysis.py          # Normalization, statistical testing, FDR correction
  de_result.py            # Result dataclasses with provenance
  enrichment_analyzer.py  # Gene set enrichment via g:Profiler
  gene_ranker.py          # Gene prioritization/ranking methods
  report_generator.py     # JSON, TSV, and console output formatting
  study_grouper.py        # Group samples by GEO study
  species_merger.py       # Cross-species ortholog mapping (framework)
  metrics.py              # Search quality metrics
  examples/               # Pre-built example queries and results
```
