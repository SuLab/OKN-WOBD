# Alzheimer Disease in Brain — Biological Interpretation

## Overview

Analysis of 4 Alzheimer disease vs 200 healthy brain samples (after quality
filtering) identified 11 upregulated and 468 downregulated genes (DESeq2,
FDR < 0.05, |log2FC| >= 1.0).

## Top Differentially Expressed Genes

### Upregulated genes reflect neuronal and neuropeptide signatures

All 11 upregulated genes are neuronal markers:

- **NPY** (log2FC +8.79): Neuropeptide Y, one of the most abundant
  neuropeptides in the brain. NPY is involved in memory, feeding, circadian
  rhythms, and stress response. Studies show altered NPY levels in AD,
  though the direction varies by brain region.
- **CORT** (+7.48): Cortistatin, a neuropeptide related to somatostatin.
  Cortistatin has neuroprotective properties and modulates inflammatory
  responses in the CNS.
- **GPR88** (+7.31): Orphan G protein-coupled receptor enriched in the
  striatum. Involved in reward and motor behavior.
- **GRIN2B** (+7.24): NMDA receptor subunit NR2B, critical for synaptic
  plasticity and memory. GRIN2B is a focus of AD drug development as NMDA
  receptor dysfunction is central to excitotoxicity in neurodegeneration.
- **HIGD1B** (+7.70): Hypoxia-inducible gene domain family member,
  involved in cytochrome c oxidase assembly.
- **ANO3** (+5.66): Anoctamin 3 (TMEM16C), a calcium-activated chloride
  channel expressed in sensory neurons.
- **ENHO** (+5.46): Adropin, a secreted peptide involved in energy
  homeostasis and neuroprotection.
- **TCAP** (+4.33): Titin-cap/telethonin, involved in sarcomere assembly
  but also expressed in brain.
- **SLC25A41** (+4.31): Mitochondrial carrier family member.
- **FTCD** (+7.78): Formiminotransferase cyclodeaminase, involved in
  histidine catabolism and folate metabolism.
- **SYNDIG1L** (+7.63): Synapse differentiation inducing gene 1-like,
  involved in synapse development.

### Downregulated genes reflect immune and epithelial signatures

The downregulated genes are dominated by immune and epithelial markers
absent from brain tissue:

- **LCN2** (-18.2): Lipocalin 2, an acute-phase protein. Its extreme
  downregulation reflects absence in brain vs presence in control samples
  that may include non-brain tissue.
- **KRT16** (-14.5), **KRT6A** (-13.9): Keratinocyte keratins, suggesting
  the control pool contains skin or epithelial samples.
- **HLA-DRA** (-10.6), **HLA-DOA** (-11.4): MHC class II molecules,
  reflecting reduced antigen presentation. This could reflect genuine
  microglial changes in AD or control pool composition.
- **CTSG** (-11.7): Cathepsin G, a neutrophil serine protease.
- **MMP12** (-11.4): Matrix metalloproteinase 12, macrophage elastase.
- **CXCL13** (-11.1): B cell chemoattractant.
- **GZMB** (-10.1): Granzyme B, cytotoxic lymphocyte effector.

The extreme fold changes and zero/near-zero expression in test samples
indicate that many of these "downregulated" genes are not truly
repressed in AD brain but rather reflect tissue composition differences
between the 4 AD brain samples and the heterogeneous control pool.

## Enrichment Analysis

### Upregulated pathway enrichment (6 terms)

With only 11 upregulated genes, enrichment power is very limited. The
6 significant terms are:

- **Hormone activity** (GO:0005179, padj 3.8e-3, 3 genes)
- **Neuropeptide hormone activity** (GO:0005184, padj 1.2e-2, 2 genes)
- **Neuropeptide activity** (GO:0160041, padj 1.3e-2, 2 genes)
- **Neuroactive ligand-receptor interaction** (KEGG:04080, padj 3.6e-2, 3 genes)
- **Detection of external stimulus** (GO:0009581, padj 4.2e-2, 3 genes)
- **Detection of abiotic stimulus** (GO:0009582, padj 4.5e-2, 3 genes)

The neuropeptide and neuroactive receptor terms are consistent with
the neuronal identity of the upregulated genes (NPY, CORT, GRIN2B).
These reflect the brain-specific signature of the test samples rather
than AD-specific pathology per se.

### Downregulated pathway enrichment (672 terms)

- **Immune system process** (GO:0002376, padj 3.1e-29, 155 genes)
- **Response to stimulus** (GO:0050896, padj 6.4e-28, 301 genes)
- **Cell activation** (GO:0001775, padj 1.6e-23, 86 genes)
- **Immune response** (GO:0006955, padj 1.8e-21, 116 genes)
- **Response to stress** (GO:0006950, padj 1.3e-20, 169 genes)
- **Regulation of immune system process** (GO:0002682, padj 5.4e-20, 97 genes)
- **Vesicle** (GO:0031982, padj 1.0e-19, 167 genes)
- **Immune System** (REAC:R-HSA-168256, padj 1.0e-19, 137 genes)
- **Leukocyte activation** (GO:0045321, padj 1.5e-19, 74 genes)
- **Lymphocyte activation** (GO:0046649, padj 2.2e-17, 64 genes)

The downregulated enrichment is overwhelmingly immune-related.
This primarily reflects the tissue composition effect: brain has far
fewer immune cells than the mixed-tissue control pool. However, there
may be a genuine AD component — reduced microglial antigen presentation
(HLA-DRA) and altered neuroimmune signaling have been reported in
late-stage AD, though this typically manifests as activation rather
than suppression of immune pathways.

## Limitations

- **Very small test set**: Only 4 AD brain samples from 1 study provide
  extremely limited statistical power. The 11 upregulated genes likely
  represent a small fraction of the true AD transcriptomic signature.
- **Control pool heterogeneity**: The 200 control samples span 147 studies
  and likely include non-brain tissues, explaining the extreme
  downregulation of keratins (KRT16, KRT6A) and neutrophil markers (CTSG).
- **Brain region not controlled**: AD pathology is region-specific
  (hippocampus, entorhinal cortex most affected). The query "alzheimer
  disease" + "brain" does not control for region, and the 4 test samples
  may come from a single region not matched to controls.
- **Stage not controlled**: AD is progressive; the transcriptomic signature
  differs between early (Braak I-II) and late (Braak V-VI) stages.
- **Known AD markers not detected**: Expected signatures like upregulation
  of APOE, TREM2, APP processing genes, tau phosphorylation cascades,
  and neuroinflammatory markers (IL1B, TNF, complement) are absent,
  likely due to insufficient sample size and control pool mismatch.

## Conclusion

The analysis identifies a brain-specific neuropeptide signature (NPY,
CORT, GRIN2B, SYNDIG1L) that distinguishes the AD brain samples from
the broader control pool. The neuropeptide enrichment is biologically
plausible for brain tissue. However, the dominant signal reflects
tissue-type differences rather than AD-specific pathology, and the
4-sample test set severely limits the ability to detect disease-specific
changes. This example illustrates both the potential and the limitations
of automated sample selection from ARCHS4: the pipeline successfully
found AD brain samples and detected brain-specific markers, but sample
size and control matching are insufficient for robust disease-specific
conclusions.
