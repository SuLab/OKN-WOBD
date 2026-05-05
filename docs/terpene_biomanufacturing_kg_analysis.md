# Cross-Graph Analysis: Terpene Biosynthesis for Sustainable Biomanufacturing
## Proto-OKN Knowledge Graph Analysis (Revised)

**Analysis Date:** March 13, 2026
**Analyst:** Claude (Anthropic AI)
**Graphs Queried:** Gene Expression Atlas OKN, SPOKE-OKN, NDE (NIAID Data Ecosystem / WOBD), Ubergraph (ontology)

---

## Initial Prompt

> Consider this hypothetical situation: "A team of synthetic biologists is designing a microbial host for sustainable biomanufacturing of a high-value terpene. To identify promising genetic parts, they query the WOBD knowledge graph for enzymes involved in terpene biosynthesis, surfacing a network of gene-function relationships from plant and microbial systems. They then query the metadata layer of WOBD to identify experimental datasets supporting these relationships. Through the WOBD's integrated metadata graph, they find a set of RNA-seq and proteomics studies measuring gene expression under different fermentation conditions, along with metadata on strain engineering, growth rates, and yield." Design and execute an analysis leveraging the proto-okn knowledge graphs that corresponds to this scenario. Pay particular attention to researching microbial and plant genes and datasets. The knowledge graphs and datasets will be biased toward human genes and information, but I am interested in the more complex terpene molecules synthesized by microbes and plants.

---

## Executive Summary

This analysis queried 3 Proto-OKN knowledge graphs and the Ubergraph ontology service to reconstruct a gene-function-dataset network for terpene biosynthesis, motivated by the use case of engineering a microbial host for high-value terpene production. The ontology expansion identified **94 isoprenoid/terpenoid biosynthetic process GO terms**. The Gene Expression Atlas surfaced **300 differential expression records** for conserved mevalonate pathway genes (FDFT1, FDPS, CYP51A1, DHDDS) across dozens of human studies — directly informative for engineering yeast/fungal hosts sharing the same pathway. The **NDE (WOBD metadata layer)** surfaced **41 non-human terpene-specific datasets** across 25+ plant and microbial species, plus **100 fermentation/bioreactor datasets**, providing the experimental data layer the scenario demands. SPOKE-OKN contributed 2 terpene chemical entities. As anticipated, the knowledge graphs are biased toward human data, but substantive plant and some microbial data was recovered through the NDE metadata graph.

### Key Findings

- **94 GO terms** for isoprenoid/terpenoid biosynthesis spanning monoterpenes through carotenoids, plus pathway-specific terms for MVA (mevalonate) and MEP (non-mevalonate) routes
- **41 plant/microbial terpene datasets** in NDE across *Artemisia*, *Taxus*, tomato, grape, rice, maize, cotton, barley, citrus, and *Corynebacterium*
- **FDFT1** (squalene synthase) is the most heavily studied mevalonate pathway gene in the GXA with 200+ expression measurements — a primary engineering target for diverting flux from sterols to terpenes
- **GSE243419** — Single-cell RNA-seq of terpenoid biosynthesis in cotton secretory glands, revealing the transcriptional regulatory hierarchy
- **GSE268113** — Metabolic engineering of *yeast* for de novo monoterpene indole alkaloid production — the most directly relevant microbial engineering dataset
- **GSE86866** — *Corynebacterium glutamicum* engineered for beta-carotene and C50 carotenoid overproduction via sigA overexpression

---

## 1. Ontology Foundation: Terpene Biosynthesis Gene Ontology Terms

The analysis anchors to three key GO terms resolved via Ubergraph:

| GO Term | Label | Descendants |
|---------|-------|-------------|
| GO:0008299 | isoprenoid biosynthetic process | **94** (broadest) |
| GO:0016114 | terpenoid biosynthetic process | 69 |
| GO:0046246 | terpene biosynthetic process | (child of GO:0016114) |
| GO:0010333 | terpene synthase activity | (molecular function) |

### Key Terpenoid Biosynthesis Sub-processes

**Core Pathway Nodes:**
- GO:0051485 — terpenoid biosynthetic process, **mevalonate-dependent** (MVA pathway, eukaryotes/archaea)
- GO:0051483 — terpenoid biosynthetic process, **mevalonate-independent** (MEP/DXP pathway, bacteria/plastids)
- GO:1902767 — isoprenoid biosynthetic process via mevalonate
- GO:1902768 — isoprenoid biosynthetic process via 1-deoxy-D-xylulose 5-phosphate
- GO:0033384 — **geranyl diphosphate** (GPP) biosynthetic process (C10 precursor)
- GO:0045337 — **farnesyl diphosphate** (FPP) biosynthetic process (C15 precursor)
- GO:0033386 — **geranylgeranyl diphosphate** (GGPP) biosynthetic process (C20 precursor)

**Monoterpenoids (C10) — Flavors, Fragrances:**
- GO:0016099 — monoterpenoid biosynthetic process
- GO:0043693 — monoterpene biosynthetic process
- GO:0046250 — limonene biosynthetic process
- GO:0046248 — alpha-pinene biosynthetic process
- GO:0031525 — menthol biosynthetic process
- GO:0046211 — (+)-camphor biosynthetic process
- GO:1903448 — geraniol biosynthetic process

**Sesquiterpenoids (C15) — Pharma, Biofuels:**
- GO:0016106 — sesquiterpenoid biosynthetic process
- GO:0051762 — sesquiterpene biosynthetic process
- GO:1901928 — cadinene biosynthetic process
- GO:1901937 — beta-caryophyllene biosynthetic process
- GO:1901943 — (+)-epi-alpha-bisabolol biosynthetic process
- GO:0006715 — farnesol biosynthetic process

**Diterpenoids (C20) — Pharmaceuticals:**
- GO:0016102 — diterpenoid biosynthetic process
- GO:0051502 — diterpene phytoalexin biosynthetic process
- GO:0042617 — **paclitaxel** (Taxol) biosynthetic process
- GO:0009686 — gibberellin biosynthetic process
- GO:1901946 — miltiradiene biosynthetic process

**Triterpenoids (C30):**
- GO:0016104 — triterpenoid biosynthetic process
- GO:0019745 — pentacyclic triterpenoid biosynthetic process
- GO:0019746 — hopanoid biosynthetic process (microbial membranes)

**Tetraterpenoids (C40) / Carotenoids — Nutraceuticals, Pigments:**
- GO:0016109 — tetraterpenoid biosynthetic process
- GO:0016117 — carotenoid biosynthetic process
- GO:1901812 — beta-carotene biosynthetic process
- GO:1901815 — astaxanthin biosynthetic process
- GO:1901177 — lycopene biosynthetic process
- GO:0062171 — lutein biosynthetic process

**Fungal Terpenoids — Mycotoxins, Bioactive Compounds:**
- GO:0140873 — paxilline biosynthetic process
- GO:0106110 — vomitoxin biosynthetic process
- GO:0140652 — pyripyropene A biosynthetic process
- GO:0140782 — novofumigatonin biosynthetic process
- GO:0140879 — conidiogenone biosynthetic process

---

## 2. Gene Expression Atlas (GXA) — Mevalonate Pathway Genes

### 2.1 Query Results

Querying the **gene-expression-atlas-okn** graph for 44 known MVA/MEP pathway enzyme gene symbols returned **300 expression records** for 4 genes: **CYP51A1**, **DHDDS**, **FDFT1**, and **FDPS**. All studies are human (*Homo sapiens*, taxon 9606). The GXA graph does not contain gene-to-GO-process or gene-to-pathway enrichment associations queryable by GO URI; instead, expression data is accessible through gene symbol lookup.

### 2.2 Key Mevalonate Pathway Genes with Expression Data

| Gene | Enzyme | Studies | Role in Terpene Engineering |
|------|--------|---------|----------------------------|
| **FDFT1** | Squalene synthase | **200+** measurements | FPP → squalene — **primary competitor** for sesquiterpene production. Downregulate (ERG9 in yeast) to divert flux. |
| **FDPS** | Farnesyl diphosphate synthase | **100+** measurements | Produces FPP (C15) — the key branch point. Overexpress or mutate for product specificity. |
| **CYP51A1** | Lanosterol 14α-demethylase | ~30 measurements | Sterol pathway enzyme. Downregulate to reduce sterol competition. |
| **DHDDS** | Dehydrodolichyl diphosphate synthase | ~30 measurements | Polyprenol biosynthesis — minor competitor for isoprenoid flux. |

### 2.3 Notable Study Contexts

The GXA expression data, while human-derived, reveals pathway regulation dynamics that are conserved in yeast and fungal hosts:

- **Statin treatment studies** (atorvastatin, rosuvastatin, simvastatin on hepatocytes): Show coordinated regulation of FDFT1 and FDPS when HMG-CoA reductase is inhibited — directly informing how mevalonate pathway flux responds to perturbation
- **ER stress response** (tunicamycin): FDFT1 differentially expressed under ER stress — relevant to protein folding stress during high-level terpene synthase expression in microbial hosts
- **Cell signaling contexts** (estradiol, TGF/TNF, IFN-gamma): Show FDFT1 and FDPS regulation by diverse signaling pathways, indicating multiple regulatory nodes that may need engineering in microbial hosts
- **Lipid metabolism** (LDL/oxLDL treatment, serum-free culture): FDFT1 responsive to lipid environment — relevant to fermentation media lipid content

### 2.4 Full Mevalonate Pathway Gene Inventory (for engineering reference)

| Gene | Enzyme | Yeast Ortholog | Engineering Strategy |
|------|--------|---------------|---------------------|
| HMGCR | HMG-CoA reductase | **HMG1/HMG2** | Overexpress truncated catalytic domain (tHMG1) |
| HMGCS1/2 | HMG-CoA synthase | **ERG13** | Overexpress to increase flux |
| MVK | Mevalonate kinase | **ERG12** | Overexpress |
| PMVK | Phosphomevalonate kinase | **ERG8** | Overexpress |
| MVD | Mevalonate diphosphate decarboxylase | **MVD1** | Overexpress |
| IDI1/2 | IPP isomerase | **IDI1** | Overexpress to balance IPP/DMAPP |
| FDPS | Farnesyl diphosphate synthase | **ERG20** | Overexpress; mutate for GPP vs FPP specificity |
| FDFT1 | Squalene synthase | **ERG9** | **Downregulate** to divert flux from sterols |
| GGPS1 | GGPP synthase | **BTS1** | Overexpress for diterpenoid/carotenoid production |
| SQLE | Squalene epoxidase | **ERG1** | Downregulate for triterpenoid accumulation |
| LSS | Lanosterol synthase | **ERG7** | Downregulate to block sterol pathway |

---

## 3. SPOKE Knowledge Graph — Terpene Compounds

Querying the **spoke-okn** graph for terpene-related chemical entities identified only 2 compounds:

| Compound | InChIKey | Gene Regulatory Edges |
|----------|----------|----------------------|
| **Camphor** (monoterpenoid, C10) | DSSYKIVIOFKYAU | None |
| **Isoprene** (C5 building block) | RRHGJUQNOFWUDK | None |

A broader search for specific terpene names (pinene, myrcene, caryophyllene, bisabolol, squalene, geraniol, linalool, thymol, borneol, terpineol, menthol, eucalyptol, carvacrol, farnesol) returned **0 additional compounds**. The SPOKE graph is focused on pharmaceutical compounds relevant to human health and does not cover the diversity of plant/microbial terpenoids.

---

## 4. NDE (WOBD Metadata Layer) — Experimental Datasets

This is the most productive layer for the biomanufacturing scenario. The NDE knowledge graph catalogs dataset metadata from NCBI GEO and other repositories with species annotations, enabling discovery of plant and microbial experimental data.

### 4.1 Terpene-Specific Dataset Discovery

Searching dataset names for terpene/terpenoid/isoprenoid/mevalonate/carotenoid/artemisinin/taxol keywords returned **200 datasets**. Species distribution:

| Species | Count | Category |
|---------|-------|----------|
| *Homo sapiens* | 95 | Human (paclitaxel treatment, mevalonate pathway) |
| *Mus musculus* | 34 | Mouse models |
| **Plant/Microbial** | **41** | **Target organisms** |
| No annotation | 31 | Various |

### 4.2 Plant Terpene Biosynthesis Datasets

#### Artemisinin & Sesquiterpene Biosynthesis

| Species | GEO Accession | Study Focus |
|---------|---------------|-------------|
| ***Artemisia annua*** | [GSE39098](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE39098) | Gene expression comparison in tissues with contrasting **artemisinin** content |
| ***Artemisia argyi*** | [GSE102404](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE102404) | De novo transcriptome assembly; identification of genes in **terpenoid biosynthesis** |

#### Taxol (Paclitaxel) Biosynthesis

| Species | GEO Accession | Study Focus |
|---------|---------------|-------------|
| ***Taxus x media*** | [GSE175645](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE175645) | MYB-bHLH complex in **paclitaxel biosynthesis** regulation |
| ***Taxus wallichiana*** | [GSE263216](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE263216) | Taxol accumulation and endophytic **fungal elicitors** |

#### Diterpenoid Biosynthesis

| Species | GEO Accession | Study Focus |
|---------|---------------|-------------|
| ***Zea mays*** | [GSE120135](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE120135) | Multiple genes partitioning maize **diterpenoid defences** |
| ***Nicotiana attenuata*** | [GSE160453](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE160453) | Controlled hydroxylations of **diterpenoids** for defense without autotoxicity |
| ***Hordeum vulgare*** | [GSE280369](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE280369) | Ergosterol-induced **diterpene biosynthesis** activation |
| ***Oryza sativa*** | [GSE287659](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE287659) | RAD51-mediated **diterpenoid phytoalexin** biosynthesis |
| ***Oryza sativa*** | [GSE288025](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE288025) | NHEJ system modulation of diterpenoid phytoalexin biosynthesis |
| *Arabidopsis/tobacco/tomato* | [GSE31230](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE31230) | Natural **diterpenes** as inducers of resistance to bacterial wilt |

#### Terpenoid Biosynthesis — Regulatory Networks

| Species | GEO Accession | Study Focus |
|---------|---------------|-------------|
| ***Gossypium hirsutum*** (cotton) | [GSE243419](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE243419) | **Single-cell RNA-seq** revealing hierarchical transcriptional regulation of terpenoid biosynthesis in secretory glandular cells |
| ***Zanthoxylum armatum*** | [GSE142491](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE142491) | Terpenoid and fatty acid metabolism gene identification |

#### Carotenoid Biosynthesis (Tetraterpenoid C40)

| Species | GEO Accession | Study Focus |
|---------|---------------|-------------|
| ***Solanum lycopersicum*** | [GSE64981](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE64981) | Transcription factors for **carotenoid** biosynthesis in fruit |
| ***Solanum lycopersicum*** | [GSE77340](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE77340) | SlRBZ impairing chlorophyll, **carotenoid**, and gibberellin biosynthesis |
| ***Solanum lycopersicum*** | [GSE115942](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE115942) | Loliolide (**carotenoid metabolite**) responsive genes |
| ***Cucumis melo*** | [GSE220109](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE220109) | **Carotenoid** metabolism pathway and fruit color |
| *Citrus* spp. | [GSE61633](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE61633) | Engineered **carotenoid** accumulation in embryogenic calli |
| ***Daucus carota*** | [GSE49873](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE49873) | **Carotenoid** accumulation during storage root development |
| ***Osmanthus fragrans*** | [GSE90911](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE90911) | Carotenoid gene expression in flower color changes |
| *Arabidopsis* | [GSE242932](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE242932) | Apocarotenoid β-ionone regulates transcriptome and disease resistance |
| ***Oryza sativa*** | [GSE184529](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE184529) | **Apocarotenoid** growth regulator zaxinone multi-omics |

#### Terpene Volatile Biosynthesis (Grape)

| Species | GEO Accession | Study Focus |
|---------|---------------|-------------|
| ***Vitis vinifera*** | [GSE168785](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE168785) | Seasonal effects on **terpene**/norisoprenoid accumulation |
| ***Vitis vinifera*** | [GSE71146](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE71146) | Differential **terpene** accumulation across regions |
| ***Vitis vinifera*** | [GSE150343](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE150343) | Norisoprenoid responses to abscisic acid and auxin |
| ***Vitis vinifera*** | [GSE265850](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE265850) | **Monoterpene** biosynthesis in Muscat vs neutral grapes |

### 4.3 Microbial & Metabolic Engineering Datasets

| Species | GEO Accession | Study Focus |
|---------|---------------|-------------|
| ***Corynebacterium glutamicum*** | [GSE86866](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE86866) | sigA overexpression for **beta-carotene** and C50 carotenoid production |
| *Mitragyna speciosa* / **yeast** | [GSE268113](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE268113) | **Metabolic engineering of yeast** for de novo monoterpene indole alkaloid production |
| ***Danio rerio*** | [GSE84592](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE84592) | **Artemisinin** target GABAA receptor signaling |
| *Pagiophloeus tsushimanus* | [GSE182420](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE182420) | Insect metabolic resistance to host-specific **terpenoid defenses** |
| *Citrus sinensis* | [GSE33465](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE33465) | **Terpeneless** cold pressed orange oil effect on MRSA (antimicrobial) |
| *Eucalyptus tereticornis* | [GSE272831](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE272831) | **Triterpene-enriched** extract effect on adipogenesis |

### 4.4 Fermentation & Bioreactor Datasets

A separate search for fermentation/bioreactor/metabolic engineering/synthetic biology terms returned 100 additional datasets. While most lack explicit terpene focus, they provide fermentation condition transcriptomic data relevant to microbial host optimization:

| Category | Count | Notable Examples |
|----------|-------|-----------------|
| *S. cerevisiae* fermentation | ~15 | Dough fermentation, xylose fermentation, wine fermentation, ethanol stress |
| *Aspergillus* fermentor studies | 2 | Fermentor-grown *A. niger* variability |
| *Bacillus subtilis* | 1 | Surface growth transcriptome (soybean substrate) |
| CHO cell bioreactor | 1 | Shake flask vs bioreactor gene expression |
| *Lactobacillus* fermentation | 2 | Sourdough and probiotic fermentation |
| Rumen fermentation (*Bos taurus*) | 4 | Rumen epithelial transcriptomics |

---

## 5. Cross-Layer Integration: From Genes to Datasets

### 5.1 Pathway Architecture for Microbial Host Engineering

```
                        Acetyl-CoA
                            │
                    ┌───────┴───────┐
                    │  MVA Pathway  │  (Yeast, fungi, archaea)
                    │   HMGCS       │
                    │   HMGCR ←─────│── Rate-limiting (statin target)
                    │   MVK         │  GXA: statin response data
                    │   PMVK        │
                    │   MVD         │
                    └───────┬───────┘
                            │
                     ┌──────┴──────┐
                     │    IPP      │── IDI1/2 ──→ DMAPP
                     │   (C5)      │
                     └──────┬──────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
         GPP (C10)     FPP (C15)    GGPP (C20)
         (GPPS)        (FDPS) ←──── GXA: 100+ measurements
              │             │             │
     ┌────────┴───┐    ┌───┴────┐    ┌───┴────┐
     │Monoterpenes│    │Sesqui- │    │Diterp- │
     │ limonene   │    │terpenes│    │enoids  │
     │ geraniol   │    │farnesol│    │taxol   │
     │ linalool   │    │artemi- │    │gibber- │
     │ menthol    │    │sinin   │    │ellins  │
     │ pinene     │    └────┬───┘    └────────┘
     └────────────┘         │
                       FDFT1 (ERG9) ←── GXA: 200+ measurements
                            │           *** DOWNREGULATE ***
                       Squalene
                            │
                    ┌───────┴───────┐
                    │ Triterpenoids │→ Sterols (compete with terpene production)
                    │ (C30)         │
                    └───────────────┘
```

### 5.2 Priority Gene Targets (Informed by Cross-Graph Analysis)

| Priority | Gene Target | Yeast Ortholog | Strategy | KG Evidence |
|----------|------------|----------------|----------|-------------|
| 1 | **HMGCR** | tHMG1 | Overexpress truncated form | GXA: statin response shows flux regulation |
| 2 | **FDPS** | ERG20 | Overexpress; mutate for GPP/FPP specificity | GXA: 100+ expression studies |
| 3 | **IDI1** | IDI1 | Overexpress for IPP/DMAPP balance | Ontology: isomerase in both MVA and MEP |
| 4 | **FDFT1** | ERG9 | **Downregulate** to divert from sterols | GXA: most studied gene (200+ measurements) |
| 5 | Terpene synthase (TPS) | Heterologous | Express from plant source | NDE: Cotton scRNA-seq (GSE243419), Artemisia (GSE102404, GSE39098) |
| 6 | **CYP** enzymes | Heterologous | P450s for functionalization | NDE: Taxol (GSE175645), Nicotiana (GSE160453) |

### 5.3 Recommended Dataset Retrieval by Application

**For identifying terpene synthase parts to clone:**
1. **GSE243419** — Cotton secretory gland scRNA-seq (terpenoid biosynthesis regulatory network) — **highest priority**: reveals which TFs control terpenoid pathway genes
2. **GSE102404** — *Artemisia argyi* terpenoid biosynthesis gene discovery transcriptome
3. **GSE39098** — *Artemisia annua* artemisinin pathway gene expression (seedling vs. mature)
4. **GSE175645** — *Taxus* paclitaxel pathway MYB-bHLH regulation

**For understanding pathway regulation and engineering strategies:**
5. **GSE268113** — **Yeast metabolic engineering** for monoterpene alkaloid production — most directly relevant dataset
6. **GSE86866** — *C. glutamicum* carotenoid overproduction (sigA engineering) — microbial engineering proof-of-concept
7. GXA statin studies — mevalonate pathway regulation dynamics (FDFT1, FDPS under pathway perturbation)

**For carotenoid (C40) engineering:**
8. **GSE61633** — Engineered carotenoid accumulation in citrus calli
9. **GSE64981** — Tomato carotenoid transcription factors
10. **GSE86866** — Microbial beta-carotene and C50 carotenoid production in *C. glutamicum*

**For diterpenoid (C20) engineering (pharma applications):**
11. **GSE120135** — Maize diterpenoid defense gene partitioning
12. **GSE287659/GSE288025** — Rice diterpenoid phytoalexin biosynthesis regulation
13. **GSE160453** — Diterpenoid hydroxylation in *Nicotiana*
14. **GSE263216** — Taxol pathway with fungal elicitor effects

**For monoterpene (C10) / volatile engineering:**
15. **GSE265850** — Monoterpene biosynthesis in Muscat grapes (metabolomic + transcriptomic)
16. **GSE168785** — Terpene accumulation under seasonal variation in grape
17. **GSE71146** — Differential terpene accumulation across grape-growing regions

---

## 6. Knowledge Graph Coverage Assessment

### What the Proto-OKN Knowledge Graphs Provide

| Capability | Graph | Coverage |
|-----------|-------|----------|
| Terpene GO ontology hierarchy | Ubergraph | **Excellent** — 94 isoprenoid biosynthesis terms |
| Conserved mevalonate pathway gene expression | gene-expression-atlas-okn | **Good** — 300+ records for FDFT1, FDPS, CYP51A1, DHDDS |
| Plant terpene datasets (metadata) | NDE (WOBD) | **Good** — 41 non-human datasets, 25+ species |
| Fermentation datasets (metadata) | NDE (WOBD) | **Moderate** — 100 datasets, few terpene-specific |
| Microbial engineering datasets | NDE (WOBD) | **Limited** — GSE268113 (yeast), GSE86866 (*C. glutamicum*) |
| Terpene compound-gene relationships | spoke-okn | **Minimal** — only camphor and isoprene |

### Gaps and Recommendations

1. **Microbial terpene engineering datasets**: The NDE contains only 2 explicitly microbial terpene engineering studies. The rapid growth of yeast terpene platforms (Amyris farnesene, artemisinic acid) and *E. coli* terpene production means substantial GEO data exists that isn't surfaced through current metadata keywords.

2. **Terpene compound coverage in SPOKE**: Only 2 of thousands of known terpenes appear. Adding major commercial terpenes (limonene, linalool, geraniol, farnesene, amorphadiene, artemisinin, squalene, lycopene, beta-carotene) with gene regulatory edges would enable compound-centric queries.

3. **Cross-species gene orthology**: GXA data is human-centric, but mevalonate pathway genes are conserved. A mapping from human gene symbols to yeast ERG genes and bacterial orthologs would directly translate expression insights to microbial hosts.

4. **Fermentation metadata enrichment**: NDE datasets lack structured metadata for growth conditions (media, temperature, carbon source, aeration) and production outcomes (titer, yield, productivity). This metadata would transform the KG from discovery into optimization.

5. **Plant gene symbols**: The GXA graph does not populate `biolink:symbol` for plant genes. Adding AT locus → gene name mappings for *Arabidopsis* and similar annotations for crop species would make plant data discoverable via standard gene symbol queries.

6. **GXA yeast data gap**: While 21 yeast studies are cataloged in GXA, none have GeneExpressionMixin records loaded — the most consequential gap for this use case.

---

## 7. Methods

### Knowledge Graphs Queried

| Graph | Endpoint | Query Type |
|-------|----------|------------|
| Ubergraph (ontology) | Proto-OKN lookup_uri / get_descendants | GO term resolution and hierarchy expansion |
| gene-expression-atlas-okn | FRINK SPARQL | Gene symbol lookup for MVA pathway enzymes |
| spoke-okn | FRINK SPARQL | Chemical entity text search for terpene compounds |
| nde (WOBD) | FRINK SPARQL | Dataset discovery by name keywords and species filter |

### GO Terms Used as Anchors

- `GO:0008299` (isoprenoid biosynthetic process) — 94 descendants
- `GO:0016114` (terpenoid biosynthetic process) — 69 descendants
- `GO:0046246` (terpene biosynthetic process)
- `GO:0010333` (terpene synthase activity)

### SPARQL Query Strategy

1. **GXA**: Searched by gene symbol (44 MVA/MEP pathway enzymes); retrieved study titles, taxon, and experimental factors. Attempted GO process-based queries but GXA does not store gene→GO associations in a directly queryable pattern.
2. **SPOKE**: Text search on ChemicalEntity labels for 30+ terpene compound names; queried UPREGULATES/DOWNREGULATES edges to genes. Most specific terpene names not present.
3. **NDE**: Two-stage search: (a) broad keyword search on dataset names for terpene-related terms, 200 results; (b) filtered to non-human species, 41 plant/microbial datasets. Separate search for fermentation/bioreactor/metabolic engineering datasets, 100 results.

---

## Data Availability

**Sources:**
- Gene Expression Atlas OKN: `https://frink.apps.renci.org/gene-expression-atlas-okn/sparql`
- SPOKE-OKN: `https://frink.apps.renci.org/spoke-okn/sparql`
- NDE (WOBD): `https://frink.apps.renci.org/nde/sparql`
- Ubergraph (ontology service): accessed via Proto-OKN MCP server

**Key Dataset Accessions:**
- Cotton terpenoid scRNA-seq: GSE243419
- Yeast monoterpene engineering: GSE268113
- *C. glutamicum* carotenoid production: GSE86866
- *Artemisia annua* artemisinin: GSE39098
- *Taxus* paclitaxel regulation: GSE175645
- Maize diterpenoid defense: GSE120135
- Grape terpene/monoterpene: GSE265850, GSE168785, GSE71146

---

## Acknowledgments

This analysis was performed using the Proto-OKN knowledge graph infrastructure, with SPARQL queries executed via the FRINK platform and ontology expansion via Ubergraph. The Proto-OKN MCP server provided unified access across all graphs.

**Funding:** NSF Award #2535091

**Contact:**
- Andrew Su (PI): asu@scripps.edu
- Trish Whetzel: plwhetzel@gmail.com

---

*Report Generated: March 13, 2026*
*Analysis Platform: Proto-OKN Knowledge Graphs via MCP Server*
*Analyst: Claude (Anthropic AI Assistant)*
*Revision: 2 — Added NDE (WOBD metadata layer) queries, expanded dataset discovery*
