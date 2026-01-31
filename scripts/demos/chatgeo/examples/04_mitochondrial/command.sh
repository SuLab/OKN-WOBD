#!/bin/bash
# ChatGEO Example: Mitochondrial Myopathy
# Run from: scripts/demos/

export ARCHS4_DATA_DIR="/Users/bgood/scripps/data/archs4"

python -m chatgeo.cli "mitochondrial myopathy" \
    --tissue muscle \
    --method deseq2 \
    --fdr 0.05 \
    --log2fc 1.0 \
    --max-test 200 \
    --max-control 200 \
    --include-mt-genes \
    --output chatgeo/examples/04_mitochondrial/results.json \
    --verbose
