# ChatGEO

Natural language differential expression analysis using ARCHS4 bulk RNA-seq data.

ChatGEO takes a plain-text disease query (e.g., "psoriasis in skin tissue"), finds matching disease and control samples in the ARCHS4 compendium, and runs a statistical differential expression analysis.

## Prerequisites

**Python dependencies** (beyond the core `okn-wobd` package):

```
numpy
pandas
scipy
pydeseq2          # DESeq2 statistical model (optional alternative)
gprofiler-official  # optional, for gene set enrichment analysis
anthropic         # optional, for AI interpretation
python-dotenv     # optional, for .env file support
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
| `--method {mann-whitney,welch-t,deseq2}` | `mann-whitney` | Statistical method for DE |
| `--fdr FLOAT` | `0.05` | FDR significance threshold |
| `--log2fc FLOAT` | `1.0` | Minimum absolute log2 fold change |
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
# Basic psoriasis analysis with output directory
python -m chatgeo.cli "psoriasis in skin tissue" \
    --output chatgeo/examples/01_psoriasis --verbose

# Lung fibrosis with explicit tissue and stricter thresholds
python -m chatgeo.cli "lung fibrosis" \
    --tissue lung \
    --fdr 0.01 --log2fc 2.0 \
    --output chatgeo/examples/02_fibrosis

# With RDF export and limited sample sizes
python -m chatgeo.cli "rheumatoid arthritis" \
    --tissue synovial \
    --max-test 200 --max-control 200 \
    --fdr 0.01 --log2fc 2.0 \
    --output chatgeo/examples/03_arthritis \
    --rdf --verbose

# Mitochondrial myopathy, include MT genes (relevant to disease)
python -m chatgeo.cli "mitochondrial myopathy" \
    --tissue muscle \
    --include-mt-genes \
    --output chatgeo/examples/04_mitochondrial --rdf

# Quick summary to stdout (no file output)
python -m chatgeo.cli "alzheimer disease" --tissue brain
```

Pre-built examples with saved results are in `examples/`. Run them all with:

```bash
cd scripts/demos/chatgeo/examples
python run_all_examples.py
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

## How It Works

1. **Query parsing** -- The natural language query is split into disease and tissue terms.

2. **Query expansion** -- Tissue/disease synonyms are added (e.g., "skin" expands to skin|dermal|cutaneous|epidermal) to broaden the ARCHS4 metadata search.

3. **Sample discovery** -- ARCHS4 metadata is searched for test samples matching the disease term, and control samples matching the tissue + control keywords (healthy, control, normal). Overlap between groups is removed.

4. **Expression retrieval** -- Raw gene expression counts are loaded from the ARCHS4 HDF5 file for both sample groups.

5. **Pre-processing** -- Samples with low library sizes (< 1M reads by default) are removed. Genes are filtered to protein-coding biotypes, duplicate gene symbols are collapsed, and low-count genes (< 10 total reads across all samples) are removed. Mitochondrial (MT-) and ribosomal (RPS/RPL) genes are optionally excluded.

6. **DE testing (Mann-Whitney U)** -- By default, a non-parametric Mann-Whitney U rank test is applied per gene across disease vs. control samples on log2(CPM+1) values. P-values are corrected with Benjamini-Hochberg FDR. DESeq2 and Welch t-test are available as alternatives via `--method` (see [Why Mann-Whitney is the default](#why-mann-whitney-is-the-default) below).

7. **Enrichment analysis** -- Significant upregulated and downregulated gene lists are submitted to g:Profiler for Gene Ontology (BP, CC, MF), KEGG, and Reactome enrichment analysis.

8. **AI interpretation** -- An LLM summarizes the biological significance of the DE and enrichment results.

9. **RDF export** (opt-in) -- Results are converted to Biolink Model RDF for integration into knowledge graphs.

## Why Mann-Whitney Is the Default

ChatGEO uses the [ARCHS4](https://maayanlab.cloud/archs4/) compendium as its expression data source. ARCHS4 processes raw GEO submissions through Kallisto pseudoalignment, rounds the resulting pseudocounts to integers for compression, and stores them as gene-level estimated counts. This preprocessing has important implications for statistical method choice.

### The problem with DESeq2 on ARCHS4 data

DESeq2 is the gold standard for differential expression -- **when given proper input**. The standard pipeline is raw FASTQ -> STAR/Kallisto -> [tximport](https://bioconductor.org/packages/tximport/) -> DESeq2. The tximport step creates a gene-level offset matrix that corrects for transcript length bias, and DESeq2 then fits a negative binomial model assuming the input follows that distribution.

ARCHS4 short-circuits this pipeline by providing pre-processed, rounded Kallisto pseudocounts without the tximport offset matrix. Feeding these directly into DESeq2 violates its distributional assumptions in three ways:

1. **Pseudocounts are estimates, not true counts** -- they carry estimation uncertainty that the negative binomial model does not account for.
2. **Without tximport's length offset**, changes in isoform usage across conditions appear as expression changes.
3. **Rounding introduces artifacts** in the variance structure that DESeq2's dispersion estimation relies on.

On top of this, ChatGEO pools samples across GEO studies, introducing batch effects that further confuse the parametric model.

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

## Module Structure

```
chatgeo/
  cli.py                  # Entry point and argument parsing
  sample_finder.py        # ARCHS4 sample search (pooled and study-matched modes)
  query_builder.py        # Query expansion strategies (pattern-based, ontology placeholder)
  de_analysis.py          # Normalization, statistical testing, FDR correction
  de_result.py            # Result dataclasses with provenance
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
