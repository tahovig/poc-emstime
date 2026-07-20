import { useQuery } from "@tanstack/react-query";
import { api } from "./client";
import type { RunSummary } from "./types";

const ACTIVE_STATUSES = new Set(["queued", "running"]);

export function useRuns() {
  return useQuery({
    queryKey: ["runs"],
    queryFn: api.listRuns,
    // Polls only while something is actually in flight -- a finished
    // dashboard shouldn't keep hitting the API for no reason.
    refetchInterval: (query) => {
      const runs = (query.state.data ?? []) as RunSummary[];
      return runs.some((r) => ACTIVE_STATUSES.has(r.status)) ? 2000 : false;
    },
  });
}
