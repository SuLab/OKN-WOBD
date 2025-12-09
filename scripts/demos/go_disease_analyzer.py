#!/usr/bin/env python3
"""
GO Term Disease Analyzer - Multi-Layer Gene Expression Analysis

This tool analyzes gene expression changes for genes in a Gene Ontology (GO) term
in the context of a specific disease and tissue. It integrates three data sources:

1. FRINK/Ubergraph (Knowledge Graph) - Discovers genes annotated to the GO term
2. CellxGene Census (Single-Cell RNA-seq) - Analyzes cell-type-specific expression
3. ARCHS4 (Bulk RNA-seq) - Validates findings across independent studies

WHAT QUESTIONS CAN THIS TOOL ANSWER?
=====================================

This tool answers questions of the form:

    "Which genes involved in [BIOLOGICAL PROCESS] are dysregulated in
     [DISEASE], and which cell types drive those changes?"

Examples:
- "Which genes in extracellular matrix organization are dysregulated in pulmonary fibrosis?"
- "Which inflammatory response genes are altered in rheumatoid arthritis?"
- "Which apoptosis genes are changed in breast cancer?"
- "Which lipid metabolism genes are dysregulated in non-alcoholic fatty liver disease?"

INPUT PARAMETERS
================

Required:
  --go-term         GO term ID (e.g., GO:0030198 for "extracellular matrix organization")
  --disease         Disease name as it appears in CellxGene (e.g., "pulmonary fibrosis")

Tissue Selection (one required):
  --tissue          Tissue name for CellxGene filtering (e.g., "lung", "liver", "brain")
  --uberon-id       UBERON ontology ID for precise tissue filtering (e.g., UBERON:0002048)

Optional:
  --go-label        Human-readable GO term label (auto-fetched if not provided)
  --control-term    Search term for control samples in ARCHS4 (default: "normal {tissue}")
  --max-genes       Maximum genes to analyze (default: 30)
  --output, -o      Output JSON file path
  --no-cache        Disable caching of intermediate results
  --skip-cellxgene  Skip single-cell analysis layer
  --skip-archs4     Skip bulk RNA-seq validation layer

OUTPUT
======

The tool produces:
1. Console output with formatted results
2. JSON file (if --output specified) containing:
   - query: Input parameters
   - layer1_knowledge: Discovered genes with GO annotations
   - layer2_singlecell: Cell-type-specific expression changes
   - layer3_validation: Bulk RNA-seq validation with differential expression
   - llm_summary: Natural language summary with data provenance

USAGE EXAMPLES
==============

# Basic usage - ECM genes in pulmonary fibrosis
python go_disease_analyzer.py \\
    --go-term GO:0030198 \\
    --disease "pulmonary fibrosis" \\
    --tissue lung \\
    --output ecm_fibrosis.json

# Inflammatory response in rheumatoid arthritis
python go_disease_analyzer.py \\
    --go-term GO:0006954 \\
    --go-label "inflammatory response" \\
    --disease "rheumatoid arthritis" \\
    --tissue "synovial tissue" \\
    --output inflammatory_ra.json

# Apoptosis in breast cancer
python go_disease_analyzer.py \\
    --go-term GO:0006915 \\
    --disease "breast cancer" \\
    --tissue breast \\
    --max-genes 20 \\
    --output apoptosis_bc.json

REQUIREMENTS
============
- Python 3.8+
- cellxgene-census (pip install cellxgene-census)
- archs4py (pip install archs4py)
- anthropic (pip install anthropic) - for LLM summaries
- Environment variables in .env:
  - DATA_DIR: Base data directory for caching
  - ARCHS4_DATA_DIR: Path to ARCHS4 HDF5 file
  - ANTHROPIC_API_KEY: API key for LLM summaries
"""

import os
import sys
import json
import argparse
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from sparql_client import SPARQLClient

# Optional imports with graceful degradation
try:
    from cellxgene_client import CellxGeneClient
    HAS_CELLXGENE = True
except ImportError:
    HAS_CELLXGENE = False

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

try:
    from archs4_client import ARCHS4Client
    HAS_ARCHS4 = True
except ImportError:
    HAS_ARCHS4 = False

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class GOGene:
    """A gene associated with a GO term."""
    symbol: str
    go_terms: List[str] = field(default_factory=list)


# =============================================================================
# Caching Utilities
# =============================================================================

def get_cache_dir(subdir: str = "go_disease_cache") -> Optional[Path]:
    """Get the cache directory from environment."""
    data_dir = os.environ.get("DATA_DIR")
    if not data_dir:
        return None
    cache_dir = Path(data_dir) / subdir
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_cache_key(params: Dict[str, Any]) -> str:
    """Generate a cache key from parameters."""
    param_str = json.dumps(params, sort_keys=True)
    return hashlib.md5(param_str.encode()).hexdigest()[:12]


def load_from_cache(cache_file: Path) -> Optional[Dict]:
    """Load data from cache file."""
    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)
    return None


def save_to_cache(cache_file: Path, data: Dict):
    """Save data to cache file."""
    with open(cache_file, "w") as f:
        json.dump(data, f, indent=2, default=str)


# =============================================================================
# Layer 1: Knowledge Graph - GO Term Gene Discovery
# =============================================================================

def get_go_genes(
    go_term: str,
    go_label: Optional[str] = None,
    max_genes: int = 100,
    use_cache: bool = True,
) -> List[GOGene]:
    """
    Query Ubergraph for GO term subclasses, then Wikidata for gene annotations.

    This uses a two-step approach instead of federated SPARQL:
    1. Query Ubergraph to get the GO term and its subclasses
    2. Query Wikidata to get genes annotated to those GO terms
    """
    cache_dir = get_cache_dir()
    cache_key = get_cache_key({"go_term": go_term, "max_genes": max_genes})
    cache_file = cache_dir / f"go_genes_{cache_key}.json" if cache_dir else None

    # Try cache first
    if use_cache and cache_file:
        cached = load_from_cache(cache_file)
        if cached:
            print(f"  [Cache] Loaded from {cache_file.name}")
            genes = [GOGene(symbol=g["symbol"], go_terms=g["go_terms"])
                     for g in cached["genes"]]
            print(f"  Found {len(genes)} genes from cache")
            return genes[:max_genes]

    # Convert GO term format for Ubergraph query
    go_id_numeric = go_term.replace("GO:", "GO_")

    # Step 1: Get GO term and its subclasses from Ubergraph
    ubergraph_query = f'''
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX obo: <http://purl.obolibrary.org/obo/>

    SELECT DISTINCT ?go_id ?go_label WHERE {{
      ?go_term rdfs:subClassOf* obo:{go_id_numeric} .
      ?go_term rdfs:label ?go_label .
      BIND(REPLACE(STR(?go_term), "http://purl.obolibrary.org/obo/GO_", "GO:") AS ?go_id)
    }}
    LIMIT 200
    '''

    print(f"  Querying Ubergraph for GO term subclasses of {go_term}...")

    ubergraph_client = SPARQLClient("https://ubergraph.apps.renci.org/sparql")
    go_results = ubergraph_client.query(ubergraph_query)

    # Collect GO terms and their labels
    go_terms_map = {}  # go_id -> label
    for row in go_results:
        go_id = row.get("go_id", {}).get("value", "")
        label = row.get("go_label", {}).get("value", "")
        if go_id and go_id.startswith("GO:"):
            go_terms_map[go_id] = label

    print(f"  Found {len(go_terms_map)} GO terms (including subclasses)")

    if not go_terms_map:
        print(f"  Warning: No GO terms found for {go_term}")
        return []

    # Step 2: Query Wikidata for genes annotated to these GO terms
    # Use VALUES clause to query multiple GO terms at once
    go_ids_list = list(go_terms_map.keys())

    # Query in batches to avoid too-large queries
    batch_size = 50
    gene_terms = defaultdict(list)

    wikidata_client = SPARQLClient("wikidata")

    for i in range(0, len(go_ids_list), batch_size):
        batch = go_ids_list[i:i + batch_size]
        values_clause = " ".join(f'"{go_id}"' for go_id in batch)

        wikidata_query = f'''
        PREFIX wdt: <http://www.wikidata.org/prop/direct/>
        PREFIX wd: <http://www.wikidata.org/entity/>

        SELECT DISTINCT ?go_id ?symbol WHERE {{
          VALUES ?go_id {{ {values_clause} }}
          ?go_wd wdt:P686 ?go_id .
          ?protein wdt:P682 ?go_wd ;
                   wdt:P703 wd:Q15978631 ;
                   wdt:P702 ?gene .
          ?gene wdt:P353 ?symbol .
        }}
        '''

        print(f"  Querying Wikidata for genes (batch {i // batch_size + 1})...")

        try:
            wd_results = wikidata_client.query(wikidata_query)
            for row in wd_results:
                symbol = row.get("symbol", {}).get("value", "")
                go_id = row.get("go_id", {}).get("value", "")
                if symbol and go_id:
                    term_label = go_terms_map.get(go_id, go_id)
                    if term_label not in gene_terms[symbol]:
                        gene_terms[symbol].append(term_label)
        except Exception as e:
            print(f"  Warning: Wikidata query failed: {e}")
            continue

        # Stop early if we have enough genes
        if len(gene_terms) >= max_genes * 2:
            break

    genes = [GOGene(symbol=sym, go_terms=terms)
             for sym, terms in gene_terms.items()]

    print(f"  Found {len(genes)} genes")

    # Cache results
    if use_cache and cache_file:
        save_to_cache(cache_file, {
            "go_term": go_term,
            "genes": [{"symbol": g.symbol, "go_terms": g.go_terms} for g in genes]
        })

    return genes[:max_genes]


# =============================================================================
# Layer 2: CellxGene Single-Cell Expression
# =============================================================================

def analyze_cellxgene_expression(
    gene_symbols: List[str],
    tissue: str,
    disease: str,
    uberon_id: Optional[str] = None,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """
    Analyze single-cell expression comparing disease vs normal.
    """
    if not HAS_CELLXGENE:
        return {"error": "cellxgene-census not installed"}

    cache_dir = get_cache_dir()
    cache_key = get_cache_key({
        "genes": sorted(gene_symbols),
        "tissue": tissue,
        "disease": disease,
        "tissue_ontology_term_id": uberon_id,
    })
    cache_file = cache_dir / f"cellxgene_{cache_key}.json" if cache_dir else None

    # Try cache first
    if use_cache and cache_file:
        cached = load_from_cache(cache_file)
        if cached and len(cached.get("results", {})) == len(gene_symbols):
            print(f"  [Cache] Loaded from {cache_file.name}")
            return cached

    print(f"  Analyzing {len(gene_symbols)} genes in {tissue}...")
    print(f"  Comparing: normal vs {disease}")

    results = {}

    with CellxGeneClient() as client:
        for gene in gene_symbols:
            try:
                # Get cached per-gene results if available
                gene_cache_key = get_cache_key({
                    "gene": gene, "tissue": tissue, "disease": disease, "tissue_ontology_term_id": uberon_id
                })
                gene_cache_file = cache_dir / f"gene_expr_{gene_cache_key}_{gene}.json" if cache_dir else None

                if use_cache and gene_cache_file and gene_cache_file.exists():
                    with open(gene_cache_file) as f:
                        gene_data = json.load(f)
                    results[gene] = gene_data.get("data", {})
                    continue

                # Query CellxGene
                comparison = client.get_cell_type_comparison(
                    gene_symbol=gene,
                    tissue=tissue,
                    tissue_ontology_term_id=uberon_id,
                    condition_a="normal",
                    condition_b=disease,
                )
                results[gene] = comparison

                # Cache per-gene
                if use_cache and gene_cache_file:
                    save_to_cache(gene_cache_file, {
                        "gene": gene,
                        "data": comparison,
                        "tissue": tissue,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })

            except Exception as e:
                print(f"    Warning: Could not analyze {gene}: {e}")
                continue

    # Cache full results
    if use_cache and cache_file:
        save_to_cache(cache_file, {"results": results})

    return {"results": results}


def aggregate_expression_results(
    gene_data: Dict[str, List[str]],
    expression_results: Dict[str, Any],
) -> Dict[str, Any]:
    """Aggregate expression results across genes and cell types."""
    results = expression_results.get("results", {})

    gene_summaries = []
    cell_type_stats = defaultdict(lambda: {"upregulated": [], "downregulated": []})

    for symbol, cell_type_data in results.items():
        if not cell_type_data:
            continue

        max_fc = 0
        max_fc_ct = "unknown"

        for ct, data in cell_type_data.items():
            fc = data.get("fold_change", 1.0)
            if fc > max_fc:
                max_fc = fc
                max_fc_ct = ct

            if fc > 1.5:
                cell_type_stats[ct]["upregulated"].append(symbol)
            elif fc < 0.67:
                cell_type_stats[ct]["downregulated"].append(symbol)

        gene_summaries.append({
            "symbol": symbol,
            "max_fold_change": max_fc,
            "top_cell_type": max_fc_ct,
            "go_terms": gene_data.get(symbol, []),
        })

    # Sort by fold change
    gene_summaries.sort(key=lambda x: x["max_fold_change"], reverse=True)

    # Determine up/down regulated
    upregulated = [g for g in gene_summaries if g["max_fold_change"] > 1.5]
    downregulated = [g for g in gene_summaries if g["max_fold_change"] < 0.67]

    # Cell type drivers
    cell_type_drivers = []
    for ct, stats in cell_type_stats.items():
        if stats["upregulated"] or stats["downregulated"]:
            cell_type_drivers.append({
                "cell_type": ct,
                "n_upregulated": len(stats["upregulated"]),
                "n_downregulated": len(stats["downregulated"]),
                "genes": stats["upregulated"] + stats["downregulated"],
            })

    cell_type_drivers.sort(key=lambda x: x["n_upregulated"], reverse=True)

    return {
        "n_genes_analyzed": len(gene_summaries),
        "n_upregulated": len(upregulated),
        "n_downregulated": len(downregulated),
        "top_upregulated": upregulated[:10],
        "top_downregulated": downregulated[:10],
        "cell_type_drivers": cell_type_drivers,
        "all_genes": gene_summaries,
    }


# =============================================================================
# Layer 3: ARCHS4 Bulk RNA-seq Validation
# =============================================================================

def validate_with_archs4(
    genes: List[str],
    disease_search_term: str,
    control_search_term: str = "normal lung",
    max_studies: int = 10,
    max_control_samples: int = 100,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """
    Validate findings in bulk RNA-seq studies from ARCHS4.
    Compares disease samples to control samples.

    This function searches through ALL available studies until it finds
    max_studies with usable expression data, or exhausts the available studies.
    """
    if not HAS_ARCHS4:
        return {"available": False, "reason": "ARCHS4 not installed"}

    data_dir = os.environ.get("ARCHS4_DATA_DIR")
    if not data_dir:
        return {"available": False, "reason": "ARCHS4_DATA_DIR not configured"}

    # Check cache first
    cache_dir = get_cache_dir()
    cache_key = get_cache_key({
        "genes": sorted(genes),
        "disease_search_term": disease_search_term,
        "control_search_term": control_search_term,
        "max_studies": max_studies,
    })
    cache_file = cache_dir / f"archs4_{cache_key}.json" if cache_dir else None

    if use_cache and cache_file:
        cached = load_from_cache(cache_file)
        if cached:
            print(f"  [Cache] Loaded ARCHS4 results from {cache_file.name}")
            return cached

    try:
        client = ARCHS4Client(data_dir=data_dir)
    except Exception as e:
        return {"available": False, "reason": str(e)}

    print(f"  Searching ARCHS4 for '{disease_search_term}' studies...")

    try:
        # Search for disease studies
        disease_metadata = client.search_metadata(disease_search_term)
        if disease_metadata.empty:
            return {"available": True, "n_studies": 0, "reason": "No disease studies found"}

        # Extract ALL series IDs (don't limit yet - we'll search until we find enough)
        gse_series = disease_metadata["series_id"].str.split(',').explode().str.strip().dropna()
        all_gse_ids = [gse for gse in gse_series.unique() if gse.startswith("GSE")]

        print(f"  Found {len(all_gse_ids)} unique studies with {len(disease_metadata)} samples in metadata")

        # Search for control samples
        print(f"  Searching for control samples ('{control_search_term}')...")
        control_metadata = client.search_metadata(control_search_term)

        if not control_metadata.empty:
            disease_samples = set(disease_metadata["geo_accession"])
            control_metadata = control_metadata[
                ~control_metadata["geo_accession"].isin(disease_samples)
            ]

        n_control = len(control_metadata) if not control_metadata.empty else 0
        print(f"  Found {n_control} control samples in metadata")

        # Get control expression
        control_expr = None
        control_sample_info = []
        control_samples_with_data = 0
        if n_control > 0:
            control_samples = list(control_metadata["geo_accession"].head(max_control_samples))
            control_expr = client.get_expression_by_samples(control_samples, genes=genes)

            if control_expr is not None and not control_expr.empty:
                control_samples_with_data = len(control_expr.columns)

            for _, row in control_metadata.head(10).iterrows():
                control_sample_info.append({
                    "gsm": row["geo_accession"],
                    "series": row["series_id"].split(',')[0] if row["series_id"] else "unknown",
                    "title": str(row["title"])[:100] if row["title"] else "N/A",
                    "source": str(row["source_name_ch1"])[:80] if row["source_name_ch1"] else "N/A",
                })

        print(f"  Control samples with expression data: {control_samples_with_data}")

        # Process disease studies - search ALL until we find max_studies with data
        study_results = []
        study_stats = {
            "total_examined": 0,
            "no_samples_in_metadata": 0,
            "no_expression_data": 0,
            "expression_empty": 0,
            "no_target_genes": 0,
            "exceptions": 0,
            "success": 0,
            "failed_studies": [],  # Track which studies failed and why
        }

        total_disease_samples_with_data = 0

        print(f"  Searching for studies with expression data (target: {max_studies})...")

        for gse in all_gse_ids:
            # Stop if we have enough successful studies
            if len(study_results) >= max_studies:
                break

            study_stats["total_examined"] += 1

            try:
                series_mask = disease_metadata["series_id"].str.contains(gse, na=False)
                series_data = disease_metadata.loc[series_mask]
                series_samples = list(series_data["geo_accession"])

                if not series_samples:
                    study_stats["no_samples_in_metadata"] += 1
                    study_stats["failed_studies"].append({
                        "gse": gse, "reason": "no_samples_in_metadata", "n_samples": 0
                    })
                    continue

                expr = client.get_expression_by_samples(series_samples, genes=genes)

                if expr is None:
                    study_stats["no_expression_data"] += 1
                    study_stats["failed_studies"].append({
                        "gse": gse, "reason": "no_expression_data",
                        "n_samples": len(series_samples),
                        "sample_ids": series_samples[:5]  # First 5 for debugging
                    })
                    continue

                if expr.empty:
                    study_stats["expression_empty"] += 1
                    study_stats["failed_studies"].append({
                        "gse": gse, "reason": "expression_empty",
                        "n_samples": len(series_samples)
                    })
                    continue

                genes_found = [g for g in genes if g in expr.index]

                if not genes_found:
                    study_stats["no_target_genes"] += 1
                    study_stats["failed_studies"].append({
                        "gse": gse, "reason": "no_target_genes_found",
                        "n_samples": len(expr.columns)
                    })
                    continue

                # Success! Collect sample metadata
                sample_titles = [str(row["title"])[:100] for _, row in series_data.iterrows()]
                study_title = _infer_study_title(sample_titles)

                sample_info = []
                for _, row in series_data.head(5).iterrows():
                    sample_info.append({
                        "gsm": row["geo_accession"],
                        "title": str(row["title"])[:100] if row["title"] else "N/A",
                        "source": str(row["source_name_ch1"])[:80] if row["source_name_ch1"] else "N/A",
                    })

                # Calculate mean expression per gene
                # Handle both Series (single row) and DataFrame (duplicate gene indices)
                mean_expr = {}
                for gene in genes_found:
                    gene_data = expr.loc[gene]
                    if hasattr(gene_data, 'values') and len(gene_data.shape) > 1:
                        # DataFrame case - multiple rows for same gene, flatten and mean
                        mean_expr[gene] = float(gene_data.values.flatten().mean())
                    else:
                        # Series case - single row
                        mean_expr[gene] = float(gene_data.mean())

                n_samples_with_data = len(expr.columns)
                total_disease_samples_with_data += n_samples_with_data

                study_results.append({
                    "gse": gse,
                    "study_title": study_title,
                    "n_samples": n_samples_with_data,
                    "n_samples_in_metadata": len(series_samples),
                    "n_genes_detected": len(genes_found),
                    "genes_detected": genes_found,
                    "mean_expression": mean_expr,
                    "sample_info": sample_info,
                })

                study_stats["success"] += 1
                print(f"    ✓ {gse}: {n_samples_with_data} samples, {len(genes_found)} genes")

            except Exception as e:
                study_stats["exceptions"] += 1
                study_stats["failed_studies"].append({
                    "gse": gse, "reason": f"exception: {str(e)[:100]}"
                })
                continue

        # Summary of study search
        print(f"\n  Study search summary:")
        print(f"    Examined: {study_stats['total_examined']} of {len(all_gse_ids)} studies")
        print(f"    Successful: {study_stats['success']}")
        print(f"    No samples in metadata: {study_stats['no_samples_in_metadata']}")
        print(f"    No expression data in HDF5: {study_stats['no_expression_data']}")
        print(f"    Expression data empty: {study_stats['expression_empty']}")
        print(f"    No target genes found: {study_stats['no_target_genes']}")
        print(f"    Exceptions: {study_stats['exceptions']}")
        print(f"    Total disease samples with data: {total_disease_samples_with_data}")

        # Calculate differential expression
        differential_expression = []
        if control_expr is not None and not control_expr.empty and study_results:
            print("  Calculating differential expression vs controls...")

            for gene in genes:
                disease_values = [s["mean_expression"].get(gene) for s in study_results
                                  if gene in s["mean_expression"]]
                disease_values = [v for v in disease_values if v is not None]

                control_values = []
                if gene in control_expr.index:
                    row = control_expr.loc[gene]
                    # Handle both Series (single row) and DataFrame (duplicate index)
                    if hasattr(row, 'values'):
                        control_values = row.values.flatten().tolist()
                    else:
                        control_values = [row]

                if disease_values and control_values:
                    mean_disease = sum(disease_values) / len(disease_values)
                    mean_control = sum(control_values) / len(control_values)

                    pseudo_count = 1.0
                    fold_change = (mean_disease + pseudo_count) / (mean_control + pseudo_count)
                    log2_fc = np.log2(fold_change) if HAS_NUMPY else None

                    differential_expression.append({
                        "gene": gene,
                        "mean_disease": round(mean_disease, 2),
                        "mean_control": round(mean_control, 2),
                        "fold_change": round(fold_change, 2),
                        "log2_fc": round(log2_fc, 2) if log2_fc else None,
                        "n_disease_studies": len(disease_values),
                        "n_control_samples": len(control_values),
                    })

            differential_expression.sort(key=lambda x: x["fold_change"], reverse=True)

        # Concordance
        concordance = 0
        if study_results:
            all_detected = set()
            for s in study_results:
                all_detected.update(s["genes_detected"])
            concordance = len(all_detected) / len(genes) if genes else 0

        result = {
            "available": True,
            "n_studies": len(study_results),
            "n_studies_examined": study_stats["total_examined"],
            "n_studies_in_metadata": len(all_gse_ids),
            "n_disease_samples_in_metadata": len(disease_metadata),
            "n_disease_samples_with_data": total_disease_samples_with_data,
            "n_control_samples_in_metadata": n_control,
            "n_control_samples_with_data": control_samples_with_data,
            "study_search_stats": study_stats,
            "studies": study_results,
            "control_samples": control_sample_info,
            "differential_expression": differential_expression,
            "genes_queried": genes,
            "concordance": concordance,
        }

        # Cache results
        if use_cache and cache_file:
            save_to_cache(cache_file, result)
            print(f"  [Cache] Saved ARCHS4 results to {cache_file.name}")

        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"available": False, "reason": str(e)}


def _infer_study_title(sample_titles: List[str]) -> str:
    """Infer study title from sample titles."""
    if not sample_titles:
        return "Unknown study"
    if len(sample_titles) == 1:
        return sample_titles[0]

    prefix = sample_titles[0]
    for title in sample_titles[1:]:
        while prefix and not title.startswith(prefix):
            prefix = prefix[:-1]

    if len(prefix) > 10:
        return prefix.rstrip(" -_:")
    return sample_titles[0]


# =============================================================================
# LLM Summary Generation
# =============================================================================

def generate_llm_summary(result: Dict[str, Any]) -> Optional[str]:
    """Generate a natural language summary using Claude."""
    if not HAS_ANTHROPIC:
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    query = result.get("query", {})
    layer1 = result.get("layer1_knowledge", {})
    layer2 = result.get("layer2_singlecell", {})
    layer3 = result.get("layer3_validation", {})

    # Build provenance
    provenance_parts = [
        f"- Gene Ontology term {query.get('go_term')} ({query.get('go_label', 'biological process')})",
        "- FRINK/Ubergraph federated SPARQL query (ubergraph.apps.renci.org)",
        "- Wikidata gene-GO term associations",
    ]

    if not layer2.get("skipped"):
        provenance_parts.append(f"- CellxGene Census single-cell RNA-seq (tissue: {query.get('tissue')})")
        provenance_parts.append(f"- Disease comparison: {query.get('disease')} vs normal")

    if layer3.get("available") and layer3.get("n_studies", 0) > 0:
        provenance_parts.append(f"- ARCHS4 bulk RNA-seq ({layer3.get('n_studies')} studies)")
        for study in layer3.get("studies", [])[:5]:
            provenance_parts.append(f"  - {study.get('gse')}: {study.get('study_title', 'Unknown')[:50]}")

    data_summary = json.dumps({
        "query": query,
        "layer1_knowledge": {"n_genes": layer1.get("n_genes", 0), "genes": layer1.get("sample_genes", [])},
        "layer2_singlecell": {
            "n_upregulated": layer2.get("n_upregulated", 0),
            "top_upregulated": layer2.get("top_upregulated", []),
            "cell_type_drivers": layer2.get("cell_type_drivers", []),
        },
        "layer3_validation": {
            "n_studies": layer3.get("n_studies", 0),
            "differential_expression": layer3.get("differential_expression", []),
        },
    }, indent=2)

    prompt = f"""You are a computational biology expert. Summarize this multi-layer gene expression analysis.

QUESTION: Which genes involved in {query.get('go_label', 'the biological process')} are dysregulated in {query.get('disease')}, and which cell types drive those changes?

ANALYSIS WORKFLOW:
1. Layer 1 (Knowledge Graph): Discovered genes annotated to GO term {query.get('go_term')} and its subclasses via Ubergraph + Wikidata
2. Layer 2 (Single-Cell): Analyzed expression in {query.get('tissue')} comparing "{query.get('disease')}" vs "normal" using CellxGene Census
   - TISSUE-LEVEL: A gene is "upregulated" if its max fold change > 1.5 in ANY cell type within that tissue
   - CELL-TYPE LEVEL: Individual cell populations may show different patterns (same gene can be UP in lymphocytes but DOWN in NK cells)
3. Layer 3 (Bulk Validation): Tested whether genes upregulated in single-cell (Layer 2) are also upregulated in independent bulk RNA-seq studies from ARCHS4/GEO

DATA PROVENANCE:
{chr(10).join(provenance_parts)}

RESULTS:
{data_summary}

Provide a scientific summary (3-4 paragraphs) covering:
1. Key gene expression findings - clarify tissue-level patterns vs cell-type-specific patterns
2. Cell types driving the changes - note if different cell types show opposite patterns
3. Validation results - do the single-cell findings replicate in bulk RNA-seq?
4. Biological interpretation and data sources (include GEO series IDs)
"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        print(f"  LLM summary error: {e}")
        return None


# =============================================================================
# Main Analysis Function
# =============================================================================

def run_analysis(
    go_term: str,
    disease: str,
    tissue: str,
    go_label: Optional[str] = None,
    uberon_id: Optional[str] = None,
    control_term: Optional[str] = None,
    max_genes: int = 30,
    skip_cellxgene: bool = False,
    skip_archs4: bool = False,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """
    Run the full multi-layer analysis.
    """
    # Set control term default
    if control_term is None:
        control_term = f"normal {tissue}"

    print("=" * 70)
    print("GO Term Disease Analyzer - Multi-Layer Analysis")
    print("=" * 70)
    print()
    print(f"  GO Term: {go_term}" + (f" ({go_label})" if go_label else ""))
    print(f"  Disease: {disease}")
    print(f"  Tissue: {tissue}" + (f" ({uberon_id})" if uberon_id else ""))
    print(f"  Control: {control_term}")
    print(f"  Max Genes: {max_genes}")
    print()

    result = {
        "query": {
            "go_term": go_term,
            "go_label": go_label,
            "disease": disease,
            "tissue": tissue,
            "uberon_id": uberon_id,
            "control_term": control_term,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Layer 1: Knowledge Graph
    print("-" * 70)
    print("[Layer 1] FRINK/Ubergraph: GO Term Gene Discovery")
    print("-" * 70)

    genes = get_go_genes(go_term, go_label, max_genes=max_genes * 2, use_cache=use_cache)
    genes = genes[:max_genes]
    gene_data = {g.symbol: g.go_terms for g in genes}

    result["layer1_knowledge"] = {
        "n_genes": len(genes),
        "sample_genes": [g.symbol for g in genes[:10]],
        "genes_with_go_terms": [{"symbol": g.symbol, "go_terms": g.go_terms[:3]} for g in genes[:5]],
    }

    # Update go_label if we found it
    if genes and genes[0].go_terms and not go_label:
        result["query"]["go_label"] = genes[0].go_terms[0]

    print(f"\n  Sample genes found:")
    for g in genes[:5]:
        print(f"    {g.symbol}: {', '.join(g.go_terms[:2])}")
    print()

    # Layer 2: Single-Cell Expression
    print("-" * 70)
    print("[Layer 2] CellxGene Census: Single-Cell Expression")
    print("-" * 70)

    if skip_cellxgene or not HAS_CELLXGENE:
        print("  Skipping single-cell analysis")
        result["layer2_singlecell"] = {"skipped": True}
        aggregated = {"n_genes_analyzed": 0, "top_upregulated": []}
    else:
        gene_symbols = list(gene_data.keys())
        expr_results = analyze_cellxgene_expression(
            gene_symbols, tissue, disease, uberon_id, use_cache
        )
        aggregated = aggregate_expression_results(gene_data, expr_results)

        result["layer2_singlecell"] = {
            "n_genes_analyzed": aggregated["n_genes_analyzed"],
            "n_upregulated": aggregated["n_upregulated"],
            "n_downregulated": aggregated["n_downregulated"],
            "top_upregulated": [
                {"symbol": g["symbol"], "fold_change": round(g["max_fold_change"], 2),
                 "top_cell_type": g["top_cell_type"]}
                for g in aggregated["top_upregulated"][:5]
            ],
            "cell_type_drivers": aggregated["cell_type_drivers"][:5],
        }

        print(f"\n  Results: {aggregated['n_upregulated']} upregulated, "
              f"{aggregated['n_downregulated']} downregulated")

        if aggregated["top_upregulated"]:
            print(f"\n  Top Upregulated:")
            for g in aggregated["top_upregulated"][:5]:
                print(f"    {g['symbol']}: {g['max_fold_change']:.1f}x in {g['top_cell_type']}")
    print()

    # Layer 3: ARCHS4 Validation
    print("-" * 70)
    print("[Layer 3] ARCHS4: Bulk RNA-seq Validation")
    print("-" * 70)

    if skip_archs4:
        print("  Skipping ARCHS4 validation")
        result["layer3_validation"] = {"skipped": True}
    else:
        top_genes = [g["symbol"] for g in aggregated.get("top_upregulated", [])][:10]
        if not top_genes:
            top_genes = [g.symbol for g in genes[:10]]

        validation = validate_with_archs4(top_genes, disease, control_term, use_cache=use_cache)
        result["layer3_validation"] = validation

        if validation.get("available") and validation.get("n_studies", 0) > 0:
            print(f"\n  Disease studies: {validation['n_studies']}")
            print(f"  Control samples: {validation.get('n_control_samples', 0)}")

            if validation.get("differential_expression"):
                print(f"\n  Differential Expression:")
                for de in validation["differential_expression"][:5]:
                    direction = "up" if de["fold_change"] > 1 else "down"
                    print(f"    {de['gene']}: {de['fold_change']:.1f}x {direction}")
    print()

    # LLM Summary
    print("-" * 70)
    print("[Layer 4] LLM Summary")
    print("-" * 70)
    print()

    llm_summary = generate_llm_summary(result)
    if llm_summary:
        result["llm_summary"] = llm_summary
        for line in llm_summary.split('\n'):
            print(f"  {line}")
    else:
        print("  (LLM summary not available)")
        result["llm_summary"] = None

    print()
    print("=" * 70)
    print("Analysis Complete")
    print("=" * 70)

    return result


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Analyze gene expression for a GO term in a disease context",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # ECM genes in pulmonary fibrosis
  python go_disease_analyzer.py --go-term GO:0030198 --disease "pulmonary fibrosis" --tissue lung

  # Inflammatory response in rheumatoid arthritis
  python go_disease_analyzer.py --go-term GO:0006954 --disease "rheumatoid arthritis" --tissue "synovial tissue"

  # Apoptosis in breast cancer
  python go_disease_analyzer.py --go-term GO:0006915 --disease "breast cancer" --tissue breast
        """,
    )

    # Required arguments
    parser.add_argument("--go-term", required=True, help="GO term ID (e.g., GO:0030198)")
    parser.add_argument("--disease", required=True, help="Disease name for CellxGene")
    parser.add_argument("--tissue", required=True, help="Tissue name for filtering")

    # Optional arguments
    parser.add_argument("--go-label", help="Human-readable GO term label")
    parser.add_argument("--uberon-id", help="UBERON ID for precise tissue filtering")
    parser.add_argument("--control-term", help="Search term for control samples (default: 'normal {tissue}')")
    parser.add_argument("--max-genes", type=int, default=30, help="Maximum genes to analyze")
    parser.add_argument("--output", "-o", help="Output JSON file")
    parser.add_argument("--no-cache", action="store_true", help="Disable caching")
    parser.add_argument("--skip-cellxgene", action="store_true", help="Skip single-cell analysis")
    parser.add_argument("--skip-archs4", action="store_true", help="Skip bulk validation")

    args = parser.parse_args()

    result = run_analysis(
        go_term=args.go_term,
        disease=args.disease,
        tissue=args.tissue,
        go_label=args.go_label,
        uberon_id=args.uberon_id,
        control_term=args.control_term,
        max_genes=args.max_genes,
        skip_cellxgene=args.skip_cellxgene,
        skip_archs4=args.skip_archs4,
        use_cache=not args.no_cache,
    )

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\nResults saved to: {args.output}")

        # Generate visualization
        try:
            from visualize_results import generate_visualization
            viz_output = args.output.replace(".json", "_provenance.txt")
            visualization = generate_visualization(result)
            with open(viz_output, "w") as f:
                f.write(visualization)
            print(f"Provenance visualization saved to: {viz_output}")
        except ImportError:
            print("  (Visualization not available - visualize_results.py not found)")
        except Exception as e:
            print(f"  (Visualization error: {e})")


if __name__ == "__main__":
    main()
