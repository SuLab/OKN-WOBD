# Build plan: `dataset_search` — keywords + optional facets

**Use in a new chat:** attach or `@`-mention this file and ask the agent to *implement this plan*. All paths are relative to the repo root `OKN-WOBD/`.

## Checklist (implementation order)

1. [ ] **SPARQL** — Add `buildNDEDatasetKeywordAndFacetQuery` (or equivalent) in `web-v2/lib/ontology/templates.ts`: keywords `REGEX` on `schema:name` / optional `schema:description`; optional AND filters on `schema:healthCondition`, `schema:species`, `schema:infectiousAgent` via linked `DefinedTerm` + `schema:name` (and IRI match when input looks like a URI). Support `geoOnly` (GEO identifier filter) like the current keyword query in `dataset_search.ts`.
2. [ ] **Template** — In `web-v2/lib/templates/templates/dataset_search.ts`, on the **non–ontology-workflow** keyword branch, read `health_condition`, `species`, `infectious_agent` from `intent.slots` and call the new builder. Preserve existing ontology branches unless trivial to unify.
3. [ ] **Pack** — `web-v2/context/packs/wobd.yaml`: `dataset_search` → `optional_slots: [health_condition, species, infectious_agent]` (keep `required_slots: [keywords]`).
4. [ ] **UI** — `web-v2/components/dashboard/SlotForm.tsx`: `SLOT_LABELS` for the three slots; use `OrganismAutocomplete` for `species`; plain text for `health_condition` and `infectious_agent`.
5. [ ] **Copy** — `web-v2/lib/landing/template-meta.ts`: update `dataset_search` blurb/description to mention optional filters.
6. [ ] **Verify** — `/template/dataset_search` and `/template/geo_dataset_search` (keywords only; + each filter; + combined).

## Scope

| Slot | Required? | RDF path (from `src/okn_wobd/rdf_converter.py`) |
|------|-------------|--------------------------------------------------|
| `keywords` | **Yes** | `REGEX` on `schema:name` / optional `schema:description` |
| `health_condition` | No | `schema:healthCondition` → term + `schema:name` (and/or MONDO IRI) |
| `species` | No | `schema:species` → term + `schema:name` (and/or UniProt taxonomy IRI) |
| `infectious_agent` | No | `schema:infectiousAgent` → term + `schema:name` |

- **AND** semantics across filled optional slots; empty slots ignored.
- **Out of scope:** repository, funder, author, dates, `topicCategory`, changes to `rdf_converter.py`.

## Consumer note

`buildDatasetSearchQuery` is shared: **template page** (`runTemplateQuery` → `intent-to-sparql`) and any **chat** path that emits `task: dataset_search` with the new slots. Chat UI does not gain new fields unless separately built; behavior changes only when those slots are set.

## Key files

- `web-v2/lib/ontology/templates.ts` — new query builder; mirror patterns near `buildNDEDiseaseAndOrganismQuery` / `buildNDESpeciesQueryIRI`.
- `web-v2/lib/templates/templates/dataset_search.ts` — keyword branch wiring.
- `web-v2/lib/templates/generator.ts` — ensure `dataset_search` still dispatches here (no change expected).
- `web-v2/context/packs/wobd.yaml` — slots.
- `web-v2/components/dashboard/SlotForm.tsx` — form controls.
- `web-v2/lib/landing/template-meta.ts` — user-facing copy.

## Future (separate work)

Additional portal-style facets, RDF gaps (`topicCategory`, etc.), full NDE Discovery Portal inventory.
