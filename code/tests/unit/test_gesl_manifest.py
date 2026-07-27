from poc_emstime.gesl_manifest import NEGATIVE_CONTROL_SIGIDS, TIMING_SIGNATURES


def test_negative_control_sigids_are_a_fixed_set_of_15():
    assert len(NEGATIVE_CONTROL_SIGIDS) == 15
    assert len(set(NEGATIVE_CONTROL_SIGIDS)) == 15  # no accidental duplicates


def test_negative_control_sigids_do_not_overlap_timing_signatures():
    timing_ids = {sig.sigid for sig in TIMING_SIGNATURES}
    assert timing_ids.isdisjoint(NEGATIVE_CONTROL_SIGIDS)
