# poc-emstime — Grid Timing Anomaly Detection

A Python ML pipeline for sub-second power-grid time-series data. Ingests
real micro-PMU (µPMU) synchrophasor data, synthesizes labeled timing-fault
anomalies (GPS jitter, signal dropout, clock-step offsets, time-quality-flag
corruption), engineers rolling/gap-aware features, and scores an Isolation
Forest anomaly detector against the injected ground truth.

Fourth in a series of portfolio projects supporting a pivot from software
engineering to cybersecurity engineering (see `poc-osint`, `poc-logids`,
`poc-scada`). Long-term goal: apply this to satellite clock (GPS) anomaly
detection for power-grid time synchronization infrastructure. Current phase
is data + model only — see `CLAUDE.md` for full background and `data/README.md`
for dataset provenance and schema.

## Status

Phase 1 (data + model, no app/reporting layer) complete: `ingest.py`,
`faults.py`, `features.py`, `model.py`, `evaluate.py`, `pipeline.py`, 17 unit
tests + 1 integration test, all passing. Validated against ~1.13 hours of
real LBNL µPMU data (see Results below), not just synthetic fixtures.

## Setup

```bash
cd code
python3 -m venv poc-emstime-venv
source poc-emstime-venv/bin/activate
pip install -e ".[dev]"
pytest
```

Real data is not committed (`data/raw/` is gitignored, files are hundreds of
MB). Fetch with `data/fetch.sh <filename>` — see `data/README.md` for the
file listing and confirmed schema.

## Results (real data)

Ran `pipeline.run()` against ~1.13 hours of real LBNL `a6_bus1` data (487,640
rows at 120Hz: real `L1MAG` voltage magnitude + real `LSTATE` as the TQ
column), with one injected fault of each type. Detection rate (recall) per
fault type:

| fault type         | detected |
|---------------------|----------|
| `timestamp_jitter`  | 100% |
| `tq_corruption`      | 100% |
| `dropout`            | 0% |
| `clock_step`          | 0% |

Overall: precision 0.12%, recall 60%, F1 0.25% (`contamination=0.01` flags
~1% of all 487,640 rows — most flags are real electrical events in the data,
not the ~16 rows belonging to injected faults, so precision against *this*
synthetic ground truth is expected to be low; it isn't a claim that those
other flagged rows are false alarms in reality).

**Two real findings, not tuned away:**

1. **IsolationForest's default row-subsampling made rare faults nearly
   invisible.** sklearn's default `max_samples='auto'` caps each tree's
   training subsample at 256 rows. Against 487,640 rows, a 3-4-row fault
   has under a 1-in-500 chance of landing in any given tree's subsample —
   so almost no tree ever learns to split around it. This held even for the
   TQ-flag corruption, which is ~400 standard deviations from baseline.
   Confirmed by raising `max_samples` to the full dataset in `model.py`,
   which took `timestamp_jitter`/`tq_corruption` detection from 0% to 100%.
   Doesn't scale to the full multi-day dataset as-is (100 trees x millions
   of rows) — future work should use stratified/weighted sampling instead.

2. **`dropout` and `clock_step` are still undetected — root cause identified,
   not yet fixed.** A short gap under `ffill_limit` still leaves real `NaN`s
   in the value column, which propagate through the next `window - 1` rows
   of every rolling feature (`rolling(10)` touches its previous 9 rows).
   `dropna(subset=feature_cols)` then drops those rows outright — including
   the exact row where the gap's evidence (`Time_Delta_ms` spiking to ~5x
   nominal) is strongest. The anomaly is real and large, but it gets deleted
   before the model ever sees it. Fixing this (e.g., excluding `Time_Delta_ms`
   from the rolling-NaN-driven drop, or evaluating gap detection at the
   reindexed/`Was_Filled` row instead of relying on `dropna` survivors) is
   scoped as follow-up work, not patched here to avoid inflating the numbers
   above.
