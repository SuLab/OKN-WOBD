#!/bin/bash
# ChatGEO Example: Systemic Lupus Erythematosus in Blood
# Generated: 2026-02-02T12:52:34.817790

export ARCHS4_DATA_DIR="/Users/bgood/scripps/data/archs4"

python -m chatgeo.cli "systemic lupus erythematosus in blood" \
    --tissue blood \
    --method deseq2 \
    --fdr 0.01 \
    --log2fc 2.0 \
    --max-test 200 \
    --max-control 200 \
    --output chatgeo/examples/08_sle/results.json \
    --verbose
