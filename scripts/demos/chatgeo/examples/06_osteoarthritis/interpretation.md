# Osteoarthritis in Knee — Biological Interpretation

## Overview

Analysis of 192 osteoarthritis vs 81 healthy knee samples (after quality
filtering) identified 3,474 upregulated and 2,965 downregulated genes
(DESeq2, FDR < 0.05, |log2FC| >= 1.0).

## Top Differentially Expressed Genes

### Upregulated genes: innate immune infiltration and inflammation

The top upregulated genes are dominated by innate immune cell markers,
reflecting the inflammatory component of OA synovial tissue:

**Neutrophil/granulocyte markers** (highest fold changes):

- **CXCR1** (log2FC +10.7): IL-8 receptor, expressed on neutrophils.
- **FCGR3B** (+10.5): Fc gamma receptor IIIb, neutrophil-specific.
- **ADGRE3** (+10.2): Adhesion GPCR, expressed on neutrophils/monocytes.
- **DEFA1B/DEFA3** (+10.2, +9.5): Alpha-defensins, neutrophil granule proteins.
- **FPR2** (+9.1): Formyl peptide receptor, neutrophil chemotaxis.
- **AQP9** (+9.0): Aquaporin 9, expressed in leukocytes.
- **S100A12** (+8.8): Calgranulin C, neutrophil-derived inflammatory marker.
  Elevated in OA synovial fluid and a proposed OA biomarker.
- **VNN2** (+9.0): Vanin 2, involved in neutrophil migration.

**Platelet markers** (likely from synovial fluid/blood):

- **GP9** (+10.4): Platelet glycoprotein IX.
- **PPBP** (+8.7): Platelet basic protein (CXCL7/NAP-2).

**Key OA-relevant inflammatory mediators** (significant but with moderate fold changes):

- **TNF** (+5.1, padj 4.4e-26): Tumor necrosis factor, central inflammatory
  cytokine in OA. Therapeutic target, though anti-TNF biologics have shown
  limited efficacy in OA compared to RA.
- **IL1B** (+4.7, padj 1.3e-24): Interleukin-1 beta, the canonical catabolic
  cytokine driving cartilage degradation. Target of anakinra trials in OA.
- **CXCL8** (+3.8, padj 2.8e-16): IL-8, neutrophil chemoattractant.
- **PTGS2** (+2.5, padj 1.0e-9): COX-2, the direct target of NSAIDs and
  coxibs (celecoxib), the mainstay of OA pharmacotherapy.
- **IL6** (+1.8, padj 1.7e-4): Inflammatory cytokine elevated in OA joints.
- **MMP1** (+1.3): Collagenase 1, degrades type II collagen.
- **MMP9** (+1.7): Gelatinase B, matrix degradation.
- **RUNX2** (+1.2): Transcription factor driving chondrocyte hypertrophy,
  a key feature of OA cartilage degeneration.

### Downregulated genes: cartilage matrix loss and chondrocyte dysfunction

The downregulated genes directly reflect the hallmark of OA — progressive
loss of articular cartilage:

**Cartilage matrix structural proteins**:

- **COL2A1** (-2.9): Type II collagen, the primary collagen in hyaline
  cartilage. Its downregulation is the defining molecular feature of OA.
- **ACAN** (-2.0): Aggrecan, the major proteoglycan in cartilage.
- **COMP** (-2.8): Cartilage oligomeric matrix protein, a biomarker of
  cartilage turnover (measured in serum for OA monitoring).
- **HAPLN1** (-2.0): Link protein that stabilizes aggrecan-hyaluronan
  aggregates in the cartilage matrix.
- **FMOD** (-2.2): Fibromodulin, a small leucine-rich proteoglycan.
- **BGN** (-1.2): Biglycan, a cartilage ECM proteoglycan.

**Chondrocyte regulatory genes**:

- **SOX9** (-2.6): The master transcription factor for chondrocyte
  differentiation and COL2A1 expression. SOX9 loss drives the shift from
  chondrocyte to hypertrophic/degradative phenotype in OA.
- **COL10A1** (-2.2): Type X collagen, a marker of chondrocyte hypertrophy.
- **WNT16** (-1.6): Wnt pathway gene identified in OA GWAS studies.

**Joint-specific proteins**:

- **PRG4** (-1.3): Lubricin, essential for joint lubrication. PRG4
  deficiency causes cartilage damage in camptodactyly-arthropathy syndrome.
- **CHAD** (-5.0): Chondroadherin, mediates chondrocyte-matrix interactions.
- **CYTL1** (-5.1): Cytokine-like 1, promotes chondrogenesis.
- **UCMA** (-4.6): Upper zone of cartilage matrix-associated protein.

**Other notable downregulated genes**:

- **SOST** (-5.8): Sclerostin, inhibitor of Wnt/bone formation. OA is
  associated with altered subchondral bone remodeling.
- **MT1M/MT1X** (-4.7, -4.6): Metallothioneins, metal-binding stress response
  proteins highly expressed in cartilage.
- **SCX** (-4.8): Scleraxis, a tendon/ligament transcription factor.
- **ADAMTS4** (-1.2): Aggrecanase 1 — downregulated rather than upregulated,
  possibly reflecting chondrocyte loss (fewer cells to produce ADAMTS4) or
  the specific tissue composition of the samples.
- **TNFRSF11B** (-1.2): Osteoprotegerin (OPG), a decoy receptor for RANKL
  that inhibits osteoclastogenesis. Its loss suggests increased bone turnover.
- **VEGFA** (-1.5): Normally upregulated in OA cartilage (angiogenesis), but
  downregulation here may reflect control pool composition.

## Enrichment Analysis

### Upregulated pathway enrichment (1,275 terms)

The upregulated enrichment is overwhelmingly immune/inflammatory:

- **Immune system process** (GO:0002376, padj 2.4e-167, 964 genes)
- **Immune response** (GO:0006955, padj 4.4e-151, 760 genes)
- **Regulation of immune system process** (GO:0002682, padj 6.5e-128, 608 genes)
- **Defense response** (GO:0006952, padj 1.4e-125, 668 genes)
- **Cell activation** (GO:0001775, padj 1.3e-116, 479 genes)
- **Leukocyte activation** (GO:0045321, padj 1.0e-111, 432 genes)
- **Signal transduction** (GO:0007165, padj 1.9e-94, 1386 genes)

This reflects the inflammatory synovitis that accompanies OA. While OA was
historically classified as "non-inflammatory" arthritis (vs. RA), modern
understanding recognizes a significant inflammatory component, particularly
in the synovium. These enrichment results are consistent with activated
innate immune pathways (neutrophils, macrophages) rather than the adaptive
immune (T/B cell) signature seen in RA.

### Downregulated pathway enrichment (275 terms)

- **Ribosomal subunit** (GO:0044391, padj 4.6e-40, 100 genes)
- **SRP-dependent cotranslational protein targeting** (REAC:R-HSA-1799339, padj 3.7e-30, 70 genes)
- **Eukaryotic Translation Elongation** (REAC:R-HSA-156842, padj 6.2e-30, 63 genes)
- **Ribosome** (KEGG:03010, padj 4.3e-29, 80 genes)
- **Developmental process** (GO:0032502, padj 5.2e-23, 1010 genes)

The striking downregulation of ribosomal and translational machinery
suggests reduced protein synthesis capacity in OA tissue. Chondrocytes in
OA cartilage undergo senescence and lose their biosynthetic capacity —
they can no longer maintain the cartilage matrix (consistent with
COL2A1/ACAN/COMP downregulation). The ribosomal signature may reflect
this shift from anabolic to catabolic chondrocyte phenotype.

## Comparison with Rheumatoid Arthritis

The OA signature differs from the RA example (#3) in several ways:

| Feature | OA (this analysis) | RA (example #3) |
|---------|-------------------|-----------------|
| Top immune markers | Neutrophil (CXCR1, FCGR3B, S100A12) | T cell (CD3E, IFNG) |
| Key cytokines | IL1B, TNF, CXCL8 | IL6, TNF, IFNG, CXCL9/10 |
| Dominant enrichment | Innate immunity, defense response | Adaptive immunity (JAK-STAT) |
| Cartilage genes | COL2A1, ACAN, COMP downregulated | COL2A1, ACAN downregulated |
| Unique to OA | PTGS2 (COX-2 target), RUNX2, SOST | JAK2, STAT1 |

## Limitations

- **Sample heterogeneity**: The 200 test samples span 69 studies and likely
  include diverse tissue types (articular cartilage, synovium, meniscus,
  subchondral bone). The dominant neutrophil/platelet signature suggests
  many samples contain synovial fluid or vascularized tissue.
- **Blood contamination**: GP9, PPBP, and other platelet markers suggest
  some samples contain blood components.
- **OA stage not controlled**: OA ranges from early cartilage softening
  (KL grade 1) to bone-on-bone (KL grade 4), with different molecular profiles.
- **ADAMTS4/5 paradox**: Aggrecanases are expected to be upregulated in OA
  but appear downregulated here, likely reflecting tissue composition
  (fewer chondrocytes in damaged tissue) rather than per-cell expression.

## Conclusion

The analysis correctly identifies the two central features of OA biology:
**(1) inflammatory activation** (TNF, IL1B, PTGS2/COX-2, neutrophil
infiltration) and **(2) cartilage matrix degradation** (loss of COL2A1,
ACAN, SOX9, COMP, PRG4). The COX-2 upregulation directly corresponds to
the mechanism of action of NSAIDs, the most widely used OA treatment. The
SOX9 downregulation and RUNX2 upregulation together capture the
chondrocyte phenotype shift from matrix-maintaining to hypertrophic/catabolic
that defines OA progression. The ribosomal pathway downregulation provides
additional evidence for reduced biosynthetic capacity in OA cartilage.
This is a biologically strong result that aligns well with current
understanding of OA pathophysiology.
