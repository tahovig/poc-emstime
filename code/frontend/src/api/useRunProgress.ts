import { useEffect, useRef, useState } from "react";

export interface ProgressEvent {
  run_id: number;
  stage: string;
  elapsed_s: number;
  stage_elapsed_s: number;
  // Client-side timestamp of when this event arrived -- not from the
  // server -- so the panel can interpolate a smoothly ticking elapsed
  // time between the ~3s heartbeat pings instead of only updating in
  // 3-second jumps.
  receivedAt: number;
}

export type TerminalStatus = "completed" | "failed";

interface RunProgressState {
  latest: ProgressEvent | null;
  terminal: TerminalStatus | null;
}

export function useRunProgress(runId: number, onTerminal?: (status: TerminalStatus) => void) {
  const [state, setState] = useState<RunProgressState>({ latest: null, terminal: null });
  const onTerminalRef = useRef(onTerminal);
  onTerminalRef.current = onTerminal;

  useEffect(() => {
    setState({ latest: null, terminal: null });
    const source = new EventSource(`/api/runs/${runId}/progress`);

    source.addEventListener("progress", (e) => {
      const data = JSON.parse((e as MessageEvent).data) as Omit<ProgressEvent, "receivedAt">;
      setState((s) => ({ ...s, latest: { ...data, receivedAt: Date.now() } }));
    });

    source.addEventListener("terminal", (e) => {
      const data = JSON.parse((e as MessageEvent).data) as { run_id: number; status: TerminalStatus };
      setState((s) => ({ ...s, terminal: data.status }));
      onTerminalRef.current?.(data.status);
      source.close();
    });

    // EventSource retries transient network errors on its own; nothing to
    // do here beyond that -- we only act on an explicit terminal event or
    // on unmount (the cleanup below).
    source.onerror = () => {};

    return () => source.close();
  }, [runId]);

  return state;
}
