# Pulmonary Fibrosis in Lung — Biological Interpretation

## Overview

Analysis of 200 pulmonary fibrosis vs 200 healthy lung samples (after quality
filtering) identified 4,456 upregulated and 1,982 downregulated genes (DESeq2,
FDR < 0.05, |log2FC| >= 1.0).

## Top Differentially Expressed Genes

### Upregulated genes are dominated by liver-specific markers

The top 20 upregulated genes are almost entirely hepatocyte markers:

- **ALB** (log2FC +16.4): Serum albumin, the most abundant liver protein.
- **APOC3**, **APOB**, **APOA2**, **APOA1**: Apolipoproteins synthesized in liver.
- **GC** (+14.0): Vitamin D binding protein, liver-produced.
- **AHSG** (+13.7): Alpha-2-HS-glycoprotein (fetuin-A), liver-secreted.
- **CYP3A4**, **CYP2E1**, **CYP2C8/9**: Cytochrome P450 enzymes (drug metabolism).
- **SERPINC1** (+13.2), **KNG1** (+13.2), **F9** (+13.0): Coagulation factors.
- **ALDOB** (+12.7): Fructose-bisphosphate aldolase B, liver/kidney glycolytic enzyme.
- **CRP** (+12.4): C-reactive protein, acute-phase reactant made in liver.

This liver gene signature strongly suggests that the ARCHS4 metadata search for
"pulmonary fibrosis" captured samples from multiple tissue types, likely
including liver biopsies from fibrosis patients (hepatic fibrosis is a common
comorbidity) or studies examining systemic effects.

### Downregulated genes correctly reflect loss of alveolar epithelial markers

Despite the liver contamination in the test group, the downregulated genes
contain biologically meaningful signals:

- **SFTPA1/A2** (-5.8, -6.7): Surfactant protein A isoforms.
- **SFTPB** (-5.7): Surfactant protein B.
- **SFTPC** (-6.1): Surfactant protein C, the most specific type II
  pneumocyte marker.
- **SFTPD** (-5.1): Surfactant protein D.
- **NAPSA** (-5.6): Napsin A, processes surfactant proteins in type II cells.
- **AGER** (-5.5): RAGE receptor, the most specific marker of type I alveolar
  epithelial cells. Loss of AGER is a hallmark of IPF.

The downregulation of surfactant proteins and AGER is consistent with
destruction of the alveolar epithelium in pulmonary fibrosis, where both
type I and type II pneumocytes are progressively lost and replaced by
fibroblastic foci.

**MAGE family cancer-testis antigens** (MAGEA6/4/2/3/1) are among the most
downregulated genes. These are normally silenced in somatic tissue and their
presence in controls likely reflects the heterogeneous control pool.

## Enrichment Analysis

### Upregulated pathway enrichment (676 terms)

The top enriched terms are all olfactory/sensory:

- **Detection of chemical stimulus involved in sensory perception** (GO:0050907, padj 1.1e-168)
- **Sensory perception of chemical stimulus** (GO:0007606, padj 1.1e-163)
- **Olfactory receptor activity** (GO:0004984, padj 5.0e-148)
- **G protein-coupled receptor activity** (GO:0004930, padj 1.8e-151)

This is a well-known artifact in differential expression analyses that compare
across tissue types. Olfactory receptors (ORs) are low-expression genes spread
across many chromosomes. When a large number of genes shift in one direction
(as occurs with tissue-type confounding), ORs are swept up in bulk, producing
these extreme but biologically meaningless enrichments. This artifact is
further evidence of tissue-type confounding in the test set.

### Downregulated pathway enrichment (962 terms)

- **Anatomical structure development** (GO:0048856, padj 3.5e-69)
- **Developmental process** (GO:0032502, padj 1.1e-64)
- **Extracellular region** (GO:0005576, padj 1.6e-54)
- **Extracellular space** (GO:0005615, padj 2.3e-50)
- **Tissue development** (GO:0009888, padj 3.3e-48)
- **Cell motility / migration** (GO:0048870/0016477)

Extracellular region and tissue development terms are consistent with the
known pathology of IPF: disruption of normal lung architecture, loss of
alveolar structure, and aberrant extracellular matrix remodeling. However,
these broad developmental terms likely also reflect the tissue-type mixing
effect rather than fibrosis-specific biology alone.

## Limitations

- **Tissue-type confounding**: The dominant signal is liver vs lung, not
  fibrotic vs healthy lung. The metadata search for "pulmonary fibrosis"
  captured samples from non-lung tissues, overwhelming the fibrosis-specific
  signal.
- **Olfactory receptor artifact**: The top upregulated pathways are entirely
  olfactory receptors, a known artifact of tissue-type comparisons.
- **True fibrosis markers partially obscured**: COL1A1, COL3A1, FN1, POSTN,
  and other fibrosis hallmarks may be present but buried under liver gene
  signal. A tissue-restricted reanalysis would be needed.

## Conclusion

The analysis correctly identifies loss of surfactant proteins (SFTPA1/A2,
SFTPB, SFTPC, SFTPD) and AGER as hallmarks of alveolar epithelial
destruction in pulmonary fibrosis. However, the primary upregulated signal
reflects tissue-type confounding (liver-derived samples in the test set)
rather than fibrosis-specific pathways. This example illustrates a key
limitation of automated metadata-based sample selection: the query
"pulmonary fibrosis" + "lung" did not sufficiently exclude non-lung samples
from fibrosis patient cohorts. Refining the query or adding explicit tissue
filtering would improve biological specificity.
