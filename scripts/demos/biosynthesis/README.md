# Biosynthesis: Terpenoid Gene Expression Network Visualizations

This directory queries three SPARQL endpoints to find genes involved in terpenoid/isoprenoid biosynthesis that are significantly upregulated in Arabidopsis experiments, then renders the results as interactive network visualizations.

## Data Sources

| Endpoint | URL | Role |
|----------|-----|------|
| **Ubergraph** | `https://ubergraph.apps.renci.org/sparql` | Gene Ontology hierarchy (GO term descendants) |
| **UniProt** | `https://sparql.uniprot.org/sparql` | Gene-to-GO-term annotations for Arabidopsis |
| **GXA (local Fuseki)** | `http://localhost:3030/GXA-v2/sparql` | Gene expression fold changes from Gene Expression Atlas RDF |

## Prerequisites

- Local Apache Fuseki server running with the `GXA-v2` dataset loaded
- Python packages: `requests`, `SPARQLWrapper`, `pandas`
- Run from `scripts/demos/` so that `sparql_client` and `fuseki_client` imports resolve

## How the Visualizations Were Produced

Both `terpenoid_network.html` and `terpenoid_focused.html` follow the same three-step pipeline, differing only in filtering stringency.

### Step 1: Get GO terms from Ubergraph

Query the Gene Ontology hierarchy for terpenoid biosynthetic process (GO:0016114) and its child terms.

**`visualize_terpenoid_network.py`** uses transitive closure to get all descendants:

```sparql
SELECT DISTINCT ?goId ?label WHERE {
    ?subclass rdfs:subClassOf* obo:GO_0016114 .
    ?subclass a owl:Class .
    ?subclass rdfs:label ?label .
    BIND(REPLACE(STR(?subclass), "http://purl.obolibrary.org/obo/GO_", "GO:") AS ?goId)
    FILTER(STRSTARTS(STR(?subclass), "http://purl.obolibrary.org/obo/GO_"))
}
ORDER BY ?label
```

**`visualize_terpenoid_focused.py`** restricts to the root term plus direct children only (no transitive closure):

```sparql
SELECT DISTINCT ?goId ?label WHERE {
    {
        BIND(obo:GO_0016114 AS ?term)
        ?term rdfs:label ?label .
        BIND("GO:0016114" AS ?goId)
    }
    UNION
    {
        ?term rdfs:subClassOf obo:GO_0016114 .
        ?term a owl:Class .
        ?term rdfs:label ?label .
        BIND(REPLACE(STR(?term), "http://purl.obolibrary.org/obo/GO_", "GO:") AS ?goId)
        FILTER(STRSTARTS(STR(?term), "http://purl.obolibrary.org/obo/GO_"))
    }
}
ORDER BY ?label
```

### Step 2: Get Arabidopsis genes from UniProt

For each GO term found in Step 1, query UniProt for Arabidopsis thaliana (taxon 3702) proteins annotated to that term, returning AGI locus IDs (e.g., AT4G17190):

```sparql
PREFIX up: <http://purl.uniprot.org/core/>
PREFIX taxon: <http://purl.uniprot.org/taxonomy/>

SELECT DISTINCT ?gene ?go ?geneName WHERE {
    VALUES ?go { <http://purl.obolibrary.org/obo/GO_0016114> ... }
    ?protein a up:Protein ;
             up:organism taxon:3702 ;
             up:classifiedWith ?go ;
             up:encodedBy ?geneResource .
    ?geneResource up:locusName ?gene .
    OPTIONAL { ?protein up:recommendedName/up:fullName ?geneName }
}
```

### Step 3: Query GXA for expression data

Query the local GXA RDF for those genes' expression in Arabidopsis studies. The gene URIs are constructed from AGI locus IDs and passed as a VALUES clause:

```sparql
SELECT DISTINCT ?studyId ?studyTitle ?assayId ?geneSymbol ?log2fc ?pvalue
WHERE {
    VALUES ?gene { <http://identifiers.org/aracyc/AT4G17190> ... }

    ?expr a biolink:GeneExpressionMixin ;
          biolink:subject ?assay ;
          biolink:object ?gene ;
          spokegenelab:log2fc ?log2fc ;
          spokegenelab:adj_p_value ?pvalue .

    FILTER(?log2fc > 1.0)
    FILTER(?pvalue < 0.05)

    ?study biolink:has_output ?assay ;
           biolink:name ?studyId ;
           biolink:in_taxon ?taxon .
    FILTER(?taxon = "Arabidopsis thaliana" || ?taxon = "3702")

    OPTIONAL { ?study spokegenelab:project_title ?studyTitle }

    BIND(REPLACE(STR(?gene), ".*[/#]", "") AS ?geneSymbol)
    BIND(REPLACE(STR(?assay), ".*[/#]", "") AS ?assayId)
}
ORDER BY ?studyId DESC(?log2fc)
```

The focused visualization applies stricter thresholds (`log2fc > 3.0`, `pvalue < 0.001`) and limits the output to the top 10 genes by maximum fold change, with one assay per gene.

### Step 4: Build and render the network

Both scripts assemble the query results into a vis.js network graph with four node types:

| Node type | Shape | Represents |
|-----------|-------|------------|
| GO term | diamond | Terpenoid biosynthesis GO terms |
| Gene | dot | Arabidopsis genes (AGI locus IDs) |
| Assay | square | GXA experimental comparisons |
| Study | triangle | GXA studies containing assays |

Edges encode relationships from different data sources:

| Edge | Label | Source |
|------|-------|--------|
| Gene → GO term | "annotated_to" | UniProt |
| Study → Assay | "has_assay" | GXA |
| Assay → Gene | fold change (e.g., "↑2.5") | GXA |

The HTML files are self-contained (inline vis.js from CDN) with interactive features: zoom, drag, hover tooltips, and physics-based layout. The focused visualization also includes a click-to-inspect side panel.

## Network vs. Focused

| | `terpenoid_network.html` | `terpenoid_focused.html` |
|-|--------------------------|--------------------------|
| GO terms | All descendants of GO:0016114 | Direct children only |
| Expression filter | log2FC > 1, p < 0.05 | log2FC > 3, p < 0.001 |
| Gene limit | All significant | Top 10 by fold change |
| Assays per gene | All | 1 (highest fold change) |
| Result | Large exploratory network | Small interpretable network |

## Other Scripts

The remaining scripts in this directory run related queries and export CSV files:

| Script | Output CSV | What it does |
|--------|-----------|--------------|
| `query_biosynthesis_enrichments.py` | `isoprenoid_biosynthesis_enrichments.csv` | Finds GXA assays with pathway enrichment for isoprenoid biosynthesis GO terms |
| `query_isoprenoid_genes_expression.py` | `isoprenoid_genes_upregulated.csv` | Finds upregulated genes in enriched assays (enrichment + expression in same query) |
| `query_isoprenoid_genes_uniprot.py` | `isoprenoid_genes_uniprot.csv` | Finds upregulated genes by UniProt annotation (no enrichment required) |
| `query_isoprenoid_cross_species.py` | `isoprenoid_cross_species.csv` | Cross-species analysis: Arabidopsis, human, mouse, zebrafish, Drosophila |

These scripts use the parent GO term GO:0008299 (isoprenoid biosynthetic process), which is a parent of GO:0016114 (terpenoid biosynthetic process) used by the visualization scripts.
