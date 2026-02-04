# Testing Doxycycline → SFRP2 Queries Without FRINK

Since the data isn't in FRINK yet and GraphDB isn't set up, here are ways to test the queries with available data.

## What You CAN Test Locally

### 1. Gene Expression (GXA) Data Only - Find Studies Where SFRP2 is Up/Downregulated

You have gene expression `.ttl` files locally, so you can test finding studies/experiments where SFRP2 is upregulated or downregulated. This query extracts study IDs (like `E-GEOD-10311`) that you can then use to connect to other graphs.

**Key Query:** "Find studies where SFRP2 is upregulated or downregulated."

This query returns the required fields:
- **`studyId`**: The study identifier (e.g., "E-GEOD-10311") - **this is what you'll use to link to other graphs**
- **`gene`**: Gene URI
- **`geneSymbol`**: Gene symbol ("SFRP2")
- **`expressionDirection`**: "upregulated" or "downregulated"
- Plus: `experimentId`, `log2fc`, `adjPValue`, `experimentLabel`

**Testing Options:**

**Option A: Using the preset query tester**
```bash
python scripts/test_preset_queries.py --query "Find studies where SFRP2 is upregulated or downregulated." --verbose
```

**Option B: Using the SFRP2-specific test script (recommended for merged data)**
```bash
# Test with merged graph - loads all files into one graph
# This simulates having all files loaded in a single SPARQL endpoint
# (allows queries to find associations across multiple files)
python scripts/test_doxycycline_sfrp2.py --all-files

# Test with specific file if you know which one has SFRP2 associations
python scripts/test_doxycycline_sfrp2.py --file E-GEOD-XXXXX.ttl
```

**What the tests show:**
- `studyId`: Study identifier (e.g., "E-GEOD-10311") - key for linking to other graphs
- `gene` and `geneSymbol`: Gene information (SFRP2)
- `expressionDirection`: "upregulated" or "downregulated"
- `log2fc`, `adjPValue`: Expression values
- `experimentId`, `experimentName`: Experiment details

### 2. Simplified Local Query (No SERVICE clauses)

If you want to test the query structure without federated queries, use this simplified version that works with local data:

```sparql
PREFIX biolink: <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>

SELECT DISTINCT
    ?gene
    ?geneSymbol
    ?experiment
    (REPLACE(STR(?experiment), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentId)
    ?experimentLabel
    ?log2fc
    ?adjPValue
WHERE {
    # Find gene expression associations for SFRP2
    ?association a biolink:GeneExpressionMixin ;
        biolink:object ?gene ;
        biolink:subject ?experiment ;
        spokegenelab:log2fc ?log2fc ;
        spokegenelab:adj_p_value ?adjPValue .
    
    # Filter for SFRP2 gene
    ?gene biolink:symbol ?geneSymbol .
    FILTER(LCASE(?geneSymbol) = "sfrp2" || LCASE(?geneSymbol) = "sfrp-2")
}
ORDER BY DESC(?log2fc)
LIMIT 200
```

Test with:
```bash
python scripts/test_preset_queries.py --file <file-with-sfrp2>.ttl --verbose
```

## What You CANNOT Test Locally (Yet)

### SPOKE-OKN Data (Drug-Gene Relationships)
- **Needed**: Access to `https://frink.apps.renci.org/spoke-okn/sparql`
- **What it provides**: Doxycycline → SFRP2 relationships
- **Workaround**: You can manually verify the query syntax, but can't execute it without FRINK

### Ubergraph Data (Gene-Disease Relationships)
- **Needed**: Access to `https://frink.apps.renci.org/ubergraph/sparql`
- **What it provides**: SFRP2 → Disease connections
- **Workaround**: Same as above - verify syntax only

### Federated Queries
- **Needed**: All three endpoints accessible via FRINK
- **What it provides**: Complete Doxycycline → SFRP2 → Disease network
- **Workaround**: Test each part separately when endpoints become available

## Testing Strategy

### Phase 1: Local Testing (Now)
1. ✅ Test GXA queries with local `.ttl` files
2. ✅ Verify query syntax and structure
3. ✅ Check data format matches expectations

### Phase 2: Individual Endpoint Testing (When FRINK Available)
1. Test SPOKE-OKN query separately:
   ```bash
   # Direct query against SPOKE-OKN endpoint
   curl -X POST https://frink.apps.renci.org/spoke-okn/sparql \
     -H "Content-Type: application/sparql-query" \
     --data @queries/spoke_doxycycline_sfrp2.sparql
   ```

2. Test Ubergraph query separately:
   ```bash
   # Direct query against Ubergraph endpoint
   curl -X POST https://frink.apps.renci.org/ubergraph/sparql \
     -H "Content-Type: application/sparql-query" \
     --data @queries/ubergraph_sfrp2_diseases.sparql
   ```

3. Test GXA query separately:
   ```bash
   # Direct query against gene expression endpoint
   curl -X POST https://frink.apps.renci.org/geneexpr/sparql \
     -H "Content-Type: application/sparql-query" \
     --data @queries/gxa_sfrp2_expression.sparql
   ```

### Phase 3: Federated Query Testing (When All Endpoints Available)
1. Test complete federated query via FRINK
2. Verify SERVICE clauses work correctly
3. Validate cross-endpoint joins

## Manual Query Validation

Even without FRINK access, you can:

1. **Validate SPARQL Syntax**:
   - Use online SPARQL validators
   - Check predicate names against Biolink Model docs
   - Verify namespace prefixes

2. **Check Query Structure**:
   - Ensure SERVICE clauses are correct
   - Verify variable bindings
   - Check FILTER conditions

3. **Prepare Test Cases**:
   - Document expected results
   - Identify edge cases
   - Plan validation steps

## Alternative: Use GraphDB Locally

If you set up GraphDB locally and load sample data:

1. **Set up GraphDB** (see `docs/graphdb_vs_fuseki.md`):
   ```bash
   docker run -d --name graphdb \
     -p 7200:7200 \
     ontotext/graphdb:latest
   ```

2. **Load Data** (if you have sample SPOKE/Ubergraph data):
   - Create repositories for each source
   - Import sample `.ttl` files
   - Update `demo.local.yaml` with local endpoints

3. **Test Federated Queries**:
   - Update SERVICE URLs to point to local GraphDB
   - Test complete query structure

## Next Steps

1. **Now**: Run `python scripts/test_doxycycline_sfrp2.py` to test GXA part
2. **When FRINK Available**: Test individual endpoint queries
3. **Final**: Test complete federated query

See `docs/doxycycline_sfrp2_queries.md` for all query examples.

