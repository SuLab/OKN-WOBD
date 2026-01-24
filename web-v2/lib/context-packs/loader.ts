import { readFileSync, readdirSync, existsSync } from "fs";
import { join } from "path";
import { parse } from "yaml";
import type { ContextPack, GraphMetadata } from "./types";

const PACKS_DIR = join(process.cwd(), "context", "packs");
const GRAPHS_DIR = join(process.cwd(), "context", "graphs");

let packsCache: Map<string, ContextPack> | null = null;

function loadGraphMetadata(): GraphMetadata[] {
  const metadata: GraphMetadata[] = [];

  if (!existsSync(GRAPHS_DIR)) {
    return metadata;
  }

  try {
    const files = readdirSync(GRAPHS_DIR);
    for (const file of files) {
      if (file.endsWith(".yaml") || file.endsWith(".yml")) {
        try {
          const content = readFileSync(join(GRAPHS_DIR, file), "utf-8");
          const graph = parse(content) as GraphMetadata;
          metadata.push(graph);
        } catch (error) {
          console.error(`Error loading graph metadata from ${file}:`, error);
        }
      }
    }
  } catch (error) {
    console.error(`Error reading graphs directory ${GRAPHS_DIR}:`, error);
  }

  return metadata;
}

export function loadContextPack(packId: string): ContextPack | null {
  if (!packsCache) {
    loadAllPacks();
  }
  return packsCache?.get(packId) || null;
}

export function loadAllPacks(): Map<string, ContextPack> {
  if (packsCache) {
    return packsCache;
  }

  packsCache = new Map();

  try {
    const files = readdirSync(PACKS_DIR);
    for (const file of files) {
      if (file.endsWith(".yaml") || file.endsWith(".yml") || file.endsWith(".json")) {
        try {
          const filePath = join(PACKS_DIR, file);
          const content = readFileSync(filePath, "utf-8");

          let pack: ContextPack;
          if (file.endsWith(".json")) {
            pack = JSON.parse(content);
          } else {
            pack = parse(content) as ContextPack;
          }

          if (pack.id) {
            // Merge detailed graph metadata from separate files
            const detailedGraphs = loadGraphMetadata();
            pack.graphs_metadata = pack.graphs_metadata || [];

            // Merge: detailed files override basic pack metadata
            for (const detailed of detailedGraphs) {
              const existingIdx = pack.graphs_metadata.findIndex(g => g.id === detailed.id);
              if (existingIdx >= 0) {
                // Merge detailed metadata with existing basic metadata
                pack.graphs_metadata[existingIdx] = {
                  ...pack.graphs_metadata[existingIdx],
                  ...detailed
                };
              } else {
                // Add new graph metadata from detailed files
                pack.graphs_metadata.push(detailed);
              }
            }

            packsCache.set(pack.id, pack);
          }
        } catch (error) {
          console.error(`Error loading context pack from ${file}:`, error);
        }
      }
    }
  } catch (error) {
    console.error(`Error reading packs directory ${PACKS_DIR}:`, error);
  }

  return packsCache;
}

export function listPacks(): ContextPack[] {
  const packs = loadAllPacks();
  return Array.from(packs.values());
}






