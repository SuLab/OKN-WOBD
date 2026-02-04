#!/bin/bash
# ChatGEO Example: Rheumatoid Arthritis
# Generated: 2026-02-02T12:46:59.264597

export ARCHS4_DATA_DIR="/Users/bgood/scripps/data/archs4"

python -m chatgeo.cli "rheumatoid arthritis" \
    --tissue synovial \
    --method deseq2 \
    --fdr 0.01 \
    --log2fc 2.0 \
    --max-test 200 \
    --max-control 200 \
    --output chatgeo/examples/03_arthritis \
    --verbose
