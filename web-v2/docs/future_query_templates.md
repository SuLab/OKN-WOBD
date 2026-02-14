# Future Query Templates (Roadmap)

This document records **planned FRINK-only query templates** derived from the biological question demos in `scripts/demos`. These templates are not yet implemented; the dashboard and slot form design should anticipate adding these template IDs and slots later.

## Planned FRINK-only templates (from `scripts/demos`)

### Gene–disease map (Q1)

- **Question:** What diseases is {gene} connected to, and through what mechanisms?
- **Data sources:** SPOKE-OKN, Ubergraph (Wikidata used in demos but optional for “FRINK only”).
- **Slot:** `gene_symbol`
- **Status:** New template required. Would query SPOKE-OKN and/or Ubergraph for gene–disease paths (markers, GO pathways, etc.).

### Gene neighborhood (Q2)

- **Question:** What is the biological neighborhood of {gene} across FRINK knowledge graphs?
- **Data sources:** SPOKE-OKN, SPOKE-GeneLab, NDE, BioBricks-AOPWiki (all FRINK).
- **Slot:** `gene_symbol`
- **Status:** New template required. Would query multiple FRINK graphs for the immediate neighborhood of a gene (related entities, types, predicates).

### Drug vs disease opposing expression (Q5, optional)

- **Question:** What genes show opposing drug vs disease expression?
- **Data sources:** GXA (FRINK) only.
- **Status:** Could be a dedicated template with slots for drug/disease direction, or documented use of existing `gene_expression_genes_discordance` with factor filters (drug vs disease semantics).

---

No implementation in the current dashboard work; this is design/roadmap documentation only.
