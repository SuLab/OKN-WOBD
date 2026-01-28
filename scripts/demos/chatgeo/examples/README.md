# ChatGEO Differential Expression Examples

This folder contains example results from the ChatGEO differential expression analysis pipeline.

## Examples

| Example | Query | Disease | Tissue |
|---------|-------|---------|--------|
| 1 | `psoriasis in skin tissue` | Psoriasis | Skin |
| 2 | `lung fibrosis` | Pulmonary fibrosis | Lung |
| 3 | `rheumatoid arthritis` | Rheumatoid arthritis | Synovial tissue |
| 4 | `mitochondrial myopathy` | Mitochondrial myopathy | Muscle |
| 5 | `alzheimer disease` | Alzheimer's disease | Brain |

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

### Run All Examples

```bash
cd scripts/demos/chatgeo/examples
python run_all_examples.py
```

### Run Individual Examples

```bash
# Example 1: Psoriasis
python -m chatgeo.cli "psoriasis in skin tissue" \
    --output examples/01_psoriasis_results.json \
    --verbose

# Example 2: Lung fibrosis
python -m chatgeo.cli "lung fibrosis" \
    --tissue lung \
    --output examples/02_fibrosis_results.json \
    --verbose

# Example 3: Rheumatoid arthritis
python -m chatgeo.cli "rheumatoid arthritis" \
    --tissue synovial \
    --output examples/03_arthritis_results.json \
    --verbose

# Example 4: Mitochondrial myopathy
python -m chatgeo.cli "mitochondrial myopathy" \
    --tissue muscle \
    --output examples/04_mitochondrial_results.json \
    --verbose

# Example 5: Alzheimer's disease
python -m chatgeo.cli "alzheimer disease" \
    --tissue brain \
    --output examples/05_alzheimers_results.json \
    --verbose
```

## Output Files

Each example produces:

- `*_results.json` - Full results with provenance
- `*_genes.tsv` - Gene table for spreadsheet analysis
- `*_summary.txt` - Human-readable summary

## File Structure

```
examples/
├── README.md
├── run_all_examples.py
├── 01_psoriasis/
│   ├── command.sh
│   ├── results.json
│   ├── genes.tsv
│   └── summary.txt
├── 02_fibrosis/
│   ├── command.sh
│   ├── results.json
│   ├── genes.tsv
│   └── summary.txt
├── 03_arthritis/
│   ├── command.sh
│   ├── results.json
│   ├── genes.tsv
│   └── summary.txt
├── 04_mitochondrial/
│   ├── command.sh
│   ├── results.json
│   ├── genes.tsv
│   └── summary.txt
└── 05_alzheimers/
    ├── command.sh
    ├── results.json
    ├── genes.tsv
    └── summary.txt
```
