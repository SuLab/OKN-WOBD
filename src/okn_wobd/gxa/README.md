# GXA (Gene Expression Atlas) to RDF Pipeline

Converts differential expression experiments from the [EBI Gene Expression Atlas](https://www.ebi.ac.uk/gxa/) into Biolink-compatible RDF Turtle files for loading into FRINK/ProtoOKN knowledge graphs.

## Source Data

Experiment archives are downloaded from the EBI FTP server (`ftp.ebi.ac.uk:/pub/databases/microarray/data/atlas/experiments`). The pipeline handles all GXA experiment prefixes (E-GEOD, E-MTAB, E-MEXP, E-TABM, etc.).

Files consumed per experiment:

| File | Format | Content |
|------|--------|---------|
| `*.idf.txt` | Tab-delimited | Experiment metadata (title, description, submitter, experiment type) |
| `*.condensed-sdrf.tsv` | Tab-delimited | Sample annotations (organism, disease, tissue, ontology URIs) |
| `*-configuration.xml` | XML | Assay group definitions and contrast specifications |
| `*-analytics.tsv` | Tab-delimited | DE results per gene per contrast (p-value, log2 fold change) |
| `*.go.gsea.tsv` | Tab-delimited | GO enrichment results |
| `*.reactome.gsea.tsv` | Tab-delimited | Reactome pathway enrichment results |
| `*.interpro.gsea.tsv` | Tab-delimited | InterPro domain enrichment results |

## CLI Commands

### Download

```bash
# Download all GXA experiments
okn-wobd gxa fetch --data-dir /path/to/gxa_data

# Download only E-GEOD experiments
okn-wobd gxa fetch --data-dir /path/to/gxa_data --prefix E-GEOD

# Download a single experiment
okn-wobd gxa fetch --data-dir /path/to/gxa_data --experiment E-GEOD-5305

# Preview without downloading
okn-wobd gxa fetch --data-dir /path/to/gxa_data --dry-run
```

| Option | Default | Description |
|--------|---------|-------------|
| `--data-dir` | (required) | Directory for downloaded experiment data |
| `--prefix` | `""` (all) | Experiment prefix filter (e.g., `E-GEOD`, `E-MTAB`) |
| `--experiment` | none | Download a single experiment by accession |
| `--max-size` | `10.0` | Maximum file size in MB (larger files skipped) |
| `--dry-run` | off | List files without downloading |

Each experiment is saved to `{accession}-gea/` within the data directory. Download state is persisted to `.download_state.json` for resume after interruption.

### Convert

```bash
# Convert all experiments
okn-wobd gxa convert --data-dir /path/to/gxa_data --output-dir data/gxa_rdf

# Convert a single experiment
okn-wobd gxa convert --data-dir /path/to/gxa_data --output-dir data/gxa_rdf \
    --experiment E-GEOD-5305

# Custom thresholds
okn-wobd gxa convert --data-dir /path/to/gxa_data --output-dir data/gxa_rdf \
    --p-value 0.05 --log2fc 0.5

# Skip pathway enrichment
okn-wobd gxa convert --data-dir /path/to/gxa_data --output-dir data/gxa_rdf --no-gsea
```

| Option | Default | Description |
|--------|---------|-------------|
| `--data-dir` | (required) | Directory containing `*-gea/` experiment subdirectories |
| `--output-dir` | `data/gxa_rdf` | Output directory for `.ttl` files |
| `--experiment` | none | Process a single experiment by accession |
| `--p-value` | `0.01` | Adjusted p-value threshold for DE genes and GSEA terms |
| `--log2fc` | `1.0` | Minimum \|log2 fold change\| for DE gene inclusion |
| `--no-gsea` | off | Skip GSEA/pathway enrichment extraction |

Output: one `{accession}.ttl` per experiment. Already-processed experiments (existing `.ttl` files) are skipped on re-runs.

### Fetch + Convert

```bash
okn-wobd gxa run --data-dir /path/to/gxa_data --output-dir data/gxa_rdf
```

Accepts all options from both `fetch` and `convert`.

## Filtering Thresholds

DE genes are included when **both** conditions are met:

1. Adjusted p-value <= `--p-value` (default: 0.01)
2. |log2 fold change| >= `--log2fc` (default: 1.0, i.e., 2-fold change)

GSEA enrichment terms are included when:

1. Adjusted p-value <= `--p-value` (default: 0.01)

All significant terms are included — there is no cap on the number of enrichment terms per contrast.

Gene nodes are emitted **only** for genes that appear in at least one DE association. Genes that were measured but not differentially expressed are excluded from the RDF output. This reduces per-experiment file size by 10-80x compared to emitting all measured genes.

## RDF Data Model

### Graph Shape

```
Study (biolink:Study)
  ├── IN_TAXON → OrganismTaxon (biolink:OrganismTaxon)
  ├── STUDIES → Disease (biolink:Disease)
  ├── HAS_ATTRIBUTE → Sex, DevelopmentalStage, EthnicGroup, OrganismStatus
  └── HAS_OUTPUT → Assay (biolink:Assay)
        ├── HAS_ATTRIBUTE → Anatomy, CellType, Disease
        ├── MEASURED_DIFFERENTIAL_EXPRESSION → Gene (biolink:Gene)
        │     [reified: log2fc, adj_p_value, direction]
        └── ENRICHED_IN → GOTerm / ReactomePathway / InterProDomain
              [reified: adj_p_value, effect_size, direction, enrichment_source]
```

### Biolink Class Mapping

| Internal Type | Biolink Class |
|---------------|---------------|
| Study | `biolink:Study` |
| Assay | `biolink:Assay` |
| MGene / Gene | `biolink:Gene` |
| Disease | `biolink:Disease` |
| Anatomy | `biolink:AnatomicalEntity` |
| CellType | `biolink:Cell` |
| OrganismTaxon | `biolink:OrganismTaxon` |
| Sex | `biolink:BiologicalSex` |
| DevelopmentalStage | `biolink:LifeStage` |
| EthnicGroup | `biolink:PopulationOfIndividualOrganisms` |
| OrganismStatus | `biolink:Attribute` |
| GOTerm | `biolink:OntologyClass` |
| ReactomePathway | `biolink:Pathway` |
| InterProDomain | `biolink:ProteinDomain` |

### Relationship Mapping

| Relationship | Biolink Predicate | Reified? |
|-------------|-------------------|----------|
| Study → Assay | `biolink:has_output` | No |
| Study → Disease | `biolink:studies` | No |
| Study → Taxon | `biolink:in_taxon` | No |
| Study/Assay → characteristics | `biolink:has_attribute` | No |
| Assay → Gene (DE) | `biolink:affects_expression_of` | Yes (`biolink:GeneExpressionMixin`) |
| Assay → GO/Reactome/InterPro | `biolink:associated_with` | Yes (`biolink:Association`) |

Reified associations use the Biolink association pattern: a blank node with `biolink:subject`, `biolink:predicate`, `biolink:object`, plus property triples.

## URI Patterns

| Entity | Namespace | Example |
|--------|-----------|---------|
| Study | `http://purl.org/okn/wobd/study/` | `okn-wobd:study/E-GEOD-5305` |
| Assay (contrast) | `http://purl.org/okn/wobd/assay/` | `okn-wobd:assay/E-GEOD-5305-g1_g3` |
| Gene (human, NCBI) | `https://www.ncbi.nlm.nih.gov/gene/` | `ncbigene:3620` |
| Gene (non-human, Ensembl) | `http://identifiers.org/ensembl/` | `ensembl:ENSMUSG00000029580` |
| Taxon | `http://purl.obolibrary.org/obo/NCBITaxon_` | `NCBITaxon:9606` |
| Disease | `http://purl.obolibrary.org/obo/MONDO_` | `MONDO:0005015` |
| Anatomy | `http://purl.obolibrary.org/obo/UBERON_` | `UBERON:0001052` |
| Cell type | `http://purl.obolibrary.org/obo/CL_` | `CL:0000540` |
| GO term | `http://purl.obolibrary.org/obo/GO_` | `GO:0006955` |
| Reactome pathway | `https://reactome.org/content/detail/` | `REACT:R-HSA-168256` |
| InterPro domain | `https://www.ebi.ac.uk/interpro/entry/InterPro/` | `INTERPRO:IPR000001` |
| DE association | `http://purl.org/okn/wobd/Association/` | `okn-wobd:Association/{uuid12}` |
| Enrichment association | `http://purl.org/okn/wobd/enrichment/` | `okn-wobd:enrichment/{uuid12}` |

Characteristics without ontology URIs in SDRF annotations get fallback URIs under `http://purl.org/okn/wobd/{NodeType}/{value}`.

## Gene ID Resolution

Human genes (taxonomy 9606) are mapped from Ensembl to NCBI Gene IDs using the HGNC complete gene set. Non-human genes retain their Ensembl IDs.

- **Source**: [HGNC complete set](https://www.genenames.org/download/statistics-and-files/) (TSV from Google Cloud mirror)
- **Cache**: `~/.okn_wobd/hgnc_ensembl_ncbi_map.tsv`, auto-downloaded, 30-day expiry
- **Fallback**: If an Ensembl ID has no HGNC mapping, the gene retains its Ensembl URI
- **Supported organisms**: Human (9606), mouse (10090), rat (10116), zebrafish (7955), fly (7227), worm (6239), yeast (4932), Arabidopsis (3702). Other organisms get Ensembl IDs with empty taxonomy.

## Technology Detection

The pipeline reads `Comment[AEExperimentType]` from each experiment's IDF file to determine the assay technology:

| IDF Value | Technology Label |
|-----------|-----------------|
| `transcription profiling by array` | DNA microarray |
| `RNA-seq of coding RNA` | RNA-seq |
| `RNA-seq of non coding RNA` | RNA-seq |
| (other values) | passed through as-is |
| (missing) | `unknown` |

## Custom Property Predicates

Properties on reified associations use the `http://purl.org/okn/wobd/` namespace:

| Predicate | Used On | Type |
|-----------|---------|------|
| `okn-wobd:log2fc` | DE association | xsd:double |
| `okn-wobd:adj_p_value` | DE and enrichment associations | xsd:double |
| `okn-wobd:direction` | DE and enrichment associations | `"up"` or `"down"` |
| `okn-wobd:effect_size` | Enrichment association | xsd:double |
| `okn-wobd:enrichment_source` | Enrichment association | `"GXA:GO"`, `"GXA:Reactome"`, `"GXA:InterPro"` |

Study/Assay node properties: `okn-wobd:organism`, `okn-wobd:technology`, `okn-wobd:pubmed_id`, `okn-wobd:source`, `okn-wobd:project_title`, `okn-wobd:submitter_name`, `okn-wobd:array_design`, `okn-wobd:contrast_id`, `okn-wobd:experimental_factors`, `okn-wobd:secondary_accessions`.

Standard Biolink properties: `biolink:name`, `biolink:symbol`, `biolink:id`, `biolink:description`.

## Example SPARQL Queries

**Differentially expressed genes with fold changes:**

```sparql
PREFIX biolink: <https://w3id.org/biolink/vocab/>
PREFIX okn: <http://purl.org/okn/wobd/>

SELECT ?study ?assay ?gene ?symbol ?fc ?pval WHERE {
  ?study a biolink:Study ;
         biolink:has_output ?assay .
  ?assoc a biolink:GeneExpressionMixin ;
         biolink:subject ?assay ;
         biolink:object ?gene ;
         okn:log2fc ?fc ;
         okn:adj_p_value ?pval .
  ?gene biolink:symbol ?symbol .
}
ORDER BY ASC(?pval)
LIMIT 20
```

**Enriched pathways and GO terms:**

```sparql
PREFIX biolink: <https://w3id.org/biolink/vocab/>
PREFIX okn: <http://purl.org/okn/wobd/>

SELECT ?assay ?term ?name ?pval ?source WHERE {
  ?assoc a biolink:Association ;
         biolink:subject ?assay ;
         biolink:object ?term ;
         okn:adj_p_value ?pval ;
         okn:enrichment_source ?source .
  ?term biolink:name ?name .
}
ORDER BY ASC(?pval)
LIMIT 20
```

**Study metadata and organism:**

```sparql
PREFIX biolink: <https://w3id.org/biolink/vocab/>
PREFIX okn: <http://purl.org/okn/wobd/>

SELECT ?study ?title ?organism ?technology ?taxon WHERE {
  ?study a biolink:Study ;
         biolink:name ?title ;
         okn:organism ?organism ;
         biolink:in_taxon ?taxon ;
         biolink:has_output ?assay .
  ?assay okn:technology ?technology .
}
```

**All upregulated genes in a disease across studies:**

```sparql
PREFIX biolink: <https://w3id.org/biolink/vocab/>
PREFIX okn: <http://purl.org/okn/wobd/>

SELECT ?gene ?symbol (COUNT(DISTINCT ?study) AS ?n_studies) (AVG(?fc) AS ?avg_fc) WHERE {
  ?study a biolink:Study ;
         biolink:studies ?disease ;
         biolink:has_output ?assay .
  ?disease biolink:name ?disease_name .
  FILTER(CONTAINS(LCASE(?disease_name), "asthma"))
  ?assoc a biolink:GeneExpressionMixin ;
         biolink:subject ?assay ;
         biolink:object ?gene ;
         okn:log2fc ?fc ;
         okn:direction "up" .
  ?gene biolink:symbol ?symbol .
}
GROUP BY ?gene ?symbol
ORDER BY DESC(?n_studies)
LIMIT 20
```

## Module Structure

| Module | Purpose |
|--------|---------|
| `parser.py` | Parse IDF, SDRF, configuration.xml, analytics, and GSEA files |
| `gene_id_mapper.py` | Ensembl → NCBI gene ID mapping via HGNC |
| `study_extractor.py` | Extract Study node data from parsed experiments |
| `assay_extractor.py` | Extract Assay nodes, SDRF characteristics, factor relationships |
| `gene_extractor.py` | Extract gene nodes and DE relationships with filtering |
| `gsea_extractor.py` | Extract GSEA enrichment results (GO, Reactome, InterPro) |
| `rdf_builder.py` | Bridge pipeline DataFrames to `de_rdf.TurtleWriter` |
| `pipeline.py` | Orchestrate extraction and RDF generation per experiment |
| `downloader.py` | FTP download with resume support |

## SDRF Characteristics

The following SDRF annotation types are extracted as nodes and relationships:

| SDRF Annotation | Node Type | Ontology | Relationship |
|----------------|-----------|----------|--------------|
| `disease` | Disease | MONDO | Study → STUDIES, Assay → HAS_ATTRIBUTE |
| `organism part` | Anatomy | UBERON | Assay → HAS_ATTRIBUTE |
| `cell type` | CellType | CL | Assay → HAS_ATTRIBUTE |
| `sex` | Sex | PATO | Study → HAS_ATTRIBUTE |
| `developmental stage` | DevelopmentalStage | EFO | Study → HAS_ATTRIBUTE |
| `ethnic group` | EthnicGroup | HANCESTRO | Study → HAS_ATTRIBUTE |
| `organism status` | OrganismStatus | PATO | Study → HAS_ATTRIBUTE |

Skipped characteristics: `individual`, `age`, `organism` (organism is captured via taxonomy).

## Notes

- The `p-value` column in GXA analytics files is already FDR-adjusted; the pipeline stores it as `adj_p_value`.
- In GXA GSEA files, the `Term` column contains the ontology ID and `Accession` contains the name (counterintuitive naming by EBI). The parser handles this correctly.
- GO terms are typed as `biolink:OntologyClass` rather than a specific GO namespace (BP/MF/CC) because the GSEA files do not include namespace information.
- Direction is derived from sign: log2fc > 0 = `"up"`, log2fc <= 0 = `"down"` for DE; effect_size > 0 = `"up"` for enrichment.

## Run Statistics

**Full corpus run — 2026-03-13**

Thresholds: adjusted p-value <= 0.01, |log2FC| >= 1.0, no cap on genes or enrichment terms.

### Corpus Summary

| Metric | Value |
|--------|-------|
| Experiments (TTL files) | 4,673 |
| Total triples | ~103.7 million |
| Total size on disk | 4.34 GB |
| Conversion failures | 6 (99.87% success) |

### Per-Experiment Triples

| Stat | Value |
|------|-------|
| Mean | 22,199 |
| Median | 4,890 |
| Min | 5 |
| Max | 1,443,085 |

### Unique Entities (corpus-wide)

| Entity Type | Count |
|-------------|-------|
| Studies | 4,673 |
| Assays (contrasts) | 15,003 |
| Genes (Ensembl + NCBI) | 284,509 |
| Diseases (MONDO + fallback) | 285 |
| Organisms (NCBITaxon) | 9 |
| Anatomical entities (UBERON + fallback) | 414 |
| Cell types (CL) | 272 |
| GO terms | 5,090 |
| Reactome pathways | 4,862 |
| InterPro domains | 3,367 |

### Differential Expression

| Metric | Value |
|--------|-------|
| Total DE associations | 8,828,954 |
| Experiments with DE results | 3,798 / 4,673 (81%) |
| Avg DE associations per experiment (when present) | 2,324 |
| Avg DE genes per experiment (when present) | 1,965 |
| Max DE genes in one experiment | 56,748 |

### Pathway/GO Enrichment

| Metric | Value |
|--------|-------|
| Total enrichment associations | 287,615 |
| Experiments with enrichment | 3,185 / 4,673 (68%) |
| Avg enrichment terms per experiment (when present) | 90 |

### Organisms

| Taxon | Species |
|-------|---------|
| NCBITaxon:9606 | Human |
| NCBITaxon:10090 | Mouse |
| NCBITaxon:10116 | Rat |
| NCBITaxon:7955 | Zebrafish |
| NCBITaxon:7227 | *Drosophila melanogaster* |
| NCBITaxon:6239 | *Caenorhabditis elegans* |
| NCBITaxon:4932 | *Saccharomyces cerevisiae* |
| NCBITaxon:3702 | *Arabidopsis thaliana* |
| NCBITaxon:11623 | *Aspergillus nidulans* |
