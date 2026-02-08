## Gene Expression Atlas OKN shape (GXA differential expression)

This document describes how differential expression (DE) results and **contrasts / conditions** are modeled in the `gene-expression-atlas-okn` graph and in local TTL exports such as `data/gene_expression/E-GEOD-76.ttl`. It is meant to guide SPARQL template design and UI interpretation (no additional analytics or recomputation is assumed).

---

### Core entities

- **Genes**
  - Class: `biolink:Gene`
  - Example (from `E-GEOD-76.ttl`):

    ```1:18:data/gene_expression/E-GEOD-76.ttl
    ensembl:ENSMUSG00000000001 a biolink:Gene ;
        spokegenelab:ensembl_id "ENSMUSG00000000001"^^xsd:string ;
        spokegenelab:id_source "Ensembl"^^xsd:string ;
        biolink:id "ENSMUSG00000000001"^^xsd:string ;
        biolink:in_taxon "10090"^^xsd:string,
            "Mus musculus"^^xsd:string ;
        biolink:name ""^^xsd:string ;
        biolink:symbol "Gnai3"^^xsd:string .
    ```

- **Gene–expression associations (DE results)**
  - Class: `biolink:GeneExpressionMixin`
  - Metrics:
    - `spokegenelab:log2fc` (log2 fold-change, float)
    - `spokegenelab:adj_p_value` (adjusted p‑value, float)
  - Direction (up/down) is implied by the sign of `log2fc`.
  - The association links:
    - `biolink:subject` → a **contrast / assay** (see below).
    - `biolink:object` → a `biolink:Gene`.
  - Example:

    ```62948:62953:data/gene_expression/E-GEOD-76.ttl
    <https://spoke.ucsf.edu/genelab/Association/0052cb80c8e9> a biolink:GeneExpressionMixin ;
        spokegenelab:adj_p_value "0.0070078112089092"^^xsd:float ;
        spokegenelab:log2fc "-0.6"^^xsd:float ;
        biolink:object ensembl:ENSMUSG00000024132 ;
        biolink:predicate biolink:affects_expression_of ;
        biolink:subject spokegenelab:E-GEOD-76-g8_g2 .
    ```

- **Contrasts / assays (condition comparisons)**
  - Class: `biolink:Assay`
  - Identified by URIs of the form `spokegenelab:E-GEOD-76-g8_g2`.
  - Key properties:
    - `spokegenelab:contrast_id` – short ID like `"g8_g2"`.
    - `spokegenelab:factors_1`, `spokegenelab:factors_2` – lists of factor levels (e.g. timepoint, treatment).
    - `spokegenelab:array_design`, `spokegenelab:measurement` – platform/measurement metadata.
    - `biolink:id` – full ID string (e.g. `"E-GEOD-76-g11_g5"`).
    - `biolink:name` – **human‑readable contrast label**, typically encoding the comparison (e.g. `"aortic banding at 4 hour vs sham at 4 hour"`).
  - Example:

    ```64096:64112:data/gene_expression/E-GEOD-76.ttl
    spokegenelab:E-GEOD-76-g11_g5 a biolink:Assay ;
        spokegenelab:array_design "A-AFFY-3"^^xsd:string ;
        spokegenelab:contrast_id "g11_g5"^^xsd:string ;
        spokegenelab:factors_1 "4 hour"^^xsd:string,
            "sham"^^xsd:string ;
        spokegenelab:factors_2 "4 hour"^^xsd:string,
            "aortic banding"^^xsd:string ;
        spokegenelab:measurement "transcription profiling"^^xsd:string ;
        biolink:id "E-GEOD-76-g11_g5"^^xsd:string ;
        biolink:name "'aortic banding' at '4 hour' vs 'sham' at '4 hour'"^^xsd:string .
    ```

- **Coverage query variables**
  - In the “what gene expression datasets exist?” query:
    - **`contrastCount`** = `COUNT(DISTINCT ?contrast)` = number of distinct condition comparisons (Assays) in that experiment.
    - **`sampleContrastLabel`** = `SAMPLE(?contrastLabel)` where `?contrastLabel` is `?contrast biolink:name`. So it is **one example** of the human‑readable contrast label for that experiment (e.g. `'aortic banding' at '4 hour' vs 'sham' at '4 hour'`). Here “sample” means the SPARQL aggregate **SAMPLE()** (one arbitrary value per group), not “biological sample.”

- **Pathway/GO/InterPro enrichment associations (per-contrast)**
  - Various `biolink:Association` individuals representing enrichment results.
  - Also carry:
    - `spokegenelab:contrast_id` (same short ID like `"g8_g2"`).
    - `spokegenelab:experiment_accession` (e.g. `"E-GEOD-76"`).
    - `spokegenelab:effect_size`, `spokegenelab:adj_p_value`, `spokegenelab:enrichment_type`, etc.
  - Example:

    ```64114:64122:data/gene_expression/E-GEOD-76.ttl
    spokegenelab:E-GEOD-76_g8_g2_Assembly_of_collagen_fibrils_and_other_multimeric_structures a biolink:Association ;
        spokegenelab:adj_p_value "0.0016426609327478"^^xsd:float ;
        spokegenelab:contrast_id "g8_g2"^^xsd:string ;
        spokegenelab:effect_size "3.56190476190476"^^xsd:float ;
        spokegenelab:enrichment_type "reactome"^^xsd:string ;
        spokegenelab:experiment_accession "E-GEOD-76"^^xsd:string ;
        spokegenelab:genes_significant 10 ;
        spokegenelab:genes_total 14 ;
        ...
    ```

---

### How contrasts are modeled (sample vs. control / condition comparison)

**Definition:** A *contrast* is a **condition comparison**: one group vs. another (e.g. treatment vs. control, or timepoint A vs. timepoint B). In the graph it is represented as a `biolink:Assay` node whose ID encodes the experiment accession plus a short contrast suffix (e.g. `E-GEOD-76-g8_g2`, where `g8_g2` typically means “group 8 vs. group 2” in the experiment design). It captures:

- The **pair of conditions** being compared (via `factors_1` / `factors_2` lists).
- A **short contrast identifier** (via `spokegenelab:contrast_id` like `"g8_g2"`).
- A **human‑readable label** (via `biolink:name`).

DE associations (`biolink:GeneExpressionMixin`) then attach to that contrast as their `biolink:subject`. This makes the contrast a **first‑class node** in the graph.

---

### Multiple contrasts per dataset / study

- A single experiment/dataset accession (e.g. `E-GEOD-76`) has **multiple contrast assays**, such as:
  - `spokegenelab:E-GEOD-76-g7_g1`
  - `spokegenelab:E-GEOD-76-g8_g2`
  - `spokegenelab:E-GEOD-76-g9_g3`
  - `spokegenelab:E-GEOD-76-g12_g6`
- Each of these assays:
  - Has its own `contrast_id` and `biolink:name`.
  - Is the `biolink:subject` of many `GeneExpressionMixin` associations (one per gene with DE statistics in that contrast).
  - Is also referenced by pathway/GO enrichment associations via matching `contrast_id` and `experiment_accession`.

**Implication:** Any query or UI that talks about “DE genes in dataset X” is, in the data, actually talking about **DE genes in one or more specific contrasts of dataset X**. The contrast ID and label are essential for interpretability.

---

### Linking contrasts to differential expression results

To connect DE metrics with contrasts and experiments:

- Start from `GeneExpressionMixin`:
  - `?assoc a biolink:GeneExpressionMixin`
  - `?assoc biolink:subject ?contrast` (contrast/assay node)
  - `?assoc biolink:object ?gene`
  - `?assoc spokegenelab:log2fc ?log2fc`
  - `?assoc spokegenelab:adj_p_value ?adjPValue`
- From the contrast node `?contrast`:
  - Get **contrast identifier**:
    - `?contrast spokegenelab:contrast_id ?contrastId`
  - Get **human‑readable label**:
    - `?contrast biolink:name ?contrastLabel`
  - Optionally get **condition factors**:
    - `?contrast spokegenelab:factors_1 ?factor1`
    - `?contrast spokegenelab:factors_2 ?factor2`
  - Derive **experiment/dataset accession** either by:
    - Parsing the URI or `biolink:id` string (e.g. using a regex to extract `E-GEOD-76` from `E-GEOD-76-g8_g2`), or
    - Joining to enrichment associations that carry `spokegenelab:experiment_accession`.

---

### Guidance for query templates

For any SPARQL templates involving differential expression (genes‑in‑dataset, datasets‑for‑gene, cross‑dataset summaries), results should:

- **Return contrast identifiers and labels**
  - Include a machine‑readable `?contrastId` (e.g. `g8_g2`) and a human‑readable `?contrastLabel` (from `biolink:name`).
  - Optionally expose factor values (e.g. `?factor1`, `?factor2`) where helpful.

- **Treat contrast as a first‑class dimension**
  - Do not aggregate DE to a single dataset‑level value.
  - Allow a single dataset/study to contribute multiple rows, one per contrast, each with its own DE statistics for a given gene.

- **Align with existing experiment/dataset handling**
  - Reuse or extend existing patterns (e.g. `experimentId` extraction via regex as in `buildGeneExpressionQuery` in `[web-v2/lib/ontology/templates.ts](web-v2/lib/ontology/templates.ts)`).
  - When summarizing across datasets:
    - Define clearly whether counts are over **dataset–contrast pairs** or rolled up per dataset, and reflect that in wording (e.g. “across N contrasts in M datasets…”).

This contrast‑aware shape is primarily for **interpretability and trust** in the UI; it does not require any additional analytics beyond the precomputed DE metrics already present in the graph.

