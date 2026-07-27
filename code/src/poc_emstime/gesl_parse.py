"""Parses a downloaded GESL signature zip into a channel-lookup-ready frame.

GESL's zip nesting (confirmed by downloading and unzipping a real signature):
an outer zip holds a metadata CSV plus one nested zip; the nested zip holds
one or more wide-format CSVs (`Time, P001_df, P001_f, P001_ip_a, P001_ip_m,
P001_vp_a, P001_vp_m, P002_...`). Only one CSV was observed in practice, but
`extract_pmu_frame` merges on `Time` if more than one is ever present, rather
than assuming exactly one.
"""

import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

# Arbitrary anchor, not real wall-clock time: GESL's `Time` column is float
# seconds-from-signature-start (~30Hz for PMU sources), not an absolute
# epoch like LBNL's. ingest.regularize()/features.add_delta_and_rolling()
# only ever consume *relative* spacing (gap sizes, rolling windows), and
# nothing downstream compares timestamps across two different signatures,
# so any fixed anchor works.
GESL_EPOCH_ANCHOR = pd.Timestamp("2000-01-01")


def extract_pmu_frame(outer_zip_path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(outer_zip_path) as outer:
        inner_names = [n for n in outer.namelist() if n.endswith(".zip")]
        if not inner_names:
            raise ValueError(f"no nested zip found in {outer_zip_path} (found: {outer.namelist()})")
        inner_bytes = outer.read(inner_names[0])

    with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner:
        csv_names = [n for n in inner.namelist() if n.endswith(".csv")]
        if not csv_names:
            raise ValueError(f"no CSV found inside the nested zip (found: {inner.namelist()})")
        frames = [pd.read_csv(io.BytesIO(inner.read(name))) for name in csv_names]

    frame = frames[0]
    for extra in frames[1:]:
        frame = frame.merge(extra, on="Time", how="outer")

    frame = frame.set_index(GESL_EPOCH_ANCHOR + pd.to_timedelta(frame["Time"], unit="s"))
    frame = frame.drop(columns=["Time"])
    frame.index.name = "Time"

    # Confirmed against real data (sigid 5732, an "outliers preceding missing
    # data" signature): GESL's source CSVs can contain a literal inf value --
    # a genuine data-quality artifact in the raw measurement, not something
    # this project injects. Every downstream consumer (StandardScaler,
    # IsolationForest, rolling stats) requires finite input, and the rest of
    # this pipeline already has a well-defined way to represent "no usable
    # reading here": NaN. Normalizing at parse time means every consumer gets
    # that for free instead of each one needing its own inf guard.
    frame = frame.replace([np.inf, -np.inf], np.nan)
    return frame


def list_pmu_prefixes(frame: pd.DataFrame) -> list[str]:
    """['P001', 'P002', ...] derived from column names actually present, not
    an assumed count -- signatures vary in how many PMUs they cover."""
    prefixes = set()
    for col in frame.columns:
        prefix = col.split("_", 1)[0]
        if prefix.startswith("P") and prefix[1:].isdigit():
            prefixes.add(prefix)
    return sorted(prefixes, key=lambda p: int(p[1:]))


def load_signature_channel(frame: pd.DataFrame, pmu_prefix: str, suffix: str) -> pd.Series | None:
    """Locates a column by exact header name, never positional/fixed-width
    slicing: some PMUs carry an extra `_status` column absent from others in
    the same file, so the column count per PMU isn't uniform. Returns None
    if this PMU doesn't report the requested measurement at all."""
    col = f"{pmu_prefix}{suffix}"
    if col not in frame.columns:
        return None
    return frame[col]
