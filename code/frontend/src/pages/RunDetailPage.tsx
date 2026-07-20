import { useParams, Link } from "react-router-dom";
import { useRunDetail } from "../api/useRunDetail";
import StatusBadge from "../components/StatusBadge";
import MetricsCard from "../components/MetricsCard";
import FaultTypeTable from "../components/FaultTypeTable";
import "./RunDetailPage.css";

// Progress streaming (SSE) and the anomaly-score chart land in a later
// milestone; this page polls the plain REST endpoint for now, which is
// enough to watch a run go queued -> running -> completed.
export default function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const id = Number(runId);
  const { data: run, isLoading, error } = useRunDetail(id);

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

      {(run.status === "queued" || run.status === "running") && (
        <p className="run-detail__pending-note">Run in progress ({run.status}) — this page refreshes automatically.</p>
      )}

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
        </>
      )}

      <p>
        <Link to="/">← Back to dashboard</Link>
      </p>
    </div>
  );
}
