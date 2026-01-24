// TypeScript types for context packs

export interface GraphMetadata {
  id: string;
  endpoint?: string;
  description: string;
  good_for: string[];
  provides_ontologies?: string[];
  uses_ontologies?: string[];
  notable_relationships?: string[];
  example_predicates?: string[];
  queryable_by?: Array<{
    entity_type: string;
    property: string;
  }>;
}

export interface ContextPack {
  id: string;
  label: string;
  description?: string;
  version: string;
  endpoint_mode: {
    default: "federated" | "direct";
    federated_endpoint: string;
    direct_endpoints?: Record<string, string>;
  };
  graphs: {
    default_shortnames: string[];
    allow_user_select: boolean;
  };
  prefixes: Record<string, string>;
  guardrails: {
    max_limit: number;
    timeout_seconds: number;
    max_rows_download: number;
    allow_raw_sparql: boolean;
    allow_open_nl2sparql: boolean;
    allow_service: boolean;
    service_policy: "allowlist" | "allow_any_frink" | "allow_any" | "forbid_all";
    service_allowlist?: string[];
    forbid_ops: string[];
  };
  templates?: TemplateDefinition[];
  schema_hints?: {
    example_queries?: string[];
    common_predicates?: string[];
  };
  intent_routing?: {
    default_lane: "template" | "open";
    open_query_threshold: number;
  };
  graphs_metadata?: GraphMetadata[];
}

export interface TemplateDefinition {
  id: string;
  description: string;
  required_slots: string[];
  optional_slots?: string[];
}






