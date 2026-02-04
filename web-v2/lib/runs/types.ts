import type { RunRecord } from "@/types";

// Run record storage interface

export interface RunStore {
  save(record: RunRecord): void;
  get(runId: string): RunRecord | null;
  list(filters?: {
    pack_id?: string;
    lane?: string;
    date_range?: { start: string; end: string };
  }): RunRecord[];
}






