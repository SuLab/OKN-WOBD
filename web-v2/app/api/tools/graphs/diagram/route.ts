import { NextResponse } from "next/server";
import { readFile } from "fs/promises";
import path from "path";
import { loadContextPack } from "@/lib/context-packs/loader";
import type { GraphMetadata } from "@/lib/context-packs/types";
import type { ContextFileFormat } from "@/lib/graph-context/types";

const GRAPH_CONTEXT_DIR =
  process.env.GRAPH_CONTEXT_DIR
    ? path.resolve(process.env.GRAPH_CONTEXT_DIR)
    : path.join(process.cwd(), "context", "graphs");

function toId(s: string): string {
  return s.replace(/[^a-zA-Z0-9_]/g, "_").replace(/^_+|_+$/g, "") || "Node";
}

/**
 * Mermaid erDiagram reserves some words (e.g. "Class"); use safe entity ids to avoid parse errors.
 */
const RESERVED_ENTITY_IDS: Record<string, string> = {
  Class: "RDFClass",
  Object: "RDFObject",
  String: "StringType",
  Number: "NumberType",
  Date: "DateType",
  Array: "ArrayType",
  Boolean: "BooleanType",
};

function toSafeEntityId(label: string): string {
  const id = toId(label);
  return RESERVED_ENTITY_IDS[id] ?? id;
}

/** Extract a short label from an IRI (local name after # or last path segment). */
function iriToLabel(iri: string): string {
  if (!iri) return "Entity";
  const hash = iri.indexOf("#");
  if (hash >= 0) return iri.slice(hash + 1);
  const parts = iri.split("/").filter(Boolean);
  return parts[parts.length - 1] || "Entity";
}

/**
 * Load raw *_global.json when available (for full classes and object_properties).
 */
async function loadRawContextFile(shortname: string): Promise<ContextFileFormat | null> {
  const p = path.join(GRAPH_CONTEXT_DIR, `${shortname}_global.json`);
  try {
    const raw = await readFile(p, "utf-8");
    return JSON.parse(raw) as ContextFileFormat;
  } catch {
    return null;
  }
}

interface ClassNode {
  id: string;
  label: string;
  count?: number;
  attributes?: string[];
}

interface Edge {
  from: string;
  to: string;
  label: string;
}

/**
 * Derive all classes and edges from meta (context pack YAML) and optional
 * raw *_global.json (classes, queryable_by, object_properties).
 */
function deriveClassesAndEdges(
  meta: GraphMetadata,
  raw: ContextFileFormat | null
): { classes: ClassNode[]; edges: Edge[] } {
  const classMap = new Map<string, ClassNode>(); // id -> {id, label, count}
  const edges: Edge[] = [];

  // ---- Classes ----
  if (raw?.classes && raw.classes.length > 0) {
    for (const c of raw.classes) {
      const label = iriToLabel(c.iri);
      const id = toSafeEntityId(label);
      if (!classMap.has(id)) classMap.set(id, { id, label, count: c.count });
    }
  } else {
    // Fallback: derive from meta (original deriveClasses logic)
    if (meta.good_for?.includes("dataset_search")) {
      const id = toSafeEntityId("Dataset");
      if (!classMap.has(id)) classMap.set(id, { id, label: "Dataset" });
    }
    for (const q of meta.queryable_by || []) {
      if (q.entity_type) {
        const id = toSafeEntityId(q.entity_type);
        if (!classMap.has(id)) classMap.set(id, { id, label: q.entity_type });
      }
    }
  }

  // ---- Edges from queryable_by (dataset-centric: Dataset --property--> entity_type) ----
  const qb = raw?.queryable_by ?? meta.queryable_by;
  if (qb && meta.good_for?.includes("dataset_search")) {
    const subject = "Dataset";
    const subjectId = toSafeEntityId(subject);
    if (!classMap.has(subjectId)) classMap.set(subjectId, { id: subjectId, label: subject });
    for (const q of qb) {
      if (q.entity_type && q.property) {
        const toId_ = toSafeEntityId(q.entity_type);
        if (!classMap.has(toId_)) classMap.set(toId_, { id: toId_, label: q.entity_type });
        edges.push({ from: subjectId, to: toId_, label: q.property });
      }
    }
  }

  // ---- Edges from object_properties (ontology: class --property--> filler) ----
  const op = raw?.object_properties;
  if (op) {
    for (const [propKey, prop] of Object.entries(op)) {
      const edgeLabel = prop.curie || prop.label || iriToLabel(prop.iri) || iriToLabel(propKey);
      for (const r of prop.in_restriction || []) {
        const fromLabel = iriToLabel(r.class_iri);
        const toLabel = iriToLabel(r.filler_iri);
        const fromId = toSafeEntityId(fromLabel);
        const toId_ = toSafeEntityId(toLabel);
        if (!classMap.has(fromId)) classMap.set(fromId, { id: fromId, label: fromLabel });
        if (!classMap.has(toId_)) classMap.set(toId_, { id: toId_, label: toLabel });
        edges.push({ from: fromId, to: toId_, label: edgeLabel });
      }
    }
  }

  // ---- Collect attributes for Dataset class (from dataset_properties) ----
  if (raw?.dataset_properties && meta.good_for?.includes("dataset_search")) {
    const subjectId = toSafeEntityId("Dataset");
    const datasetNode = classMap.get(subjectId);
    if (datasetNode) {
      // Get properties that are already shown as relationship edges
      const relationshipProps = new Set(edges.map(e => e.label));
      
      // Collect attribute properties (exclude relationship properties and common RDF/system properties)
      const attributeEntries: Array<{ name: string; count: number }> = [];
      const skipProps = new Set([
        "rdf:type",
        "owl:sameAs",
        "rdfs:type",
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
        "http://www.w3.org/2002/07/owl#sameAs",
      ]);
      
      for (const [propKey, prop] of Object.entries(raw.dataset_properties)) {
        const propLabel = prop.curie || iriToLabel(prop.iri) || iriToLabel(propKey);
        const propIri = prop.iri || propKey;
        
        // Skip if already shown as relationship or is a system property
        if (relationshipProps.has(propLabel) || skipProps.has(propLabel) || skipProps.has(propIri)) {
          continue;
        }
        
        // Extract short name (e.g., "schema:name" -> "name", "http://schema.org/name" -> "name")
        let shortName: string;
        if (prop.curie && prop.curie.includes(":")) {
          shortName = prop.curie.split(":")[1];
        } else {
          shortName = iriToLabel(propIri);
        }
        
        // Sanitize for Mermaid (no spaces, special chars)
        shortName = shortName.replace(/[^a-zA-Z0-9_]/g, "_");
        
        if (shortName && shortName.length > 0) {
          attributeEntries.push({
            name: shortName,
            count: prop.count || 0,
          });
        }
      }
      
      // Sort by count (descending) and take top 8
      attributeEntries.sort((a, b) => b.count - a.count);
      datasetNode.attributes = attributeEntries.slice(0, 8).map(e => e.name);
    }
  }

  const classes = Array.from(classMap.values()).sort((a, b) => a.label.localeCompare(b.label));
  return { classes, edges };
}

/**
 * Build a Mermaid erDiagram (classes + relationships) similar to
 * https://frink.renci.org/kg-stats/spoke-okn/
 */
function buildErDiagram(classes: ClassNode[], edges: Edge[]): string {
  const lines: string[] = ["erDiagram"];

  for (const c of classes) {
    const attrs: string[] = [];
    
    // Add count if available
    if (c.count != null) {
      attrs.push("int count");
    }
    
    // Add attributes if available
    if (c.attributes && c.attributes.length > 0) {
      for (const attr of c.attributes) {
        attrs.push(`string ${attr}`);
      }
    }
    
    // Fallback if no attributes
    if (attrs.length === 0) {
      attrs.push("string value");
    }
    
    // Mermaid erDiagram requires each attribute on a separate line
    if (attrs.length === 1) {
      lines.push(`  ${c.id} { ${attrs[0]} }`);
    } else {
      lines.push(`  ${c.id} {`);
      for (const attr of attrs) {
        lines.push(`    ${attr}`);
      }
      lines.push(`  }`);
    }
  }

  for (const e of edges) {
    // Use }o--o{ as generic "relates to" (no cardinality from metadata)
    // Replace " and : in labels to avoid Mermaid parse errors (e.g. "Syntax error in text")
    const label = e.label.replace(/"/g, '\\"').replace(/:/g, "-");
    lines.push(`  ${e.from} }o--o{ ${e.to} : "${label}"`);
  }

  if (classes.length === 0 && edges.length === 0) {
    lines.push('  Schema { string "(No classes or relationships in metadata)" }');
  }

  return lines.join("\n");
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const shortname = searchParams.get("shortname");
  const packId = searchParams.get("pack_id") || "wobd";

  if (!shortname || !shortname.trim()) {
    return NextResponse.json(
      { error: "Specify a graph, e.g. @diagram nde or @diagram ubergraph" },
      { status: 400 }
    );
  }

  const trimmed = shortname.trim().toLowerCase();

  try {
    const pack = loadContextPack(packId);
    if (!pack) {
      return NextResponse.json(
        { error: `Context pack "${packId}" not found` },
        { status: 404 }
      );
    }

    const meta = pack.graphs_metadata?.find(
      (g) => g.id?.toLowerCase() === trimmed
    );

    if (!meta) {
      const available = (pack.graphs_metadata || [])
        .map((g) => g.id)
        .filter(Boolean);
      return NextResponse.json(
        {
          error: `Graph "${shortname}" not found in context pack.`,
          available_graphs: available,
        },
        { status: 404 }
      );
    }

    const raw = await loadRawContextFile(trimmed);
    const { classes, edges } = deriveClassesAndEdges(meta, raw);
    const mermaid = buildErDiagram(classes, edges);

    return NextResponse.json({
      mermaid,
      graphShortname: meta.id,
      label: meta.description || meta.id,
      source: raw ? "context_pack+global_json" : "context_pack",
      classes: classes.map((c) => c.label),
      edges: edges.length,
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Unknown error";
    console.error("Error generating diagram:", err);
    return NextResponse.json(
      { error: `Failed to generate diagram: ${message}` },
      { status: 500 }
    );
  }
}
