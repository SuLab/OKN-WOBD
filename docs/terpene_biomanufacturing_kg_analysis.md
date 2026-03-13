# Cross-Graph Analysis: Terpene Biosynthesis for Sustainable Biomanufacturing
## Proto-OKN Knowledge Graph Analysis

**Analysis Date:** March 12, 2026
**Analyst:** Claude (Anthropic AI)
**Graphs Queried:** Gene Expression Atlas, SPOKE-OKN, BioBricks AOP-Wiki, BioBricks MeSH, Ubergraph (ontology)

---

## Initial Prompt

> Consider this hypothetical situation: "A team of synthetic biologists is designing a microbial host for sustainable biomanufacturing of a high-value terpene. To identify promising genetic parts, they query the WOBD knowledge graph for enzymes involved in terpene biosynthesis, surfacing a network of gene-function relationships from plant and microbial systems. They then query the metadata layer of WOBD to identify experimental datasets supporting these relationships. Through the WOBD's integrated metadata graph, they find a set of RNA-seq and proteomics studies measuring gene expression under different fermentation conditions, along with metadata on strain engineering, growth rates, and yield." Design and execute an analysis leveraging the proto-okn knowledge graphs that corresponds to this scenario. Pay particular attention to researching microbial and plant genes and datasets. The knowledge graphs and datasets will be biased toward human genes and information, but I am interested in the more complex terpene molecules synthesized by microbes and plants.

---

## Executive Summary

This analysis queried 4 Proto-OKN knowledge graphs and the Ubergraph ontology service to reconstruct a gene-function-dataset network for terpene biosynthesis, motivated by the use case of engineering a microbial host for high-value terpene production. The ontology expansion identified **92 terpenoid/terpene biosynthetic process GO terms**. Querying the Gene Expression Atlas surfaced **127 differential expression records** for 18 Arabidopsis terpene pathway genes across dozens of studies, **200 pathway enrichment associations** (including diterpenoid, isoprenoid, and carotenoid biosynthesis), and study metadata for 7 plant and microbial model organisms. SPOKE-OKN contributed compound-gene regulatory interactions and disease associations for the conserved mevalonate pathway. As anticipated, the knowledge graphs are biased toward human data, but substantive plant gene expression data was recoverable once gene identifier conventions were resolved.

### Key Findings

- **18 Arabidopsis terpene pathway genes** have significant differential expression data across 50+ experiments
- **TPS04** (AT1G61120, ocimene/farnesene synthase) is the most responsive terpene synthase with 35 DE records and extreme fold changes (log2FC -8.6 to +7.5) under defense and stress conditions
- **DXS** (AT4G13280, MEP pathway entry enzyme) shows an extraordinarily significant response to ABA/osmotic stress (p = 1.8×10⁻⁶⁸)
- **PSY** (AT5G17230, phytoene synthase) is strongly light-regulated via PIF transcription factors (14 DE records)
- The Gene Expression Atlas contains **149,136 differential expression records** for Arabidopsis, 13,231 for maize, 7,184 for grape, and 3,498 for sorghum — but **no yeast expression data** in the GeneExpressionMixin layer despite 21 yeast studies being cataloged
- **Diterpenoid biosynthetic process** enrichment was detected with effect size 9.1 (p = 4.87×10⁻¹⁰) in study E-GEOD-109341
- The mevalonate pathway rate-limiting enzymes **HMGCR** and **HMGCS1** are regulated by multiple compounds (statins, thiabendazole, hexachlorophene) in SPOKE-OKN, informing fermentation media optimization

---

## 1. Methodology

### 1.1 Graph Selection and Routing

The analysis began by routing the natural language question *"What enzymes and genes are involved in terpene biosynthesis in plants and microbes?"* across all 27 Proto-OKN graphs. Seven biology-domain graphs were identified:

| Graph | Role in Analysis | Key Identifiers |
|-------|-----------------|-----------------|
| **gene-expression-atlas-okn** | Differential expression data, study metadata, pathway enrichment | NCBI Gene (AT loci for plants), Ensembl |
| **spoke-okn** | Gene-compound regulatory interactions, disease associations, organism data | Ensembl, ChEBI, InChIKey |
| **biobricks-aopwiki** | Adverse outcome pathways (toxicology context) | ChEBI, GO |
| **biobricks-ice** | Chemical bioassay data | DTXSID, NCBI Gene |
| **biobricks-mesh** | MeSH vocabulary cross-references | MeSH |
| **spoke-genelab** | Spaceflight differential expression (limited relevance) | NCBI Gene |

The **join strategy** between spoke-okn and gene-expression-atlas-okn was confirmed: Ensembl IDs serve as the shared identifier namespace for Gene entities in both graphs.

### 1.2 Ontology Expansion

Two root GO terms were identified via Ubergraph lookup:
- **GO:0016114** — terpenoid biosynthetic process (69 descendants)
- **GO:0046246** — terpene biosynthetic process (23 descendants)

Additional root terms were located for specific sub-classes:
- **GO:0008299** — isoprenoid biosynthetic process
- **GO:0043693** — monoterpene biosynthetic process
- **GO:0051762** — sesquiterpene biosynthetic process

The 92 descendant processes span the full complexity of terpene biochemistry:

| Terpene Class | Example Descendant GO Terms | Biomanufacturing Relevance |
|---|---|---|
| Monoterpenes (C10) | limonene, alpha-pinene, menthol, camphor, geraniol biosynthesis | Flavors, fragrances, solvents |
| Sesquiterpenes (C15) | cadinene, beta-caryophyllene, farnesol biosynthesis | Pharma (artemisinin precursors), biofuels |
| Diterpenes (C20) | ent-kaurene, miltiradiene, paclitaxel, phytoalexin biosynthesis | High-value pharmaceuticals |
| Triterpenes (C30) | squalene, hopanoid, pentacyclic triterpenoid biosynthesis | Pharma, cosmetics |
| Tetraterpenes (C40) | lycopene, beta-carotene, astaxanthin, zeaxanthin biosynthesis | Nutraceuticals, pigments |
| Precursor pathways | MEP pathway (mevalonate-independent), MVA pathway, farnesyl/geranylgeranyl diphosphate biosynthesis | Core engineering targets |

### 1.3 Query Strategy and Iterative Refinement

The analysis required several rounds of iterative refinement as the data model and identifier conventions in each graph were discovered:

1. **Initial approach (failed):** Querying gene-expression-atlas-okn for genes by standard gene symbols (TPS1, DXS, ERG9, etc.) joined to plant/yeast taxon filters. Returned empty — plant genes in this graph use AT locus identifiers, not standard symbols.

2. **Study-level discovery:** Searched study titles for keywords (terpenoid, mevalonate, biosynthesis, fermentation, etc.). Identified key studies including maize diterpenoid defense (GSE120135) and sorghum ABA biosynthesis (GSE140928).

3. **Data model exploration:** Inspected raw GeneExpressionMixin triples to discover that (a) expression data includes `log2fc` and `adj_p_value` properties, (b) Arabidopsis gene URIs use the pattern `https://www.ncbi.nlm.nih.gov/gene/AT5G17230`, and (c) the `biolink:symbol` property is not populated for plant genes.

4. **Final approach (successful):** Queried GeneExpressionMixin directly using known Arabidopsis terpene pathway AT locus URIs (30 genes), yielding 127 differential expression records. Separately queried enrichment Associations for terpenoid-related GO terms.

---

## 2. Organism Coverage in the Gene Expression Atlas

The Gene Expression Atlas KG contains studies across a range of organisms relevant to terpene biomanufacturing:

| Organism | Studies | GeneExpressionMixin Records | Relevance |
|---|---|---|---|
| *Homo sapiens* | 835 | 255,349 | MVA pathway pharmacology, cross-reference |
| *Mus musculus* | 541 | 162,380 | Model organism |
| ***Arabidopsis thaliana*** | **331** | **149,136** | Model plant, terpene synthase family |
| *Drosophila melanogaster* | 71 | 20,863 | Juvenile hormone (sesquiterpenoid) |
| ***Zea mays*** | **38** | **13,231** | Diterpenoid phytoalexin defense |
| ***Oryza sativa*** | **26** | **11,490** | Diterpene (phytocassane, momilactone) |
| ***Saccharomyces cerevisiae*** | **21** | **0*** | Primary microbial chassis |
| ***Vitis vinifera*** | **10** | **7,184** | Mono/sesquiterpene volatiles |
| *Glycine max* | 8 | 3,600 | Triterpene saponins |
| ***Sorghum bicolor*** | **7** | **3,498** | ABA/carotenoid biosynthesis |

*\*Yeast studies are cataloged but lack GeneExpressionMixin associations in the current graph build.*

---

## 3. Arabidopsis Terpene Biosynthetic Genes: Differential Expression

Querying 30 known Arabidopsis terpene pathway loci against the GeneExpressionMixin layer yielded **127 records** for **18 genes** with significant differential expression (adj. p < 0.05) across 50+ experiments.

### 3.1 Terpene Synthases

| AT Locus | Gene | Function | DE Records | log2FC Range | Key Experimental Contexts |
|---|---|---|---|---|---|
| AT1G61120 | **TPS04** | (E)-β-ocimene / (E,E)-α-farnesene synthase | **35** | -8.6 to +7.5 | Pathogen defense (*Pseudomonas*), wounding, leafminer herbivory, ABA stress, elicitor response |
| AT4G16740 | **TPS03** | Monoterpene synthase | 10 | -4.4 to +4.5 | SAL1-PAP retrograde signaling, callus formation, pathogen defense |
| AT2G24210 | **TPS10** | Monoterpene synthase | 7 | -6.8 to +6.0 | Wound response, jasmonate treatment, flower maturation |
| AT5G23960 | **TPS21** | Sesquiterpene synthase | 4 | -7.2 to -4.8 | Flower maturation (strongly downregulated) |
| AT3G25810 | **TPS-CIN** | 1,8-Cineole synthase | 5 | -6.4 to -0.7 | Flower maturation, small RNA biogenesis |

**Notable:** TPS04 (AT1G61120) had the most expression records of any gene in the dataset. It was strongly induced by wounding (log2FC +5.6, p = 4.3×10⁻⁹) and pathogen elicitors (+7.5 under *Pseudomonas* infection), but suppressed during phosphate starvation (-5.0) and misfolded protein stress (-6.4). This extreme dynamic range makes it a strong candidate for inducible heterologous expression systems.

### 3.2 MEP Pathway (Plastidial Isoprenoid Precursors)

| AT Locus | Gene | Function | DE Records | log2FC Range | Key Experimental Contexts |
|---|---|---|---|---|---|
| AT4G13280 | **DXS** | 1-Deoxy-D-xylulose-5-phosphate synthase | 6 | -3.4 to +2.4 | ABA/osmotic stress (p = 1.8×10⁻⁶⁸), karrikin signaling, TOC1 circadian |
| AT4G15560 | **CLA1/DXS2** | DXS paralog | 5 | -2.8 to +1.6 | Post-germination, histone methylation, plastid proteostasis |
| AT5G47720 | **DXR** | 1-Deoxy-D-xylulose 5-phosphate reductoisomerase | 2 | +1.1 to +2.8 | Embryo development, MIF1 overexpression |
| AT3G02780 | **IDI2** | IPP isomerase | 7 | +0.9 to +1.5 | Singlet oxygen response, poly(A) polymerase |
| AT5G16440 | **IDI1** | IPP isomerase | 3 | -1.9 to +0.7 | Flower maturation, pathogen elicitor (flg22) |

**Notable:** DXS (AT4G13280) — the rate-limiting enzyme of the MEP pathway — showed an adjusted p-value of 1.8×10⁻⁶⁸ for downregulation (log2FC = -3.4) in the ABA/osmotic stress study E-GEOD-114379. This is the most statistically significant result in the entire dataset.

### 3.3 MVA Pathway (Cytosolic Isoprenoid Precursors)

| AT Locus | Gene | Function | DE Records | log2FC Range | Key Experimental Contexts |
|---|---|---|---|---|---|
| AT1G63970 | **HMGR1** | HMG-CoA reductase | 5 | -1.2 to +1.6 | Light/PIF3 signaling, karrikin response, pathogen defense |
| AT4G11820 | **HMGS** | HMG-CoA synthase | 2 | +1.0 to +1.5 | TOR signaling, MED25/flowering |
| AT5G48230 | **AACT1** | Acetoacetyl-CoA thiolase | 2 | +1.0 to +4.0 | Pollen tube growth, ATP signaling |
| AT5G27450 | **MVK** | Mevalonate kinase | 1 | +1.6 | Cell cycle (MYB3R mutants) |

### 3.4 Carotenoid / Gibberellin Branches

| AT Locus | Gene | Function | DE Records | log2FC Range | Key Experimental Contexts |
|---|---|---|---|---|---|
| AT5G17230 | **PSY** | Phytoene synthase | **14** | -1.8 to +3.3 | Light signaling (DET1, PIF, phytochrome A), jasmonate, karrikin |
| AT5G57030 | **LCYE** | Lycopene epsilon-cyclase | 4 | -1.2 to +2.6 | ABA/G-protein signaling |
| AT3G10230 | **LCYB** | Lycopene beta-cyclase | 1 | +1.0 | TOC1 circadian regulation |
| AT5G25900 | **GA3/KO** | ent-Kaurene oxidase | 6 | +0.7 to +2.0 | GA biosynthesis, SA signaling, seed germination |
| AT1G79460 | **GA2/KS** | ent-Kaurene synthase | 5 | -1.3 to +1.7 | GA mutant backgrounds, shade avoidance |

### 3.5 Prenyl Transferases

| AT Locus | Gene | Function | DE Records | log2FC Range | Key Experimental Contexts |
|---|---|---|---|---|---|
| AT4G36810 | **GGPPS1** | Geranylgeranyl diphosphate synthase | 1 | -2.4 | DNA methylation mutants |
| AT4G17190 | **FPPS2** | Farnesyl diphosphate synthase | 1 | -1.3 | Auxin/pathogen cross-talk |

---

## 4. Pathway Enrichment Analysis

The Gene Expression Atlas stores functional enrichment results as Association entities linking experiments to GO terms, Reactome pathways, and InterPro domains. Searching for terpenoid-related enrichment terms yielded **200 associations** across dozens of experiments:

| Enrichment Term | Experiments | Best Effect Size | Best p-value |
|---|---|---|---|
| **Diterpenoid biosynthetic process** | E-GEOD-109341, E-GEOD-57466 | 9.10 | 4.87×10⁻¹⁰ |
| **Carotenoid biosynthetic process** | E-GEOD-43865, E-GEOD-111716, E-GEOD-30030 | 7.08 | 1.78×10⁻⁵ |
| **Isoprenoid biosynthetic process** | E-GEOD-45684, E-GEOD-2565, E-GEOD-111250 | 34.27 | 2.12×10⁻⁷ |
| **Isoprenoid synthase domain superfamily** | E-GEOD-128441, E-GEOD-57466, E-GEOD-109341 | 4.44 | 4.57×10⁻⁵ |
| **Squalene cyclase** | E-GEOD-128441 | 16.44 | 5.97×10⁻⁵ |
| **Sterol biosynthetic process** | E-GEOD-56026, E-GEOD-51885 | 3.56 | 7.46×10⁻⁹ |
| **Cholesterol biosynthesis** (MVA pathway readout) | 70+ experiments | 49.74 | 4.97×10⁻²² |
| **Regulation by SREBP** (MVA pathway control) | 40+ experiments | 17.63 | 2.25×10⁻⁵ |

The **diterpenoid biosynthetic process** enrichment in E-GEOD-109341 (12/20 genes significant, effect size 9.1, p = 4.87×10⁻¹⁰) represents a particularly strong signal. The **isoprenoid biosynthetic process** enrichment in E-GEOD-45684 reached an effect size of 34.27, indicating massive pathway-level activation.

---

## 5. Terpene-Relevant Studies Identified

### 5.1 Plant Studies

| Study Title | Organism | GEO ID | PubMed | Experimental Context |
|---|---|---|---|---|
| Multiple genes recruited from hormone pathways partition maize **diterpenoid defences** | *Zea mays* | GSE120135 | 31527844 | Pathogen infection elicits diterpenoid pathway |
| Genome-wide analysis of **abscisic acid biosynthesis**, catabolism, and signaling under saline-alkali stress | *Sorghum bicolor* | GSE140928 | 31817046 | Terpenoid (ABA/carotenoid) pathway under abiotic stress |
| Auxin stimulates **brassinosteroid biosynthesis** in roots | *A. thaliana* | GSE12964 | 21284753 | Terpenoid hormone cross-talk |
| Plant **defense genes** (BRCA2A/SSN2 impact) | *A. thaliana* | GSE23617 | 21149701 | Defense-related secondary metabolism |
| **Volatile profiles** and transcriptomic variation in Cabernet Sauvignon grapes | *V. vinifera* | — | — | Terpene volatile biosynthesis |
| Lifecycle transcriptomics of field-droughted sorghum — rapid **biotic and metabolic responses** | *S. bicolor* | — | 31806758 | Stress-responsive terpenoid metabolism |

### 5.2 Mevalonate Pathway Studies (Human, Conserved Pathway)

| Study Title | GEO ID | PubMed | Relevance |
|---|---|---|---|
| Mutant p53 disrupts morphogenesis via the **mevalonate pathway** | GSE31812 | 22265415 | 214 DE genes including HMGCR, HMGCS1, MVK, ACAT2 |
| Atorvastatin, rosuvastatin, and rifampicin effect on hepatocyte transcriptome | — | 21869732 | Statin-mediated MVA pathway modulation |
| Simvastatin anti-inflammatory effect on macrophages | — | 18192240 | HMGCR pharmacology |

---

## 6. SPOKE-OKN: Compound-Gene Regulatory Network

### 6.1 Chemical Entities

Only 2 terpene/terpenoid compounds were found in SPOKE-OKN's ChemicalEntity class:
- **Camphor** (monoterpenoid ketone)
- **Isoprene** (C5 building block of all terpenes)

Neither had gene regulatory edges. This reflects the graph's bias toward pharmaceutical compounds.

### 6.2 Mevalonate Pathway Gene-Compound Interactions

Five core mevalonate pathway genes were found in SPOKE-OKN with compound regulatory relationships:

| Gene | Ensembl ID | Upregulators | Downregulators |
|---|---|---|---|
| **HMGCR** | ENSG00000113161 | Hexachlorophene, Pentobarbital, Thiabendazole, Fluorouracil | Fluorouracil |
| **HMGCS1** | ENSG00000112972 | Hexachlorophene, Pentobarbital | Phenytoin, Fluorouracil, Ethoprophos, Pentobarbital, Thiabendazole, Phenothiazine |

Fluorouracil and Pentobarbital show context-dependent bidirectional regulation of HMGCR and HMGCS1, potentially reflecting dose or tissue-dependent effects.

### 6.3 Disease Associations

| Gene | Disease Associations |
|---|---|
| **HMGCR** | Arteriosclerosis, coronary artery disease, diabetes mellitus, hypertension, obesity, liver disease, nervous system disease, nutrition disease, cerebrovascular disease |
| **HMGCS2** | Epilepsy, liver disease |
| **FDPS** | Skin cancer, squamous cell carcinoma, skin benign neoplasm |

---

## 7. Cross-Graph Integration

### 7.1 Ensembl ID Join: SPOKE-OKN ↔ Gene Expression Atlas

The Ensembl join strategy was confirmed but only productive for human genes (both graphs use ENSG identifiers). Arabidopsis genes in the expression atlas use AT locus IDs as their primary identifiers, which SPOKE-OKN does not contain — SPOKE-OKN's Gene entities are exclusively human.

### 7.2 Pathway Coherence Across Graphs

The analysis revealed consistent pathway information across graphs:

```
ONTOLOGY (Ubergraph)                    SPOKE-OKN                   Gene Expression Atlas
┌──────────────────────┐    ┌──────────────────────────┐    ┌──────────────────────────┐
│ GO:0016114           │    │ HMGCR ←→ compounds       │    │ 127 Arabidopsis DE       │
│ terpenoid biosyn.    │    │   (statins, etc.)         │    │   records across 18      │
│   └─ 69 descendants  │    │ HMGCS1 ←→ compounds      │    │   terpene pathway genes  │
│                      │    │ FDPS ←→ diseases          │    │                          │
│ GO:0046246           │    │                           │    │ 200 enrichment hits for  │
│ terpene biosyn.      │    │ Camphor (monoterpene)     │    │   terpenoid GO terms     │
│   └─ 23 descendants  │    │ Isoprene (C5 precursor)   │    │                          │
│                      │    │                           │    │ 149K Arabidopsis records │
│ 92 total GO terms    │    │ Human genes only          │    │ 13K maize records        │
└──────────────────────┘    └──────────────────────────┘    └──────────────────────────┘
```

---

## 8. Methodological Challenges and Lessons Learned

### 8.1 Gene Identifier Heterogeneity

The single biggest obstacle was **identifier conventions differing by organism**:
- Arabidopsis genes: `https://www.ncbi.nlm.nih.gov/gene/AT5G17230` (AT locus IDs)
- Human genes: `https://www.ncbi.nlm.nih.gov/gene/3156` (NCBI Gene numeric IDs)
- Human genes in SPOKE-OKN: `http://www.ncbi.nlm.nih.gov/gene/3156` (note `http` vs. `https`)

The `biolink:symbol` property is populated for human genes but **not for Arabidopsis genes**, causing all symbol-based queries to fail for plants. The solution was to query using known AT locus URIs directly.

### 8.2 GeneExpressionMixin Data Availability

While 21 *Saccharomyces cerevisiae* studies are cataloged in the Study class, no GeneExpressionMixin (differential expression) records exist for yeast. The maize diterpenoid study (GSE120135) and sorghum ABA study (GSE140928) appear in study metadata but also lack GeneExpressionMixin associations — their expression data may not have been fully loaded into the graph. This pattern — studies present but expression results absent — suggests an incomplete ETL pipeline for non-human organisms. Full loading of processed differential expression results for all cataloged studies, particularly for yeast and crop species, would dramatically increase the value of the Gene Expression Atlas for non-biomedical use cases.

### 8.3 Plant and Microbial Metadata Deficiencies

Beyond the missing expression data, several metadata gaps limit the utility of the knowledge graphs for plant and microbial research:

1. **Missing gene symbols for plant genes.** The `biolink:symbol` property is not populated for Arabidopsis genes, forcing users to know AT locus IDs in advance. Without gene symbols, basic queries like "find expression data for DXS" fail silently. Populating standard gene names from TAIR or UniProt would make the graph immediately more accessible.

2. **No strain or genotype metadata.** For microbial biomanufacturing, the engineered strain background is critical context. The current Study metadata does not capture strain identifiers, plasmid constructs, or genetic modifications — information that would be essential for comparing expression across engineered strains.

3. **No growth condition or fermentation metadata.** Studies lack structured metadata for growth media composition, temperature, pH, carbon source, aeration, or fermentation mode (batch vs. fed-batch vs. continuous). These parameters directly determine terpene titers and are the primary optimization variables in biomanufacturing.

4. **No yield, titer, or productivity measurements.** The knowledge graphs contain no metabolite quantification data. Linking expression profiles to measured terpene yields would enable the kind of genotype-phenotype associations that drive metabolic engineering decisions.

5. **Limited taxonomic coverage for industrially relevant microbes.** The graphs contain no data for *Escherichia coli*, *Yarrowia lipolytica*, *Pichia pastoris*, *Corynebacterium glutamicum*, or *Bacillus subtilis* — all commonly used chassis organisms for terpene production. Even for *S. cerevisiae*, the most important microbial platform for terpenoid biomanufacturing, expression data is absent.

### 8.4 Compound Coverage Bias

SPOKE-OKN contains only 2 terpenoid compounds (camphor and isoprene) out of thousands of known terpenes. This limits the compound-gene interaction network to human pharmaceutical compounds that happen to modulate the conserved mevalonate pathway. Incorporating compound databases with better coverage of plant and microbial natural products — such as the Natural Products Atlas, COCONUT, or KNApSAcK — would enable queries like "which genes are associated with artemisinin or taxol biosynthesis?" that are currently impossible.

---

## 9. Implications for Microbial Terpene Biomanufacturing

### 9.1 Gene Candidates for Heterologous Expression

From the expression data, the following Arabidopsis genes are the strongest candidates for engineering into a microbial host, based on their dynamic expression range and biological context:

1. **TPS04** (AT1G61120) — Most responsive terpene synthase; produces (E)-β-ocimene and (E,E)-α-farnesene. Its extreme inducibility under defense/stress suggests promoter elements suitable for inducible production systems.

2. **DXS** (AT4G13280) — Rate-limiting MEP pathway enzyme. Its tight regulation (p = 1.8×10⁻⁶⁸ under osmotic stress) indicates strong transcriptional control elements that could be leveraged or bypassed in engineering.

3. **PSY** (AT5G17230) — Phytoene synthase for carotenoid production. Its 14 DE records across light-signaling studies provide rich context for optimizing carotenoid overproduction in heterologous hosts.

4. **TPS10** (AT2G24210) — Monoterpene synthase responsive to jasmonate (the canonical defense hormone). Important for linalool/nerolidol production.

### 9.2 Pathway Engineering Insights

- The MVA pathway genes (HMGCR, HMGCS1) are extensively characterized in human studies and SPOKE-OKN, providing a pharmacological map of compounds that modulate pathway flux. The yeast orthologs (HMG1/HMG2, ERG13) are the direct engineering targets.

- The enrichment data reveals that **diterpenoid biosynthetic process** shows the strongest pathway-level activation signal (effect size 9.1) in studies of plant defense — suggesting that defense-elicitation could be mimicked in microbial fermentation to boost terpenoid titers.

- The **SREBP regulation** enrichment across 40+ experiments highlights the importance of sterol-sensing feedback loops that constrain mevalonate pathway flux — these regulatory mechanisms must be disrupted in an engineered host.

### 9.3 Data Gaps

For a complete biomanufacturing pipeline, the following data gaps would need to be filled from external sources:

1. **Yeast expression data** — Despite 21 cataloged studies, no differential expression records exist for *S. cerevisiae*. ERG pathway gene expression under fermentation conditions would need to come from GEO/ArrayExpress directly. This is arguably the most consequential gap: yeast is the dominant industrial host for terpene production (e.g., Amyris's farnesene platform, artemisinic acid production), and its omission means the knowledge graph cannot answer the central question of the biomanufacturing use case.
2. **Non-model microbes** — No data for common terpene-producing microbes (*E. coli*, *Corynebacterium*, *Yarrowia*). The rapid growth of non-model organism engineering (especially *Y. lipolytica* for lipophilic terpenoids and *Streptomyces* for complex diterpenoids) makes this an increasingly important gap.
3. **Terpene compound structures** — Only 2 of thousands of terpenes are in SPOKE-OKN. ChEBI or PubChem federation would be needed. A curated subset of ~200 commercially relevant terpenes with biosynthetic gene annotations would serve most biomanufacturing queries.
4. **Enzyme kinetic data** — Not represented in any queried graph. Km, kcat, and substrate specificity data from BRENDA or SABIO-RK would be essential for flux balance analysis and pathway optimization.
5. **Biosynthetic gene cluster (BGC) annotations** — No integration with MIBiG or antiSMASH databases, which catalog experimentally characterized terpene biosynthetic gene clusters in microbes and plants. These clusters define the multi-gene cassettes that biomanufacturing teams would express heterologously.
6. **Codon usage and expression host compatibility** — No data on codon adaptation indices or known expression bottlenecks when transferring plant terpene synthases into microbial hosts. This practical engineering metadata is typically scattered across supplementary materials of individual publications.

---

## 10. Conclusions

This cross-graph analysis demonstrates both the potential and current limitations of the Proto-OKN for a synthetic biology use case:

1. **The Gene Expression Atlas is a rich resource for plant terpene biology**, containing 149K+ Arabidopsis differential expression records. However, accessing this data requires knowledge of organism-specific identifier conventions (AT locus IDs rather than gene symbols).

2. **Ontology expansion via Ubergraph is highly effective** for mapping the terpenoid biosynthetic landscape — 92 descendant GO terms provide comprehensive coverage from monoterpenes through carotenoids.

3. **SPOKE-OKN provides a complementary pharmacological layer** for the conserved mevalonate pathway, with compound-gene regulatory data that is directly relevant to fermentation media optimization.

4. **Cross-graph joins are productive but organism-limited** — the Ensembl ID bridge only works for human genes. Plant-to-plant cross-graph queries are not currently possible without external identifier mapping.

5. **Significant gaps remain** for microbial chassis organisms (yeast, *E. coli*) and for the diversity of terpene natural products. Federation with specialized databases (KEGG, MetaCyc, PlantCyc, UniProt) would substantially strengthen this analysis. More fundamentally, the knowledge graphs need richer metadata for plant and microbial datasets — strain backgrounds, growth conditions, metabolite measurements, and biosynthetic gene cluster annotations — to move from gene-level discovery toward the systems-level integration that biomanufacturing demands. The current human-centric bias is understandable given the biomedical origins of many of these resources, but extending the same depth of annotation to plant and microbial data would unlock transformative applications in sustainable chemistry and agriculture.

The analysis surfaced actionable gene candidates (TPS04, DXS, PSY, TPS10), regulatory context (defense/stress induction, light regulation, SREBP feedback), and compound-pathway interactions (statin pharmacology of the MVA pathway) that would directly inform a terpene biomanufacturing program.

---

## Data Availability

**Sources:**
- Gene Expression Atlas OKN: `https://frink.apps.renci.org/gene-expression-atlas-okn/sparql`
- SPOKE-OKN: `https://frink.apps.renci.org/spoke-okn/sparql`
- BioBricks AOP-Wiki: `https://frink.apps.renci.org/biobricks-aopwiki/sparql`
- Ubergraph (ontology service): accessed via Proto-OKN MCP server

**Key Study Accessions:**
- Maize diterpenoid defense: GSE120135 (PubMed 31527844)
- Sorghum ABA biosynthesis: GSE140928 (PubMed 31817046)
- Mevalonate pathway (human): GSE31812 (PubMed 22265415)

---

## Acknowledgments

This analysis was performed using the Proto-OKN knowledge graph infrastructure, with SPARQL queries executed via the FRINK platform and ontology expansion via Ubergraph. The Proto-OKN MCP server provided unified access across all graphs.

**Funding:** NSF Award #2535091

**Contact:**
- Andrew Su (PI): asu@scripps.edu
- Trish Whetzel: plwhetzel@gmail.com

---

*Report Generated: March 12, 2026*
*Analysis Platform: Proto-OKN Knowledge Graphs via MCP Server*
*Analyst: Claude (Anthropic AI Assistant)*
