# okn_wobd.de_rdf

Reusable library for converting differential expression results into [Biolink Model](https://biolink.github.io/biolink-model/) RDF. Part of the `okn-wobd` pip package.

## Overview

This package provides a source-agnostic pipeline for generating RDF from any differential expression analysis. The caller populates a `DEExperiment` data model, and `build_rdf()` produces a complete RDF graph with study metadata, gene-level associations, and enrichment results.

Gene symbols are resolved to NCBI Gene IDs via a local HGNC cache (auto-downloaded, 30-day expiry).

## Usage

```python
from okn_wobd.de_rdf import DEExperiment, DEGene, EnrichmentAssociation, RdfConfig, build_rdf, GeneMapper

# Resolve gene symbols to NCBI IDs
mapper = GeneMapper()
symbol_map = mapper.resolve_symbols(["IDO1", "DEFB4A", "CCL17"])

# Build the experiment model
experiment = DEExperiment(
    id="psoriasis_skin_20260204",
    name="DE: psoriasis in skin",
    organism="Homo sapiens",
    taxon_id="9606",
    test_condition="psoriasis",
    control_condition="healthy",
    tissue="skin",
    test_method="deseq2",
    platform="ARCHS4",
    timestamp="2026-02-04T15:21:09",
    sample_ids_test=["GSM123", "GSM456"],
    sample_ids_control=["GSM789", "GSM012"],
    summary="616 significant genes (494 up, 122 down)...",
    interpretation="The DE signature shows classic psoriatic inflammation...",
    genes=[
        DEGene(
            gene_symbol="IDO1",
            gene_id=symbol_map.get("IDO1"),
            log2_fold_change=6.01,
            pvalue_adjusted=5.77e-31,
            direction="up",
            is_significant=True,
        ),
    ],
    enrichment_results=[
        EnrichmentAssociation(
            term_id="GO:0006955",
            term_name="immune response",
            source="GO:BP",
            direction="up",
            pvalue_adjusted=3.39e-24,
            intersection_size=84,
        ),
    ],
)

# Generate RDF
writer = build_rdf(experiment)
writer.write("results.ttl")          # Turtle format
writer.write("results.nt", fmt="nt") # N-Triples format

# Or serialize to string
ttl_string = writer.serialize("turtle")

# Query the graph
results = writer.query("""
    PREFIX biolink: <https://w3id.org/biolink/vocab/>
    PREFIX okn-wobd: <http://purl.org/okn/wobd/>
    SELECT ?symbol ?log2fc WHERE {
        ?assoc a biolink:GeneExpressionMixin ;
               biolink:object ?gene ;
               okn-wobd:log2fc ?log2fc ;
               okn-wobd:direction "up" .
        ?gene biolink:symbol ?symbol .
        FILTER(?log2fc > 4)
    }
    ORDER BY DESC(?log2fc)
""")
```

## Modules

| Module | Description |
|--------|-------------|
| `model.py` | Source-agnostic dataclasses: `DEExperiment`, `DEGene`, `EnrichmentAssociation` |
| `config.py` | Namespace definitions (`BIOLINK`, `OKN_WOBD`, `NCBIGENE`, etc.) and `RdfConfig` |
| `biolink_mapping.py` | Biolink class/predicate maps and property lookups |
| `turtle_writer.py` | `TurtleWriter` — rdflib wrapper with `add_node()`, `add_relationship()`, reification |
| `experiment_builder.py` | `build_rdf()` — orchestrates model to RDF conversion |
| `gene_mapper.py` | `GeneMapper` — HGNC-based gene symbol to NCBI Gene ID resolution |

## RDF Output Structure

Base namespace: `http://purl.org/okn/wobd/` (prefix `okn-wobd`)

```
biolink:Study (experiment)
  ├── biolink:in_taxon → NCBITaxon (organism)
  ├── biolink:studies → MONDO (disease)
  └── biolink:has_output → biolink:Assay (comparison)
        ├── okn-wobd:test_method, platform, n_test_samples, n_control_samples
        ├── okn-wobd:summary, interpretation
        ├── okn-wobd:test_samples, control_samples (comma-separated GSM IDs)
        ├── okn-wobd:disease_terms, tissue_include_terms, tissue_exclude_terms
        ├── biolink:GeneExpressionMixin (reified DE association)
        │     ├── biolink:subject → Assay
        │     ├── biolink:object → biolink:Gene (ncbigene:XXXX)
        │     ├── okn-wobd:log2fc, adj_p_value, direction
        │     └── okn-wobd:mean_test, mean_control
        └── biolink:Association (enrichment)
              ├── biolink:object → GO/KEGG/Reactome term
              └── okn-wobd:adj_p_value, direction, intersection_size
```

## Configuration

`RdfConfig` controls output behavior:

| Field | Default | Description |
|-------|---------|-------------|
| `base_uri` | `http://purl.org/okn/wobd/` | Base namespace for generated URIs |
| `output_format` | `turtle` | Default serialization (`turtle` or `nt`) |
| `include_all_genes` | `False` | Include non-significant genes |
| `include_enrichment` | `True` | Include enrichment associations |
| `include_provenance` | `True` | Include sample IDs, search terms, thresholds |

## Gene ID Resolution

`GeneMapper` downloads the HGNC complete gene set and caches it locally at `~/.okn_wobd/hgnc_gene_map.tsv`. It maps approved symbols, previous symbols, and aliases to NCBI Gene IDs.

- Cache auto-downloads on first use
- Re-downloads if cache is older than 30 days
- Falls back to stale cache if download fails
- Cache path configurable via `HGNC_CACHE_PATH` environment variable
- Uses stdlib `csv` — no pandas dependency

## Adapters

This package provides the core RDF generation. Source-specific adapters convert their result formats into the `DEExperiment` model:

- **ChatGEO**: `scripts/demos/chatgeo/rdf_export.py` — converts `DEResult` + `EnrichmentResult` to `DEExperiment`

To integrate a new DE source, create an adapter that populates `DEExperiment` from your result format and calls `build_rdf()`.
