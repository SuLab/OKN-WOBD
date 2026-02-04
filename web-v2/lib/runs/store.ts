// In-memory run record storage

import type { RunRecord } from "@/types";
import type { RunStore } from "./types";

class MemoryRunStore implements RunStore {
  private records: Map<string, RunRecord> = new Map();

  save(record: RunRecord): void {
    this.records.set(record.run_id, record);
  }

  get(runId: string): RunRecord | null {
    return this.records.get(runId) || null;
  }

  list(filters?: {
    pack_id?: string;
    lane?: string;
    date_range?: { start: string; end: string };
  }): RunRecord[] {
    let results = Array.from(this.records.values());

    if (filters?.pack_id) {
      results = results.filter(r => r.context_pack_id === filters.pack_id);
    }

    if (filters?.lane) {
      results = results.filter(r => r.lane === filters.lane);
    }

    if (filters?.date_range) {
      const start = new Date(filters.date_range.start);
      const end = new Date(filters.date_range.end);
      results = results.filter(r => {
        const timestamp = new Date(r.timestamp);
        return timestamp >= start && timestamp <= end;
      });
    }

    // Sort by timestamp descending
    results.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

    return results;
  }
}

export const runStore: RunStore = new MemoryRunStore();






