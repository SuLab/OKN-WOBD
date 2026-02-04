#!/usr/bin/env python3
"""Test Doxycycline → SFRP2 queries against local gene expression data.

This script tests queries related to Doxycycline and SFRP2 using only
local gene expression data (GXA). Since SPOKE-OKN and Ubergraph data
aren't available locally, we can only test the gene expression part.

For complete testing, you'll need access to FRINK endpoints.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "web"))

from rdflib import Graph, Namespace, RDF

# Test query: Find SFRP2 gene expression data (what we CAN test locally)
# This query extracts study IDs that can be used to connect to other graphs
SFRP2_EXPRESSION_QUERY = """PREFIX biolink: <https://w3id.org/biolink/vocab/>
PREFIX spokegenelab: <https://spoke.ucsf.edu/genelab/>

SELECT DISTINCT
    ?gene
    ?geneSymbol
    ?experiment
    ?studyId
    ?experimentName
    ?log2fc
    ?adjPValue
    ?expressionDirection
    (REPLACE(STR(?experiment), "^.*/(E-[A-Z0-9-]+)-.*$", "$1") AS ?experimentId)
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
    
    # Get study ID from experiment (this is the key for connecting to other graphs)
    ?experiment spokegenelab:study_id ?studyId .
    
    # Get experiment name/label
    OPTIONAL {
        ?experiment biolink:name ?experimentName .
    }
    
    # Determine if upregulated or downregulated
    BIND(IF(?log2fc > 0, "upregulated", "downregulated") AS ?expressionDirection)
}
ORDER BY ?studyId DESC(?log2fc)
LIMIT 200
"""

def find_sfrp2_files(data_dir: Path) -> list[Path]:
    """Find .ttl files that contain SFRP2."""
    sfrp2_files = []
    
    print(f"Searching for files containing SFRP2...")
    for ttl_file in sorted(data_dir.glob("*.ttl")):
        try:
            g = Graph()
            g.parse(str(ttl_file), format="turtle")
            
            # Quick check if SFRP2 exists
            biolink = Namespace('https://w3id.org/biolink/vocab/')
            found = False
            for gene in g.subjects(RDF.type, biolink.Gene):
                symbol = g.value(gene, biolink.symbol, None)
                if symbol and ('sfrp2' in str(symbol).lower() or 'sfrp-2' in str(symbol).lower()):
                    found = True
                    break
            
            if found:
                sfrp2_files.append(ttl_file)
                print(f"  ✓ {ttl_file.name}")
        except Exception:
            pass  # Skip files with errors
    
    return sfrp2_files


def test_sfrp2_query(gene_expr_dir: Path, specific_file: str | None = None, all_files: bool = False) -> None:
    """Test SFRP2 gene expression query against local data.
    
    Args:
        gene_expr_dir: Directory containing .ttl files
        specific_file: Test specific file only
        all_files: Load all files into one graph (like Fuseki does)
    """
    biolink = Namespace('https://w3id.org/biolink/vocab/')
    spoke = Namespace('https://spoke.ucsf.edu/genelab/')
    
    if all_files:
        # Load ALL files into one graph (matches what Fuseki does)
        print(f"\nLoading ALL files into merged graph (like Fuseki)...")
        merged_graph = Graph()
        ttl_files = sorted(gene_expr_dir.glob("*.ttl"))
        loaded = 0
        for ttl_file in ttl_files:
            try:
                merged_graph.parse(str(ttl_file), format="turtle")
                loaded += 1
                if loaded % 100 == 0:
                    print(f"  Loaded {loaded} files...")
            except Exception:
                pass
        print(f"  ✓ Loaded {loaded} files ({len(merged_graph)} triples)\n")
        
        # Test query against merged graph
        print("Testing SFRP2 expression query against merged graph...")
        print("-" * 80)
        try:
            result = merged_graph.query(SFRP2_EXPRESSION_QUERY)
            rows = list(result)
            print(f"✓ Found {len(rows)} SFRP2 expression associations\n")
            
            if rows:
                print("Results (first 10):")
                for i, row in enumerate(rows[:10], 1):
                    row_dict = {}
                    for key in row.labels:
                        value = row[key]
                        if value:
                            value_str = str(value)
                            if "/" in value_str:
                                value_str = value_str.split("/")[-1]
                            if "#" in value_str:
                                value_str = value_str.split("#")[-1]
                            row_dict[key] = value_str
                    
                    print(f"  {i}. Study ID: {row_dict.get('studyId', 'N/A')}")
                    print(f"     Experiment: {row_dict.get('experimentId', 'N/A')}")
                    print(f"     Gene: {row_dict.get('geneSymbol', 'N/A')}")
                    print(f"     Expression: {row_dict.get('expressionDirection', 'N/A')} (log2fc: {row_dict.get('log2fc', 'N/A')})")
                    print(f"     p-value: {row_dict.get('adjPValue', 'N/A')}")
                    if row_dict.get('experimentName'):
                        label = row_dict['experimentName'][:60]
                        print(f"     Experiment name: {label}...")
                    print()
                
                if len(rows) > 10:
                    print(f"  ... and {len(rows) - 10} more results\n")
        except Exception as e:
            print(f"✗ Error: {e}\n")
        return
    
    # Original single-file testing
    if specific_file:
        files_to_test = [gene_expr_dir / specific_file]
    else:
        # Find files with SFRP2
        files_to_test = find_sfrp2_files(gene_expr_dir)
        if not files_to_test:
            print("✗ No files found containing SFRP2")
            return
    
    print(f"\nTesting SFRP2 expression query against {len(files_to_test)} file(s)...\n")
    
    for ttl_file in files_to_test:
        print(f"File: {ttl_file.name}")
        print("-" * 80)
        
        g = Graph()
        try:
            g.parse(str(ttl_file), format="turtle")
            
            # Execute query
            result = g.query(SFRP2_EXPRESSION_QUERY)
            rows = list(result)
            
            print(f"✓ Found {len(rows)} SFRP2 expression associations\n")
            
            if rows:
                print("Results:")
                for i, row in enumerate(rows[:10], 1):  # Show first 10
                    row_dict = {}
                    for key in row.labels:
                        value = row[key]
                        if value:
                            value_str = str(value)
                            # Extract shorter identifiers
                            if "/" in value_str:
                                value_str = value_str.split("/")[-1]
                            if "#" in value_str:
                                value_str = value_str.split("#")[-1]
                            row_dict[key] = value_str
                    
                    print(f"  {i}. Study ID: {row_dict.get('studyId', 'N/A')}")
                    print(f"     Experiment: {row_dict.get('experimentId', 'N/A')}")
                    print(f"     Gene: {row_dict.get('geneSymbol', 'N/A')}")
                    print(f"     Expression: {row_dict.get('expressionDirection', 'N/A')} (log2fc: {row_dict.get('log2fc', 'N/A')})")
                    print(f"     p-value: {row_dict.get('adjPValue', 'N/A')}")
                    if row_dict.get('experimentName'):
                        print(f"     Experiment name: {row_dict['experimentName'][:60]}...")
                    print()
                
                if len(rows) > 10:
                    print(f"  ... and {len(rows) - 10} more results\n")
        except Exception as e:
            print(f"✗ Error: {e}\n")


def main() -> int:
    import argparse
    
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gene-expr-dir",
        type=Path,
        default=Path("data/gene_expression"),
        help="Directory containing gene expression .ttl files",
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Test specific file (e.g., E-GEOD-XXXXX.ttl)",
    )
    parser.add_argument(
        "--all-files",
        action="store_true",
        help="Load ALL files into merged graph - slower but simulates a single SPARQL endpoint with all data",
    )
    
    args = parser.parse_args()
    
    if not args.gene_expr_dir.is_dir():
        print(f"Error: Directory not found: {args.gene_expr_dir}")
        return 1
    
    print("=" * 80)
    print("Testing SFRP2 Gene Expression Query (Local Data Only)")
    print("=" * 80)
    print("\nNote: This tests only the GXA (gene expression) part.")
    print("For complete testing (SPOKE-OKN + Ubergraph), you'll need FRINK access.\n")
    
    if args.all_files:
        print("Using --all-files: Loading all files into merged graph")
        print("This simulates a single SPARQL endpoint with all data loaded.\n")
    
    test_sfrp2_query(args.gene_expr_dir, args.file, all_files=args.all_files)
    
    print("\n" + "=" * 80)
    print("Next Steps:")
    print("=" * 80)
    print("1. To test SPOKE-OKN queries: Need FRINK access to https://frink.apps.renci.org/spoke-okn/sparql")
    print("2. To test Ubergraph queries: Need FRINK access to https://frink.apps.renci.org/ubergraph/sparql")
    print("3. To test federated queries: Need all three endpoints accessible via FRINK")
    print("\nSee docs/doxycycline_sfrp2_queries.md for complete query examples.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

