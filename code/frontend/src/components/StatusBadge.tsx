import type { RunStatus } from "../api/types";
import "./StatusBadge.css";

const LABELS: Record<RunStatus, string> = {
  queued: "Queued",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
};

export default function StatusBadge({ status }: { status: RunStatus }) {
  return <span className={`status-badge status-badge--${status}`}>{LABELS[status]}</span>;
}
