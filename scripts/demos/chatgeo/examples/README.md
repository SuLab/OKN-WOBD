# ChatGEO Differential Expression Examples

This folder contains example results from the ChatGEO differential expression
analysis pipeline using DESeq2 on ARCHS4 bulk RNA-seq data.

## Examples

| # | Disease | Tissue | Test / Control | Up | Down | Quality |
|---|---------|--------|---------------:|---:|-----:|---------|
| 1 | Psoriasis | Skin | 66 / 131 | 564 | 8,471 | Strong — IL-17/Th17 axis confirmed |
| 2 | Pulmonary fibrosis | Lung | 200 / 200 | 4,456 | 1,982 | Mixed — tissue confounding (liver samples) |
| 3 | Rheumatoid arthritis | Synovial | 98 / 76 | 987 | 580 | Legacy (pre-DESeq2) |
| 4 | Mitochondrial myopathy | Muscle | 15 / 200 | 193 | 2,414 | Strong — FGF21 + mitochondrial pathways |
| 5 | Alzheimer disease | Brain | 4 / 200 | 11 | 468 | Limited — only 4 test samples |

## Running Examples

### Prerequisites

1. Set the ARCHS4 data directory:
   ```bash
   export ARCHS4_DATA_DIR=/path/to/archs4/data
   ```

2. Ensure the human ARCHS4 file exists:
   ```
   $ARCHS4_DATA_DIR/human_gene_v2.latest.h5
   ```

3. Install PyDESeq2:
   ```bash
   pip install pydeseq2
   ```

### Run All Examples

```bash
cd scripts/demos/chatgeo/examples
python run_all_examples.py
```

### Run Individual Examples

```bash
# Example 1: Psoriasis
python -m chatgeo.cli "psoriasis in skin tissue" \
    --output examples/01_psoriasis/results.json \
    --verbose

# Example 2: Lung fibrosis
python -m chatgeo.cli "lung fibrosis" \
    --tissue lung \
    --output examples/02_fibrosis/results.json \
    --verbose

# Example 3: Rheumatoid arthritis (currently fails with DESeq2 — 0 control samples)
python -m chatgeo.cli "rheumatoid arthritis" \
    --tissue synovial \
    --method mann-whitney \
    --output examples/03_arthritis/results.json \
    --verbose

# Example 4: Mitochondrial myopathy (include MT genes)
python -m chatgeo.cli "mitochondrial myopathy" \
    --tissue muscle \
    --include-mt-genes \
    --output examples/04_mitochondrial/results.json \
    --verbose

# Example 5: Alzheimer's disease
python -m chatgeo.cli "alzheimer disease" \
    --tissue brain \
    --output examples/05_alzheimers/results.json \
    --verbose
```

## Output Files

Each example produces:

- `results.json` — Full results with provenance (query, samples, methods)
- `genes.tsv` — Gene table for spreadsheet analysis
- `enrichment.tsv` — Enriched GO/KEGG/Reactome terms (up and down)
- `summary.txt` — Human-readable summary with top genes and terms
- `interpretation.md` — Biological interpretation of results
- `command.sh` — The CLI command used to generate results

## File Structure

```
examples/
├── README.md
├── run_all_examples.py
├── 01_psoriasis/
│   ├── command.sh
│   ├── results.json
│   ├── genes.tsv
│   ├── enrichment.tsv
│   ├── summary.txt
│   └── interpretation.md
├── 02_fibrosis/
│   ├── command.sh
│   ├── results.json
│   ├── genes.tsv
│   ├── enrichment.tsv
│   ├── summary.txt
│   └── interpretation.md
├── 03_arthritis/          (legacy results, pre-DESeq2)
│   ├── command.sh
│   ├── results.json
│   ├── genes.tsv
│   └── summary.txt
├── 04_mitochondrial/
│   ├── command.sh
│   ├── results.json
│   ├── genes.tsv
│   ├── enrichment.tsv
│   ├── summary.txt
│   └── interpretation.md
└── 05_alzheimers/
    ├── command.sh
    ├── results.json
    ├── genes.tsv
    ├── enrichment.tsv
    ├── summary.txt
    └── interpretation.md
```

## Methods

All examples (except #3) use the DESeq2 pipeline:

1. **Sample selection**: ARCHS4 metadata search with disease/tissue query expansion
2. **Quality filtering**: Remove samples with < 1M total reads
3. **Gene filtering**: Protein-coding genes only (except MT genes when relevant)
4. **Statistical testing**: PyDESeq2 (negative binomial model, Wald test, BH FDR)
5. **Enrichment**: g:Profiler (GO:BP, GO:CC, GO:MF, KEGG, Reactome)

Example #3 (rheumatoid arthritis) uses the legacy pipeline (Mann-Whitney U +
log-quantile normalization) because the "synovial" tissue query returns 0
control samples with the current search strategy.
