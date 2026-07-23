"""Hardcoded provenance for the GESL (Grid Event Signature Library) external
validation: which real, independently-labeled Data Quality signatures to
check, and which of their tagged measurements to extract.

These IDs were discovered once via GESL's undocumented internal API (session-
JWT via username+password, not the documented email+apikey endpoint) -- that
endpoint is not a dependency this project keeps long-term. Going forward,
only the documented `output: "data"` endpoint (email+apikey) is used, against
this fixed list. GESL is static published data, not something that changes
underneath a given signature ID.

Column suffixes reflect exactly which sub-measurement each signature's real
`Instrument::Timing::*` tags name (not every tag on the signature -- most of
these also carry unrelated tags like Missing data/Locked values/Quantization,
which aren't Timing and aren't checked here).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SignatureRef:
    sigid: int
    source: str  # GESL "Data Source" field, e.g. "PMU - Eastern Interconnection"
    description: str
    columns: tuple[str, ...]  # measurement-column suffixes to check, e.g. ("_f", "_vp_a")


# The 14 Data Quality signatures (of 157 total) tagged Instrument::Timing::*
# -- real GPS/clock-error examples, independently labeled by ORNL/PNNL
# researchers, not injected by this project.
TIMING_SIGNATURES: tuple[SignatureRef, ...] = (
    SignatureRef(
        5711, "PMU - Eastern Interconnection",
        "Leap second insertion, clock error | Number of measuring PMUs: 80",
        ("_f", "_ip_a", "_vp_a"),
    ),
    SignatureRef(
        5712, "PMU - Eastern Interconnection",
        "Leap second insertion, missing data for several hours after leap second "
        "insertion, different PMUs recover at different times | Number of measuring PMUs: 10",
        ("_f", "_ip_a", "_vp_a"),
    ),
    SignatureRef(
        5724, "PMU - Eastern Interconnection",
        "Periodic jumps visible in voltage angle measurements, manifests as "
        "intermittent frequency spikes | Number of measuring PMUs: 3",
        ("_vp_a",),
    ),
    SignatureRef(
        5726, "PMU - Eastern Interconnection",
        "Clock error/drift leads to periodic adjustment of voltage angle | "
        "Number of measuring PMUs: 11",
        ("_vp_a",),
    ),
    SignatureRef(
        5735, "PMU - Eastern Interconnection",
        "Jump every ~20 seconds visible in voltage angle measurements, manifests "
        "as intermittent frequency spikes | Number of measuring PMUs: 3",
        ("_vp_a",),
    ),
    SignatureRef(
        5737, "PMU - Eastern Interconnection",
        "(no primary description; Timing tag present alongside other, dominant "
        "tags) | Number of measuring PMUs: 3",
        ("_vp_a",),
    ),
    SignatureRef(
        5757, "PMU - Eastern Interconnection",
        "(no primary description; Timing tag present alongside other, dominant "
        "tags) | Number of measuring PMUs: 3",
        ("_vp_a",),
    ),
    SignatureRef(
        5790, "PMU - Western Interconnection",
        "Leap second insertion | Number of measuring PMUs: 24",
        ("_ip_a", "_vp_a"),
    ),
    SignatureRef(
        5791, "PMU - Western Interconnection",
        "Clock error | Number of measuring PMUs: 24",
        ("_f", "_ip_a", "_vp_a"),
    ),
    SignatureRef(
        5829, "PMU - Western Interconnection",
        "Clock error, jump in voltage angle visible every ~15 seconds, which "
        "manifests as intermittent drops in frequency | Number of measuring PMUs: 2",
        ("_f", "_vp_a"),
    ),
    SignatureRef(
        5830, "PMU - Western Interconnection",
        "Clock error, jump in voltage angle, spike in frequency | Number of measuring PMUs: 2",
        ("_f", "_vp_a"),
    ),
    SignatureRef(
        5831, "PMU - Western Interconnection",
        "Clock error, jump in voltage angle, spike in frequency | Number of measuring PMUs: 2",
        ("_f", "_vp_a"),
    ),
    SignatureRef(
        5832, "PMU - Western Interconnection",
        "Clock error, jump in voltage angle, spike in frequency | Number of measuring PMUs: 2",
        ("_f", "_vp_a"),
    ),
    SignatureRef(
        5833, "PMU - Western Interconnection",
        "Clock error, jump in voltage angle, spike in frequency | Number of measuring PMUs: 2",
        ("_f", "_vp_a"),
    ),
)

# Non-Timing-tagged Data Quality signatures, sampled once (fixed seed) as a
# negative control -- populated in M5 by querying the documented
# `output: "sigids", sigtype: "data quality"` endpoint and excluding the 14
# IDs above. Empty until then.
NEGATIVE_CONTROL_SIGIDS: tuple[int, ...] = ()
