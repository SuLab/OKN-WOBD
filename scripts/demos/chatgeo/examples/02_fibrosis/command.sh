#!/bin/bash
# ChatGEO Example: Lung Fibrosis
# Run from: scripts/demos/

export ARCHS4_DATA_DIR="/Users/bgood/scripps/data/archs4"

python -m chatgeo.cli "lung fibrosis" \
    --tissue lung \
    --method deseq2 \
    --fdr 0.05 \
    --log2fc 1.0 \
    --max-test 200 \
    --max-control 200 \
    --output chatgeo/examples/02_fibrosis/results.json \
    --verbose
