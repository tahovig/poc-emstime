import { useQuery } from "@tanstack/react-query";
import { api } from "./client";

const ACTIVE_STATUSES = new Set(["queued", "running"]);

export function useRunDetail(runId: number) {
  return useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.getRun(runId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ACTIVE_STATUSES.has(status) ? 2000 : false;
    },
  });
}
