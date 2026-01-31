#!/bin/bash
# ChatGEO Example: Osteoarthritis in Knee
# Run from: scripts/demos/

export ARCHS4_DATA_DIR="/Users/bgood/scripps/data/archs4"

python -m chatgeo.cli "osteoarthritis in knee" \
    --tissue knee \
    --method deseq2 \
    --fdr 0.05 \
    --log2fc 1.0 \
    --max-test 200 \
    --max-control 200 \
    --output chatgeo/examples/06_osteoarthritis/results.json \
    --verbose
