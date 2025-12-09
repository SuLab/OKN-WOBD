#!/usr/bin/env python3
"""
ECM Genes in Pulmonary Fibrosis - Multi-Layer Analysis Demo

This demo demonstrates how integrating knowledge graphs with expression data
enables discovery that keyword search cannot achieve.

Scientific Question:
    Which genes involved in extracellular matrix organization are dysregulated
    in pulmonary fibrosis, and which cell types drive those changes?

Three Layers:
    1. FRINK/Ubergraph → Get ECM-related genes via GO term expansion
    2. CellxGene Census → Get cell-type-resolved expression in IPF vs normal lung
       (focused on pulmonary interstitium - UBERON:0000114)
    3. ARCHS4 → Validate findings across independent bulk RNA-seq studies

Usage:
    python demo_ecm_fibrosis.py
    python demo_ecm_fibrosis.py --max-genes 20  # Faster demo with fewer genes
    python demo_ecm_fibrosis.py --skip-archs4   # Skip bulk validation layer
    python demo_ecm_fibrosis.py --no-cache      # Force fresh queries (no cache)

Caching:
    Intermediate results are cached in DATA_DIR/ecm_fibrosis_cache/ to allow
    restarts and faster re-runs. Set DATA_DIR in .env file.
"""

import os
import sys
import json
import argparse
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
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
# Configuration
# =============================================================================

# Tissue ontology configuration
TISSUE_CONFIG = {
    "pulmonary_interstitium": {
        "uberon_id": "UBERON:0000114",
        "label": "pulmonary interstitium",
        "general_tissue": "lung",
    },
    "lung": {
        "uberon_id": "UBERON:0002048",
        "label": "lung",
        "general_tissue": "lung",
    },
}

# Default tissue for this demo (lung has more data than pulmonary_interstitium in CellxGene)
DEFAULT_TISSUE = "lung"


# =============================================================================
# Caching Utilities
# =============================================================================

def get_cache_dir() -> Optional[Path]:
    """Get cache directory from DATA_DIR environment variable."""
    data_dir = os.environ.get("DATA_DIR")
    if not data_dir:
        return None
    cache_dir = Path(data_dir) / "ecm_fibrosis_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_cache_key(prefix: str, **kwargs) -> str:
    """Generate a cache key from parameters."""
    # Sort kwargs for consistent hashing
    param_str = json.dumps(kwargs, sort_keys=True)
    hash_val = hashlib.md5(param_str.encode()).hexdigest()[:12]
    return f"{prefix}_{hash_val}"


def load_from_cache(cache_key: str) -> Optional[Dict]:
    """Load data from cache if available."""
    cache_dir = get_cache_dir()
    if not cache_dir:
        return None

    cache_file = cache_dir / f"{cache_key}.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
            print(f"  [Cache] Loaded from {cache_file.name}")
            return data
        except Exception as e:
            print(f"  [Cache] Failed to load: {e}")
            return None
    return None


def save_to_cache(cache_key: str, data: Dict) -> bool:
    """Save data to cache."""
    cache_dir = get_cache_dir()
    if not cache_dir:
        return False

    cache_file = cache_dir / f"{cache_key}.json"
    try:
        with open(cache_file, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"  [Cache] Saved to {cache_file.name}")
        return True
    except Exception as e:
        print(f"  [Cache] Failed to save: {e}")
        return False


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class ECMGene:
    """A gene annotated to ECM-related GO terms."""
    symbol: str
    go_terms: List[str] = field(default_factory=list)


@dataclass
class CellTypeChange:
    """Expression change for a gene in a specific cell type."""
    cell_type: str
    mean_normal: float
    mean_disease: float
    fold_change: float
    log2_fc: float
    n_cells_normal: int
    n_cells_disease: int


@dataclass
class GeneAnalysis:
    """Complete analysis for one gene."""
    symbol: str
    go_terms: List[str]
    cell_type_changes: List[CellTypeChange]
    max_fold_change: float
    top_cell_type: str


# =============================================================================
# Layer 1: Knowledge Graph - ECM Gene Discovery
# =============================================================================

def get_ecm_genes(max_genes: int = 500, use_cache: bool = True) -> List[ECMGene]:
    """
    Query FRINK/Ubergraph for GO:0030198 (ECM organization) subclasses,
    then Wikidata for human genes annotated to those terms.

    This federated query demonstrates ontology-driven gene discovery.

    Args:
        max_genes: Maximum number of genes to return
        use_cache: Whether to use cached results if available

    Returns:
        List of ECMGene objects with symbol and GO term annotations
    """
    # Check cache first
    cache_key = get_cache_key("ecm_genes", max_genes=max_genes)
    if use_cache:
        cached = load_from_cache(cache_key)
        if cached:
            genes = [ECMGene(symbol=g["symbol"], go_terms=g["go_terms"])
                     for g in cached.get("genes", [])]
            print(f"  Found {len(genes)} genes from cache")
            return genes

    print("  Querying ubergraph for ECM-related GO terms...")

    client = SPARQLClient(timeout=120)

    # Federated query: ubergraph (ontology) -> Wikidata (genes)
    query = f'''
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX obo: <http://purl.obolibrary.org/obo/>
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>
    PREFIX wd: <http://www.wikidata.org/entity/>

    SELECT DISTINCT ?go_label ?symbol WHERE {{
      # Get ECM organization (GO:0030198) and all subclasses from ubergraph
      ?go_term rdfs:subClassOf* obo:GO_0030198 .
      ?go_term rdfs:label ?go_label .

      # Convert OBO URI to GO ID string for joining with Wikidata
      BIND(REPLACE(STR(?go_term), "http://purl.obolibrary.org/obo/GO_", "GO:") AS ?go_id)

      # Get human genes annotated to these GO terms from Wikidata
      SERVICE <https://query.wikidata.org/sparql> {{
        ?go_wd wdt:P686 ?go_id .
        ?protein wdt:P682 ?go_wd ;
                 wdt:P703 wd:Q15978631 ;
                 wdt:P702 ?gene .
        ?gene wdt:P353 ?symbol .
      }}
    }}
    LIMIT {max_genes}
    '''

    try:
        result = client.query(query, endpoint="ubergraph", include_prefixes=False)
    except Exception as e:
        print(f"  Warning: Federated query failed ({e}), trying direct Wikidata query...")
        # Fallback: query Wikidata directly for ECM-related genes
        return get_ecm_genes_fallback(max_genes, use_cache=use_cache)

    # Group results by gene symbol, collect GO terms
    gene_terms: Dict[str, List[str]] = defaultdict(list)

    for row in result.bindings:
        symbol = row.get("symbol", {}).get("value", "")
        go_label = row.get("go_label", {}).get("value", "")
        if symbol and go_label:
            if go_label not in gene_terms[symbol]:
                gene_terms[symbol].append(go_label)

    # Convert to ECMGene objects
    genes = [ECMGene(symbol=sym, go_terms=terms) for sym, terms in gene_terms.items()]

    print(f"  Found {len(genes)} unique genes annotated to ECM organization terms")

    # Save to cache
    if use_cache and genes:
        save_to_cache(cache_key, {
            "genes": [{"symbol": g.symbol, "go_terms": g.go_terms} for g in genes],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    return genes


def get_ecm_genes_fallback(max_genes: int = 100, use_cache: bool = True) -> List[ECMGene]:
    """
    Fallback: Query Wikidata directly for genes annotated to ECM GO term.
    Used when federated query fails.
    """
    print("  Using Wikidata fallback for ECM genes...")

    client = SPARQLClient(timeout=60)

    query = f'''
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>
    PREFIX wd: <http://www.wikidata.org/entity/>
    PREFIX wikibase: <http://wikiba.se/ontology#>
    PREFIX bd: <http://www.bigdata.com/rdf#>

    SELECT DISTINCT ?symbol WHERE {{
      ?go_term wdt:P686 "GO:0030198" .
      ?protein wdt:P682 ?go_term ;
               wdt:P703 wd:Q15978631 ;
               wdt:P702 ?gene .
      ?gene wdt:P353 ?symbol .
    }}
    LIMIT {max_genes}
    '''

    result = client.query(query, endpoint="wikidata", include_prefixes=False)

    genes = []
    for row in result.bindings:
        symbol = row.get("symbol", {}).get("value", "")
        if symbol:
            genes.append(ECMGene(symbol=symbol, go_terms=["extracellular matrix organization"]))

    print(f"  Found {len(genes)} genes via Wikidata fallback")

    # Save to cache (using fallback key)
    if use_cache and genes:
        cache_key = get_cache_key("ecm_genes_fallback", max_genes=max_genes)
        save_to_cache(cache_key, {
            "genes": [{"symbol": g.symbol, "go_terms": g.go_terms} for g in genes],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    return genes


# =============================================================================
# Layer 2: Single-Cell Expression Analysis
# =============================================================================

def analyze_cellxgene_expression(
    genes: List[str],
    tissue_config: str = DEFAULT_TISSUE,
    condition_a: str = "normal",
    condition_b: str = "pulmonary fibrosis",
    use_cache: bool = True,
) -> Dict[str, Dict]:
    """
    For each gene, compare expression in disease vs normal using CellxGene Census.
    Returns cell-type-level fold changes.

    Supports incremental caching - each gene result is cached separately,
    allowing restart of interrupted analyses.

    Args:
        genes: List of gene symbols to analyze
        tissue_config: Key from TISSUE_CONFIG dict (e.g., "pulmonary_interstitium")
        condition_a: Control condition
        condition_b: Disease condition
        use_cache: Whether to use/save cached results

    Returns:
        Dict mapping gene symbol -> cell type comparison data
    """
    if not HAS_CELLXGENE:
        print("  Warning: CellxGene Census not available (install cellxgene-census)")
        return {}

    # Get tissue configuration
    tissue_info = TISSUE_CONFIG.get(tissue_config, TISSUE_CONFIG["lung"])
    uberon_id = tissue_info["uberon_id"]
    tissue_label = tissue_info["label"]
    general_tissue = tissue_info["general_tissue"]

    print(f"  Tissue filter: {tissue_label} ({uberon_id})")

    # Check for complete cached analysis
    analysis_cache_key = get_cache_key(
        "cellxgene_analysis",
        genes=sorted(genes),
        tissue=tissue_config,
        condition_a=condition_a,
        condition_b=condition_b,
    )

    if use_cache:
        cached_analysis = load_from_cache(analysis_cache_key)
        if cached_analysis and cached_analysis.get("complete"):
            print(f"  Found complete cached analysis")
            return cached_analysis.get("results", {})

    results = {}
    n_analyzed = 0
    n_cached = 0
    n_errors = 0

    # Load any per-gene cached results
    gene_cache_prefix = get_cache_key(
        "gene_expr",
        tissue=tissue_config,
        condition_a=condition_a,
        condition_b=condition_b,
    )

    if use_cache:
        for gene in genes:
            gene_cache_key = f"{gene_cache_prefix}_{gene}"
            cached_gene = load_from_cache(gene_cache_key)
            if cached_gene:
                results[gene] = cached_gene.get("data", {})
                n_cached += 1

        if n_cached > 0:
            print(f"  Loaded {n_cached} genes from cache")

    # Determine which genes still need analysis
    genes_to_analyze = [g for g in genes if g not in results]

    if not genes_to_analyze:
        print(f"  All {len(genes)} genes already cached")
        return results

    print(f"  Analyzing {len(genes_to_analyze)} genes (skipping {n_cached} cached)...")

    with CellxGeneClient() as client:
        for i, gene in enumerate(genes_to_analyze):
            try:
                # Get cell-type-level comparison using specific UBERON tissue ontology
                # This filters to specific tissue (e.g., pulmonary interstitium)
                # rather than all lung cells, dramatically reducing data volume
                ct_comparison = client.get_cell_type_comparison(
                    gene_symbol=gene,
                    tissue_ontology_term_id=uberon_id,  # Specific UBERON filter
                    condition_a=condition_a,
                    condition_b=condition_b,
                )

                if ct_comparison:
                    results[gene] = ct_comparison
                    n_analyzed += 1

                    # Cache this gene's result immediately (incremental caching)
                    if use_cache:
                        gene_cache_key = f"{gene_cache_prefix}_{gene}"
                        save_to_cache(gene_cache_key, {
                            "gene": gene,
                            "data": ct_comparison,
                            "tissue": tissue_config,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })

                # Progress indicator
                if (i + 1) % 5 == 0:
                    print(f"    Analyzed {i + 1}/{len(genes_to_analyze)} genes...")

            except Exception as e:
                n_errors += 1
                print(f"    Error analyzing {gene}: {e}")
                continue

    print(f"  Successfully analyzed {n_analyzed} new genes ({n_errors} errors)")
    print(f"  Total genes with data: {len(results)}")

    # Save complete analysis
    if use_cache and len(results) == len(genes):
        save_to_cache(analysis_cache_key, {
            "complete": True,
            "results": results,
            "n_genes": len(genes),
            "tissue": tissue_config,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    return results


def aggregate_expression_results(
    gene_data: Dict[str, List[str]],  # gene -> go_terms
    expression_results: Dict[str, Dict],
    fold_change_threshold: float = 1.5,
) -> Dict[str, Any]:
    """
    Aggregate single-cell expression results.

    Returns:
        Dict with:
        - top_dysregulated: genes with highest fold changes
        - cell_type_drivers: cell types with most dysregulated genes
        - summary statistics
    """
    gene_summaries = []

    for gene, go_terms in gene_data.items():
        if gene not in expression_results:
            continue

        ct_data = expression_results[gene]
        if not ct_data:
            continue

        # Find max fold change and top cell type
        max_fc = 0
        top_ct = None
        cell_type_changes = []

        for ct, data in ct_data.items():
            fc = data.get("fold_change", 1.0)
            if abs(fc - 1.0) > abs(max_fc - 1.0):  # Further from 1.0
                max_fc = fc
                top_ct = ct

            cell_type_changes.append({
                "cell_type": ct,
                "fold_change": fc,
                "mean_normal": data.get("mean_normal", 0),
                "mean_disease": data.get("mean_disease", 0),
                "n_cells_normal": data.get("n_cells_normal", 0),
                "n_cells_disease": data.get("n_cells_disease", 0),
            })

        gene_summaries.append({
            "symbol": gene,
            "go_terms": go_terms,
            "max_fold_change": max_fc,
            "top_cell_type": top_ct,
            "cell_type_changes": cell_type_changes,
        })

    # Sort by max fold change (most upregulated first)
    gene_summaries.sort(key=lambda x: x["max_fold_change"], reverse=True)

    # Identify dysregulated genes
    dysregulated = [g for g in gene_summaries if g["max_fold_change"] >= fold_change_threshold]
    downregulated = [g for g in gene_summaries if g["max_fold_change"] <= 1/fold_change_threshold]

    # Aggregate by cell type
    cell_type_counts = defaultdict(lambda: {"upregulated": 0, "downregulated": 0, "genes": []})
    for g in gene_summaries:
        if g["top_cell_type"]:
            ct = g["top_cell_type"]
            if g["max_fold_change"] >= fold_change_threshold:
                cell_type_counts[ct]["upregulated"] += 1
            elif g["max_fold_change"] <= 1/fold_change_threshold:
                cell_type_counts[ct]["downregulated"] += 1
            cell_type_counts[ct]["genes"].append(g["symbol"])

    # Convert to sorted list
    cell_type_drivers = [
        {
            "cell_type": ct,
            "n_upregulated": data["upregulated"],
            "n_downregulated": data["downregulated"],
            "genes": data["genes"][:5],  # Top 5 genes
        }
        for ct, data in cell_type_counts.items()
    ]
    cell_type_drivers.sort(key=lambda x: x["n_upregulated"], reverse=True)

    return {
        "n_genes_analyzed": len(gene_summaries),
        "n_upregulated": len(dysregulated),
        "n_downregulated": len(downregulated),
        "top_upregulated": dysregulated[:10],
        "top_downregulated": downregulated[:10],
        "cell_type_drivers": cell_type_drivers[:10],
        "all_genes": gene_summaries,
    }


# =============================================================================
# Layer 3: ARCHS4 Bulk RNA-seq Validation
# =============================================================================

def validate_with_archs4(
    genes: List[str],
    search_term: str = "pulmonary fibrosis",
    control_search_term: str = "normal lung",
    max_studies: int = 10,
    max_control_samples: int = 100,
) -> Dict[str, Any]:
    """
    Validate findings in independent bulk RNA-seq studies from ARCHS4.

    Includes:
    - Study metadata (titles, sample descriptions)
    - Control sample comparison for differential expression
    - Gene-level statistics

    Args:
        genes: List of gene symbols to validate
        search_term: Search term to find disease studies
        control_search_term: Search term to find control samples
        max_studies: Maximum number of disease studies to analyze
        max_control_samples: Maximum control samples to use

    Returns:
        Dict with validation summary including differential expression
    """
    if not HAS_ARCHS4:
        print("  Warning: ARCHS4 not available (install archs4py or set ARCHS4_DATA_DIR)")
        return {"available": False, "reason": "ARCHS4 not installed"}

    # Check for data directory
    data_dir = os.environ.get("ARCHS4_DATA_DIR")
    if not data_dir:
        print("  Warning: ARCHS4_DATA_DIR not set in environment")
        return {"available": False, "reason": "ARCHS4_DATA_DIR not configured"}

    try:
        client = ARCHS4Client(data_dir=data_dir)
    except Exception as e:
        print(f"  Warning: Could not initialize ARCHS4 client: {e}")
        return {"available": False, "reason": str(e)}

    print(f"  Searching ARCHS4 for '{search_term}' studies...")

    try:
        # Search for disease studies
        disease_metadata = client.search_metadata(search_term)

        if disease_metadata.empty:
            return {
                "available": True,
                "n_studies": 0,
                "reason": f"No studies found for '{search_term}'"
            }

        # Extract unique series IDs from series_id column
        gse_series = disease_metadata["series_id"].str.split(',').explode().str.strip().dropna()
        gse_ids = [gse for gse in gse_series.unique() if gse.startswith("GSE")][:max_studies]

        print(f"  Found {len(gse_ids)} relevant studies with {len(disease_metadata)} disease samples")

        # Search for control samples
        print(f"  Searching for control samples ('{control_search_term}')...")
        control_metadata = client.search_metadata(control_search_term)

        # Filter out samples that are also in disease set (avoid overlap)
        if not control_metadata.empty:
            disease_samples = set(disease_metadata["geo_accession"])
            control_metadata = control_metadata[
                ~control_metadata["geo_accession"].isin(disease_samples)
            ]

        n_control_samples = len(control_metadata) if not control_metadata.empty else 0
        print(f"  Found {n_control_samples} control samples")

        # Get control expression data
        control_expr = None
        control_sample_info = []
        if n_control_samples > 0:
            control_samples = list(control_metadata["geo_accession"].head(max_control_samples))
            control_expr = client.get_expression_by_samples(control_samples, genes=genes)

            # Collect control sample metadata
            for _, row in control_metadata.head(max_control_samples).iterrows():
                control_sample_info.append({
                    "gsm": row["geo_accession"],
                    "series": row["series_id"].split(',')[0] if row["series_id"] else "unknown",
                    "title": row["title"][:100] if row["title"] else "N/A",
                    "source": row["source_name_ch1"][:80] if row["source_name_ch1"] else "N/A",
                })

        # Process each disease study
        study_results = []
        all_disease_expr = []

        for gse in gse_ids:
            try:
                # Get samples for this series from our metadata
                series_mask = disease_metadata["series_id"].str.contains(gse, na=False)
                series_data = disease_metadata.loc[series_mask]
                series_samples = list(series_data["geo_accession"])

                if not series_samples:
                    continue

                # Get expression by sample IDs
                expr = client.get_expression_by_samples(series_samples, genes=genes)
                if expr is None or expr.empty:
                    continue

                genes_found = [g for g in genes if g in expr.index]
                n_samples = len(expr.columns)

                # Collect sample metadata for this study
                sample_info = []
                sample_titles = []
                for _, row in series_data.iterrows():
                    title = row["title"][:100] if row["title"] else "N/A"
                    sample_titles.append(title)
                    sample_info.append({
                        "gsm": row["geo_accession"],
                        "title": title,
                        "source": row["source_name_ch1"][:80] if row["source_name_ch1"] else "N/A",
                    })

                # Infer study title from sample titles (common prefix or first title)
                study_title = _infer_study_title(sample_titles)

                # Calculate mean expression for detected genes
                mean_expr = {}
                for gene in genes_found:
                    mean_expr[gene] = float(expr.loc[gene].mean())
                    all_disease_expr.append((gene, float(expr.loc[gene].mean())))

                study_results.append({
                    "gse": gse,
                    "study_title": study_title,
                    "n_samples": n_samples,
                    "n_genes_detected": len(genes_found),
                    "genes_detected": genes_found,
                    "mean_expression": mean_expr,
                    "sample_info": sample_info[:5],  # First 5 samples as examples
                })

            except Exception as e:
                continue

        # Calculate differential expression if we have control data
        differential_expression = []
        if control_expr is not None and not control_expr.empty and study_results:
            print("  Calculating differential expression vs controls...")

            # Aggregate disease expression across all studies
            for gene in genes:
                disease_values = []
                control_values = []

                # Get disease values from all studies
                for study in study_results:
                    if gene in study["mean_expression"]:
                        disease_values.append(study["mean_expression"][gene])

                # Get control values
                if gene in control_expr.index:
                    control_values = control_expr.loc[gene].tolist()

                if disease_values and control_values:
                    mean_disease = sum(disease_values) / len(disease_values)
                    mean_control = sum(control_values) / len(control_values)

                    # Calculate fold change with pseudo-count
                    pseudo_count = 1.0  # Use 1 for count data
                    fold_change = (mean_disease + pseudo_count) / (mean_control + pseudo_count)
                    log2_fc = np.log2(fold_change) if HAS_NUMPY else 0

                    differential_expression.append({
                        "gene": gene,
                        "mean_disease": round(mean_disease, 2),
                        "mean_control": round(mean_control, 2),
                        "fold_change": round(fold_change, 2),
                        "log2_fc": round(log2_fc, 2) if HAS_NUMPY else None,
                        "n_disease_studies": len(disease_values),
                        "n_control_samples": len(control_values),
                    })

            # Sort by fold change
            differential_expression.sort(key=lambda x: x["fold_change"], reverse=True)

        # Calculate concordance
        if study_results:
            all_detected = set()
            for s in study_results:
                all_detected.update(s["genes_detected"])
            concordance = len(all_detected) / len(genes) if genes else 0
        else:
            concordance = 0

        return {
            "available": True,
            "n_studies": len(study_results),
            "n_disease_samples": len(disease_metadata),
            "n_control_samples": n_control_samples,
            "studies": study_results,
            "control_samples": control_sample_info[:10],  # First 10 as examples
            "differential_expression": differential_expression,
            "genes_queried": genes,
            "concordance": concordance,
        }

    except Exception as e:
        import traceback
        print(f"  Error querying ARCHS4: {e}")
        traceback.print_exc()
        return {"available": False, "reason": str(e)}


def _infer_study_title(sample_titles: List[str]) -> str:
    """Infer a study title from sample titles by finding common patterns."""
    if not sample_titles:
        return "Unknown study"

    # If all titles share a common prefix, use that
    if len(sample_titles) == 1:
        return sample_titles[0]

    # Find common prefix
    prefix = sample_titles[0]
    for title in sample_titles[1:]:
        while prefix and not title.startswith(prefix):
            prefix = prefix[:-1]

    if len(prefix) > 10:
        return prefix.rstrip(" -_:")

    # Otherwise, return first title
    return sample_titles[0]


# =============================================================================
# LLM Summary Generation
# =============================================================================

def generate_llm_summary(result: Dict[str, Any]) -> Optional[str]:
    """
    Generate a natural language summary of the analysis results using Claude.

    Includes provenance information for all data sources.

    Args:
        result: The complete analysis result dictionary

    Returns:
        Natural language summary string, or None if LLM not available
    """
    if not HAS_ANTHROPIC:
        print("  Warning: anthropic package not installed, skipping LLM summary")
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  Warning: ANTHROPIC_API_KEY not set, skipping LLM summary")
        return None

    # Build the prompt with all the data
    query = result.get("query", {})
    layer1 = result.get("layer1_knowledge", {})
    layer2 = result.get("layer2_singlecell", {})
    layer3 = result.get("layer3_validation", {})

    # Build provenance section
    provenance_parts = []

    # Knowledge graph provenance
    provenance_parts.append(f"- Gene Ontology term {query.get('go_term', 'GO:0030198')} ({query.get('go_label', 'extracellular matrix organization')})")
    provenance_parts.append("- FRINK/Ubergraph federated SPARQL query (ubergraph.apps.renci.org)")
    provenance_parts.append("- Wikidata gene-GO term associations")

    # Single-cell provenance
    if not layer2.get("skipped"):
        provenance_parts.append(f"- CellxGene Census single-cell RNA-seq data (tissue: {query.get('tissue_uberon', 'UBERON:0002048')})")
        provenance_parts.append(f"- Disease comparison: {query.get('disease', 'pulmonary fibrosis')} vs normal")

    # ARCHS4 provenance
    if layer3.get("available") and layer3.get("n_studies", 0) > 0:
        provenance_parts.append(f"- ARCHS4 bulk RNA-seq ({layer3.get('n_studies', 0)} studies, {layer3.get('n_disease_samples', 0)} disease samples)")
        for study in layer3.get("studies", [])[:5]:
            provenance_parts.append(f"  - {study.get('gse', 'Unknown')}: {study.get('study_title', 'Unknown study')[:60]} ({study.get('n_samples', 0)} samples)")
        if layer3.get("n_control_samples", 0) > 0:
            provenance_parts.append(f"- Normal lung controls ({layer3.get('n_control_samples', 0)} samples)")

    provenance_text = "\n".join(provenance_parts)

    # Build data summary for the prompt
    data_summary = json.dumps({
        "query": query,
        "layer1_knowledge": {
            "n_genes": layer1.get("n_genes", 0),
            "genes": layer1.get("sample_genes", []),
        },
        "layer2_singlecell": {
            "n_upregulated": layer2.get("n_upregulated", 0),
            "n_downregulated": layer2.get("n_downregulated", 0),
            "top_upregulated": layer2.get("top_upregulated", []),
            "cell_type_drivers": layer2.get("cell_type_drivers", []),
        },
        "layer3_validation": {
            "n_studies": layer3.get("n_studies", 0),
            "studies": [
                {"gse": s.get("gse"), "title": s.get("study_title"), "n_samples": s.get("n_samples")}
                for s in layer3.get("studies", [])[:5]
            ],
            "differential_expression": layer3.get("differential_expression", []),
        },
    }, indent=2)

    prompt = f"""You are a computational biology expert summarizing results from a multi-layer gene expression analysis.

ANALYSIS QUESTION:
Which genes involved in extracellular matrix (ECM) organization are dysregulated in pulmonary fibrosis, and which cell types drive those changes?

DATA PROVENANCE:
{provenance_text}

ANALYSIS RESULTS:
{data_summary}

Please provide a comprehensive scientific summary that:
1. Describes the key findings from each layer of analysis
2. Highlights the most significant genes and their expression patterns
3. Discusses which cell types show the strongest ECM dysregulation
4. Notes any concordance or discordance between single-cell and bulk RNA-seq findings
5. Provides biological context for the findings (what these genes do, why the cell types matter)
6. Includes a "Data Sources" section listing all GEO series IDs used with their study descriptions

Write the summary in a clear, scientific style suitable for a research report. Use 3-4 paragraphs plus the data sources section.
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
        print(f"  Error generating LLM summary: {e}")
        return None


# =============================================================================
# Main Demo Function
# =============================================================================

def run_ecm_fibrosis_demo(
    max_genes: int = 50,
    skip_cellxgene: bool = False,
    skip_archs4: bool = False,
    tissue: str = DEFAULT_TISSUE,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """
    Main entry point demonstrating three-layer integration.

    Args:
        max_genes: Maximum genes to analyze (for faster demo)
        skip_cellxgene: Skip single-cell analysis layer
        skip_archs4: Skip bulk validation layer
        tissue: Tissue configuration key (e.g., "pulmonary_interstitium", "lung")
        use_cache: Whether to use file-based caching

    Returns:
        Complete analysis result as dictionary
    """
    # Get tissue info
    tissue_info = TISSUE_CONFIG.get(tissue, TISSUE_CONFIG[DEFAULT_TISSUE])

    print("=" * 70)
    print("ECM Genes in Pulmonary Fibrosis - Multi-Layer Analysis")
    print("=" * 70)
    print()
    print("Scientific Question:")
    print("  Which genes involved in extracellular matrix organization are")
    print("  dysregulated in pulmonary fibrosis, and which cell types drive")
    print("  those changes?")
    print()
    print(f"Tissue Focus: {tissue_info['label']} ({tissue_info['uberon_id']})")
    print(f"Caching: {'Enabled' if use_cache else 'Disabled'}")
    if use_cache:
        cache_dir = get_cache_dir()
        if cache_dir:
            print(f"Cache Dir: {cache_dir}")
        else:
            print("Cache Dir: Not configured (set DATA_DIR in .env)")
    print()

    result = {
        "query": {
            "go_term": "GO:0030198",
            "go_label": "extracellular matrix organization",
            "tissue": tissue_info["label"],
            "tissue_uberon": tissue_info["uberon_id"],
            "disease": "pulmonary fibrosis",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # =========================================================================
    # Layer 1: Knowledge Graph
    # =========================================================================
    print("-" * 70)
    print("[Layer 1] FRINK/Ubergraph: ECM Gene Discovery via Ontology")
    print("-" * 70)

    ecm_genes = get_ecm_genes(max_genes=max_genes * 2, use_cache=use_cache)  # Get extra, some may fail
    ecm_genes = ecm_genes[:max_genes]

    gene_data = {g.symbol: g.go_terms for g in ecm_genes}

    result["layer1_knowledge"] = {
        "n_genes": len(ecm_genes),
        "sample_genes": [g.symbol for g in ecm_genes[:10]],
        "genes_with_go_terms": [
            {"symbol": g.symbol, "go_terms": g.go_terms[:3]}
            for g in ecm_genes[:5]
        ],
    }

    print(f"\n  Sample ECM genes found:")
    for g in ecm_genes[:5]:
        terms_str = ", ".join(g.go_terms[:2])
        if len(g.go_terms) > 2:
            terms_str += f" (+{len(g.go_terms) - 2} more)"
        print(f"    {g.symbol}: {terms_str}")

    print()

    # =========================================================================
    # Layer 2: Single-Cell Expression
    # =========================================================================
    print("-" * 70)
    print("[Layer 2] CellxGene Census: Single-Cell Expression in IPF vs Normal")
    print("-" * 70)

    if skip_cellxgene or not HAS_CELLXGENE:
        if not HAS_CELLXGENE:
            print("  Skipping: cellxgene-census not installed")
        else:
            print("  Skipping: --skip-cellxgene flag set")
        result["layer2_singlecell"] = {"skipped": True}
        expression_results = {}
        aggregated = {"n_genes_analyzed": 0, "top_upregulated": []}
    else:
        gene_symbols = list(gene_data.keys())
        print(f"  Analyzing {len(gene_symbols)} genes in {tissue_info['label']}...")
        print(f"  Comparing: normal vs pulmonary fibrosis")
        print()

        expression_results = analyze_cellxgene_expression(
            gene_symbols,
            tissue_config=tissue,
            use_cache=use_cache,
        )
        aggregated = aggregate_expression_results(gene_data, expression_results)

        result["layer2_singlecell"] = {
            "n_genes_analyzed": aggregated["n_genes_analyzed"],
            "n_upregulated": aggregated["n_upregulated"],
            "n_downregulated": aggregated["n_downregulated"],
            "top_upregulated": [
                {
                    "symbol": g["symbol"],
                    "fold_change": round(g["max_fold_change"], 2),
                    "top_cell_type": g["top_cell_type"],
                }
                for g in aggregated["top_upregulated"][:5]
            ],
            "cell_type_drivers": aggregated["cell_type_drivers"][:5],
        }

        print(f"\n  Results Summary:")
        print(f"    Genes analyzed: {aggregated['n_genes_analyzed']}")
        print(f"    Upregulated (>1.5x): {aggregated['n_upregulated']}")
        print(f"    Downregulated (<0.67x): {aggregated['n_downregulated']}")

        if aggregated["top_upregulated"]:
            print(f"\n  Top Upregulated Genes:")
            for g in aggregated["top_upregulated"][:5]:
                print(f"    {g['symbol']}: {g['max_fold_change']:.1f}x in {g['top_cell_type']}")

        if aggregated["cell_type_drivers"]:
            print(f"\n  Cell Types Driving ECM Changes:")
            for ct in aggregated["cell_type_drivers"][:5]:
                print(f"    {ct['cell_type']}: {ct['n_upregulated']} genes upregulated")

    print()

    # =========================================================================
    # Layer 3: ARCHS4 Bulk Validation
    # =========================================================================
    print("-" * 70)
    print("[Layer 3] ARCHS4: Bulk RNA-seq Validation")
    print("-" * 70)

    if skip_archs4:
        print("  Skipping: --skip-archs4 flag set")
        result["layer3_validation"] = {"skipped": True}
    else:
        # Get top genes to validate
        top_genes = [g["symbol"] for g in aggregated.get("top_upregulated", [])][:10]

        if not top_genes:
            # Use original ECM genes if no expression data
            top_genes = [g.symbol for g in ecm_genes[:10]]

        validation = validate_with_archs4(top_genes)
        result["layer3_validation"] = validation

        if validation.get("available") and validation.get("n_studies", 0) > 0:
            print(f"\n  Validation Results:")
            print(f"    Disease studies: {validation['n_studies']}")
            print(f"    Disease samples: {validation.get('n_disease_samples', 'N/A')}")
            print(f"    Control samples: {validation.get('n_control_samples', 0)}")
            print(f"    Gene detection rate: {validation['concordance']:.0%}")

            if validation.get("studies"):
                print(f"\n  Disease Studies (with metadata):")
                for study in validation["studies"][:5]:
                    title = study.get('study_title', 'Unknown')[:50]
                    print(f"    {study['gse']}: {title}...")
                    print(f"      {study['n_samples']} samples, "
                          f"{study['n_genes_detected']}/{len(top_genes)} genes detected")

            # Show differential expression results
            if validation.get("differential_expression"):
                print(f"\n  Differential Expression (Disease vs Normal Lung):")
                for de in validation["differential_expression"][:5]:
                    direction = "↑" if de["fold_change"] > 1 else "↓"
                    print(f"    {de['gene']}: {de['fold_change']:.1f}x {direction} "
                          f"(disease={de['mean_disease']:.0f}, control={de['mean_control']:.0f})")
        else:
            reason = validation.get("reason", "Unknown error")
            print(f"  Validation not available: {reason}")

    print()

    # =========================================================================
    # LLM Summary
    # =========================================================================
    print("-" * 70)
    print("[Layer 4] LLM-Generated Summary")
    print("-" * 70)
    print()
    print("  Generating comprehensive summary with provenance...")

    llm_summary = generate_llm_summary(result)
    if llm_summary:
        result["llm_summary"] = llm_summary
        print()
        # Print with word wrapping
        for line in llm_summary.split('\n'):
            # Indent each line
            print(f"  {line}")
    else:
        print("  (LLM summary not available)")
        result["llm_summary"] = None

    print()

    # =========================================================================
    # Summary
    # =========================================================================
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print()
    print(f"  Starting Point: GO:0030198 (extracellular matrix organization)")
    print(f"  ECM Genes Found: {len(ecm_genes)}")

    if aggregated.get("n_upregulated", 0) > 0:
        print(f"  Dysregulated in IPF: {aggregated['n_upregulated']} upregulated, "
              f"{aggregated['n_downregulated']} downregulated")

        if aggregated.get("top_upregulated"):
            top = aggregated["top_upregulated"][0]
            print(f"  Top Finding: {top['symbol']} ({top['max_fold_change']:.1f}x in {top['top_cell_type']})")

    print()
    print("  This analysis demonstrates how ontology-driven gene discovery")
    print("  combined with expression data reveals biological insights that")
    print("  simple keyword search cannot achieve.")
    print()

    return result


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="ECM Genes in Pulmonary Fibrosis - Multi-Layer Analysis Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Tissue Options:
  pulmonary_interstitium  Focus on UBERON:0000114 (default, more specific)
  lung                    Full lung tissue UBERON:0002048

Caching:
  Results are cached in DATA_DIR/ecm_fibrosis_cache/ (set DATA_DIR in .env)
  Per-gene results are cached incrementally, allowing restart of interrupted runs.

Examples:
  python demo_ecm_fibrosis.py                        # Default: pulmonary interstitium
  python demo_ecm_fibrosis.py --tissue lung          # Full lung tissue
  python demo_ecm_fibrosis.py --no-cache             # Force fresh queries
  python demo_ecm_fibrosis.py --max-genes 10         # Quick test with 10 genes
        """,
    )
    parser.add_argument(
        "--max-genes",
        type=int,
        default=30,
        help="Maximum genes to analyze (default: 30, for faster demo)",
    )
    parser.add_argument(
        "--tissue",
        type=str,
        default=DEFAULT_TISSUE,
        choices=list(TISSUE_CONFIG.keys()),
        help=f"Tissue to analyze (default: {DEFAULT_TISSUE})",
    )
    parser.add_argument(
        "--skip-cellxgene",
        action="store_true",
        help="Skip CellxGene Census single-cell analysis",
    )
    parser.add_argument(
        "--skip-archs4",
        action="store_true",
        help="Skip ARCHS4 bulk RNA-seq validation",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable caching (force fresh queries)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Save results to JSON file",
    )

    args = parser.parse_args()

    result = run_ecm_fibrosis_demo(
        max_genes=args.max_genes,
        skip_cellxgene=args.skip_cellxgene,
        skip_archs4=args.skip_archs4,
        tissue=args.tissue,
        use_cache=not args.no_cache,
    )

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
