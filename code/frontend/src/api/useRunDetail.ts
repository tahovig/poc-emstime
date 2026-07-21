import { useQuery } from "@tanstack/react-query";
import { api } from "./client";

// No refetchInterval here: the SSE progress stream (useRunProgress) is
// what drives live updates on this page now. Its onTerminal callback
// invalidates this query so it refetches once with final results, instead
// of polling REST on a timer alongside a stream that's already telling us
// exactly when something changed.
export function useRunDetail(runId: number) {
  return useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.getRun(runId),
  });
}
