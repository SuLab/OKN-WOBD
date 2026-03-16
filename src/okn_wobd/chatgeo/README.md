# ChatGEO

Natural language differential expression analysis using ARCHS4 bulk RNA-seq data.

ChatGEO takes a plain-text disease query (e.g., "psoriasis in skin tissue"), finds matching disease and control samples in the ARCHS4 compendium, runs statistical differential expression analysis, and optionally performs gene set enrichment analysis and AI-powered interpretation.

## Prerequisites

**Install with chatgeo extras:**

```bash
pip install -e ".[chatgeo]"
```

This pulls in the required dependencies: `numpy`, `scipy`, `pydeseq2`, `gprofiler-official`, and `h5py`.

Optional dependencies (not installed automatically):
- `anthropic` + `python-dotenv` — for AI interpretation of results (`ANTHROPIC_API_KEY` in `.env`)

**ARCHS4 HDF5 data files** (~58 GB each):

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

ChatGEO is an installed package. Run it with:

```bash
python -m okn_wobd.chatgeo.cli "psoriasis in skin tissue" --verbose
```

## Command Line Usage

```
python -m okn_wobd.chatgeo.cli QUERY [OPTIONS]
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
| `--mode {auto,pooled,study-matched}` | `auto` | Analysis mode (see Analysis Modes below) |
| `--method {mann-whitney,welch-t,deseq2}` | `mann-whitney` | Statistical method for DE |
| `--meta-method {stouffer,fisher}` | `stouffer` | Meta-analysis p-value combination method |
| `--min-studies INT` | `3` | Minimum matched studies for study-matched mode |
| `--platform-filter {none,majority}` | `none` | Filter controls to match dominant test platform |
| `--fdr FLOAT` | `0.01` | FDR significance threshold |
| `--log2fc FLOAT` | `2.0` | Minimum absolute log2 fold change |
| `--max-test INT` | `500` | Maximum test (disease) samples |
| `--max-control INT` | `500` | Maximum control (healthy) samples |
| `--gene-filter {protein_coding,all}` | `protein_coding` | Gene biotype filter |
| `--include-mt-genes` | off | Include mitochondrial genes (MT-) |
| `--exclude-ribosomal` | off | Exclude ribosomal protein genes (RPS/RPL) |
| `--min-library-size INT` | `1000000` | Minimum library size to keep a sample |
| `--output PATH` | (none) | Output directory for all result files |
| `--format {summary,json,tsv}` | `summary` | Output format |
| `--rdf` | off | Export Biolink RDF (requires `--output`) |
| `--rdf-format {turtle,nt}` | `turtle` | RDF serialization format |
| `--no-interpret` | | Skip AI interpretation step |
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
# Basic psoriasis analysis
python -m okn_wobd.chatgeo.cli "psoriasis in skin tissue" \
    --output results/psoriasis --verbose

# Lung fibrosis with explicit tissue and stricter thresholds
python -m okn_wobd.chatgeo.cli "lung fibrosis" \
    --tissue lung \
    --fdr 0.001 --log2fc 3.0 \
    --output results/fibrosis

# Study-matched meta-analysis (explicit mode)
python -m okn_wobd.chatgeo.cli "rheumatoid arthritis" \
    --tissue synovial \
    --mode study-matched --meta-method stouffer \
    --output results/arthritis --verbose

# Pooled mode with RDF export
python -m okn_wobd.chatgeo.cli "rheumatoid arthritis" \
    --tissue synovial \
    --mode pooled \
    --max-test 200 --max-control 200 \
    --output results/arthritis_pooled \
    --rdf --verbose

# Mitochondrial myopathy, include MT genes (relevant to disease)
python -m okn_wobd.chatgeo.cli "mitochondrial myopathy" \
    --tissue muscle \
    --include-mt-genes \
    --output results/mitochondrial --rdf

# Quick summary to stdout (no file output)
python -m okn_wobd.chatgeo.cli "alzheimer disease" --tissue brain
```

## Output Files

When using `--output <dir>`, ChatGEO writes:

| File | Description |
|------|-------------|
| `results.json` | Full results with gene statistics and enrichment |
| `genes.tsv` | Gene-level DE results (symbol, log2FC, p-value, etc.) |
| `enrichment.tsv` | Enrichment terms with p-values and gene counts |
| `summary.txt` | Text summary of the analysis |
| `interpretation.md` | AI-generated biological interpretation |
| `results.ttl` | Biolink RDF export (only with `--rdf`) |

## How It Works

### 1. Query parsing

The natural language query is split into disease and tissue terms using pattern matching. When a tissue is specified, an LLM-based query builder generates expanded search terms with include/exclude patterns for precise tissue matching; a pattern-based fallback is used if the LLM is unavailable.

### 2. Query expansion

Tissue and disease synonyms are added (e.g., "skin" expands to skin|dermal|cutaneous|epidermal) to broaden the ARCHS4 metadata search.

### 3. Sample discovery

ChatGEO finds test (disease) and control (healthy) samples through two complementary strategies:

- **Keyword search** — Searches ARCHS4 sample metadata for disease/tissue terms. Test samples match the disease term; control samples match the tissue plus control keywords (healthy, control, normal). Overlap between groups is removed.
- **Ontology-enhanced search** — Maps the disease to MONDO via Ubergraph, expands to include subtypes, finds associated GEO datasets via the NDE SPARQL endpoint, then classifies their ARCHS4 samples. This path discovers samples that keyword matching would miss (e.g., "osteoarthritis" finds studies annotated only with "degenerative joint disease"). Enabled by default; disable with `CHATGEO_ONTOLOGY_SEARCH=0`.

The two strategies are merged, with ontology-discovered samples supplementing keyword results.

### 4. Analysis modes

The `--mode` flag controls how samples are grouped for statistical testing:

- **`auto`** (default) — Tries study-matched meta-analysis first. If fewer than `--min-studies` matched studies are found, falls back to study-prioritized pooling, then basic pooling.
- **`study-matched`** — Runs independent DE within each GEO study that has both disease and control samples, then combines per-study results via meta-analysis (Stouffer's weighted Z or Fisher's method). This eliminates batch effects because each comparison is within a single study.
- **`pooled`** — Pools all test and control samples into a single comparison. Fast but susceptible to batch effects from mixing GEO studies.

### 5. Expression retrieval

Raw gene expression counts are loaded from the ARCHS4 HDF5 file for both sample groups.

### 6. Pre-processing

Samples with low library sizes (< 1M reads by default) are removed. Genes are filtered to protein-coding biotypes, duplicate gene symbols are collapsed, and low-count genes (< 10 total reads across all samples) are removed. Mitochondrial (MT-) and ribosomal (RPS/RPL) genes are optionally excluded.

### 7. DE testing

By default, a non-parametric Mann-Whitney U rank test is applied per gene across disease vs. control samples on log2(CPM+1) values. P-values are corrected with Benjamini-Hochberg FDR. DESeq2 and Welch t-test are available as alternatives via `--method` (see [Why Mann-Whitney is the default](#why-mann-whitney-is-the-default) below).

In study-matched mode, DE is run independently within each study, and per-gene p-values are combined across studies using Stouffer's weighted Z method (weights by sqrt(n_samples)) or Fisher's method. The combined p-values are then FDR-corrected.

### 8. Enrichment analysis

Significant upregulated and downregulated gene lists are submitted to g:Profiler for Gene Ontology (BP, CC, MF), KEGG, and Reactome enrichment analysis.

### 9. AI interpretation

An LLM summarizes the biological significance of the DE and enrichment results (requires `ANTHROPIC_API_KEY`). Skip with `--no-interpret`.

### 10. RDF export (opt-in)

Results are converted to Biolink Model RDF for integration into knowledge graphs. See the RDF Export section below.

## Why Mann-Whitney Is the Default

ChatGEO uses the [ARCHS4](https://maayanlab.cloud/archs4/) compendium as its expression data source. ARCHS4 processes raw GEO submissions through Kallisto pseudoalignment, rounds the resulting pseudocounts to integers for compression, and stores them as gene-level estimated counts. This preprocessing has important implications for statistical method choice.

### The problem with DESeq2 on ARCHS4 data

DESeq2 is the gold standard for differential expression -- **when given proper input**. The standard pipeline is raw FASTQ -> STAR/Kallisto -> [tximport](https://bioconductor.org/packages/tximport/) -> DESeq2. The tximport step creates a gene-level offset matrix that corrects for transcript length bias, and DESeq2 then fits a negative binomial model assuming the input follows that distribution.

ARCHS4 short-circuits this pipeline by providing pre-processed, rounded Kallisto pseudocounts without the tximport offset matrix. Feeding these directly into DESeq2 violates its distributional assumptions in three ways:

1. **Pseudocounts are estimates, not true counts** -- they carry estimation uncertainty that the negative binomial model does not account for.
2. **Without tximport's length offset**, changes in isoform usage across conditions appear as expression changes.
3. **Rounding introduces artifacts** in the variance structure that DESeq2's dispersion estimation relies on.

On top of this, ChatGEO (in pooled mode) pools samples across GEO studies, introducing batch effects that further confuse the parametric model. Study-matched mode eliminates this particular problem.

### Why Mann-Whitney is robust here

Mann-Whitney U is a non-parametric rank-based test: it only asks "is gene X higher in disease than controls?" without modeling the count distribution. Even if counts are pseudocounts, rounded, or have unusual distributional properties, the **rank order is largely preserved**. This makes it much more robust to both the ARCHS4 data format and cross-study batch effects.

### When to use DESeq2

DESeq2 remains available via `--method deseq2` and is appropriate when:

- You are analyzing samples from a **single GEO study** (minimal batch effects)
- You have reprocessed raw FASTQ files through the full tximport pipeline
- You need the specific statistical properties of the negative binomial model (e.g., for very small sample sizes where rank tests lose power)

### References

- [ARCHS4 platform](https://maayanlab.cloud/archs4/) and [Nature Communications paper](https://doi.org/10.1038/s41467-018-03751-6)
- [DESeq2 vignette](https://bioconductor.org/packages/devel/bioc/vignettes/DESeq2/inst/doc/DESeq2.html)
- [tximport documentation](https://bioconductor.org/packages/tximport/)

## Performance: SQLite Metadata Index

ARCHS4's HDF5 file contains ~1.05M samples across ~36K studies. The `archs4py` library has no indexing, so every metadata lookup loads the entire series_id array and does a linear scan. The ontology-enhanced pipeline calls `get_series_sample_ids()` for each of ~272 NDE-discovered studies, resulting in 272 redundant full scans.

`ARCHS4Client` now automatically builds and uses a SQLite metadata index (`*.metadata.db` alongside the HDF5 file). The index is built on first use (~15s) and provides indexed lookups, FTS5 full-text search, and REGEXP fallback.

| Operation | Without Index | With Index | Speedup |
|-----------|--------------|------------|---------|
| `has_series(gse_id)` | ~600ms | <0.01ms | ~60,000x |
| 272-study batch classify | ~170s | <1ms | ~170,000x |
| `search_metadata` (FTS5) | ~5-15s | 33ms | ~300x |
| Full ontology pipeline (osteoarthritis) | 173s | 11s | **16x** |

The index is transparent — all existing code benefits without changes. To disable it:

```python
client = ARCHS4Client(use_index=False)
```

## RDF Export

The `--rdf` flag generates a [Biolink Model](https://biolink.github.io/biolink-model/)
RDF graph capturing the full experiment: study metadata, gene-level differential
expression associations, and enrichment results. Gene symbols are resolved to
NCBI Gene IDs via a local HGNC cache.

### RDF Schema

The output uses the `http://purl.org/okn/wobd/` namespace (`okn-wobd` prefix)
for custom properties, and standard Biolink classes for node types.

**Node types:**

- `biolink:Study` -- the experiment (disease, organism, timestamp)
- `biolink:Assay` -- the comparison (test vs control, methods, thresholds, summary, interpretation)
- `biolink:Gene` -- differentially expressed genes (NCBI Gene IDs via HGNC)
- `biolink:GeneExpressionMixin` -- reified DE associations (log2FC, p-value, direction)
- `biolink:Association` -- enrichment associations (p-value, intersection size)
- `biolink:BiologicalProcess`, `biolink:Pathway`, etc. -- enrichment terms

**Example Turtle output:**

```turtle
@prefix biolink: <https://w3id.org/biolink/vocab/> .
@prefix okn-wobd: <http://purl.org/okn/wobd/> .
@prefix ncbigene: <https://www.ncbi.nlm.nih.gov/gene/> .

# Study node
okn-wobd:experiment/psoriasis_skin_20260204 a biolink:Study ;
    biolink:name "DE: psoriasis in skin" ;
    biolink:in_taxon <http://purl.obolibrary.org/obo/NCBITaxon_9606> ;
    okn-wobd:timestamp "2026-02-04T15:21:09" .

# Assay node (comparison with provenance)
okn-wobd:assay/psoriasis_skin_20260204_comparison a biolink:Assay ;
    biolink:name "psoriasis vs healthy" ;
    okn-wobd:test_method "deseq2" ;
    okn-wobd:platform "ARCHS4" ;
    okn-wobd:n_test_samples 200 ;
    okn-wobd:n_control_samples 200 ;
    okn-wobd:summary "..." ;
    okn-wobd:interpretation "..." .

# Gene node (IDO1, resolved to NCBI Gene ID)
ncbigene:3620 a biolink:Gene ;
    biolink:symbol "IDO1" ;
    biolink:id "NCBIGene:3620" .

# Reified DE association
okn-wobd:Association/abc123 a biolink:GeneExpressionMixin ;
    biolink:subject okn-wobd:assay/psoriasis_skin_20260204_comparison ;
    biolink:predicate biolink:affects_expression_of ;
    biolink:object ncbigene:3620 ;
    okn-wobd:log2fc 6.01 ;
    okn-wobd:adj_p_value 5.77e-31 ;
    okn-wobd:direction "up" .

# Enrichment association
okn-wobd:enrichment/def456 a biolink:Association ;
    biolink:subject okn-wobd:assay/psoriasis_skin_20260204_comparison ;
    biolink:object <http://purl.obolibrary.org/obo/GO_0006955> ;
    okn-wobd:adj_p_value 3.39e-24 ;
    okn-wobd:direction "up" .
```

### Example SPARQL: Find DE Genes for a Condition

Query all upregulated genes with log2FC > 4 in any experiment:

```sparql
PREFIX biolink: <https://w3id.org/biolink/vocab/>
PREFIX okn-wobd: <http://purl.org/okn/wobd/>

SELECT ?study_name ?symbol ?log2fc ?pvalue ?direction
WHERE {
    ?assoc a biolink:GeneExpressionMixin ;
           biolink:subject ?assay ;
           biolink:object ?gene ;
           okn-wobd:log2fc ?log2fc ;
           okn-wobd:adj_p_value ?pvalue ;
           okn-wobd:direction "up" .
    ?gene biolink:symbol ?symbol .
    ?study biolink:has_output ?assay .
    ?study biolink:name ?study_name .
    FILTER(?log2fc > 4)
}
ORDER BY DESC(?log2fc)
```

Query genes shared between two conditions (e.g., psoriasis and arthritis):

```sparql
PREFIX biolink: <https://w3id.org/biolink/vocab/>
PREFIX okn-wobd: <http://purl.org/okn/wobd/>

SELECT ?symbol ?log2fc_a ?log2fc_b
WHERE {
    ?assoc_a a biolink:GeneExpressionMixin ;
             biolink:subject ?assay_a ;
             biolink:object ?gene ;
             okn-wobd:log2fc ?log2fc_a .
    ?study_a biolink:has_output ?assay_a ;
             biolink:name ?name_a .
    FILTER(CONTAINS(?name_a, "psoriasis"))

    ?assoc_b a biolink:GeneExpressionMixin ;
             biolink:subject ?assay_b ;
             biolink:object ?gene ;
             okn-wobd:log2fc ?log2fc_b .
    ?study_b biolink:has_output ?assay_b ;
             biolink:name ?name_b .
    FILTER(CONTAINS(?name_b, "arthritis"))

    ?gene biolink:symbol ?symbol .
}
ORDER BY DESC(?log2fc_a)
```

## Analysis Modes

### Auto (default)

The `auto` mode implements a tiered fallback strategy:

1. **Study-matched meta-analysis** — Finds GEO studies with both disease and control samples, runs DE independently within each, then combines via Stouffer's Z or Fisher's method. Requires at least `--min-studies` matched studies (default: 3).
2. **Study-prioritized pooling** — If not enough matched studies, pools samples but prioritizes within-study pairs to reduce batch effects.
3. **Basic pooling** — Falls back to simple pooled comparison if the above fail.

### Study-matched meta-analysis

The most statistically rigorous mode. By running DE within each study, batch effects are eliminated entirely. Results are combined using:

- **Stouffer's weighted Z** (default) — Converts per-study p-values to Z-scores signed by log2FC direction, weights by sqrt(n_samples). Preserves effect direction.
- **Fisher's method** — Combines p-values without regard to direction. More powerful when effects are consistently in the same direction across studies.

### Pooled

All test and control samples are combined into a single comparison. This maximizes statistical power (largest possible sample sizes) but is susceptible to batch effects from mixing samples processed in different GEO studies.

## Module Structure

```
chatgeo/
  cli.py                  # Entry point and argument parsing
  sample_finder.py        # ARCHS4 sample search (pooled, study-matched, ontology-enhanced)
  query_builder.py        # Query expansion strategies (pattern-based, LLM, ontology)
  de_analysis.py          # Normalization, statistical testing, FDR correction
  de_result.py            # Result dataclasses with provenance tracking
  meta_analysis.py        # Per-study DE + Stouffer/Fisher meta-analysis combination
  enrichment_analyzer.py  # Gene set enrichment via g:Profiler
  interpretation.py       # LLM-based biological interpretation
  rdf_export.py           # ChatGEO → Biolink RDF adapter
  gene_ranker.py          # Gene prioritization/ranking methods
  report_generator.py     # JSON, TSV, and console output formatting
  study_grouper.py        # Group samples by GEO study
  species_merger.py       # Cross-species ortholog mapping (framework)
  metrics.py              # Search quality metrics
  examples/               # Pre-built example queries and results
```
