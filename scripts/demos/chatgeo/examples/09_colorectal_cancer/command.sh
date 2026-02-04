#!/bin/bash
# ChatGEO Example: Colorectal Cancer vs Normal Colon
# Generated: 2026-02-02T12:55:25.634652

export ARCHS4_DATA_DIR="/Users/bgood/scripps/data/archs4"

python -m chatgeo.cli "colorectal cancer in colon tissue" \
    --tissue colon \
    --method deseq2 \
    --fdr 0.01 \
    --log2fc 2.0 \
    --max-test 200 \
    --max-control 200 \
    --output chatgeo/examples/09_colorectal_cancer \
    --verbose
