#!/bin/bash
# ChatGEO Example: Mitochondrial Myopathy
# Generated: 2026-02-02T12:48:21.657722

export ARCHS4_DATA_DIR="/Users/bgood/scripps/data/archs4"

python -m chatgeo.cli "mitochondrial myopathy" \
    --tissue muscle \
    --method deseq2 \
    --fdr 0.01 \
    --log2fc 2.0 \
    --max-test 200 \
    --max-control 200 \
    --output chatgeo/examples/04_mitochondrial/results.json \
    --verbose \
    --include-mt-genes
