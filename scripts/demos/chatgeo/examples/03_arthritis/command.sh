#!/bin/bash
# ChatGEO Example: Rheumatoid Arthritis
# Run from: scripts/demos/
# Note: This example may fail with DESeq2 due to 0 control samples for
# "synovial" tissue. Use --method mann-whitney as a fallback.

export ARCHS4_DATA_DIR="/Users/bgood/scripps/data/archs4"

python -m chatgeo.cli "rheumatoid arthritis" \
    --tissue synovial \
    --method deseq2 \
    --fdr 0.05 \
    --log2fc 1.0 \
    --max-test 200 \
    --max-control 200 \
    --output chatgeo/examples/03_arthritis/results.json \
    --verbose
