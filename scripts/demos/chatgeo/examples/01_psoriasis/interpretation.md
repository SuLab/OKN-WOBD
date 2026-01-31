# Psoriasis in Skin — Biological Interpretation

## Overview

Analysis of 66 psoriasis vs 131 healthy skin samples (after quality filtering)
identified 564 upregulated and 8,471 downregulated genes (DESeq2, FDR < 0.05,
|log2FC| >= 1.0).

## Top Differentially Expressed Genes

**Upregulated genes confirm the IL-17/Th17 pathway**, the central driver of
psoriasis pathogenesis:

- **IL17A** (log2FC +8.2): The hallmark psoriasis cytokine. All modern biologic
  therapies (secukinumab, ixekizumab, brodalumab) target this pathway.
- **IFNG** (+5.9): Th1 cytokine, part of the Th1/Th17 axis in psoriatic skin.
- **IL23R** (+4.3): Receptor for IL-23, the upstream activator of IL-17 production.
  Targeted by guselkumab, tildrakizumab, risankizumab.
- **CTLA4** (+5.7): T cell co-inhibitory receptor, reflecting activated T cells.
- **CXCR6**, **CCR6** (+5.8, +4.6): Chemokine receptors for T cell homing to skin.
- **LAG3**, **CD200R1**: Immune checkpoint molecules reflecting activated infiltrate.

**Antimicrobial/epidermal markers** correctly upregulated:

- **DEFB103A** (+4.9): Beta-defensin, antimicrobial peptide upregulated in psoriatic epidermis.
- **DEFB4A** (+3.6): Beta-defensin 2, another psoriasis-associated AMP.
- **S100A7** (+3.0): Psoriasin, a classic psoriasis biomarker.
- **SERPINB4** (+3.2): Squamous cell carcinoma antigen, epidermal differentiation marker.
- **IL36G** (+2.3): IL-36 gamma, key inflammatory cytokine in psoriasis. Targeted
  by spesolimab for generalized pustular psoriasis.
- **SPRR2A/B/F** (+4.1 to +4.9): Small proline-rich proteins, cornified envelope
  components reflecting epidermal hyperproliferation.

**Downregulated genes** include extracellular matrix and dermal structural genes
(FN1, SULF1, LOXL2, SPARC), consistent with tissue remodeling.

## Enrichment Analysis

**Upregulated pathways** (262 terms) are dominated by:

- **T cell activation** (GO:0042110, padj 2.9e-18)
- **Lymphocyte activation** (GO:0046649, padj 5.2e-19)
- **Immune system process** (GO:0002376, padj 2.0e-17)
- **Regulation of immune system process** (GO:0002682, padj 4.4e-18)

These terms directly reflect the adaptive immune infiltrate in psoriatic lesions
and are consistent with the Th17-driven pathogenesis model.

## Limitations

- S100A8 and S100A9 (calprotectin subunits) show the correct direction (+1.5,
  +1.1 log2FC) but did not reach significance, likely due to sample heterogeneity.
- KRT16/17 (hyperproliferation keratins) were not significantly upregulated,
  possibly because the "psoriasis" metadata search captures blood-derived or
  non-lesional skin samples alongside lesional biopsies.
- The large number of downregulated genes (8,471) partly reflects compositional
  differences (immune-rich psoriatic tissue vs fibroblast-rich normal skin).

## Conclusion

The analysis correctly identifies the IL-17/Th17 axis, antimicrobial peptide
response, and T cell infiltration as the primary signatures of psoriasis.
These results align with current biological understanding and the mechanism
of action of approved psoriasis therapeutics.
