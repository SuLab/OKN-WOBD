// Shared TypeScript types for WOBD Web v2

export interface Intent {
  lane: "template" | "open" | "raw";
  task: string; // e.g., "dataset_search"
  context_pack: string;
  graph_mode: "federated" | "single_graph";
  graphs: string[];
  slots: Record<string, any>;
  confidence: number;
  notes: string;
  ontology_workflow?: boolean;
}

export interface RunRecord {
  run_id: string;
  timestamp: string;
  user_message: string;
  context_pack_id: string;
  context_pack_version: string;
  lane: "template" | "open" | "raw";
  intent_json?: Intent;
  executed_sparql: string;
  repaired_sparql?: string;
  endpoint: string;
  graph_mode: "federated" | "single_graph";
  graphs: string[];
  from_clauses: string[];
  validation_decisions: {
    service_allowed: boolean;
    service_blocked_reason?: string;
    limit_injected: boolean;
    limit_value?: number;
  };
  execution_metrics: {
    latency_ms: number;
    row_count: number;
    error?: string;
  };
  repair_attempt?: {
    attempted: boolean;
    success: boolean;
    changes: string[];
    repaired_query?: string;
  };
  preflight_result?: {
    predicate_check?: {
      exists: boolean;
      count?: number;
    };
    class_check?: {
      exists: boolean;
      count?: number;
    };
    sample_query?: {
      row_count: number;
      latency_ms: number;
    };
    warnings: string[];
  };
}

export interface SPARQLResult {
  head: {
    vars: string[];
  };
  results: {
    bindings: Array<Record<string, { type: string; value: string }>>;
  };
}

export interface GraphInfo {
  shortname: string;
  label: string;
  endpoint?: string;
}

// Ontology query state types
export interface MONDOGroundingResult {
  mondo: string; // IRI
  label: string;
  matchedText: string;
  matchedPred: string;
  matchScore?: number; // OLS match score (3=exact label, 2=exact synonym, 1=fuzzy, 0=none)
  matchType?: string; // "label", "synonym", "none"
  obo_id?: string; // e.g., "MONDO:0006664"
  is_obsolete?: boolean;
  alternatives?: Array<{
    mondo: string;
    label: string;
    matchScore: number;
    matchType: string;
  }>;
}

export interface MONDOSynonymResult {
  mondo: string; // IRI
  label?: string;
  synonyms: string[];
}

export interface OntologyQueryState {
  entity_type: "disease" | "condition" | "species" | "drug" | "gene" | "other";
  raw_phrase: string;
  candidate_labels: string[];
  grounded_mondo_terms: MONDOGroundingResult[];
  synonyms: MONDOSynonymResult[];
  dataset_results?: SPARQLResult;
  fallback_used: boolean;
  nde_encoding?: "iri" | "curie";
  stage_errors?: {
    entity_identification?: string;
    alternative_generation?: string;
    mondo_grounding?: string;
    synonym_expansion?: string;
    nde_encoding?: string;
    dataset_query?: string;
  };
  debug_info?: {
    identified_entities?: Array<{ term: string; domain: string; ontology: string }>;
    primary_entity?: { term: string; domain: string; ontology: string };
    search_terms_used?: string[];
    ontology_query_executed?: boolean; // Generic name - applies to MONDO, NCBITaxon, Wikidata, etc.
    ontology_query_result_count?: number; // Generic name - applies to any ontology
    ontology_query_sample?: string;
    alternatives_used?: boolean;
    has_gene_expression?: boolean;
    recommended_graphs?: string[];
    partial_matches_need_confirmation?: Array<{
      mondo: string;
      label: string;
      obo_id?: string;
      matchScore: number;
      matchType: string;
      matchedText: string;
    }>;
  };
}

// Chat message types
export type MessageRole = "user" | "assistant" | "error";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: string;
  mermaid?: string;
  lane?: "template" | "open" | "raw";
  run_id?: string;
  intent?: Intent;
  sparql?: string;
  results?: SPARQLResult;
  error?: string;
  ontology_state?: OntologyQueryState;
  metadata?: {
    latency_ms?: number;
    row_count?: number;
    limit_applied?: number;
    results_limited?: boolean;
    repair_attempt?: RunRecord["repair_attempt"];
    preflight_result?: RunRecord["preflight_result"];
  };
  plan_id?: string;
  step_id?: string;
  query_plan?: QueryPlan;
  is_plan_preview?: boolean;
}

// Graph metadata
export interface GraphMetadata {
  id: string;
  endpoint?: string;
  description: string;
  good_for: string[]; // ["entity_lookup", "dataset_search", "entity_relationships"]
  provides_ontologies?: string[];
  uses_ontologies?: string[];
  notable_relationships?: string[];
  example_predicates?: string[];
  queryable_by?: Array<{
    entity_type: string;
    property: string;
  }>;
}

// Multi-hop query planning
export interface QueryStep {
  id: string;
  intent: Intent;
  target_graphs: string[];
  depends_on: string[];
  uses_results_from?: string;
  status: "pending" | "running" | "complete" | "failed";
  results?: SPARQLResult;
  sparql?: string;
  error?: string;
  latency_ms?: number;
  description?: string;
}

export interface QueryPlan {
  id: string;
  steps: QueryStep[];
  original_query: string;
  created_at: number;
  graph_routing_rationale?: string;
}

// Result context passing between steps
export interface StepResultContext {
  step_id: string;
  entities_resolved?: Record<string, string>;
  dataset_ids?: string[];
  disease_iris?: string[];
  disease_labels?: string[]; // For fallback text search when IRI mapping fails
  gene_iris?: string[];
  species_iris?: string[];
  drug_iris?: string[];
}

// Execution events for streaming
export type ExecutionEvent =
  | { type: "plan_generated"; plan: QueryPlan }
  | { type: "step_started"; step: QueryStep }
  | { type: "step_completed"; step: QueryStep; context: StepResultContext }
  | { type: "step_failed"; step: QueryStep; error: string }
  | { type: "plan_completed"; results: QueryStep[] };



