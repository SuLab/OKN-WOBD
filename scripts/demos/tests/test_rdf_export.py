#!/usr/bin/env python3
"""Test RDF export by loading a generated example and running SPARQL queries.

Loads the psoriasis results.ttl into an rdflib graph and validates the
structure and content with SPARQL queries against known values.

Run from scripts/demos/:
    python -m tests.test_rdf_export
"""

import sys
from pathlib import Path

from rdflib import Graph, Namespace

# Namespaces matching de_rdf output
BIOLINK = Namespace("https://w3id.org/biolink/vocab/")
OKN_WOBD = Namespace("http://purl.org/okn/wobd/")
NCBIGENE = Namespace("https://www.ncbi.nlm.nih.gov/gene/")

EXAMPLES_DIR = Path(__file__).parent.parent / "chatgeo" / "examples"
PSORIASIS_TTL = EXAMPLES_DIR / "01_psoriasis" / "results.ttl"


def load_graph() -> Graph:
    """Load the psoriasis example RDF into an rdflib graph."""
    if not PSORIASIS_TTL.exists():
        print(f"ERROR: {PSORIASIS_TTL} not found. Run the psoriasis example first.")
        sys.exit(1)

    g = Graph()
    g.parse(PSORIASIS_TTL, format="turtle")
    print(f"Loaded {len(g)} triples from {PSORIASIS_TTL.name}")
    return g


def test_study_node(g: Graph) -> bool:
    """Verify the Study node exists with expected properties."""
    query = """
    PREFIX biolink: <https://w3id.org/biolink/vocab/>
    PREFIX okn-wobd: <http://purl.org/okn/wobd/>

    SELECT ?name ?description ?timestamp
    WHERE {
        ?study a biolink:Study ;
               biolink:name ?name .
        OPTIONAL { ?study biolink:description ?description }
        OPTIONAL { ?study okn-wobd:timestamp ?timestamp }
    }
    """
    results = list(g.query(query))
    assert len(results) == 1, f"Expected 1 Study node, got {len(results)}"

    name = str(results[0]["name"])
    assert "psoriasis" in name.lower(), f"Study name should mention psoriasis: {name}"
    assert results[0]["timestamp"] is not None, "Study should have a timestamp"

    print(f"  Study: {name}")
    print(f"  Timestamp: {results[0]['timestamp']}")
    return True


def test_assay_node(g: Graph) -> bool:
    """Verify the Assay node has method, platform, summary, and interpretation."""
    query = """
    PREFIX biolink: <https://w3id.org/biolink/vocab/>
    PREFIX okn-wobd: <http://purl.org/okn/wobd/>

    SELECT ?name ?method ?platform ?n_test ?n_control ?summary ?interpretation
    WHERE {
        ?assay a biolink:Assay ;
               biolink:name ?name ;
               okn-wobd:test_method ?method ;
               okn-wobd:platform ?platform ;
               okn-wobd:n_test_samples ?n_test ;
               okn-wobd:n_control_samples ?n_control .
        OPTIONAL { ?assay okn-wobd:summary ?summary }
        OPTIONAL { ?assay okn-wobd:interpretation ?interpretation }
    }
    """
    results = list(g.query(query))
    assert len(results) == 1, f"Expected 1 Assay node, got {len(results)}"

    row = results[0]
    assert str(row["method"]) == "deseq2", f"Expected deseq2, got {row['method']}"
    assert str(row["platform"]) == "ARCHS4", f"Expected ARCHS4, got {row['platform']}"
    assert int(row["n_test"]) > 0, "Should have test samples"
    assert int(row["n_control"]) > 0, "Should have control samples"
    assert row["summary"] is not None, "Assay should have a summary"
    assert len(str(row["summary"])) > 100, "Summary should be substantial"
    assert row["interpretation"] is not None, "Assay should have an interpretation"
    assert len(str(row["interpretation"])) > 100, "Interpretation should be substantial"

    print(f"  Assay: {row['name']}")
    print(f"  Method: {row['method']}, Platform: {row['platform']}")
    print(f"  Samples: {row['n_test']} test, {row['n_control']} control")
    print(f"  Summary length: {len(str(row['summary']))} chars")
    print(f"  Interpretation length: {len(str(row['interpretation']))} chars")
    return True


def test_gene_count(g: Graph) -> bool:
    """Verify genes are present and use NCBI Gene IDs."""
    query = """
    PREFIX biolink: <https://w3id.org/biolink/vocab/>

    SELECT (COUNT(DISTINCT ?gene) AS ?n_genes)
    WHERE {
        ?gene a biolink:Gene ;
              biolink:symbol ?symbol .
    }
    """
    results = list(g.query(query))
    n_genes = int(results[0]["n_genes"])
    assert n_genes > 100, f"Expected >100 genes, got {n_genes}"

    # Check that most genes use NCBI Gene URIs
    ncbi_query = """
    PREFIX biolink: <https://w3id.org/biolink/vocab/>
    PREFIX ncbigene: <https://www.ncbi.nlm.nih.gov/gene/>

    SELECT (COUNT(?gene) AS ?n_ncbi)
    WHERE {
        ?gene a biolink:Gene .
        FILTER(STRSTARTS(STR(?gene), STR(ncbigene:)))
    }
    """
    ncbi_results = list(g.query(ncbi_query))
    n_ncbi = int(ncbi_results[0]["n_ncbi"])
    pct = (n_ncbi / n_genes) * 100

    assert pct > 90, f"Expected >90% NCBI Gene URIs, got {pct:.1f}%"

    print(f"  Total genes: {n_genes}")
    print(f"  NCBI Gene IDs: {n_ncbi} ({pct:.1f}%)")
    return True


def test_de_associations(g: Graph) -> bool:
    """Verify DE associations have required properties."""
    query = """
    PREFIX biolink: <https://w3id.org/biolink/vocab/>
    PREFIX okn-wobd: <http://purl.org/okn/wobd/>

    SELECT (COUNT(?assoc) AS ?n_assoc)
    WHERE {
        ?assoc a biolink:GeneExpressionMixin ;
               biolink:subject ?assay ;
               biolink:predicate biolink:affects_expression_of ;
               biolink:object ?gene ;
               okn-wobd:log2fc ?log2fc ;
               okn-wobd:direction ?direction .
    }
    """
    results = list(g.query(query))
    n_assoc = int(results[0]["n_assoc"])
    assert n_assoc > 100, f"Expected >100 DE associations, got {n_assoc}"

    # Count up vs down
    dir_query = """
    PREFIX biolink: <https://w3id.org/biolink/vocab/>
    PREFIX okn-wobd: <http://purl.org/okn/wobd/>

    SELECT ?direction (COUNT(?assoc) AS ?n)
    WHERE {
        ?assoc a biolink:GeneExpressionMixin ;
               okn-wobd:direction ?direction .
    }
    GROUP BY ?direction
    """
    dir_results = {str(r["direction"]): int(r["n"]) for r in g.query(dir_query)}
    assert "up" in dir_results, "Should have upregulated genes"
    assert "down" in dir_results, "Should have downregulated genes"

    print(f"  DE associations: {n_assoc}")
    print(f"  Upregulated: {dir_results.get('up', 0)}")
    print(f"  Downregulated: {dir_results.get('down', 0)}")
    return True


def test_ido1_lookup(g: Graph) -> bool:
    """Query for IDO1 (ncbigene:3620), a known psoriasis marker."""
    query = """
    PREFIX biolink: <https://w3id.org/biolink/vocab/>
    PREFIX okn-wobd: <http://purl.org/okn/wobd/>
    PREFIX ncbigene: <https://www.ncbi.nlm.nih.gov/gene/>

    SELECT ?symbol ?log2fc ?pvalue ?direction
    WHERE {
        ?assoc a biolink:GeneExpressionMixin ;
               biolink:object ncbigene:3620 ;
               okn-wobd:log2fc ?log2fc ;
               okn-wobd:adj_p_value ?pvalue ;
               okn-wobd:direction ?direction .
        ncbigene:3620 biolink:symbol ?symbol .
    }
    """
    results = list(g.query(query))
    assert len(results) == 1, f"Expected 1 IDO1 association, got {len(results)}"

    row = results[0]
    assert str(row["symbol"]) == "IDO1", f"Expected IDO1, got {row['symbol']}"
    assert str(row["direction"]) == "up", f"IDO1 should be upregulated in psoriasis"
    assert float(row["log2fc"]) > 4, f"IDO1 log2FC should be >4, got {row['log2fc']}"
    assert float(row["pvalue"]) < 0.01, f"IDO1 should be significant"

    print(f"  IDO1 (ncbigene:3620): log2FC={float(row['log2fc']):.2f}, "
          f"padj={float(row['pvalue']):.2e}, direction={row['direction']}")
    return True


def test_upregulated_genes_query(g: Graph) -> bool:
    """Run the example SPARQL query from the README: upregulated genes with log2FC > 4."""
    query = """
    PREFIX biolink: <https://w3id.org/biolink/vocab/>
    PREFIX okn-wobd: <http://purl.org/okn/wobd/>

    SELECT ?symbol ?log2fc ?pvalue
    WHERE {
        ?assoc a biolink:GeneExpressionMixin ;
               biolink:subject ?assay ;
               biolink:object ?gene ;
               okn-wobd:log2fc ?log2fc ;
               okn-wobd:adj_p_value ?pvalue ;
               okn-wobd:direction "up" .
        ?gene biolink:symbol ?symbol .
        ?study biolink:has_output ?assay .
        ?study biolink:name ?study_name .
        FILTER(?log2fc > 4)
    }
    ORDER BY DESC(?log2fc)
    """
    results = list(g.query(query))
    assert len(results) > 5, f"Expected >5 highly upregulated genes, got {len(results)}"

    # All results should be strongly upregulated
    for row in results:
        assert float(row["log2fc"]) > 4
        assert float(row["pvalue"]) < 0.01

    # Check that known psoriasis markers are in the top results
    symbols = {str(r["symbol"]) for r in results}
    known_markers = {"DEFB4A", "DEFB4B", "IDO1", "CCL17"}
    found = known_markers & symbols
    assert len(found) >= 2, (
        f"Expected at least 2 known psoriasis markers in top upregulated, "
        f"found {found} out of {known_markers}"
    )

    print(f"  Genes with log2FC > 4: {len(results)}")
    print(f"  Known psoriasis markers found: {', '.join(sorted(found))}")
    print(f"  Top 5:")
    for row in results[:5]:
        print(f"    {row['symbol']}: log2FC={float(row['log2fc']):.2f}, "
              f"padj={float(row['pvalue']):.2e}")
    return True


def test_enrichment(g: Graph) -> bool:
    """Verify enrichment terms are present."""
    query = """
    PREFIX biolink: <https://w3id.org/biolink/vocab/>
    PREFIX okn-wobd: <http://purl.org/okn/wobd/>

    SELECT ?term_name ?source ?pvalue ?direction
    WHERE {
        ?assoc a biolink:Association ;
               biolink:object ?term ;
               okn-wobd:adj_p_value ?pvalue ;
               okn-wobd:enrichment_source ?source ;
               okn-wobd:direction ?direction .
        ?term biolink:name ?term_name .
    }
    ORDER BY ?pvalue
    LIMIT 10
    """
    results = list(g.query(query))
    assert len(results) > 0, "Expected enrichment terms"

    print(f"  Top enrichment terms:")
    for row in results[:5]:
        print(f"    [{row['source']}] {row['term_name']}: "
              f"padj={float(row['pvalue']):.2e}, {row['direction']}")
    return True


def test_provenance(g: Graph) -> bool:
    """Verify provenance fields (sample IDs, disease terms) are populated."""
    query = """
    PREFIX biolink: <https://w3id.org/biolink/vocab/>
    PREFIX okn-wobd: <http://purl.org/okn/wobd/>

    SELECT ?test_samples ?control_samples ?disease_terms
    WHERE {
        ?assay a biolink:Assay .
        OPTIONAL { ?assay okn-wobd:test_samples ?test_samples }
        OPTIONAL { ?assay okn-wobd:control_samples ?control_samples }
        OPTIONAL { ?assay okn-wobd:disease_terms ?disease_terms }
    }
    """
    results = list(g.query(query))
    assert len(results) == 1, f"Expected 1 Assay, got {len(results)}"

    row = results[0]
    assert row["test_samples"] is not None, "Should have test_samples"
    assert row["control_samples"] is not None, "Should have control_samples"
    assert row["disease_terms"] is not None, "Should have disease_terms"

    test_ids = str(row["test_samples"])
    control_ids = str(row["control_samples"])
    disease = str(row["disease_terms"])

    assert "GSM" in test_ids, "test_samples should contain GSM IDs"
    assert "GSM" in control_ids, "control_samples should contain GSM IDs"
    assert "psoriasis" in disease.lower() or "psoriatic" in disease.lower(), \
        f"disease_terms should mention psoriasis: {disease[:80]}"

    n_test = len(test_ids.split(","))
    n_control = len(control_ids.split(","))
    print(f"  Test sample IDs: {n_test} entries")
    print(f"  Control sample IDs: {n_control} entries")
    print(f"  Disease terms: {disease[:80]}...")
    return True


def main():
    print("=" * 60)
    print("ChatGEO RDF Export Tests")
    print("=" * 60)
    print()

    g = load_graph()
    print()

    tests = [
        ("Study node", test_study_node),
        ("Assay node (summary + interpretation)", test_assay_node),
        ("Gene count and NCBI IDs", test_gene_count),
        ("DE associations", test_de_associations),
        ("IDO1 lookup (ncbigene:3620)", test_ido1_lookup),
        ("Upregulated genes query (log2FC > 4)", test_upregulated_genes_query),
        ("Enrichment terms", test_enrichment),
        ("Provenance fields", test_provenance),
    ]

    results = {}
    for name, test_fn in tests:
        print(f"\n{'='*60}")
        print(f"TEST: {name}")
        try:
            passed = test_fn(g)
            results[name] = passed
            print(f"  STATUS: PASSED")
        except AssertionError as e:
            results[name] = False
            print(f"  STATUS: FAILED — {e}")
        except Exception as e:
            results[name] = False
            print(f"  STATUS: ERROR — {type(e).__name__}: {e}")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {name:45s} {status}")

    n_pass = sum(1 for v in results.values() if v)
    n_total = len(results)
    print(f"\n  {n_pass}/{n_total} tests passed")
    sys.exit(0 if n_pass == n_total else 1)


if __name__ == "__main__":
    main()
