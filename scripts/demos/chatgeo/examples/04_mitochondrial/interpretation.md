# Mitochondrial Myopathy in Muscle — Biological Interpretation

## Overview

Analysis of 15 mitochondrial myopathy vs 200 healthy muscle samples (after
quality filtering) identified 193 upregulated and 2,414 downregulated genes
(DESeq2, FDR < 0.05, |log2FC| >= 1.0).

## Top Differentially Expressed Genes

### Upregulated genes confirm mitochondrial dysfunction and compensatory response

- **FGF21** (log2FC +5.84, padj 1.0e-8): Fibroblast growth factor 21, a
  mitokine secreted by muscle in response to mitochondrial stress. FGF21 is
  an established clinical biomarker for mitochondrial myopathies and is
  elevated in patient serum. This is the strongest and most specific signal.
- **MT-ND3** (+2.47), **MT-ND2** (+2.42), **MT-ND1** (+2.19): Mitochondrial
  complex I (NADH dehydrogenase) subunits. Their upregulation reflects
  compensatory mitochondrial biogenesis in response to respiratory chain
  deficiency.
- **MT-ATP6** (+2.12): Mitochondrial ATP synthase subunit, part of complex V.
- **MT-CO3** (+2.12), **MT-CO1** (+2.01), **MT-CYB** (+2.02): Mitochondrial
  complex III and IV subunits, further confirming compensatory upregulation
  of the entire electron transport chain.
- **PRKACA** (+2.82): Catalytic subunit of protein kinase A. PKA signaling
  regulates mitochondrial dynamics and CREB-mediated mitochondrial biogenesis.
- **HSPB6** (+2.46): Small heat shock protein, a stress-response marker in
  skeletal muscle.
- **LCK** (+2.85), **CD3E** (+2.36), **CXCL9** (+3.62), **CXCL10** (+2.14):
  T cell markers and chemokines suggesting immune infiltration, consistent
  with inflammatory myopathy that can accompany mitochondrial disease.

### Downregulated genes reflect muscle tissue remodeling

- **H4C3** (-10.9), **H1-4** (-9.4), **H2AC19** (-7.9), **H1-3** (-7.5),
  **H4C5** (-6.9): Histone variants, reflecting altered chromatin state and
  possibly reduced cell proliferation in damaged muscle.
- **MMP1** (-8.8): Matrix metalloproteinase 1, collagenase involved in
  extracellular matrix remodeling.
- **PTX3** (-8.6): Pentraxin 3, innate immunity and tissue repair marker.
- **HSPA1A** (-7.0): Heat shock protein 70, stress response.
- **CEMIP** (-7.1): Hyaluronan-binding protein involved in ECM remodeling.
- **DKK1** (-7.3): Dickkopf-1, Wnt signaling inhibitor.
- **CXCL1** (-7.9): Neutrophil chemoattractant.

## Enrichment Analysis

### Upregulated pathway enrichment (116 terms)

The upregulated enrichment profile is a textbook match for mitochondrial
myopathy:

- **Aerobic respiration and respiratory electron transport** (REAC:R-HSA-1428517, padj 6.6e-17, 25 genes)
- **Mitochondrion** (GO:0005739, padj 2.9e-16, 55 genes)
- **Energy derivation by oxidation of organic compounds** (GO:0015980, padj 4.7e-16, 27 genes)
- **Aerobic respiration** (GO:0009060, padj 7.5e-16, 22 genes)
- **Mitochondrial envelope** (GO:0005740, padj 1.8e-14, 36 genes)
- **Mitochondrial membrane** (GO:0031966, padj 1.8e-14, 35 genes)
- **Mitochondrial inner membrane** (GO:0005743, padj 2.2e-14, 29 genes)
- **Cellular respiration** (GO:0045333, padj 5.2e-14, 22 genes)
- **Oxidative phosphorylation** (GO:0006119, padj 7.3e-11, 16 genes)
- **Respiratory chain complex** (GO:0098803, padj 8.5e-13, 15 genes)
- **Mitochondrial protein degradation** (REAC:R-HSA-9837999, padj 4.9e-11, 15 genes)

Every one of the top enriched terms directly relates to mitochondrial
function and oxidative phosphorylation. The 55 mitochondrial genes upregulated
reflect the known compensatory mitochondrial biogenesis response:
mitochondrial myopathy patients accumulate "ragged red fibers" (subsarcolemmal
mitochondrial proliferation) visible on muscle biopsy, and this gene
expression signature is the molecular correlate of that histopathological
finding.

The enrichment of **Parkinson disease** (KEGG:05012, padj 9.2e-11, 21 genes)
reflects shared mitochondrial dysfunction pathways between mitochondrial
myopathies and neurodegenerative diseases.

### Downregulated pathway enrichment (726 terms)

- **Cell periphery** (GO:0071944, padj 2.1e-66, 1005 genes)
- **Multicellular organismal process** (GO:0032501, padj 4.0e-60, 1084 genes)
- **Developmental process** (GO:0032502, padj 7.0e-55, 985 genes)
- **System development** (GO:0048731, padj 4.3e-54, 694 genes)
- **Cell communication** (GO:0007154, padj 7.8e-43, 945 genes)
- **Signaling** (GO:0023052, padj 2.7e-41, 937 genes)

The broad downregulation of developmental and signaling programs is
consistent with muscle atrophy and impaired regeneration in mitochondrial
myopathy. The loss of cell communication and signaling pathways reflects
the progressive degeneration of muscle fibers and disrupted neuromuscular
signaling.

## Limitations

- The 2:200 study ratio (15 test vs 200 control samples from different
  studies) introduces batch effects that DESeq2 partially mitigates but
  cannot fully resolve.
- Mitochondrial-encoded genes (MT-) are retained in this analysis (MT gene
  exclusion was disabled for this example) since they are central to the
  disease mechanism. In other contexts, their high copy number can
  disproportionately influence results.
- The large number of downregulated genes (2,414) likely reflects both
  true biology (muscle wasting) and compositional differences between
  diseased and healthy muscle.

## Conclusion

This analysis produces a highly disease-relevant signature. FGF21 as the
top upregulated gene is a validated clinical biomarker for mitochondrial
myopathy. The upregulated pathway enrichment is exclusively mitochondrial
(respiratory chain, oxidative phosphorylation, mitochondrial membranes),
directly reflecting the compensatory mitochondrial biogenesis that defines
this disease class. Among all five example analyses, this one shows the
strongest concordance between gene-level and pathway-level results, and
between computational findings and established disease biology.
