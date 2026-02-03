#!/usr/bin/env python3
"""
Query: Find genes with opposing expression patterns between drug treatment and disease.

Two scenarios:
1. Drug DOWN, Disease UP: Drug suppresses a gene that is pathologically elevated in disease
2. Drug UP, Disease DOWN: Drug activates a gene that is pathologically suppressed in disease

Both patterns identify potential therapeutic mechanisms.

OPTIMIZATION NOTES:
- Uses gene URIs directly instead of symbol text matching
- No SPARQL FILTER operations - all filtering done in Python post-processing
- Orders patterns to bind most selective variables first (VALUES -> expression -> study)
- Processes in smaller batches for reliability

Usage:
    from analysis_tools import find_drug_disease_genes
    python -m analysis_tools.drug_disease
"""

from clients.sparql import SPARQLClient, GXAQueries, GXA_PREFIXES


def find_drug_disease_genes(
    drug_direction: str = "down",
    disease_direction: str = "up",
    drug_fc_threshold: float = 2.0,
    disease_fc_threshold: float = 1.5,
    pvalue_threshold: float = 0.05,
    limit: int = 2000,
    batch_size: int = 50
):
    """
    Find genes with opposing expression in drug treatment vs disease.

    Args:
        drug_direction: "down" or "up" - direction of drug effect
        disease_direction: "up" or "down" - direction of disease effect
        drug_fc_threshold: absolute log2FC threshold (will be negated for down)
        disease_fc_threshold: absolute log2FC threshold (will be negated for down)
        pvalue_threshold: adjusted p-value significance threshold
        limit: max number of drug-gene pairs to query
        batch_size: number of genes per batch in disease query

    Returns:
        List of dicts with gene, drug, and disease information
    """
    client = SPARQLClient(timeout=120)
    client.add_endpoint("gxa", "https://frink.apps.renci.org/gene-expression-atlas-okn/sparql")

    # Set up thresholds based on direction
    if drug_direction == "down":
        drug_fc_filter = f"FILTER(?drugLog2fc < -{drug_fc_threshold})"
        drug_label = "DOWN"
    else:
        drug_fc_filter = f"FILTER(?drugLog2fc > {drug_fc_threshold})"
        drug_label = "UP"

    if disease_direction == "down":
        disease_label = "DOWN"
    else:
        disease_label = "UP"

    # Step 1: Get genes regulated by compounds/treatments
    drug_query = f'''
    SELECT DISTINCT ?gene ?geneSymbol ?drugStudy ?drugTitle ?drugLog2fc
                    ?drugAssayName ?drugTestGroup ?drugRefGroup
                    ?drugName ?drugId
    WHERE {{
        # Most selective first: expression with thresholds
        ?drugExpr a biolink:GeneExpressionMixin ;
                  spokegenelab:log2fc ?drugLog2fc ;
                  spokegenelab:adj_p_value ?drugPval ;
                  biolink:subject ?drugAssayUri ;
                  biolink:object ?gene .

        # Numeric filters immediately after binding
        {drug_fc_filter}
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

        # Get the drug/compound entity (similar to disease extraction)
        OPTIONAL {{
            ?drugStudyUri biolink:studies ?drug .
            ?drug a biolink:ChemicalEntity ;
                  biolink:name ?drugName ;
                  biolink:id ?drugId .
        }}
    }}
    LIMIT {limit}
    '''

    print(f"Step 1: Querying genes {drug_label}-regulated by drugs/compounds...")
    drug_results = client.query(GXA_PREFIXES + drug_query, endpoint="gxa", include_prefixes=False).to_simple_dicts()
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
                'ref_group': r.get('drugRefGroup', ''),
                'drug_name': r.get('drugName', ''),
                'drug_id': r.get('drugId', '')
            })

    print(f"  Unique genes: {len(drug_genes)}")

    if not drug_genes:
        return []

    # Step 2: Check which genes have opposite regulation in disease
    gene_uris = list(drug_genes.keys())
    all_disease_results = []

    print(f"Step 2: Checking disease {disease_label}-regulation in {len(gene_uris)//batch_size + 1} batches...")

    for i in range(0, len(gene_uris), batch_size):
        batch = gene_uris[i:i+batch_size]
        values_str = ' '.join([f'<{uri}>' for uri in batch])

        # Optimized query - no FILTER, filter in Python
        disease_query = f'''
        SELECT ?gene ?diseaseStudy ?diseaseTitle ?diseaseLog2fc ?diseasePval ?diseaseName ?diseaseId
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
                             spokegenelab:project_title ?diseaseTitle ;
                             biolink:studies ?disease .

            # Get disease info
            ?disease a biolink:Disease ;
                     biolink:name ?diseaseName ;
                     biolink:id ?diseaseId .
        }}
        LIMIT 500
        '''

        try:
            results = client.query(GXA_PREFIXES + disease_query, endpoint="gxa", include_prefixes=False).to_simple_dicts()
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

        # Python-side filtering based on disease direction
        if disease_direction == "up":
            if disease_log2fc <= disease_fc_threshold:
                filtered_fc += 1
                continue
        else:  # down
            if disease_log2fc >= -disease_fc_threshold:
                filtered_fc += 1
                continue

        # Check p-value threshold
        if disease_pval >= pvalue_threshold:
            filtered_pval += 1
            continue

        # Exclude controls/healthy by ID or name
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
                'drug_name': drug_entry['drug_name'],
                'drug_id': drug_entry['drug_id'],
                # Disease info
                'disease_study': r.get('diseaseStudy', ''),
                'disease_title': r.get('diseaseTitle', ''),
                'disease_log2fc': disease_log2fc,
                'disease': disease,
                'disease_id': disease_id,
                'disease_test_group': r.get('diseaseTestGroup', ''),
                'disease_ref_group': r.get('diseaseRefGroup', '')
            })

    # Sort by absolute disease fold change (highest first)
    combined.sort(key=lambda x: -abs(x['disease_log2fc']))

    print(f"  Filtered out: {filtered_fc} (FC threshold), {filtered_pval} (high p-val), {filtered_control} (controls)")
    print(f"  Remaining: {len(combined)} gene-disease pairs")

    return combined, drug_label, disease_label


def print_results(results, drug_label, disease_label, max_display=None):
    """Print results in a formatted way."""
    if not results:
        print("No matching genes found.")
        return

    print(f"\nFound {len(results)} gene-drug-disease combinations:\n")

    display_results = results if max_display is None else results[:max_display]
    for i, r in enumerate(display_results, 1):
        # Full study titles
        drug_study_name = r['drug_title'] if r['drug_title'] else r['drug_study']
        disease_study_name = r['disease_title'] if r['disease_title'] else r['disease_study']
        drug_context = f"{r['drug_test_group']} vs {r['drug_ref_group']}" if r['drug_test_group'] else "N/A"
        disease_context = f"{r['disease_test_group']} vs {r['disease_ref_group']}" if r['disease_test_group'] else "N/A"

        # Drug name (fall back to test_group if no structured drug entity)
        drug_name = r['drug_name'] if r['drug_name'] else r['drug_test_group'] or "N/A"

        print(f"{i:3}. Gene: {r['gene']}")
        print(f"     DRUG {drug_label} (log2FC={r['drug_log2fc']:.1f}):")
        print(f"       Drug/Compound: {drug_name}")
        print(f"       Study: {drug_study_name}")
        print(f"       Comparison: {drug_context}")
        print(f"     DISEASE {disease_label} (log2FC={r['disease_log2fc']:.1f}):")
        print(f"       Disease: {r['disease']}")
        print(f"       Study: {disease_study_name}")
        print(f"       Comparison: {disease_context}")
        print()

    # Summary
    unique_genes = len(set(r['gene'] for r in results))
    unique_drugs = len(set(r['drug_name'] or r['drug_test_group'] for r in results))
    unique_diseases = len(set(r['disease'] for r in results))
    unique_drug_studies = len(set(r['drug_title'] or r['drug_study'] for r in results))
    unique_disease_studies = len(set(r['disease_title'] or r['disease_study'] for r in results))

    print("-" * 80)
    print(f"SUMMARY: {len(results)} combinations")
    print(f"  Unique genes: {unique_genes}")
    print(f"  Unique drugs/compounds: {unique_drugs}")
    print(f"  Unique diseases: {unique_diseases}")
    print(f"  Unique drug studies: {unique_drug_studies}")
    print(f"  Unique disease studies: {unique_disease_studies}")


def main():
    print("=" * 80)
    print("DRUG-DISEASE OPPOSING EXPRESSION PATTERNS")
    print("(Optimized: No SPARQL FILTERs in disease query - Python filtering)")
    print("=" * 80)

    # Pattern 1: Drug DOWN, Disease UP
    # Drug suppresses a gene that is pathologically elevated
    print("\n" + "=" * 80)
    print("PATTERN 1: Drug DOWN-regulates \u2192 Disease UP-regulates")
    print("(Drug suppresses genes that are pathologically elevated in disease)")
    print("=" * 80 + "\n")

    results1, drug_label1, disease_label1 = find_drug_disease_genes(
        drug_direction="down",
        disease_direction="up"
    )
    print_results(results1, drug_label1, disease_label1)

    # Pattern 2: Drug UP, Disease DOWN
    # Drug activates a gene that is pathologically suppressed
    print("\n" + "=" * 80)
    print("PATTERN 2: Drug UP-regulates \u2192 Disease DOWN-regulates")
    print("(Drug activates genes that are pathologically suppressed in disease)")
    print("=" * 80 + "\n")

    results2, drug_label2, disease_label2 = find_drug_disease_genes(
        drug_direction="up",
        disease_direction="down"
    )
    print_results(results2, drug_label2, disease_label2)

    # Overall summary
    print("\n" + "=" * 80)
    print("OVERALL SUMMARY")
    print("=" * 80)
    print(f"Pattern 1 (Drug DOWN \u2192 Disease UP): {len(results1)} combinations")
    print(f"Pattern 2 (Drug UP \u2192 Disease DOWN): {len(results2)} combinations")
    print(f"Total: {len(results1) + len(results2)} therapeutic gene-disease associations")
    print("=" * 80)


if __name__ == "__main__":
    main()
