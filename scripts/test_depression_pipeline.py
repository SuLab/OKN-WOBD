"""
Test the full depression DE pipeline via HTTP MCP, with timing at each step.

Measures:
- Ontology resolution (disease → MONDO IDs)
- Sample discovery (MONDO → NDE studies → ARCHS4 samples)
- Differential expression analysis
- Enrichment analysis

Usage: python3.11 scripts/test_depression_pipeline.py
"""

import json
import sys
import time

import httpx

MCP_URL = "http://localhost:8000/mcp"
TIMEOUT = 600

timings = []


def record(step, elapsed, details=None):
    entry = {"step": step, "elapsed_s": round(elapsed, 2)}
    if details:
        entry["details"] = details
    timings.append(entry)
    marker = ">>>" if elapsed > 10 else "   "
    print(f"\n{marker} [{elapsed:>7.1f}s] {step}")
    if details:
        for k, v in details.items():
            val = str(v)
            if len(val) > 120:
                val = val[:120] + "..."
            print(f"      {k}: {val}")


class MCPClient:
    """Synchronous MCP client for streamable-http transport."""

    def __init__(self, url):
        self.url = url
        self.session_id = None
        self.request_id = 0

    def _next_id(self):
        self.request_id += 1
        return self.request_id

    def _post_sse(self, payload):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
            with client.stream("POST", self.url, json=payload, headers=headers) as resp:
                if "mcp-session-id" in resp.headers:
                    self.session_id = resp.headers["mcp-session-id"]
                result = None
                for line in resp.iter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        if "result" in data:
                            result = data["result"]
                        elif "error" in data:
                            result = {"error": data["error"]}
                return result

    def _notify(self, method):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        with httpx.Client(timeout=30, follow_redirects=True) as c:
            c.post(self.url, json={"jsonrpc": "2.0", "method": method}, headers=headers)

    def initialize(self):
        result = self._post_sse({
            "jsonrpc": "2.0", "id": self._next_id(), "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26", "capabilities": {},
                "clientInfo": {"name": "pipeline-test", "version": "1.0"},
            },
        })
        self._notify("notifications/initialized")
        return result

    def call_tool(self, name, arguments=None):
        return self._post_sse({
            "jsonrpc": "2.0", "id": self._next_id(), "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        })


def get_json(result):
    """Extract parsed JSON from MCP tool result."""
    if result and "content" in result:
        for item in result["content"]:
            if item.get("type") == "text":
                try:
                    return json.loads(item["text"])
                except (json.JSONDecodeError, TypeError):
                    return {"_raw": item["text"]}
    return {"_raw": str(result)}


def poll_job(client, job_id, label, interval=15):
    """Poll a background job, return (data, total_elapsed, n_polls)."""
    start = time.time()
    polls = 0
    while True:
        polls += 1
        time.sleep(interval)
        elapsed = time.time() - start
        result = client.call_tool("get_analysis_result", {"job_id": job_id})
        data = get_json(result)
        status = data.get("status", "unknown")
        print(f"      poll #{polls} at {elapsed:.0f}s → {status}")
        if status in ("completed", "failed"):
            return data, time.time() - start, polls
        if elapsed > 500:
            return {"status": "timeout"}, elapsed, polls


def main():
    print("=" * 70)
    print("  DEPRESSION IN BRAIN — DE PIPELINE VIA HTTP MCP")
    print("  " + time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 70)
    T0 = time.time()

    client = MCPClient(MCP_URL)

    # -- Initialize --
    t0 = time.time()
    init = client.initialize()
    record("MCP Initialize", time.time() - t0)

    # -- Health Check --
    t0 = time.time()
    health = get_json(client.call_tool("health_check"))
    record("Health Check", time.time() - t0, {
        "archs4": health.get("capabilities", {}).get("archs4_data"),
        "api_key": health.get("capabilities", {}).get("anthropic_api_key"),
    })

    # =================================================================
    # STEP 1: Ontology Resolution
    # =================================================================
    t0 = time.time()
    ont = get_json(client.call_tool("resolve_disease_ontology", {
        "disease_name": "depression", "expand": True, "max_terms": 50,
    }))
    record("1. Resolve Disease Ontology", time.time() - t0, {
        "mondo_ids": ont.get("mondo_ids"),
        "labels": ont.get("labels"),
        "confidence": ont.get("confidence"),
        "n_expanded_ids": len(ont.get("expanded_ids", [])),
        "expanded_ids_sample": ont.get("expanded_ids", [])[:5],
    })

    # =================================================================
    # STEP 2: Find Samples
    # =================================================================
    t0 = time.time()
    find = get_json(client.call_tool("find_samples", {
        "disease_term": "depression",
        "tissue": "brain",
        "use_ontology": True,
        "max_test_samples": 200,
        "max_control_samples": 200,
    }))
    submit_time = time.time() - t0

    if "job_id" in find:
        job_id = find["job_id"]
        print(f"      → Background job {job_id}")
        data, poll_time, n_polls = poll_job(client, job_id, "find_samples", interval=10)
        inner = data.get("result", data)

        record("2. Find Samples", submit_time + poll_time, {
            "n_test": inner.get("n_test_samples"),
            "n_control": inner.get("n_control_samples"),
            "n_polls": n_polls,
        })

        # Ontology discovery breakdown
        fs = inner.get("filtering_stats", {})
        od = fs.get("ontology_discovery", {})
        if od:
            record("   └─ Ontology Discovery", 0, {
                "mondo_resolved": od.get("mondo_ids_resolved"),
                "mondo_expanded": len(od.get("expanded_mondo_ids", [])),
                "nde_studies": od.get("gse_studies_discovered"),
                "studies_w_samples": od.get("studies_with_classifiable_samples"),
                "ont_test/ctrl": f"{od.get('ontology_test_samples')}/{od.get('ontology_control_samples')}",
                "kw_test/ctrl": f"{od.get('keyword_test_samples')}/{od.get('keyword_control_samples')}",
                "merged_test/ctrl": f"{od.get('merged_test_samples')}/{od.get('merged_control_samples')}",
            })

        # Tissue filtering
        tt = fs.get("test_tissue", {})
        ct = fs.get("control_tissue", {})
        if tt:
            record("   └─ Tissue Filtering", 0, {
                "test_before→after": f"{tt.get('before')}→{tt.get('after_exclude')}",
                "control_before→after": f"{ct.get('before', '?')}→{ct.get('after_exclude', '?')}",
            })

        # Study breakdown
        sb = inner.get("study_breakdown", {})
        if isinstance(sb, dict):
            top = sb.get("top_studies", [])
            both = sb.get("studies_with_both", 0)
            record("   └─ Study Breakdown", 0, {
                "studies_w_test": sb.get("studies_with_test"),
                "studies_w_control": sb.get("studies_with_control"),
                "studies_w_both": both,
                "recommendation": sb.get("recommendation"),
            })
            if top:
                print("      Top studies:")
                for s in top[:10]:
                    if isinstance(s, dict):
                        print(f"        {s.get('study_id', '?'):12s}  "
                              f"test={s.get('n_test', 0):3d}  ctrl={s.get('n_control', 0):3d}")
    else:
        record("2. Find Samples", submit_time, find)

    # =================================================================
    # STEP 3: Differential Expression
    # =================================================================
    t0 = time.time()
    de = get_json(client.call_tool("differential_expression", {
        "query": "depression in brain",
        "disease": "depression",
        "tissue": "brain",
        "mode": "auto",
        "max_test_samples": 200,
        "max_control_samples": 200,
    }))
    submit_time = time.time() - t0

    if "job_id" in de:
        job_id = de["job_id"]
        print(f"      → Background job {job_id}")
        data, poll_time, n_polls = poll_job(client, job_id, "DE", interval=30)
        inner = data.get("result", data)

        record("3. Differential Expression", submit_time + poll_time, {
            "status": data.get("status"),
            "n_polls": n_polls,
        })

        if data.get("status") == "completed":
            de_res = inner.get("de_results", {})
            prov = inner.get("provenance", {})
            record("   └─ DE Results", 0, {
                "genes_tested": de_res.get("genes_tested"),
                "genes_significant": de_res.get("genes_significant"),
                "analysis_mode": prov.get("analysis_mode"),
                "fallback_reason": prov.get("mode_fallback_reason"),
                "test_method": prov.get("methods", {}).get("test"),
                "n_test": prov.get("samples", {}).get("n_test"),
                "n_control": prov.get("samples", {}).get("n_control"),
            })

            # Significant genes
            sig = de_res.get("significant_genes", [])
            if sig:
                up = [g for g in sig if g.get("direction") == "up"]
                down = [g for g in sig if g.get("direction") == "down"]
                print(f"\n      Significant genes: {len(sig)} total "
                      f"({len(up)} up, {len(down)} down)")
                print(f"      {'Gene':15s} {'log2FC':>8s} {'padj':>12s} {'Direction':>10s}")
                print(f"      {'-'*47}")
                for g in sig:
                    print(f"      {g['gene']:15s} {g['log2_fold_change']:>8.2f} "
                          f"{g['padj']:>12.2e} {g['direction']:>10s}")

            # Enrichment
            enrich = inner.get("enrichment", {})
            total_terms = sum(len(v) for v in enrich.values() if isinstance(v, list))
            record("   └─ Enrichment", 0, {
                "sources": list(enrich.keys()),
                "total_terms": total_terms,
            })
            for source, terms in enrich.items():
                if isinstance(terms, list) and terms:
                    print(f"      [{source}]:")
                    for t in terms[:5]:
                        if isinstance(t, dict):
                            print(f"        {t.get('name', '?')}  (p={t.get('p_value', '?'):.4g})")
        else:
            print(f"      DE FAILED: {data}")
    else:
        record("3. Differential Expression", submit_time, de)

    # =================================================================
    # STEP 4: Standalone Enrichment (with more genes if available)
    # =================================================================
    try:
        sig_genes = [g["gene"] for g in de_res.get("significant_genes", [])
                     if isinstance(g, dict)]
    except Exception:
        sig_genes = []

    if sig_genes:
        t0 = time.time()
        enrich_result = get_json(client.call_tool("enrichment_analysis", {
            "gene_list": sig_genes,
            "organism": "hsapiens",
            "sources": ["GO:BP", "GO:CC", "GO:MF", "KEGG", "REAC"],
            "threshold": 0.05,
        }))
        record("4. Enrichment Analysis (standalone)", time.time() - t0, {
            "n_input_genes": len(sig_genes),
        })

        if "error" not in enrich_result:
            for source in ["GO:BP", "GO:CC", "GO:MF", "KEGG", "REAC"]:
                terms = enrich_result.get(source, [])
                if terms:
                    print(f"      [{source}] {len(terms)} terms:")
                    for t in terms[:5]:
                        if isinstance(t, dict):
                            print(f"        {t.get('name', '?')[:50]:50s}  "
                                  f"p={t.get('p_value', 0):.4g}")
        else:
            print(f"      Enrichment error: {enrich_result.get('error')}")

    # =================================================================
    # FINAL SUMMARY
    # =================================================================
    TOTAL = time.time() - T0

    print("\n")
    print("=" * 70)
    print("  PIPELINE TIMING SUMMARY")
    print("=" * 70)
    print(f"  {'Step':<52} {'Time':>8}  {'Note'}")
    print("  " + "-" * 68)
    for t in timings:
        e = t["elapsed_s"]
        if e == 0:
            continue
        flag = " *** SLOW" if e > 30 else " * notable" if e > 10 else ""
        print(f"  {t['step']:<52} {e:>6.1f}s{flag}")
    print("  " + "-" * 68)
    print(f"  {'TOTAL PIPELINE':<52} {TOTAL:>6.1f}s")
    print("=" * 70)

    # Bottleneck analysis
    print("\n  BOTTLENECK ANALYSIS:")
    slow = [(t["step"], t["elapsed_s"]) for t in timings if t["elapsed_s"] > 5]
    for step, secs in sorted(slow, key=lambda x: -x[1]):
        pct = 100 * secs / TOTAL
        print(f"    {step:<50} {secs:>6.1f}s  ({pct:.0f}%)")


if __name__ == "__main__":
    main()
