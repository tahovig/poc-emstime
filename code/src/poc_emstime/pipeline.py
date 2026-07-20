"""Phase-1 demo entrypoint: load -> inject synthetic faults -> engineer features
-> Isolation Forest -> score against injected ground truth. Explicitly not the
"integrated application" from CLAUDE.md — no reporting/dashboard/persistence,
just enough wiring to prove the pipeline works end to end.
"""

import argparse

import pandas as pd

from poc_emstime import evaluate, faults, features, ingest, model


def default_fault_spec(index: pd.DatetimeIndex, tq_col: str) -> list[dict]:
    """Places one window per fault type, evenly spaced across the data span."""
    n = len(index)
    if n < 40:
        raise ValueError("need at least 40 samples to place 4 non-overlapping fault windows")
    step = n // 5
    return [
        {"type": "dropout", "start": index[step], "end": index[step + 3]},
        {"type": "timestamp_jitter", "start": index[2 * step], "end": index[2 * step + 3], "std_ms": 5.0, "seed": 0},
        # offset deliberately not a multiple of the sample interval — an exact
        # multiple lands shifted rows on top of existing timestamps, which get
        # silently deduplicated away in regularize() before reaching the model
        {"type": "clock_step", "start": index[3 * step], "end": index[3 * step + 3], "offset_ms": 33.5},
        {"type": "tq_corruption", "tq_col": tq_col, "start": index[4 * step], "end": index[4 * step + 3], "bad_value": 1.0},
    ]


def run(channel_paths: dict[str, str], target_col: str, tq_col: str = "TQ", window: int = 10) -> dict:
    df = ingest.load_upmu_site(channel_paths)
    if tq_col not in df.columns:
        df[tq_col] = 0.0  # synthesize an "always good" TQ column when the real data has none

    spec = default_fault_spec(df.index, tq_col)
    df, labels = faults.inject_faults(df, spec)

    df = ingest.add_gap_features(df)
    df = ingest.regularize(df)
    df = features.add_delta_and_rolling(df, target_col, window)

    feature_cols = [
        target_col,
        f"{target_col}_Delta",
        f"{target_col}_Rolling_Std",
        f"{target_col}_Dev_From_Mean",
        "Time_Delta_ms",
        tq_col,
    ]
    # A short gap leaves real NaNs in target_col beyond ffill_limit, which
    # then propagate through the next window-1 rows of every rolling stat.
    # Those rolling-derived NaNs don't mean the row is unusable — Time_Delta_ms
    # and TQ are still valid there — so neutral-fill them instead of dropping
    # the row outright; only drop where target_col/Time_Delta_ms/tq_col
    # themselves are missing, which is genuinely unrecoverable.
    rolling_cols = [f"{target_col}_Delta", f"{target_col}_Rolling_Std", f"{target_col}_Dev_From_Mean"]
    df[rolling_cols] = df[rolling_cols].fillna(0.0)
    df = df.dropna(subset=[target_col, "Time_Delta_ms", tq_col])

    pipeline = model.build_pipeline()
    y_pred = model.detect_anomalies(pipeline, df[feature_cols].values)

    y_true = evaluate.ground_truth_mask(df.index, labels)
    return {
        "overall": evaluate.score(y_true, y_pred),
        "by_fault_type": evaluate.score_by_fault_type(df.index, labels, y_pred),
        "window_level_recall": evaluate.window_level_recall(df.index, labels, y_pred),
        "n_rows": len(df),
        "n_flagged": int(y_pred.sum()),
    }


def main():
    parser = argparse.ArgumentParser(description="Run the poc-emstime anomaly-detection demo pipeline.")
    parser.add_argument("--channel", required=True, help="path to a channel file (headerless timestamp_ns,value CSV)")
    parser.add_argument("--target-col", default="MAG")
    parser.add_argument("--window", type=int, default=10)
    args = parser.parse_args()

    results = run({args.target_col: args.channel}, target_col=args.target_col, window=args.window)
    print(f"rows scored: {results['n_rows']}, flagged anomalous: {results['n_flagged']}")
    print(f"overall: {results['overall']}")
    print("by fault type (fraction of window's rows flagged / caught at all):")
    for fault_type, rate in results["by_fault_type"].items():
        caught = results["window_level_recall"][fault_type]
        print(f"  {fault_type}: {rate:.2f} / {caught}")


if __name__ == "__main__":
    main()
