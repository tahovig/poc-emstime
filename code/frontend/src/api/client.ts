import type { ChartData, DatasetOption, RunCreateRequest, RunDetail, RunSummary } from "./types";

const BASE_URL = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE_URL}${path}`, {
    headers: { "content-type": "application/json" },
    ...init,
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`${init?.method ?? "GET"} ${path} failed: ${resp.status} ${body}`);
  }
  if (resp.status === 204) {
    return undefined as T;
  }
  return resp.json() as Promise<T>;
}

export const api = {
  listDatasets: () => request<DatasetOption[]>("/datasets"),
  listRuns: () => request<RunSummary[]>("/runs"),
  getRun: (id: number) => request<RunDetail>(`/runs/${id}`),
  getRunChart: (id: number) => request<ChartData>(`/runs/${id}/chart`),
  createRun: (payload: RunCreateRequest) =>
    request<RunSummary>("/runs", { method: "POST", body: JSON.stringify(payload) }),
  deleteRun: (id: number) => request<void>(`/runs/${id}`, { method: "DELETE" }),
};
