import { useEffect, useState } from "react";
import type { ProgressEvent } from "../api/useRunProgress";
import "./RunProgressPanel.css";

function formatStage(stage: string): string {
  return stage.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

function formatSeconds(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds));
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

interface Props {
  event: ProgressEvent | null;
}

// Ticks a real, server-anchored clock forward every second between the
// ~3s heartbeat pings -- an accurate stopwatch, not a decorative spinner.
export default function RunProgressPanel({ event }: Props) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  if (!event) {
    return <p className="progress-panel progress-panel--waiting">Waiting for the run to start…</p>;
  }

  const sinceEvent = (now - event.receivedAt) / 1000;

  return (
    <div className="progress-panel">
      <div className="progress-panel__stage">{formatStage(event.stage)}</div>
      <div className="progress-panel__timers">
        <span>Elapsed: {formatSeconds(event.elapsed_s + sinceEvent)}</span>
        <span>In this stage: {formatSeconds(event.stage_elapsed_s + sinceEvent)}</span>
      </div>
    </div>
  );
}
