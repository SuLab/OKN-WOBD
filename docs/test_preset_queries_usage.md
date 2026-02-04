# Testing Preset Queries Locally

This guide explains how to test preset queries against local RDF data using `scripts/test_preset_queries.py`.

## Overview

The test script uses `rdflib` to load and query RDF files locally without needing a SPARQL server. This is useful for:
- Validating query syntax before deploying to FRINK
- Testing data links and predicates
- Quick iteration during query development
- Debugging query issues

## Quick Start

```bash
# Fastest: Test with default file (E-GEOD-76.ttl for Dusp2 query)
python scripts/test_preset_queries.py --verbose
```

## Usage Examples

### Example 1: Quick Test (Default File)
```bash
$ python scripts/test_preset_queries.py --verbose
Using default file for query: E-GEOD-10311.ttl

Loading gene expression data from 1 file(s)...
  ✓ E-GEOD-10311.ttl
Loaded 194516 triples

Testing 1 query(ies)...

Query: Find experiments where Dusp2 is upregulated.
--------------------------------------------------------------------------------
✓ Executed successfully: 1 result(s)

  Sample results:
    1. {'experiment': 'E-GEOD-10311-g5_g1', 'experimentId': 'E-GEOD-10311', 
        'experimentLabel': "'bone morphogenetic protein 2' vs 'vehicle' at '2 hour'", 
        'gene': '1844', 'geneSymbol': 'DUSP2', 'log2fc': '1.2', 
        'adjPValue': '7.90255303585693e-05'}

✓ All queries passed!
```

### Example 2: Test Specific File
```bash
$ python scripts/test_preset_queries.py --file E-GEOD-10311.ttl --verbose
Loading gene expression data from 1 file(s)...
  ✓ E-GEOD-10311.ttl
Loaded 194516 triples

Testing 1 query(ies)...

Query: Find experiments where Dusp2 is upregulated.
--------------------------------------------------------------------------------
✓ Executed successfully: 1 result(s)
...
```

### Example 3: Test All Files (Slower)
```bash
# Warning: This loads all ~2085 .ttl files - use only if needed
$ python scripts/test_preset_queries.py --all-files --verbose
Loading gene expression data from 2085 file(s)...
  ✓ E-GEOD-100100.ttl
  ✓ E-GEOD-10019.ttl
  ...
Loaded 12000000+ triples

Testing 1 query(ies)...
...
```

### Example 4: Test Specific Query
```bash
# Test Dusp2 query
$ python scripts/test_preset_queries.py --query "Find experiments where Dusp2 is upregulated." --verbose
Using default file for query: E-GEOD-10311.ttl

Loading gene expression data from 1 file(s)...

# Test SFRP2 query
$ python scripts/test_preset_queries.py --query "Find studies where SFRP2 is upregulated or downregulated." --verbose
# Note: May need --all-files flag for SFRP2 since associations are spread across files

Loading gene expression data from 1 file(s)...
  ✓ E-GEOD-76.ttl
Loaded 57716 triples

Testing 1 query(ies)...
...
```

### Example 5: Custom Directory
```bash
$ python scripts/test_preset_queries.py --gene-expr-dir /path/to/your/data --file E-GEOD-76.ttl
Loading gene expression data from 1 file(s)...
  ✓ E-GEOD-76.ttl
...
```

### Example 6: Limit Results Shown
```bash
$ python scripts/test_preset_queries.py --verbose --limit-results 5
...
✓ Executed successfully: 15 result(s)

  Sample results:
    1. {'experiment': '...', 'experimentId': 'E-GEOD-76', 'gene': '...', ...}
    2. {'experiment': '...', 'experimentId': 'E-GEOD-76', 'gene': '...', ...}
    ...
    ... and 10 more
```

### Example 7: Test SFRP2 Query (May Need All Files)
```bash
# Test SFRP2 query - may need all files since associations are spread across multiple files
$ python scripts/test_doxycycline_sfrp2.py --all-files

# Or use the preset query tester with specific file if you know which one has SFRP2
$ python scripts/test_preset_queries.py --query "Find studies where SFRP2 is upregulated or downregulated." --verbose
```

## Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--file FILE` | Load specific .ttl file (e.g., `E-GEOD-76.ttl`) | Query-specific default |
| `--all-files` | Load all .ttl files in directory | `False` |
| `--query TEXT` | Test only specific query by question text | All queries |
| `--verbose` | Show detailed results with sample data | `False` |
| `--limit-results N` | Maximum results to show in verbose mode | `10` |
| `--gene-expr-dir PATH` | Directory containing .ttl files | `data/gene_expression` |

## Query-to-File Mappings

The script automatically selects appropriate data files for each query:

| Query | Default File | Reason |
|-------|--------------|--------|
| "Find experiments where Dusp2 is upregulated." | `E-GEOD-10311.ttl` | Contains Dusp2 gene expression associations |
| "Find studies where SFRP2 is upregulated or downregulated." | None (uses all files) | SFRP2 associations may be across multiple files; recommend using `--all-files` |

**Note:** For SFRP2 query, since associations may be spread across multiple files, it's recommended to use `--all-files` flag or test with the merged graph approach (see `docs/testing_doxycycline_sfrp2_queries.md`).

## Understanding Results

### Success with Results
```
✓ Executed successfully: 15 result(s)

  Sample results:
    1. {'experiment': '...', 'experimentId': 'E-GEOD-76', 'geneSymbol': 'Dusp2', 'log2fc': 2.5, ...}
```

### Success but No Results
```
✓ Executed successfully: 0 result(s)
```
This means:
- Query executed without errors
- No data matched the query conditions
- Possible reasons:
  - Query filters too restrictive
  - Data structure doesn't match expected predicates
  - Data doesn't contain matching records

### Query Error
```
✗ Error: Variable ?geneSymbol used but not bound
    (Hint: Check query structure and predicates)
```
This means:
- Query has a syntax or structural issue
- Check predicates match data model
- Verify variable bindings in WHERE clause

## Troubleshooting

### Issue: 0 Results

1. **Check data structure:**
   ```bash
   # Inspect the file structure
   head -n 100 data/gene_expression/E-GEOD-76.ttl | grep -i dusp2
   ```

2. **Verify predicates:**
   - Ensure query uses correct namespace prefixes
   - Check that predicates match actual data (e.g., `biolink:symbol` vs `spokegenelab:symbol`)

3. **Check filters:**
   - Verify filter conditions aren't too restrictive
   - Test without filters first, then add them incrementally

### Issue: Import Errors

If you get import errors:
```bash
# Ensure you're in the project root
cd /path/to/OKN-WOBD

# Make sure web package is installed
pip install -e ./web

# Run from project root
python scripts/test_preset_queries.py
```

### Issue: File Not Found

```bash
# Check file exists
ls data/gene_expression/E-GEOD-76.ttl

# Use absolute path if needed
python scripts/test_preset_queries.py --gene-expr-dir /absolute/path/to/data
```

## Integration with Development Workflow

1. **Write/Update Query** → Edit in `web/wobd_web/preset_queries.py`

2. **Test Locally** → Run `python scripts/test_preset_queries.py --verbose`

3. **Fix Issues** → Adjust query based on results

4. **Validate** → Test again until results are correct

5. **Deploy** → Query ready for FRINK/GraphDB/Fuseki

## Next Steps

After local testing:
- Test with GraphDB (closer to FRINK behavior)
- Test with Fuseki for open-source local testing
- Deploy to FRINK for production use

See [GraphDB vs Fuseki Comparison](graphdb_vs_fuseki.md) for server setup options.

