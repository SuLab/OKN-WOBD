#!/usr/bin/env python3
"""Test CellxGene client using SOMA-based implementation.

Tests each public method of the rewritten CellxGeneClient which uses
direct SOMA API calls instead of cellxgene_census.get_anndata().

Each test runs in a subprocess with a hard timeout to catch hangs.
"""

import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import time

TIMEOUT = 180


def run_test(name, code, timeout=TIMEOUT):
    """Run Python code in a subprocess with hard process-group kill on timeout."""
    print(f"\n{'='*60}")
    print(f"TEST: {name} (timeout={timeout}s)")
    sys.stdout.flush()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        script_path = f.name

    start = time.time()
    try:
        proc = subprocess.Popen(
            [sys.executable, script_path],
            stdout=sys.stdout, stderr=sys.stderr,
            preexec_fn=os.setsid,
        )
        try:
            proc.wait(timeout=timeout)
            elapsed = time.time() - start
            if proc.returncode == 0:
                print(f"  STATUS: PASSED ({elapsed:.1f}s)")
            else:
                print(f"  STATUS: FAILED ({elapsed:.1f}s, exit={proc.returncode})")
            sys.stdout.flush()
            return proc.returncode == 0
        except subprocess.TimeoutExpired:
            elapsed = time.time() - start
            print(f"  STATUS: TIMEOUT after {elapsed:.1f}s - killing process group")
            sys.stdout.flush()
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait(timeout=5)
            return False
    finally:
        os.unlink(script_path)


def main():
    print("CellxGene SOMA Client Tests")
    print(f"Python: {sys.version}")
    print(f"Timeout per test: {TIMEOUT}s\n")

    results = {}

    # Test 1: get_gene_id
    results["get_gene_id"] = run_test(
        "get_gene_id('ACTA2')",
        textwrap.dedent("""\
            import sys
            sys.path.insert(0, '.')
            from clients import CellxGeneClient

            with CellxGeneClient() as client:
                gene_id = client.get_gene_id("ACTA2")
                print(f"  ACTA2 -> {gene_id}", flush=True)
                assert gene_id is not None, "Expected Ensembl ID for ACTA2"
                assert gene_id.startswith("ENSG"), f"Expected ENSG prefix, got {gene_id}"

                missing = client.get_gene_id("NOT_A_REAL_GENE_XYZ")
                assert missing is None, "Expected None for nonexistent gene"
                print("  NOT_A_REAL_GENE_XYZ -> None (correct)", flush=True)
        """),
    )

    # Test 2: get_expression_data (the core SOMA-based method)
    results["get_expression_data"] = run_test(
        "get_expression_data('ACTA2', lung fibroblast)",
        textwrap.dedent("""\
            import sys, numpy as np
            sys.path.insert(0, '.')
            from clients import CellxGeneClient

            with CellxGeneClient() as client:
                result = client.get_expression_data(
                    "ACTA2",
                    tissue="lung",
                    cell_types=["fibroblast"],
                    diseases=["normal"],
                    max_cells=500,
                )
                assert result is not None, "Expected data for ACTA2 in lung fibroblasts"
                expr, obs_df = result

                print(f"  expr shape: {expr.shape}", flush=True)
                print(f"  obs_df shape: {obs_df.shape}", flush=True)
                print(f"  obs_df columns: {list(obs_df.columns)}", flush=True)
                print(f"  mean expr: {np.mean(expr):.4f}", flush=True)
                print(f"  nonzero: {np.sum(expr > 0)}/{len(expr)}", flush=True)

                assert len(expr) == len(obs_df), "expr and obs_df length mismatch"
                assert len(expr) <= 500, f"Expected <= 500 cells, got {len(expr)}"
                assert "cell_type" in obs_df.columns
                assert "disease" in obs_df.columns
                assert "dataset_id" in obs_df.columns
                assert "soma_joinid" not in obs_df.columns, "soma_joinid should be dropped"
        """),
    )

    # Test 3: get_cell_type_expression
    results["get_cell_type_expression"] = run_test(
        "get_cell_type_expression('ACTA2', lung)",
        textwrap.dedent("""\
            import sys
            sys.path.insert(0, '.')
            from clients import CellxGeneClient

            with CellxGeneClient() as client:
                stats = client.get_cell_type_expression(
                    "ACTA2",
                    tissue="lung",
                    diseases=["normal"],
                    min_cells=10,
                )
                print(f"  Got {len(stats)} cell types", flush=True)
                assert len(stats) > 0, "Expected at least one cell type"

                for s in stats[:5]:
                    print(
                        f"  {s.cell_type}: mean={s.mean_expression:.2f}, "
                        f"n={s.n_cells}, pct={s.pct_expressing:.1f}%",
                        flush=True,
                    )

                # Verify sorted descending by mean
                for i in range(len(stats) - 1):
                    assert stats[i].mean_expression >= stats[i+1].mean_expression
        """),
    )

    # Test 4: compare_conditions
    results["compare_conditions"] = run_test(
        "compare_conditions('ACTA2', lung, normal vs fibrosis)",
        textwrap.dedent("""\
            import sys
            sys.path.insert(0, '.')
            from clients import CellxGeneClient

            with CellxGeneClient() as client:
                comp = client.compare_conditions(
                    "ACTA2",
                    tissue="lung",
                    condition_a="normal",
                    condition_b="pulmonary fibrosis",
                    min_cells=20,
                )
                if comp is None:
                    print("  No comparison (insufficient cells) - SKIPPED", flush=True)
                    # Not a failure, fibrosis samples may be sparse
                else:
                    print(f"  {comp.condition_a}: mean={comp.mean_a:.2f} (n={comp.n_cells_a})", flush=True)
                    print(f"  {comp.condition_b}: mean={comp.mean_b:.2f} (n={comp.n_cells_b})", flush=True)
                    print(f"  fold_change={comp.fold_change:.2f}, log2FC={comp.log2_fold_change:.2f}", flush=True)
                    print(f"  p_value={comp.p_value}", flush=True)
                    print(f"  n_datasets={comp.n_datasets}", flush=True)
                    assert comp.gene == "ACTA2"
                    assert comp.tissue == "lung"
                    assert comp.n_cells_a >= 20
                    assert comp.n_cells_b >= 20
        """),
    )

    # Test 5: get_cell_type_comparison
    results["get_cell_type_comparison"] = run_test(
        "get_cell_type_comparison('ACTA2', lung)",
        textwrap.dedent("""\
            import sys
            sys.path.insert(0, '.')
            from clients import CellxGeneClient

            with CellxGeneClient() as client:
                ct_comp = client.get_cell_type_comparison(
                    "ACTA2",
                    tissue="lung",
                    condition_a="normal",
                    condition_b="pulmonary fibrosis",
                    min_cells=10,
                )
                print(f"  Got {len(ct_comp)} cell types with comparisons", flush=True)

                if ct_comp:
                    for ct, data in sorted(
                        ct_comp.items(), key=lambda x: x[1]["fold_change"], reverse=True
                    )[:5]:
                        print(
                            f"  {ct}: FC={data['fold_change']:.2f}, "
                            f"normal={data['n_cells_normal']}, disease={data['n_cells_disease']}",
                            flush=True,
                        )
                    # Verify expected keys
                    sample = next(iter(ct_comp.values()))
                    for key in ["mean_normal", "mean_disease", "fold_change", "n_cells_normal", "n_cells_disease"]:
                        assert key in sample, f"Missing key: {key}"
                else:
                    print("  No cell types had enough cells - SKIPPED", flush=True)
        """),
    )

    # Test 6: get_available_cell_types (metadata query)
    results["get_available_cell_types"] = run_test(
        "get_available_cell_types(lung, normal)",
        textwrap.dedent("""\
            import sys
            sys.path.insert(0, '.')
            from clients import CellxGeneClient

            with CellxGeneClient() as client:
                cell_types = client.get_available_cell_types(tissue="lung", disease="normal")
                print(f"  Got {len(cell_types)} cell types in lung/normal", flush=True)
                assert len(cell_types) > 0, "Expected cell types"
                assert "fibroblast" in cell_types, f"Expected 'fibroblast' in results"
                for ct in cell_types[:10]:
                    print(f"    {ct}", flush=True)
        """),
    )

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL/TIMEOUT"
        print(f"  {name:35s} {status}")

    n_pass = sum(1 for v in results.values() if v)
    n_total = len(results)
    print(f"\n  {n_pass}/{n_total} tests passed")

    if n_pass == n_total:
        print("\n  All tests passed - SOMA-based client is working correctly.")
    else:
        print("\n  Some tests failed. Check output above for details.")

    sys.exit(0 if n_pass == n_total else 1)


if __name__ == "__main__":
    main()
