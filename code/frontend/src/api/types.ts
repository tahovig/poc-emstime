export interface DatasetOption {
  key: string;
  label: string;
  target_col: string;
  tq_col: string;
  available: boolean;
}

export type RunStatus = "queued" | "running" | "completed" | "failed";

export interface RunSummary {
  id: number;
  mode: string;
  dataset_key: string;
  status: RunStatus;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  duration_s: number | null;
  n_rows: number | null;
  n_flagged: number | null;
  precision: number | null;
  recall: number | null;
  f1: number | null;
}

export interface RunDetail extends RunSummary {
  target_col: string;
  tq_col: string;
  window: number;
  n_estimators: number;
  random_state: number;
  contamination: number;
  max_samples: number;
  by_fault_type: Record<string, number>;
  window_level_recall: Record<string, boolean>;
  error_message: string | null;
}

export interface RunCreateRequest {
  dataset_key: string;
  window?: number;
  contamination?: number;
  n_estimators?: number;
  random_state?: number;
}
