# Drug_datasets template: test case

This document describes how to test the **drug_datasets** template.

## What the template does

1. **Step 1:** Resolve drug name(s) to Wikidata IRIs.
2. **Step 2:** Find diseases treated by the drug in Wikidata (with MONDO IDs).
3. **Step 3:** Find NDE datasets for those diseases (optionally GEO-only when “Only gene expression” is checked).
4. **Step 4:** For each NDE result, check GXA (gene-expression-atlas-okn) for coverage by experiment ID (e.g. GSE76 → E-GEOD-76); attach contrast count and SPOKE-GeneLab study URL when present.

The optional “Related genes from SPOKE-GeneLab” feature was removed: the GXA/EFO overlap for common drug→disease MONDO terms was insufficient to return useful gene counts, and an ARCHS4 backend is out of scope for this demo.

## Recommended test case (NDE + GXA coverage)

- **Drug:** `methotrexate`
- **Options:** Check “Only show datasets with gene expression data”.
- **Expected:**
  - Step 2 returns diseases (e.g. rheumatoid arthritis, psoriasis) with MONDO.
  - Step 3 returns NDE datasets; with “Only gene expression” these are GEO (GSE*) datasets for those diseases.
  - Step 4 annotates rows with GXA coverage where the NDE identifier maps to an E-GEOD-* experiment in the GXA graph. Rows with coverage show contrast count and a “SPOKE-GeneLab” link to `https://spoke.ucsf.edu/genelab/E-GEOD-*`.

Other drugs that treat diseases with GEO data in NDE (e.g. atherosclerosis, major depressive disorder, glioblastoma) can also be used to test NDE + optional GXA coverage.

## Connection to `scripts/demos` (same repo)

The same FRINK **gene-expression-atlas-okn** graph is used in [scripts/demos](https://github.com/SuLab/OKN-WOBD/tree/main/scripts/demos) (e.g. Q5 Drug–disease targets, Q2 Gene neighborhood). The drug_datasets template uses it only for experiment-level coverage and SPOKE-GeneLab study links, not for a gene summary.
