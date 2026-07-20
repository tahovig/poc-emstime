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
        {"type": "clock_step", "start": index[3 * step], "end": index[3 * step + 3], "offset_ms": 50.0},
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
    df = df.dropna(subset=feature_cols)

    pipeline = model.build_pipeline()
    y_pred = model.detect_anomalies(pipeline, df[feature_cols].values)

    y_true = evaluate.ground_truth_mask(df.index, labels)
    return {
        "overall": evaluate.score(y_true, y_pred),
        "by_fault_type": evaluate.score_by_fault_type(df.index, labels, y_pred),
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
    print("by fault type (detection rate):")
    for fault_type, rate in results["by_fault_type"].items():
        print(f"  {fault_type}: {rate:.2f}")


if __name__ == "__main__":
    main()
