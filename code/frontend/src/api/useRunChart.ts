import { useQuery } from "@tanstack/react-query";
import { api } from "./client";

export function useRunChart(runId: number, enabled: boolean) {
  return useQuery({
    queryKey: ["run-chart", runId],
    queryFn: () => api.getRunChart(runId),
    enabled,
  });
}
