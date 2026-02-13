// Ontology-grounded query chaining module
// Exports for ontology workflow

export {
  detectOntologyIntent,
  processOntologyQuery,
} from "./preprocessor";

export {
  identifyEntities,
  generateAlternativeNames,
  type IdentifiedEntity,
  type EntityIdentificationResponse,
} from "./entity-identifier";

export {
  ONTOLOGY_MAPPING,
  getOntologyForDomain,
  getAvailableDomains,
  formatOntologyMappingForLLM,
  type OntologyMapping,
} from "./ontology-mapping";

export {
  detectNDEEncoding,
  clearEncodingCache,
} from "./nde-encoding";

export {
  buildMONDOSynonymQuery,
  buildNDEEncodingQuery,
  buildNDEDatasetQueryIRI,
  buildNDEDatasetQueryCURIE,
  buildNDEFallbackQuery,
} from "./templates";

export {
  searchOLS,
  groundTermToMONDO,
  groundTermToUBERON,
  resolveTissueToUberonIds,
  scoreMatch,
  rankMONDOCTerms,
} from "./ols-client";

export {
  searchHGNCByName,
  convertGeneNameToSymbol,
  isGeneName,
  type HGNCGeneResult,
} from "./hgnc-client";

export {
  groundDrugToWikidata,
  searchWikidataDrugs,
  type WikidataSearchResult,
} from "./wikidata-client";
