import { Link } from "react-router-dom";
import { useRuns } from "../api/useRuns";
import StatusBadge from "../components/StatusBadge";
import "./DashboardPage.css";

function formatPercent(value: number | null, digits = 1): string {
  return value === null ? "—" : `${(value * 100).toFixed(digits)}%`;
}

export default function DashboardPage() {
  const { data: runs, isLoading, error } = useRuns();

  if (isLoading) return <p>Loading runs…</p>;
  if (error) return <p className="error">Failed to load runs: {(error as Error).message}</p>;

  if (!runs || runs.length === 0) {
    return (
      <div className="dashboard-empty">
        <p>No runs yet.</p>
        <Link to="/runs/new">Start one</Link>
      </div>
    );
  }

  return (
    <table className="run-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Dataset</th>
          <th>Status</th>
          <th>Rows</th>
          <th>Precision</th>
          <th>Recall</th>
          <th>F1</th>
          <th>Duration (s)</th>
          <th>Created</th>
        </tr>
      </thead>
      <tbody>
        {runs.map((run) => (
          <tr key={run.id}>
            <td>
              <Link to={`/runs/${run.id}`}>{run.id}</Link>
            </td>
            <td>{run.dataset_key}</td>
            <td>
              <StatusBadge status={run.status} />
            </td>
            <td>{run.n_rows ?? "—"}</td>
            <td>{formatPercent(run.precision, 2)}</td>
            <td>{formatPercent(run.recall)}</td>
            <td>{formatPercent(run.f1, 2)}</td>
            <td>{run.duration_s ?? "—"}</td>
            <td>{new Date(`${run.created_at}Z`).toLocaleString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
