# Testing the SFRP2 Expression Query

This guide explains how to test the "Find studies where SFRP2 is upregulated or downregulated" query.

## Quick Start

```bash
# Option 1: Using preset query tester (simplest)
python scripts/test_preset_queries.py --query "Find studies where SFRP2 is upregulated or downregulated." --verbose

# Option 2: Using SFRP2-specific script with merged graph (recommended - matches Fuseki)
python scripts/test_doxycycline_sfrp2.py --all-files
```

## What the Query Returns

The query returns these key fields:
1. **`studyId`** - Study identifier (e.g., "E-GEOD-10311") - **Use this to link to other graphs**
2. **`gene`** - Gene URI
3. **`geneSymbol`** - Gene symbol ("SFRP2")
4. **`expressionDirection`** - "upregulated" or "downregulated"
5. Additional fields: `experimentId`, `log2fc`, `adjPValue`, `experimentLabel`

## Testing Methods

### Method 1: Preset Query Tester (Single File)

Tests against individual files:

```bash
# Test with default file (if configured)
python scripts/test_preset_queries.py --query "Find studies where SFRP2 is upregulated or downregulated." --verbose

# Test with specific file
python scripts/test_preset_queries.py --query "Find studies where SFRP2 is upregulated or downregulated." --file E-GEOD-10311.ttl --verbose

# Test with all files (slower, ~2085 files)
python scripts/test_preset_queries.py --query "Find studies where SFRP2 is upregulated or downregulated." --all-files --verbose
```

**Note:** Since SFRP2 associations may be spread across multiple files, individual file tests might return 0 results. Use `--all-files` or the merged graph approach below.

### Method 2: SFRP2-Specific Test Script (Merged Graph)

This script loads all files into one merged graph, simulating a single SPARQL endpoint with all data loaded:

```bash
# Load all files into merged graph (recommended - matches Fuseki setup)
python scripts/test_doxycycline_sfrp2.py --all-files

# Test specific file only
python scripts/test_doxycycline_sfrp2.py --file E-GEOD-10311.ttl

# Find which files contain SFRP2 (doesn't load associations)
python scripts/test_doxycycline_sfrp2.py
```

## Expected Output

When successful, you should see:

```
Testing SFRP2 expression query against merged graph...
--------------------------------------------------------------------------------
✓ Found X SFRP2 expression associations

Results (first 10):
  1. Study ID: E-GEOD-10311
     Experiment: E-GEOD-10311-g5_g1
     Gene: SFRP2
     Expression: upregulated (log2fc: 1.2)
     p-value: 7.90255303585693e-05
     Experiment name: 'bone morphogenetic protein 2' vs 'vehicle' at '2 hour'...

  2. Study ID: E-GEOD-10311
     ...
```

## Troubleshooting

### Issue: 0 Results Found

**Possible causes:**
1. SFRP2 associations are spread across multiple files - use `--all-files` flag
2. Gene symbol format mismatch - check if it's "SFRP2", "SFRP-2", or "sfrp2"
3. File doesn't contain SFRP2 associations (only gene definition)

**Solution:**
```bash
# Use merged graph approach (loads all files)
python scripts/test_doxycycline_sfrp2.py --all-files
```

### Issue: "No files found containing SFRP2"

This means the gene definition wasn't found. Check:
- Files are in `data/gene_expression/` directory
- Files have `.ttl` extension
- Gene symbol format in your data

## Next Steps

Once you have the `studyId` values, you can:
1. Use them to link to NDE datasets
2. Use them to find related data in SPOKE-OKN
3. Use them to find disease connections in Ubergraph

See `docs/doxycycline_sfrp2_queries.md` for complete query examples across all graphs.

