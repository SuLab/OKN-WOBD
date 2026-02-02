#!/bin/bash
# ChatGEO Example: Lung Fibrosis
# Generated: 2026-02-02T12:39:36.885387

export ARCHS4_DATA_DIR="/Users/bgood/scripps/data/archs4"

python -m chatgeo.cli "lung fibrosis" \
    --tissue lung \
    --method deseq2 \
    --fdr 0.01 \
    --log2fc 2.0 \
    --max-test 200 \
    --max-control 200 \
    --output chatgeo/examples/02_fibrosis/results.json \
    --verbose
