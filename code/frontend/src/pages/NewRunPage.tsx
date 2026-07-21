import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useDatasets } from "../api/useDatasets";
import { api } from "../api/client";
import "./NewRunPage.css";

export default function NewRunPage() {
  const { data: datasets, isLoading } = useDatasets();
  const [datasetKey, setDatasetKey] = useState("");
  const [windowSize, setWindowSize] = useState(10);
  const [contamination, setContamination] = useState(0.01);
  const [nEstimators, setNEstimators] = useState(100);
  const [randomState, setRandomState] = useState(42);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const createRun = useMutation({
    mutationFn: api.createRun,
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      navigate(`/runs/${run.id}`);
    },
    onError: (err: Error) => setSubmitError(err.message),
  });

  if (isLoading) return <p>Loading datasets…</p>;

  return (
    <form
      className="new-run-form"
      onSubmit={(e) => {
        e.preventDefault();
        setSubmitError(null);
        createRun.mutate({
          dataset_key: datasetKey,
          window: windowSize,
          contamination,
          n_estimators: nEstimators,
          random_state: randomState,
        });
      }}
    >
      <h2>Start a new run</h2>

      <label className="field">
        <span>Dataset</span>
        <select value={datasetKey} onChange={(e) => setDatasetKey(e.target.value)} required>
          <option value="" disabled>
            Select a dataset…
          </option>
          {datasets?.map((d) => (
            <option key={d.key} value={d.key} disabled={!d.available}>
              {d.label}
              {d.available ? "" : " (not downloaded)"}
            </option>
          ))}
        </select>
      </label>

      <details className="advanced-params">
        <summary>Advanced parameters</summary>

        <label className="field">
          <span>Rolling window (samples)</span>
          <input type="number" min={1} value={windowSize} onChange={(e) => setWindowSize(Number(e.target.value))} />
        </label>

        <label className="field">
          <span>Contamination</span>
          <input
            type="number"
            step="0.001"
            min={0}
            max={0.5}
            value={contamination}
            onChange={(e) => setContamination(Number(e.target.value))}
          />
        </label>

        <label className="field">
          <span>Trees (n_estimators)</span>
          <input type="number" min={1} value={nEstimators} onChange={(e) => setNEstimators(Number(e.target.value))} />
        </label>

        <label className="field">
          <span>Random state</span>
          <input type="number" value={randomState} onChange={(e) => setRandomState(Number(e.target.value))} />
        </label>
      </details>

      {submitError && <p className="error">{submitError}</p>}

      <button type="submit" disabled={!datasetKey || createRun.isPending}>
        {createRun.isPending ? "Starting…" : "Start run"}
      </button>
    </form>
  );
}
