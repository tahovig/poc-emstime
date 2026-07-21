import { useQuery } from "@tanstack/react-query";
import { api } from "./client";

export function useDatasets() {
  return useQuery({ queryKey: ["datasets"], queryFn: api.listDatasets });
}
