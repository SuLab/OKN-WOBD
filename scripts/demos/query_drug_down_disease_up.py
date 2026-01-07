#!/usr/bin/env python3
"""
Query: Find genes down-regulated by drug/compound treatment
       that are up-regulated in disease.

This identifies potential therapeutic targets where a drug suppresses
a gene that is pathologically elevated in disease.

OPTIMIZATION NOTES:
- Uses gene URIs directly instead of symbol text matching
- No SPARQL FILTER operations - all filtering done in Python post-processing
- Orders patterns to bind most selective variables first (VALUES → expression → study)
- Processes in smaller batches for reliability

Usage:
    python query_drug_down_disease_up.py
"""

from fuseki_client import FusekiClient


def find_drug_disease_genes(
    drug_fc_threshold: float = -2.0,
    disease_fc_threshold: float = 1.5,
    pvalue_threshold: float = 0.05,
    limit: int = 300,
    batch_size: int = 30
):
    """
    Find genes that are:
    1. Down-regulated by drug/compound treatment
    2. Up-regulated in disease conditions

    Args:
        drug_fc_threshold: log2FC threshold for down-regulation (negative)
        disease_fc_threshold: log2FC threshold for up-regulation (positive)
        pvalue_threshold: adjusted p-value significance threshold
        limit: max number of drug-gene pairs to query
        batch_size: number of genes per batch in disease query

    Returns:
        List of dicts with gene, drug, and disease information
    """
    client = FusekiClient(dataset='GXA-v2', timeout=120)

    # Step 1: Get genes (with URIs) down-regulated by compounds/treatments
    # Optimized: Uses VALUES for experimental factors instead of FILTER IN
    drug_query = f'''
    SELECT DISTINCT ?gene ?geneSymbol ?drugStudy ?drugTitle ?drugLog2fc
                    ?drugAssayName ?drugTestGroup ?drugRefGroup
    WHERE {{
        # Most selective first: expression with thresholds
        ?drugExpr a biolink:GeneExpressionMixin ;
                  spokegenelab:log2fc ?drugLog2fc ;
                  spokegenelab:adj_p_value ?drugPval ;
                  biolink:subject ?drugAssayUri ;
                  biolink:object ?gene .

        # Numeric filters immediately after binding
        FILTER(?drugLog2fc < {drug_fc_threshold})
        FILTER(?drugPval < {pvalue_threshold})

        # Get gene symbol
        ?gene biolink:symbol ?geneSymbol .

        # Get assay details (test vs reference comparison)
        ?drugAssayUri biolink:name ?drugAssayName .
        OPTIONAL {{ ?drugAssayUri spokegenelab:test_group_label ?drugTestGroup }}
        OPTIONAL {{ ?drugAssayUri spokegenelab:reference_group_label ?drugRefGroup }}

        # Link to study with compound/treatment factor
        VALUES ?factor {{ "compound" "treatment" "dose" }}
        ?drugStudyUri spokegenelab:experimental_factors ?factor ;
                      biolink:has_output ?drugAssayUri ;
                      biolink:name ?drugStudy ;
                      spokegenelab:project_title ?drugTitle .
    }}
    LIMIT {limit}
    '''

    print("Step 1: Querying genes down-regulated by drugs/compounds...")
    drug_results = client.query_simple(drug_query)
    print(f"  Found {len(drug_results)} drug-gene pairs")

    # Build lookup by gene URI (more precise than symbol)
    drug_genes = {}
    for r in drug_results:
        gene_uri = r.get('gene')
        symbol = r.get('geneSymbol')
        if gene_uri and symbol:
            if gene_uri not in drug_genes:
                drug_genes[gene_uri] = {
                    'symbol': symbol,
                    'entries': []
                }
            drug_genes[gene_uri]['entries'].append({
                'study': r.get('drugStudy', ''),
                'title': r.get('drugTitle', ''),
                'log2fc': float(r.get('drugLog2fc', 0)),
                'assay_name': r.get('drugAssayName', ''),
                'test_group': r.get('drugTestGroup', ''),
                'ref_group': r.get('drugRefGroup', '')
            })

    print(f"  Unique genes: {len(drug_genes)}")

    if not drug_genes:
        return []

    # Step 2: Check which genes are up-regulated in disease
    # Process in batches using gene URIs directly (no text matching)
    gene_uris = list(drug_genes.keys())
    all_disease_results = []

    print(f"Step 2: Checking disease up-regulation in {len(gene_uris)//batch_size + 1} batches...")

    for i in range(0, len(gene_uris), batch_size):
        batch = gene_uris[i:i+batch_size]
        # Build VALUES clause with full URIs
        values_str = ' '.join([f'<{uri}>' for uri in batch])

        # Optimized query:
        # - Uses gene URIs directly (no symbol lookup)
        # - No FILTER operations - filter in Python post-processing
        disease_query = f'''
        SELECT ?gene ?diseaseStudy ?diseaseLog2fc ?diseasePval ?diseaseName ?diseaseId
               ?diseaseAssayName ?diseaseTestGroup ?diseaseRefGroup
        WHERE {{
            VALUES ?gene {{ {values_str} }}

            # Expression data - start with gene constraint
            ?diseaseExpr a biolink:GeneExpressionMixin ;
                         biolink:object ?gene ;
                         biolink:subject ?diseaseAssayUri ;
                         spokegenelab:log2fc ?diseaseLog2fc ;
                         spokegenelab:adj_p_value ?diseasePval .

            # Get assay details
            ?diseaseAssayUri biolink:name ?diseaseAssayName .
            OPTIONAL {{ ?diseaseAssayUri spokegenelab:test_group_label ?diseaseTestGroup }}
            OPTIONAL {{ ?diseaseAssayUri spokegenelab:reference_group_label ?diseaseRefGroup }}

            # Link to disease study
            ?diseaseStudyUri spokegenelab:experimental_factors "disease" ;
                             biolink:has_output ?diseaseAssayUri ;
                             biolink:name ?diseaseStudy ;
                             biolink:studies ?disease .

            # Get disease info
            ?disease a biolink:Disease ;
                     biolink:name ?diseaseName ;
                     biolink:id ?diseaseId .
        }}
        LIMIT 200
        '''

        try:
            results = client.query_simple(disease_query)
            all_disease_results.extend(results)
            print(f"  Batch {i//batch_size + 1}: {len(results)} matches")
        except Exception as e:
            print(f"  Batch {i//batch_size + 1}: Error - {str(e)[:50]}")

    print(f"  Total disease matches: {len(all_disease_results)}")

    # Combine results with Python-side filtering
    print("Step 3: Filtering results in Python...")
    combined = []
    seen = set()
    filtered_fc = 0
    filtered_pval = 0
    filtered_control = 0

    # Exclude patterns for controls/healthy
    exclude_patterns = ['pato_', 'efo_0001461', 'healthy', 'normal', 'control', 'reference']

    for r in all_disease_results:
        gene_uri = r.get('gene')
        disease = r.get('diseaseName', '')
        disease_id = r.get('diseaseId', '')
        disease_log2fc = float(r.get('diseaseLog2fc', 0))
        disease_pval = float(r.get('diseasePval', 1)) if r.get('diseasePval') else 1.0

        # Python-side filtering (faster than SPARQL FILTER)
        # 1. Check fold change threshold
        if disease_log2fc <= disease_fc_threshold:
            filtered_fc += 1
            continue

        # 2. Check p-value threshold
        if disease_pval >= pvalue_threshold:
            filtered_pval += 1
            continue

        # 3. Exclude controls/healthy by ID or name
        disease_id_lower = disease_id.lower()
        disease_lower = disease.lower()
        if any(pat in disease_id_lower or pat in disease_lower for pat in exclude_patterns):
            filtered_control += 1
            continue

        key = (gene_uri, disease)

        if gene_uri in drug_genes and key not in seen:
            seen.add(key)
            gene_info = drug_genes[gene_uri]
            drug_entry = gene_info['entries'][0]  # First drug entry
            combined.append({
                'gene': gene_info['symbol'],
                'gene_uri': gene_uri,
                # Drug/treatment info
                'drug_study': drug_entry['study'],
                'drug_title': drug_entry['title'],
                'drug_log2fc': drug_entry['log2fc'],
                'drug_test_group': drug_entry['test_group'],
                'drug_ref_group': drug_entry['ref_group'],
                # Disease info
                'disease_study': r.get('diseaseStudy', ''),
                'disease_log2fc': disease_log2fc,
                'disease': disease,
                'disease_id': disease_id,
                'disease_test_group': r.get('diseaseTestGroup', ''),
                'disease_ref_group': r.get('diseaseRefGroup', '')
            })

    # Sort by disease fold change (highest first)
    combined.sort(key=lambda x: -x['disease_log2fc'])

    print(f"  Filtered out: {filtered_fc} (low FC), {filtered_pval} (high p-val), {filtered_control} (controls)")
    print(f"  Remaining: {len(combined)} gene-disease pairs")

    return combined


def main():
    print("=" * 80)
    print("GENES DOWN-REGULATED BY DRUGS, UP-REGULATED IN DISEASE")
    print("(Optimized: No SPARQL FILTERs in disease query - Python filtering)")
    print("=" * 80)
    print()

    results = find_drug_disease_genes()

    if not results:
        print("No matching genes found.")
        return

    # Print results - detailed format with assay context
    print(f"\nFound {len(results)} gene-drug-disease combinations:\n")

    for i, r in enumerate(results[:20], 1):
        drug_name = r['drug_title'][:50] if r['drug_title'] else r['drug_study']
        drug_context = f"{r['drug_test_group']} vs {r['drug_ref_group']}" if r['drug_test_group'] else "N/A"
        disease_context = f"{r['disease_test_group']} vs {r['disease_ref_group']}" if r['disease_test_group'] else "N/A"

        print(f"{i:2}. Gene: {r['gene']}")
        print(f"    DRUG DOWN-REG (log2FC={r['drug_log2fc']:.1f}):")
        print(f"      Study: {drug_name}")
        print(f"      Comparison: {drug_context[:70]}")
        print(f"    DISEASE UP-REG (log2FC={r['disease_log2fc']:.1f}):")
        print(f"      Disease: {r['disease']}")
        print(f"      Comparison: {disease_context[:70]}")
        print()

    # Summary
    unique_genes = len(set(r['gene'] for r in results))
    unique_diseases = len(set(r['disease'] for r in results))
    unique_drugs = len(set(r['drug_title'] or r['drug_study'] for r in results))

    print("=" * 80)
    print(f"SUMMARY: {len(results)} gene-disease combinations")
    print(f"         {unique_genes} unique genes")
    print(f"         {unique_drugs} unique drug studies")
    print(f"         {unique_diseases} unique diseases")
    print("=" * 80)


if __name__ == "__main__":
    main()
