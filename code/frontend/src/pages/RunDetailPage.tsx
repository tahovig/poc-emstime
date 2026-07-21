import { useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useRunDetail } from "../api/useRunDetail";
import { useRunChart } from "../api/useRunChart";
import { useRunProgress } from "../api/useRunProgress";
import StatusBadge from "../components/StatusBadge";
import MetricsCard from "../components/MetricsCard";
import FaultTypeTable from "../components/FaultTypeTable";
import RunProgressPanel from "../components/RunProgressPanel";
import AnomalyChart from "../components/AnomalyChart";
import "./RunDetailPage.css";

export default function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const id = Number(runId);
  const queryClient = useQueryClient();

  const { data: run, isLoading, error } = useRunDetail(id);

  // The SSE stream is opened regardless of the run's current status (it
  // handles the "already finished" case itself, see routers/runs.py). Its
  // terminal event is what tells this page to fetch the final REST detail
  // once, rather than polling on a timer.
  const onTerminal = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["run", id] });
    queryClient.invalidateQueries({ queryKey: ["runs"] });
  }, [queryClient, id]);
  const progress = useRunProgress(id, onTerminal);

  const chartEnabled = run?.status === "completed";
  const { data: chart } = useRunChart(id, chartEnabled);

  if (isLoading) return <p>Loading run…</p>;
  if (error) return <p className="error">Failed to load run: {(error as Error).message}</p>;
  if (!run) return null;

  return (
    <div className="run-detail">
      <div className="run-detail__header">
        <h2>Run #{run.id}</h2>
        <StatusBadge status={run.status} />
      </div>

      <p className="run-detail__dataset">{run.dataset_key}</p>

      {run.status === "failed" && run.error_message && <p className="error">{run.error_message}</p>}

      {(run.status === "queued" || run.status === "running") && <RunProgressPanel event={progress.latest} />}

      {run.status === "completed" && (
        <>
          <div className="metrics-row">
            <MetricsCard label="Rows scored" value={String(run.n_rows)} />
            <MetricsCard label="Flagged anomalous" value={String(run.n_flagged)} />
            <MetricsCard label="Precision" value={`${(run.precision! * 100).toFixed(2)}%`} />
            <MetricsCard label="Recall" value={`${(run.recall! * 100).toFixed(1)}%`} />
            <MetricsCard label="F1" value={`${(run.f1! * 100).toFixed(2)}%`} />
            <MetricsCard label="Duration" value={`${run.duration_s}s`} />
          </div>

          <h3>By fault type</h3>
          <FaultTypeTable byFaultType={run.by_fault_type} windowLevelRecall={run.window_level_recall} />

          <h3>Anomaly score over time</h3>
          {chart ? <AnomalyChart chart={chart} /> : <p>Loading chart…</p>}
        </>
      )}

      <p>
        <Link to="/">← Back to dashboard</Link>
      </p>
    </div>
  );
}
