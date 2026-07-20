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
`faults.py`, `features.py`, `model.py`, `evaluate.py`, `pipeline.py`, 20 unit
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

Ran `pipeline.run()` against ~1.13 hours of real LBNL `a6_bus1` data (487,667
rows at 120Hz: real `L1MAG` voltage magnitude + real `LSTATE` as the TQ
column), with one injected fault of each type. Two detection metrics per
fault type — see the "point-wise vs window-level" finding below for why both
are reported:

| fault type          | fraction of window flagged | caught at all |
|----------------------|------------------------------|-----------------|
| `timestamp_jitter`   | 100% | yes |
| `tq_corruption`       | 100% | yes |
| `dropout`             | 33% | yes |
| `clock_step`           | 25% | yes |

Overall (point-wise): precision 0.16%, recall 62%, F1 0.33%
(`contamination=0.01` flags ~1% of all 487,667 rows — most flags are real
electrical events in the data, not the ~16 rows belonging to injected
faults, so precision against *this* synthetic ground truth is expected to be
low; it isn't a claim that those other flagged rows are false alarms in
reality).

**Three real findings from this investigation, none tuned away:**

1. **IsolationForest's default row-subsampling made rare faults nearly
   invisible.** sklearn's default `max_samples='auto'` caps each tree's
   training subsample at 256 rows. Against 487,667 rows, a 3-4-row fault
   has under a 1-in-500 chance of landing in any given tree's subsample —
   so almost no tree ever learns to split around it. This held even for the
   TQ-flag corruption, which is ~400 standard deviations from baseline.
   Confirmed by raising `max_samples` to the full dataset in `model.py`,
   which took `timestamp_jitter`/`tq_corruption` detection from 0% to 100%.
   Doesn't scale to the full multi-day dataset as-is (100 trees x millions
   of rows) — future work should use stratified/weighted sampling instead.

2. **`dropout` and `clock_step` weren't undetected — they were mislabeled.**
   Checking the model's raw anomaly scores directly (not just the
   contamination-thresholded flags) showed the dropout resumption row
   ranked **1st most anomalous of all 487,667 rows**, and the clock_step
   boundary row ranked **2nd** — both essentially perfect catches. But both
   fell one sample *after* the fault window's original `end`, because a gap
   or clock-step's evidence (an abnormal `Time_Delta_ms`) only appears once
   time resumes to normal — the labeled window itself, `[start, end]`,
   never contains it. `evaluate.py`'s point-wise scoring checked the wrong
   rows. Fixed in `faults.py`: `inject_dropout` now pads the label's `end`
   by one nominal sample interval, and `inject_clock_step` pads both `start`
   and `end`, since a step is a discontinuity at *both* transitions. Also
   fixed the demo's default `clock_step` offset (was 50ms, an exact multiple
   of the 8.333ms sample interval — shifted rows landed exactly on existing
   timestamps and got silently deduplicated in `regularize()` before
   reaching the model; changed to 33.5ms) and stopped `pipeline.py` from
   dropping a row outright just because a rolling-window stat touching an
   upstream gap was `NaN` — `Time_Delta_ms` next to it was still valid
   evidence being thrown away for no reason.

3. **A single precise catch can still look like a low detection rate.**
   Even after the fix above, `dropout`/`clock_step` show 25-33% in the
   "fraction of window flagged" column — because only the one boundary
   *transition* row in each 3-4-row padded window is genuinely anomalous;
   correctly *not* flagging the other rows (which are either missing or
   just normally-spaced-but-shifted values) drags the per-row average down
   despite catching the fault. Added `evaluate.window_level_recall()` to
   report the coarser "was the fault caught at all" question directly — all
   four fault types are 100% caught by that measure. Point-wise recall is
   still worth keeping alongside it: it distinguishes a precise single-row
   catch from a detector that lit up the whole window indiscriminately.
