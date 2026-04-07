/**
 * Client-only slot keys: human-readable ontology labels for chips and result highlighting.
 * They must be omitted from intent sent to SPARQL generation.
 */
export type OntologyToken = { id: string; label: string };

export const UI_ONLY_ONTOLOGY_LABEL_SLOTS = [
  "health_condition_labels",
  "species_labels",
  "infectious_agent_labels",
  "organism_taxon_ids_labels",
  "tissue_uberon_ids_labels",
  "tissue_uberon_ids_ols_labels",
  "disease_efo_labels",
] as const;

/** Maps ontology id slot → parallel label array slot (same length, same order). */
export const ONTOLOGY_ID_TO_LABEL_SLOT: Record<string, string> = {
  health_condition: "health_condition_labels",
  species: "species_labels",
  infectious_agent: "infectious_agent_labels",
  organism_taxon_ids: "organism_taxon_ids_labels",
  tissue_uberon_ids: "tissue_uberon_ids_labels",
  tissue_uberon_ids_ols: "tissue_uberon_ids_ols_labels",
  disease_efo_ids: "disease_efo_labels",
};

export function omitUiOnlyOntologyLabelSlots(
  slots: Record<string, string | string[]>
): Record<string, string | string[]> {
  const out = { ...slots };
  for (const k of UI_ONLY_ONTOLOGY_LABEL_SLOTS) {
    delete out[k];
  }
  return out;
}
