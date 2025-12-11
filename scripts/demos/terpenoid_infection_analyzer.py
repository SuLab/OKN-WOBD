#!/usr/bin/env python3
"""
Terpenoid Infection Analyzer - Host Response Analysis Tool

This tool analyzes how terpenoid/isoprenoid metabolism genes respond to
infection-related conditions. Since microbial gene expression data is limited
in available databases, this tool focuses on HOST response genes.

WHAT QUESTIONS CAN THIS TOOL ANSWER?
=====================================

This tool answers questions of the form:

    "Which host genes involved in terpenoid metabolism are dysregulated
     during infection, and which cell types drive those changes?"

The terpenoid pathway is relevant to host-pathogen interactions because:
- Cholesterol (sterol) metabolism affects viral entry and replication
- Isoprenoid intermediates are required for protein prenylation in immune signaling
- Many microbial pathogens produce terpene-derived virulence factors

INPUT PARAMETERS
================

Required:
  --condition         Disease/condition (e.g., "COVID-19", "cytomegalovirus infection")
  --tissue            Tissue for analysis (e.g., "lung", "blood")

Optional:
  --go-term           GO term ID (default: GO:0006721 for terpenoid metabolic process)
  --max-genes         Maximum genes to analyze (default: 30)
  --output, -o        Output JSON file path
  --no-cache          Disable caching
  --skip-cellxgene    Skip single-cell analysis
  --skip-archs4       Skip bulk RNA-seq validation
  --skip-spoke        Skip SPOKE-OKN disease associations

OUTPUT
======

The tool produces:
1. Console output with formatted results
2. JSON file (if --output specified) containing:
   - query: Input parameters
   - layer1_knowledge: Genes from terpenoid metabolism pathways
   - layer2_singlecell: Cell-type-specific expression changes
   - layer3_validation: Bulk RNA-seq validation
   - layer4_spoke: Disease associations from SPOKE-OKN
   - llm_summary: Natural language summary

USAGE EXAMPLES
==============

# Terpenoid genes in COVID-19 lung
python terpenoid_infection_analyzer.py \\
    --condition "COVID-19" \\
    --tissue lung \\
    --output terpenoid_covid.json

# Cholesterol metabolism in CMV infection (blood)
python terpenoid_infection_analyzer.py \\
    --condition "cytomegalovirus infection" \\
    --tissue blood \\
    --go-term GO:0008203 \\
    --output cholesterol_cmv.json

AVAILABLE CONDITIONS IN CellxGene (infection-related):
- COVID-19 (5.2M cells)
- cytomegalovirus infection (7.9M cells)
- HIV infectious disease (1.8K cells)
- influenza (34K cells)
- pneumonia (32K cells)

TERPENOID-RELATED GO TERMS:
- GO:0006721 - terpenoid metabolic process (141 subclasses)
- GO:0016114 - terpenoid biosynthetic process (50 subclasses)
- GO:0008203 - cholesterol metabolic process
- GO:0008299 - isoprenoid biosynthetic process
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
from concurrent.futures import ThreadPoolExecutor, as_completed

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
# Constants
# =============================================================================

# Default GO term for terpenoid metabolic process
DEFAULT_GO_TERM = "GO:0006721"
DEFAULT_GO_LABEL = "terpenoid metabolic process"

# SPARQL endpoints
UBERGRAPH_ENDPOINT = "https://ubergraph.apps.renci.org/sparql"
WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
SPOKE_OKN_ENDPOINT = "https://frink.apps.renci.org/spoke-okn/sparql"
NDE_ENDPOINT = "https://frink.apps.renci.org/nde/sparql"

# Key terpenoid pathway genes to always include (human)
CORE_TERPENOID_GENES = [
    # Mevalonate pathway (cytosolic)
    "HMGCR",    # HMG-CoA reductase - rate-limiting enzyme
    "HMGCS1",   # HMG-CoA synthase 1
    "MVK",      # Mevalonate kinase
    "PMVK",     # Phosphomevalonate kinase
    "MVD",      # Mevalonate diphosphate decarboxylase
    "IDI1",     # Isopentenyl-diphosphate isomerase 1
    "FDPS",     # Farnesyl diphosphate synthase
    "GGPS1",    # Geranylgeranyl diphosphate synthase
    # Cholesterol synthesis
    "SQLE",     # Squalene epoxidase
    "LSS",      # Lanosterol synthase
    "DHCR7",    # 7-dehydrocholesterol reductase
    "DHCR24",   # 24-dehydrocholesterol reductase
    # Protein prenylation
    "FNTA",     # Farnesyltransferase alpha
    "FNTB",     # Farnesyltransferase beta
    "PGGT1B",   # Geranylgeranyltransferase type I beta
    # Cholesterol efflux/transport
    "ABCA1",    # ATP-binding cassette A1
    "ABCG1",    # ATP-binding cassette G1
    "NPC1",     # Niemann-Pick C1
    "NPC2",     # Niemann-Pick C2
    # Regulators
    "SREBF1",   # Sterol regulatory element binding factor 1
    "SREBF2",   # Sterol regulatory element binding factor 2
    "INSIG1",   # Insulin induced gene 1
]


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class TerpenoidGene:
    """A gene associated with terpenoid metabolism."""
    symbol: str
    go_terms: List[str] = field(default_factory=list)
    pathway: str = "terpenoid metabolism"


# =============================================================================
# Caching Utilities
# =============================================================================

def get_cache_dir(subdir: str = "terpenoid_cache") -> Optional[Path]:
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
# Layer 1: Knowledge Graph - Terpenoid Gene Discovery
# =============================================================================

def get_terpenoid_genes(
    go_term: str = DEFAULT_GO_TERM,
    go_label: Optional[str] = None,
    max_genes: int = 50,
    use_cache: bool = True,
) -> List[TerpenoidGene]:
    """
    Query Ubergraph for GO term subclasses, then Wikidata for gene annotations.
    Also includes core terpenoid pathway genes.
    """
    cache_dir = get_cache_dir()
    cache_key = get_cache_key({"go_term": go_term, "max_genes": max_genes})
    cache_file = cache_dir / f"terpenoid_genes_{cache_key}.json" if cache_dir else None

    # Try cache first
    if use_cache and cache_file:
        cached = load_from_cache(cache_file)
        if cached:
            print(f"  [Cache] Loaded from {cache_file.name}")
            genes = [TerpenoidGene(symbol=g["symbol"], go_terms=g["go_terms"], pathway=g.get("pathway", "terpenoid"))
                     for g in cached["genes"]]
            return genes[:max_genes]

    # Convert GO term format for Ubergraph
    go_id_numeric = go_term.replace("GO:", "GO_")

    # Step 1: Get GO term subclasses from Ubergraph
    ubergraph_query = f'''
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX obo: <http://purl.obolibrary.org/obo/>

    SELECT DISTINCT ?go_id ?go_label WHERE {{
      ?go_term rdfs:subClassOf* obo:{go_id_numeric} .
      ?go_term rdfs:label ?go_label .
      BIND(REPLACE(STR(?go_term), "http://purl.obolibrary.org/obo/GO_", "GO:") AS ?go_id)
    }}
    LIMIT 300
    '''

    print(f"  Querying Ubergraph for GO term subclasses of {go_term}...")

    ubergraph_client = SPARQLClient(UBERGRAPH_ENDPOINT)
    go_results = ubergraph_client.query(ubergraph_query)

    go_terms_map = {}
    for row in go_results:
        gid = row.get("go_id", {}).get("value", "")
        label = row.get("go_label", {}).get("value", "")
        if gid and gid.startswith("GO:"):
            go_terms_map[gid] = label

    print(f"  Found {len(go_terms_map)} GO terms (including subclasses)")

    # Step 2: Query Wikidata for human genes with these GO terms
    go_ids_list = list(go_terms_map.keys())
    gene_terms = defaultdict(list)

    wikidata_client = SPARQLClient(WIKIDATA_ENDPOINT)
    batch_size = 50

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
                gid = row.get("go_id", {}).get("value", "")
                if symbol and gid:
                    term_label = go_terms_map.get(gid, gid)
                    if term_label not in gene_terms[symbol]:
                        gene_terms[symbol].append(term_label)
        except Exception as e:
            print(f"  Warning: Wikidata query failed: {e}")
            continue

        if len(gene_terms) >= max_genes * 2:
            break

    # Add core terpenoid genes if not already present
    for core_gene in CORE_TERPENOID_GENES:
        if core_gene not in gene_terms:
            gene_terms[core_gene] = ["core terpenoid pathway"]

    genes = [TerpenoidGene(symbol=sym, go_terms=terms, pathway="terpenoid metabolism")
             for sym, terms in gene_terms.items()]

    print(f"  Found {len(genes)} genes total ({len(CORE_TERPENOID_GENES)} core + {len(genes) - len(CORE_TERPENOID_GENES)} from GO)")

    # Cache results
    if use_cache and cache_file:
        save_to_cache(cache_file, {
            "go_term": go_term,
            "genes": [{"symbol": g.symbol, "go_terms": g.go_terms, "pathway": g.pathway} for g in genes]
        })

    return genes[:max_genes]


# =============================================================================
# Layer 2: CellxGene Single-Cell Expression
# =============================================================================

def analyze_cellxgene_expression(
    gene_symbols: List[str],
    tissue: str,
    condition: str,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """Analyze single-cell expression comparing condition vs normal."""
    if not HAS_CELLXGENE:
        return {"error": "cellxgene-census not installed"}

    cache_dir = get_cache_dir()
    cache_key = get_cache_key({
        "genes": sorted(gene_symbols),
        "tissue": tissue,
        "condition": condition,
    })
    cache_file = cache_dir / f"cellxgene_terp_{cache_key}.json" if cache_dir else None

    if use_cache and cache_file:
        cached = load_from_cache(cache_file)
        if cached and len(cached.get("results", {})) >= len(gene_symbols) * 0.8:
            print(f"  [Cache] Loaded from {cache_file.name}")
            return cached

    print(f"  Analyzing {len(gene_symbols)} genes in {tissue}...")
    print(f"  Comparing: normal vs {condition}")

    results = {}

    with CellxGeneClient() as client:
        for gene in gene_symbols:
            try:
                gene_cache_key = get_cache_key({"gene": gene, "tissue": tissue, "condition": condition})
                gene_cache_file = cache_dir / f"terp_expr_{gene_cache_key}_{gene}.json" if cache_dir else None

                if use_cache and gene_cache_file and gene_cache_file.exists():
                    with open(gene_cache_file) as f:
                        gene_data = json.load(f)
                    results[gene] = gene_data.get("data", {})
                    continue

                comparison = client.get_cell_type_comparison(
                    gene_symbol=gene,
                    tissue=tissue,
                    condition_a="normal",
                    condition_b=condition,
                )
                results[gene] = comparison

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
        min_fc = float('inf')
        min_fc_ct = "unknown"

        for ct, data in cell_type_data.items():
            fc = data.get("fold_change", 1.0)
            if fc > max_fc:
                max_fc = fc
                max_fc_ct = ct
            if fc < min_fc:
                min_fc = fc
                min_fc_ct = ct

            if fc > 1.5:
                cell_type_stats[ct]["upregulated"].append(symbol)
            elif fc < 0.67:
                cell_type_stats[ct]["downregulated"].append(symbol)

        gene_summaries.append({
            "symbol": symbol,
            "max_fold_change": max_fc,
            "min_fold_change": min_fc,
            "top_cell_type": max_fc_ct,
            "bottom_cell_type": min_fc_ct,
            "go_terms": gene_data.get(symbol, []),
        })

    gene_summaries.sort(key=lambda x: x["max_fold_change"], reverse=True)

    upregulated = [g for g in gene_summaries if g["max_fold_change"] > 1.5]
    downregulated = [g for g in gene_summaries if g["min_fold_change"] < 0.67]

    cell_type_drivers = []
    for ct, stats in cell_type_stats.items():
        if stats["upregulated"] or stats["downregulated"]:
            cell_type_drivers.append({
                "cell_type": ct,
                "n_upregulated": len(stats["upregulated"]),
                "n_downregulated": len(stats["downregulated"]),
                "upregulated_genes": stats["upregulated"][:5],
                "downregulated_genes": stats["downregulated"][:5],
            })

    cell_type_drivers.sort(key=lambda x: x["n_upregulated"] + x["n_downregulated"], reverse=True)

    return {
        "n_genes_analyzed": len(gene_summaries),
        "n_upregulated": len(upregulated),
        "n_downregulated": len(downregulated),
        "top_upregulated": upregulated[:10],
        "top_downregulated": downregulated[:10],
        "cell_type_drivers": cell_type_drivers[:10],
        "all_genes": gene_summaries,
    }


# =============================================================================
# Layer 3: ARCHS4 Bulk RNA-seq Validation
# =============================================================================

def validate_with_archs4(
    genes: List[str],
    condition_search_term: str,
    control_search_term: str = "normal",
    max_studies: int = 10,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """Validate findings in bulk RNA-seq studies from ARCHS4."""
    if not HAS_ARCHS4:
        return {"available": False, "reason": "ARCHS4 not installed"}

    data_dir = os.environ.get("ARCHS4_DATA_DIR")
    if not data_dir:
        return {"available": False, "reason": "ARCHS4_DATA_DIR not configured"}

    cache_dir = get_cache_dir()
    cache_key = get_cache_key({
        "genes": sorted(genes),
        "condition": condition_search_term,
        "control": control_search_term,
    })
    cache_file = cache_dir / f"archs4_terp_{cache_key}.json" if cache_dir else None

    if use_cache and cache_file:
        cached = load_from_cache(cache_file)
        if cached:
            print(f"  [Cache] Loaded ARCHS4 results from {cache_file.name}")
            return cached

    try:
        client = ARCHS4Client(data_dir=data_dir)
    except Exception as e:
        return {"available": False, "reason": str(e)}

    print(f"  Searching ARCHS4 for '{condition_search_term}' studies...")

    try:
        # Search for condition studies
        condition_metadata = client.search_metadata(condition_search_term)
        if condition_metadata.empty:
            return {"available": True, "n_studies": 0, "reason": "No condition studies found"}

        gse_series = condition_metadata["series_id"].str.split(',').explode().str.strip().dropna()
        all_gse_ids = [gse for gse in gse_series.unique() if gse.startswith("GSE")]

        print(f"  Found {len(all_gse_ids)} unique studies")

        # Search for control samples
        control_metadata = client.search_metadata(control_search_term)
        if not control_metadata.empty:
            condition_samples = set(condition_metadata["geo_accession"])
            control_metadata = control_metadata[~control_metadata["geo_accession"].isin(condition_samples)]

        n_control = len(control_metadata) if not control_metadata.empty else 0
        print(f"  Found {n_control} control samples")

        # Get control expression
        control_expr = None
        if n_control > 0:
            control_samples = list(control_metadata["geo_accession"].head(100))
            control_expr = client.get_expression_by_samples(control_samples, genes=genes)

        # Process condition studies
        study_results = []
        for gse in all_gse_ids[:max_studies * 3]:
            if len(study_results) >= max_studies:
                break

            try:
                series_mask = condition_metadata["series_id"].str.contains(gse, na=False)
                series_data = condition_metadata.loc[series_mask]
                series_samples = list(series_data["geo_accession"])

                if not series_samples:
                    continue

                expr = client.get_expression_by_samples(series_samples, genes=genes)
                if expr is None or expr.empty:
                    continue

                genes_found = [g for g in genes if g in expr.index]
                if not genes_found:
                    continue

                mean_expr = {}
                for gene in genes_found:
                    gene_data = expr.loc[gene]
                    if hasattr(gene_data, 'values') and len(gene_data.shape) > 1:
                        mean_expr[gene] = float(gene_data.values.flatten().mean())
                    else:
                        mean_expr[gene] = float(gene_data.mean())

                study_results.append({
                    "gse": gse,
                    "n_samples": len(expr.columns),
                    "n_genes_detected": len(genes_found),
                    "mean_expression": mean_expr,
                })

                print(f"    Found: {gse} ({len(expr.columns)} samples)")

            except Exception:
                continue

        # Calculate differential expression
        differential_expression = []
        if control_expr is not None and not control_expr.empty and study_results:
            for gene in genes:
                condition_values = [s["mean_expression"].get(gene) for s in study_results
                                    if gene in s["mean_expression"]]
                condition_values = [v for v in condition_values if v is not None]

                control_values = []
                if gene in control_expr.index:
                    row = control_expr.loc[gene]
                    if hasattr(row, 'values'):
                        control_values = row.values.flatten().tolist()
                    else:
                        control_values = [row]

                if condition_values and control_values:
                    mean_condition = sum(condition_values) / len(condition_values)
                    mean_control = sum(control_values) / len(control_values)
                    pseudo_count = 1.0
                    fold_change = (mean_condition + pseudo_count) / (mean_control + pseudo_count)

                    differential_expression.append({
                        "gene": gene,
                        "mean_condition": round(mean_condition, 2),
                        "mean_control": round(mean_control, 2),
                        "fold_change": round(fold_change, 2),
                    })

            differential_expression.sort(key=lambda x: x["fold_change"], reverse=True)

        result = {
            "available": True,
            "n_studies": len(study_results),
            "studies": study_results,
            "differential_expression": differential_expression,
        }

        if use_cache and cache_file:
            save_to_cache(cache_file, result)

        return result

    except Exception as e:
        return {"available": False, "reason": str(e)}


# =============================================================================
# Layer 4: NDE Dataset Discovery
# =============================================================================

def discover_nde_datasets(
    condition: str,
    tissue: str,
    gene_symbols: List[str],
    use_cache: bool = True,
) -> Dict[str, Any]:
    """
    Query NDE (NIAID Data Ecosystem) for relevant datasets that might contain
    expression data for the genes of interest.

    This layer identifies datasets that:
    1. Match the condition/disease of interest
    2. Are related to the tissue
    3. Have RNA-seq or expression measurement types
    """
    cache_dir = get_cache_dir()
    cache_key = get_cache_key({
        "condition": condition,
        "tissue": tissue,
        "n_genes": len(gene_symbols),
    })
    cache_file = cache_dir / f"nde_terp_{cache_key}.json" if cache_dir else None

    if use_cache and cache_file:
        cached = load_from_cache(cache_file)
        if cached:
            print(f"  [Cache] Loaded NDE results from {cache_file.name}")
            return cached

    print(f"  Querying NDE for datasets related to '{condition}' in {tissue}...")

    nde_client = SPARQLClient(NDE_ENDPOINT)

    # Build search terms
    condition_terms = condition.lower().split()
    tissue_terms = tissue.lower().split()

    # Query for datasets matching condition and tissue
    # Search in name, description, and keywords
    nde_query = f'''
    PREFIX schema: <http://schema.org/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT DISTINCT ?dataset ?name ?description ?measurementTechnique ?url
           (GROUP_CONCAT(DISTINCT ?keyword; separator=", ") as ?keywords)
    WHERE {{
      ?dataset a schema:Dataset .
      ?dataset schema:name ?name .
      OPTIONAL {{ ?dataset schema:description ?description }}
      OPTIONAL {{ ?dataset schema:measurementTechnique ?measurementTechnique }}
      OPTIONAL {{ ?dataset schema:url ?url }}
      OPTIONAL {{ ?dataset schema:keywords ?keyword }}

      # Filter for condition-related datasets
      FILTER(
        CONTAINS(LCASE(?name), "{condition.lower()}") ||
        CONTAINS(LCASE(COALESCE(?description, "")), "{condition.lower()}") ||
        CONTAINS(LCASE(COALESCE(?keyword, "")), "{condition.lower()}")
      )
    }}
    GROUP BY ?dataset ?name ?description ?measurementTechnique ?url
    LIMIT 50
    '''

    datasets = []

    try:
        results = nde_client.query(nde_query, include_prefixes=False)

        for row in results:
            name = row.get("name", {}).get("value", "")
            description = row.get("description", {}).get("value", "")[:500] if row.get("description") else ""
            measurement = row.get("measurementTechnique", {}).get("value", "")
            url = row.get("url", {}).get("value", "")
            keywords = row.get("keywords", {}).get("value", "")

            # Score relevance
            score = 0
            name_lower = name.lower()
            desc_lower = description.lower()

            # Condition match
            if condition.lower() in name_lower:
                score += 3
            if condition.lower() in desc_lower:
                score += 2

            # Tissue match
            if tissue.lower() in name_lower or tissue.lower() in desc_lower:
                score += 2

            # Expression/RNA-seq data
            if any(term in name_lower or term in desc_lower or term in measurement.lower()
                   for term in ["rna-seq", "transcriptom", "expression", "gene expression"]):
                score += 3

            # Gene mentions
            gene_mentions = []
            for gene in gene_symbols[:10]:  # Check top genes
                if gene.lower() in name_lower or gene.lower() in desc_lower:
                    gene_mentions.append(gene)
                    score += 1

            datasets.append({
                "name": name[:150],
                "description": description[:300],
                "measurement_technique": measurement,
                "url": url,
                "keywords": keywords[:200],
                "relevance_score": score,
                "gene_mentions": gene_mentions,
                "has_expression_data": any(term in (name_lower + desc_lower + measurement.lower())
                                           for term in ["rna-seq", "transcriptom", "expression"]),
            })

        # Sort by relevance
        datasets.sort(key=lambda x: x["relevance_score"], reverse=True)

    except Exception as e:
        print(f"  Warning: NDE query failed: {e}")

    # Also search for terpenoid/cholesterol-specific datasets
    terpenoid_query = '''
    PREFIX schema: <http://schema.org/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT DISTINCT ?dataset ?name ?description ?measurementTechnique ?url
    WHERE {
      ?dataset a schema:Dataset .
      ?dataset schema:name ?name .
      OPTIONAL { ?dataset schema:description ?description }
      OPTIONAL { ?dataset schema:measurementTechnique ?measurementTechnique }
      OPTIONAL { ?dataset schema:url ?url }

      # Filter for lipid/cholesterol metabolism
      FILTER(
        CONTAINS(LCASE(?name), "cholesterol") ||
        CONTAINS(LCASE(?name), "lipid") ||
        CONTAINS(LCASE(?name), "sterol") ||
        CONTAINS(LCASE(COALESCE(?description, "")), "cholesterol") ||
        CONTAINS(LCASE(COALESCE(?description, "")), "mevalonate")
      )
    }
    LIMIT 20
    '''

    try:
        terp_results = nde_client.query(terpenoid_query, include_prefixes=False)

        for row in terp_results:
            name = row.get("name", {}).get("value", "")
            description = row.get("description", {}).get("value", "")[:500] if row.get("description") else ""
            measurement = row.get("measurementTechnique", {}).get("value", "")
            url = row.get("url", {}).get("value", "")

            # Check if already in list
            if not any(d["name"] == name[:150] for d in datasets):
                datasets.append({
                    "name": name[:150],
                    "description": description[:300],
                    "measurement_technique": measurement,
                    "url": url,
                    "keywords": "",
                    "relevance_score": 2,  # Terpenoid-related
                    "gene_mentions": [],
                    "has_expression_data": any(term in (name.lower() + description.lower() + measurement.lower())
                                               for term in ["rna-seq", "transcriptom", "expression"]),
                    "terpenoid_related": True,
                })
    except Exception as e:
        print(f"  Warning: Terpenoid-specific NDE query failed: {e}")

    # Filter to most relevant
    expression_datasets = [d for d in datasets if d.get("has_expression_data")]
    other_datasets = [d for d in datasets if not d.get("has_expression_data")]

    result = {
        "n_datasets_found": len(datasets),
        "n_expression_datasets": len(expression_datasets),
        "expression_datasets": expression_datasets[:10],
        "other_relevant_datasets": other_datasets[:5],
        "top_gene_mentions": _aggregate_gene_mentions(datasets),
    }

    if use_cache and cache_file:
        save_to_cache(cache_file, result)

    print(f"  Found {len(datasets)} datasets ({len(expression_datasets)} with expression data)")

    return result


def _aggregate_gene_mentions(datasets: List[Dict]) -> Dict[str, int]:
    """Aggregate gene mentions across datasets."""
    gene_counts = defaultdict(int)
    for d in datasets:
        for gene in d.get("gene_mentions", []):
            gene_counts[gene] += 1
    return dict(sorted(gene_counts.items(), key=lambda x: x[1], reverse=True)[:10])


# =============================================================================
# Layer 5: SPOKE-OKN Disease Associations
# =============================================================================

def get_spoke_associations(
    gene_symbols: List[str],
    use_cache: bool = True,
) -> Dict[str, Any]:
    """Query SPOKE-OKN for disease associations of genes."""
    cache_dir = get_cache_dir()
    cache_key = get_cache_key({"genes": sorted(gene_symbols)})
    cache_file = cache_dir / f"spoke_terp_{cache_key}.json" if cache_dir else None

    if use_cache and cache_file:
        cached = load_from_cache(cache_file)
        if cached:
            print(f"  [Cache] Loaded SPOKE results from {cache_file.name}")
            return cached

    print(f"  Querying SPOKE-OKN for disease associations...")

    spoke_client = SPARQLClient(SPOKE_OKN_ENDPOINT)
    gene_associations = {}

    for symbol in gene_symbols[:20]:  # Limit to avoid long queries
        query = f'''
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX biolink: <https://w3id.org/biolink/vocab/>

        SELECT DISTINCT ?disease ?diseaseLabel ?relation WHERE {{
          ?gene rdfs:label "{symbol}" .
          ?gene ?relation ?disease .
          ?disease a biolink:Disease .
          OPTIONAL {{ ?disease rdfs:label ?diseaseLabel }}
        }}
        LIMIT 20
        '''

        try:
            results = spoke_client.query(query, include_prefixes=False)
            diseases = []
            for row in results:
                disease_label = row.get("diseaseLabel", {}).get("value", "")
                relation = row.get("relation", {}).get("value", "").split("/")[-1]
                if disease_label:
                    diseases.append({"disease": disease_label, "relation": relation})

            if diseases:
                gene_associations[symbol] = diseases
        except Exception as e:
            print(f"    Warning: SPOKE query failed for {symbol}: {e}")
            continue

    result = {
        "n_genes_with_associations": len(gene_associations),
        "associations": gene_associations,
    }

    if use_cache and cache_file:
        save_to_cache(cache_file, result)

    return result


# =============================================================================
# Visualization
# =============================================================================

def generate_visualization(result: Dict[str, Any]) -> str:
    """Generate ASCII visualization of results."""
    lines = []

    query = result.get("query", {})
    layer1 = result.get("layer1_knowledge", {})
    layer2 = result.get("layer2_singlecell", {})
    layer3 = result.get("layer3_validation", {})
    layer4_nde = result.get("layer4_nde", {})
    layer5_spoke = result.get("layer5_spoke", {})

    lines.append("=" * 80)
    lines.append("TERPENOID INFECTION ANALYZER - RESULTS VISUALIZATION")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"Condition: {query.get('condition', 'N/A')}")
    lines.append(f"Tissue: {query.get('tissue', 'N/A')}")
    lines.append(f"GO Term: {query.get('go_term', DEFAULT_GO_TERM)}")
    lines.append("")

    # Layer 1: Knowledge Graph
    lines.append("-" * 80)
    lines.append("[LAYER 1] KNOWLEDGE GRAPH - Gene Discovery")
    lines.append("-" * 80)
    lines.append(f"Total genes discovered: {layer1.get('n_genes', 0)}")
    lines.append("")
    lines.append("Sample genes:")
    for gene in layer1.get("sample_genes", [])[:10]:
        lines.append(f"  - {gene}")
    lines.append("")

    # Layer 2: Single-Cell Expression
    lines.append("-" * 80)
    lines.append("[LAYER 2] SINGLE-CELL EXPRESSION")
    lines.append("-" * 80)

    if layer2.get("skipped"):
        lines.append("  (Skipped)")
    else:
        lines.append(f"Genes analyzed: {layer2.get('n_genes_analyzed', 0)}")
        lines.append(f"Upregulated (FC > 1.5): {layer2.get('n_upregulated', 0)}")
        lines.append(f"Downregulated (FC < 0.67): {layer2.get('n_downregulated', 0)}")
        lines.append("")

        # Top upregulated
        lines.append("Top Upregulated Genes:")
        for gene in layer2.get("top_upregulated", [])[:5]:
            symbol = gene.get("symbol", "")
            fc = gene.get("fold_change", 1.0)
            ct = gene.get("top_cell_type", "unknown")
            bar = "#" * min(int(fc * 5), 30)
            lines.append(f"  {symbol:10s} {fc:5.2f}x {bar} ({ct})")
        lines.append("")

        # Cell type drivers
        lines.append("Cell Types Driving Changes:")
        for ct_info in layer2.get("cell_type_drivers", [])[:5]:
            ct = ct_info.get("cell_type", "")
            n_up = ct_info.get("n_upregulated", 0)
            n_down = ct_info.get("n_downregulated", 0)
            lines.append(f"  {ct}: {n_up} up, {n_down} down")
    lines.append("")

    # Layer 3: Bulk Validation
    lines.append("-" * 80)
    lines.append("[LAYER 3] BULK RNA-SEQ VALIDATION (ARCHS4)")
    lines.append("-" * 80)

    if not layer3.get("available"):
        lines.append(f"  Not available: {layer3.get('reason', 'unknown')}")
    elif layer3.get("n_studies", 0) == 0:
        lines.append("  No studies found")
    else:
        lines.append(f"Studies analyzed: {layer3.get('n_studies', 0)}")
        lines.append("")
        lines.append("Differential Expression (condition vs control):")
        for de in layer3.get("differential_expression", [])[:5]:
            gene = de.get("gene", "")
            fc = de.get("fold_change", 1.0)
            direction = "UP" if fc > 1.0 else "DOWN"
            bar = "#" * min(int(abs(fc) * 5), 30)
            lines.append(f"  {gene:10s} {fc:5.2f}x {direction:4s} {bar}")
    lines.append("")

    # Layer 4: NDE Dataset Discovery
    lines.append("-" * 80)
    lines.append("[LAYER 4] NDE DATASET DISCOVERY")
    lines.append("-" * 80)

    n_datasets = layer4_nde.get("n_datasets_found", 0)
    n_expression = layer4_nde.get("n_expression_datasets", 0)
    lines.append(f"Total datasets found: {n_datasets}")
    lines.append(f"Datasets with expression data: {n_expression}")
    lines.append("")

    if n_expression > 0:
        lines.append("Expression Datasets (potential for gene analysis):")
        for ds in layer4_nde.get("expression_datasets", [])[:5]:
            name = ds.get("name", "")[:60]
            score = ds.get("relevance_score", 0)
            lines.append(f"  [{score}] {name}")
            if ds.get("url"):
                lines.append(f"      URL: {ds['url'][:70]}")
    lines.append("")

    # Layer 5: SPOKE Associations
    lines.append("-" * 80)
    lines.append("[LAYER 5] SPOKE-OKN DISEASE ASSOCIATIONS")
    lines.append("-" * 80)

    n_with_assoc = layer5_spoke.get("n_genes_with_associations", 0)
    lines.append(f"Genes with disease associations: {n_with_assoc}")

    if n_with_assoc > 0:
        lines.append("")
        for gene, diseases in list(layer5_spoke.get("associations", {}).items())[:5]:
            lines.append(f"  {gene}:")
            for d in diseases[:3]:
                lines.append(f"    - {d.get('disease', '')} ({d.get('relation', '')})")
    lines.append("")

    lines.append("=" * 80)
    lines.append("END OF VISUALIZATION")
    lines.append("=" * 80)

    return "\n".join(lines)


# =============================================================================
# LLM Summary
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
    layer4_nde = result.get("layer4_nde", {})
    layer5_spoke = result.get("layer5_spoke", {})

    data_summary = json.dumps({
        "query": query,
        "layer1_knowledge": {"n_genes": layer1.get("n_genes", 0), "genes": layer1.get("sample_genes", [])},
        "layer2_singlecell": {
            "n_upregulated": layer2.get("n_upregulated", 0),
            "top_upregulated": layer2.get("top_upregulated", [])[:5],
            "cell_type_drivers": layer2.get("cell_type_drivers", [])[:5],
        },
        "layer3_validation": {
            "n_studies": layer3.get("n_studies", 0),
            "differential_expression": layer3.get("differential_expression", [])[:5],
        },
        "layer4_nde": {
            "n_datasets": layer4_nde.get("n_datasets_found", 0),
            "n_expression_datasets": layer4_nde.get("n_expression_datasets", 0),
            "expression_datasets": [d.get("name", "")[:80] for d in layer4_nde.get("expression_datasets", [])[:5]],
        },
        "layer5_spoke": {
            "n_genes_with_associations": layer5_spoke.get("n_genes_with_associations", 0),
        },
    }, indent=2)

    prompt = f"""You are a computational biology expert. Summarize this analysis of terpenoid metabolism genes during infection.

QUESTION: Which host terpenoid metabolism genes are dysregulated in {query.get('condition')}, and which cell types drive those changes?

BIOLOGICAL CONTEXT:
- Terpenoid/isoprenoid metabolism is critical for cholesterol synthesis, protein prenylation, and immune signaling
- Many viruses hijack host cholesterol pathways for entry and replication
- The mevalonate pathway provides precursors for immune cell signaling

ANALYSIS RESULTS:
{data_summary}

DATA SOURCES:
- Gene Ontology (Ubergraph): GO term hierarchy for {query.get('go_term', DEFAULT_GO_TERM)}
- Wikidata: Human gene annotations
- CellxGene Census: Single-cell RNA-seq in {query.get('tissue')} ({query.get('condition')} vs normal)
- ARCHS4: Bulk RNA-seq validation
- NDE (NIAID Data Ecosystem): Relevant datasets for future analysis
- SPOKE-OKN: Disease associations

Provide a scientific summary (3-4 paragraphs) covering:
1. Key gene expression findings and biological relevance
2. Cell types driving the changes
3. Validation from bulk RNA-seq
4. Related datasets from NDE that could be used for further investigation
5. Potential implications for host-pathogen interactions
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
# Main Analysis
# =============================================================================

def run_analysis(
    condition: str,
    tissue: str,
    go_term: str = DEFAULT_GO_TERM,
    go_label: Optional[str] = None,
    max_genes: int = 30,
    skip_cellxgene: bool = False,
    skip_archs4: bool = False,
    skip_spoke: bool = False,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """Run the full multi-layer analysis."""

    if go_label is None:
        go_label = DEFAULT_GO_LABEL

    print("=" * 70)
    print("Terpenoid Infection Analyzer - Multi-Layer Analysis")
    print("=" * 70)
    print()
    print(f"  Condition: {condition}")
    print(f"  Tissue: {tissue}")
    print(f"  GO Term: {go_term} ({go_label})")
    print(f"  Max Genes: {max_genes}")
    print()

    result = {
        "query": {
            "condition": condition,
            "tissue": tissue,
            "go_term": go_term,
            "go_label": go_label,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Layer 1: Knowledge Graph
    print("-" * 70)
    print("[Layer 1] Knowledge Graph: Terpenoid Gene Discovery")
    print("-" * 70)

    genes = get_terpenoid_genes(go_term, go_label, max_genes=max_genes * 2, use_cache=use_cache)
    genes = genes[:max_genes]
    gene_data = {g.symbol: g.go_terms for g in genes}

    result["layer1_knowledge"] = {
        "n_genes": len(genes),
        "sample_genes": [g.symbol for g in genes[:15]],
        "genes_with_go_terms": [{"symbol": g.symbol, "go_terms": g.go_terms[:3]} for g in genes[:5]],
    }

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
        expr_results = analyze_cellxgene_expression(gene_symbols, tissue, condition, use_cache)
        aggregated = aggregate_expression_results(gene_data, expr_results)

        result["layer2_singlecell"] = {
            "n_genes_analyzed": aggregated["n_genes_analyzed"],
            "n_upregulated": aggregated["n_upregulated"],
            "n_downregulated": aggregated["n_downregulated"],
            "top_upregulated": [
                {"symbol": g["symbol"], "fold_change": round(g["max_fold_change"], 2),
                 "top_cell_type": g["top_cell_type"]}
                for g in aggregated["top_upregulated"][:10]
            ],
            "top_downregulated": [
                {"symbol": g["symbol"], "fold_change": round(g["min_fold_change"], 2),
                 "bottom_cell_type": g["bottom_cell_type"]}
                for g in aggregated["top_downregulated"][:10]
            ],
            "cell_type_drivers": aggregated["cell_type_drivers"][:10],
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

        validation = validate_with_archs4(top_genes, condition, f"normal {tissue}", use_cache=use_cache)
        result["layer3_validation"] = validation

        if validation.get("available") and validation.get("n_studies", 0) > 0:
            print(f"\n  Found {validation['n_studies']} studies")
            if validation.get("differential_expression"):
                print(f"\n  Differential Expression:")
                for de in validation["differential_expression"][:5]:
                    direction = "up" if de["fold_change"] > 1 else "down"
                    print(f"    {de['gene']}: {de['fold_change']:.1f}x {direction}")
    print()

    # Layer 4: NDE Dataset Discovery
    print("-" * 70)
    print("[Layer 4] NDE: Dataset Discovery")
    print("-" * 70)

    nde_results = discover_nde_datasets(condition, tissue, [g.symbol for g in genes], use_cache)
    result["layer4_nde"] = nde_results

    if nde_results.get("n_expression_datasets", 0) > 0:
        print(f"\n  Expression datasets found:")
        for ds in nde_results.get("expression_datasets", [])[:5]:
            name = ds.get("name", "")[:60]
            print(f"    - {name}")
            if ds.get("url"):
                print(f"      URL: {ds['url'][:80]}")
    print()

    # Layer 5: SPOKE-OKN Disease Associations
    print("-" * 70)
    print("[Layer 5] SPOKE-OKN: Disease Associations")
    print("-" * 70)

    if skip_spoke:
        print("  Skipping SPOKE query")
        result["layer5_spoke"] = {"skipped": True}
    else:
        spoke_results = get_spoke_associations([g.symbol for g in genes[:20]], use_cache)
        result["layer5_spoke"] = spoke_results

        if spoke_results.get("n_genes_with_associations", 0) > 0:
            print(f"\n  {spoke_results['n_genes_with_associations']} genes have disease associations")
            for gene, diseases in list(spoke_results.get("associations", {}).items())[:3]:
                print(f"    {gene}: {', '.join(d['disease'] for d in diseases[:2])}")
    print()

    # LLM Summary
    print("-" * 70)
    print("[Layer 6] LLM Summary")
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
        description="Analyze terpenoid metabolism genes in infection conditions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Terpenoid genes in COVID-19 lung
  python terpenoid_infection_analyzer.py --condition "COVID-19" --tissue lung

  # Cholesterol metabolism in CMV infection (blood)
  python terpenoid_infection_analyzer.py --condition "cytomegalovirus infection" --tissue blood

Available conditions: COVID-19, cytomegalovirus infection, HIV infectious disease, influenza, pneumonia
        """,
    )

    parser.add_argument("--condition", required=True, help="Disease/condition name")
    parser.add_argument("--tissue", required=True, help="Tissue for analysis")
    parser.add_argument("--go-term", default=DEFAULT_GO_TERM, help="GO term ID (default: GO:0006721)")
    parser.add_argument("--go-label", help="GO term label")
    parser.add_argument("--max-genes", type=int, default=30, help="Maximum genes to analyze")
    parser.add_argument("--output", "-o", help="Output JSON file")
    parser.add_argument("--no-cache", action="store_true", help="Disable caching")
    parser.add_argument("--skip-cellxgene", action="store_true", help="Skip single-cell analysis")
    parser.add_argument("--skip-archs4", action="store_true", help="Skip bulk validation")
    parser.add_argument("--skip-spoke", action="store_true", help="Skip SPOKE-OKN queries")

    args = parser.parse_args()

    result = run_analysis(
        condition=args.condition,
        tissue=args.tissue,
        go_term=args.go_term,
        go_label=args.go_label,
        max_genes=args.max_genes,
        skip_cellxgene=args.skip_cellxgene,
        skip_archs4=args.skip_archs4,
        skip_spoke=args.skip_spoke,
        use_cache=not args.no_cache,
    )

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\nResults saved to: {args.output}")

        # Generate visualization
        viz_output = args.output.replace(".json", "_viz.txt")
        visualization = generate_visualization(result)
        with open(viz_output, "w") as f:
            f.write(visualization)
        print(f"Visualization saved to: {viz_output}")


if __name__ == "__main__":
    main()
