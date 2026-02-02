#!/bin/bash
# ChatGEO Example: Alzheimer's Disease
# Generated: 2026-02-02T12:50:01.306707

export ARCHS4_DATA_DIR="/Users/bgood/scripps/data/archs4"

python -m chatgeo.cli "alzheimer disease" \
    --tissue brain \
    --method deseq2 \
    --fdr 0.01 \
    --log2fc 2.0 \
    --max-test 200 \
    --max-control 200 \
    --output chatgeo/examples/05_alzheimers/results.json \
    --verbose
