import pandas as pd
import pytest

from poc_emstime.features import add_delta_and_rolling, unwrap_phase


def test_add_delta_and_rolling_matches_hand_computed_values():
    df = pd.DataFrame({"X": [1.0, 2.0, 4.0, 4.0, 10.0]})
    out = add_delta_and_rolling(df, "X", window=2)

    assert out["X_Delta"].tolist()[1:] == pytest.approx([1.0, 2.0, 0.0, 6.0])
    # rolling mean, window=2: [nan, 1.5, 3.0, 4.0, 7.0]
    assert out["X_Rolling_Mean"].dropna().tolist() == pytest.approx([1.5, 3.0, 4.0, 7.0])
    # dev from mean = |X - rolling_mean|, only where rolling_mean is defined
    expected_dev = [abs(4.0 - 3.0), abs(4.0 - 4.0), abs(10.0 - 7.0)]
    assert out["X_Dev_From_Mean"].dropna().tolist()[-3:] == pytest.approx(expected_dev)


def test_unwrap_phase_prevents_spurious_wrap_spike_degrees():
    # crosses the +/-180 boundary: 170 -> -170 is a real 20-degree move,
    # not the raw 340-degree jump a naive diff would compute.
    raw = pd.Series([160.0, 170.0, -170.0, -160.0])
    unwrapped = unwrap_phase(raw, period=360.0)
    raw_delta_at_wrap = abs(raw.iloc[2] - raw.iloc[1])
    unwrapped_delta_at_wrap = abs(unwrapped.iloc[2] - unwrapped.iloc[1])

    assert raw_delta_at_wrap > 300  # the spurious spike a naive diff would see
    assert unwrapped_delta_at_wrap < 30  # the true, small angular move
