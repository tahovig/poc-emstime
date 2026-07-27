# Data: LBNL Open µPMU

Source: Lawrence Berkeley National Laboratory reference micro-PMU dataset
(Stewart, E.M. 2016, *Lawrence Berkeley National Laboratory Reference microPMU
dataset, Oct 1 2015 - Dec 31 2015*), sponsored by DOE ARPA-E (DE-AR0000340),
instrumentation by Power Standards Laboratory. Download portal:
https://powerdata.lbl.gov (files served from powerdata-download.lbl.gov/data/).
No explicit redistribution license is stated in the portal's README — treat as
research data, do not redistribute raw files, do not commit them to git.

Not committed: `data/raw/` is gitignored. Files are 260-850MB each. Re-fetch
with `data/fetch.sh <filename>` against the listing at the URL above.

## Confirmed real schema (verified against a real download, not assumed)

Three sites available: `a6_bus1`, `bank_514`, `grizzly_bus1_2`. Each site is
split into **one file per channel**, not one wide CSV — this is the key
divergence from the research template's `Timestamp`/`Frequency`-column
assumption, and it means `ingest.py` has to join per-channel files on
timestamp rather than read a single file:

- `C1ANG` / `C2ANG` / `C3ANG`, `C1MAG` / `C2MAG` / `C3MAG` — current phasor
  angle/magnitude, phases A/B/C
- `L1ANG` / `L2ANG` / `L3ANG`, `L1MAG` / `L2MAG` / `L3MAG` — voltage (line)
  phasor angle/magnitude, phases A/B/C
- `LSTATE` — status/state code (verified below)

Each file: gzip-compressed, **headerless**, 2 columns, comma-separated:

```
<timestamp_ns>,<value>
1443657600000000000,0.000000
1443657600008333333,0.000000
```

- Column 1: Unix epoch **nanoseconds** (not ISO 8601 — template's
  `pd.to_datetime(errors='coerce')` won't auto-parse this; needs
  `pd.to_datetime(col, unit='ns')`).
- Column 2: float value for that channel.
- Sample interval confirmed from real deltas: `8333333 ns` = 1/120s → **120 Hz**,
  matching the µPMU spec.
- `a6_bus1` `LSTATE` file: 120,000,000 rows ≈ 11.6 days of continuous data
  starting 2015-10-01T00:00:00Z (matches the citation's Oct-Dec 2015 window).

### LSTATE as TQ-flag stand-in — confirmed usable

`LSTATE` is mostly `0.0` (checked via coarse + dense sampling) and transitions
to other discrete values (observed `4.0` in a contiguous run starting
~317s into the file) during what's presumably a flagged condition. This
behaves like a status/quality code, not a continuous measurement — treat it
as categorical, pass through as a direct feature per the research note's
"Time Quality flag" guidance, do not apply rolling stats to it.

No formal codebook enumerating what each LSTATE value means was found in the
portal's README — the numeric codes are being treated as opaque categorical
state, not decoded to specific meanings (e.g. "GPS lock lost" vs "voltage
sag"). This is a stated limitation, not a gap to silently paper over.

## Fixture data policy

`code/tests/fixtures/` contains **synthetic** data matching this confirmed
schema (timestamp_ns + value, 120Hz spacing, headerless 2-column format) —
not real LBNL-collected values, since the redistribution terms for the real
data aren't clearly stated.

## Getting a real (not synthetic) sample without the full 700-850MB download

The channel files are gzip-compressed as one continuous stream, but the
server supports HTTP range requests. Pulling a small byte-range prefix of
the compressed file and decompressing it (ignoring the trailing "unexpected
end of file" from the truncated stream) yields real, validly-decoded rows
up to the truncation point — used to validate the pipeline against ~1.13
hours of real `L1MAG` + `LSTATE` data for the Results section in the top
`README.md`, without pulling the full file:

```bash
curl -r 0-3000000 -o raw/_LBNL_a6_bus1_L1MAG_partial.gz \
  https://powerdata-download.lbl.gov/data/_LBNL_a6_bus1_L1MAG.gz
gunzip -c raw/_LBNL_a6_bus1_L1MAG_partial.gz > raw/_LBNL_a6_bus1_L1MAG_partial.csv
# drop the last line or two — the truncation point can corrupt a partial row
```

`LSTATE` (already fully downloaded for schema recon) can be aligned to the
same real time window by taking the same row count from its head, since
both channels start at the same timestamp and sample rate with no dropouts
in this early slice. These `*_partial.csv` files are real LBNL-collected
values (not synthetic) — they stay under `data/raw/`, gitignored, same as
the full files.

# Data: GESL (Grid Event Signature Library)

Source: ORNL/PNNL-hosted, DOE-funded repository of real US utility PMU
measurements (https://gesl.ornl.gov). Used for external validation against
real, independently-labeled data — see the top-level `README.md`'s
"External Validation (GESL)" section for the actual results. No stated
redistribution license was found — same policy as LBNL: not committed,
not redistributed.

Not committed: `data/gesl/raw/` is gitignored. Re-fetch with
`poc_emstime.gesl_client.download_signature(sigid)` (requires real
`GESL_EMAIL`/`GESL_APIKEY` in a repo-root `.env`, see `.env.example`).

## Confirmed real schema (verified against real downloads)

A downloaded signature is an outer zip containing a metadata CSV plus one
nested inner zip; the inner zip holds one wide-format CSV per signature:

```
Time, P001_df, P001_f, P001_ip_a, P001_ip_m, P001_vp_a, P001_vp_m, P002_...
0.0,   ...
0.033, ...
```

- `Time` — float **seconds relative to signature start** (not an absolute
  epoch like LBNL). Observed sample rate ~30Hz for PMU-sourced signatures,
  not LBNL's fixed 120Hz — `gesl_validate.py` infers `freq_ns` per signature
  from the median `Time` delta rather than assuming a fixed rate.
- Per-PMU suffixes: `_df` (frequency deviation), `_f` (frequency), `_ip_a`
  /`_ip_m` (positive-seq current angle/magnitude), `_vp_a`/`_vp_m` (positive-
  seq voltage angle/magnitude). Some PMUs unexpectedly carry an extra
  `_status` column absent from others in the same file — column layout is
  **not uniform per PMU**; `gesl_parse.load_signature_channel` looks up by
  exact header name, never by position.
- Real source data can contain a literal `inf` value (confirmed: signature
  5732, "outliers preceding missing data") — `gesl_parse.extract_pmu_frame`
  normalizes `inf`/`-inf` to `NaN` at parse time so every downstream
  consumer gets the same "no usable reading" representation the rest of
  the pipeline already understands.

Ground truth is **whole-signature-level** (the entire multi-minute clip
carries a tag like `Instrument::Timing::Frequency`), not a precise
`(start, end)` sub-window the way this project's own injected LBNL faults
are labeled — hence `evaluate.signature_level_recall`, a coarser
"was anything in this whole clip flagged" check, rather than
`window_level_recall`.

## API quirks (documented endpoint: `POST /api/apps/gesl`, `{email, apikey, output, ...}`)

- `output: "eventtags"` always returns the main **Event Signatures**
  taxonomy (public library, physical disturbances only), never the
  **Data Quality** library's tag hierarchy — regardless of the `sigtype`
  filter. The Data Quality tag IDs and the 14 real Timing signature IDs
  used here were only discoverable via the site's own undocumented
  internal API (session-JWT login), used once for research and not
  depended on going forward.
- `output: "sigids"` rejects a request with no filter at all (400
  `"Invalid or no criteria option(s) in request"`). `sensor: ["PMU"]` is a
  valid filter and returns all 123 PMU-sourced Data Quality signatures
  (contiguous ids 5711-5833) — short of the 157 total seen via the internal
  API; no filter value tried surfaced the remaining non-PMU signatures
  through the documented endpoint.

## Fixture data policy

`code/tests/fixtures/gesl_sample_pmu_frame.csv` is **synthetic**, matching
this confirmed schema (including the `_status` wrinkle on one PMU only).
The outer/inner zip nesting itself is built **in-memory inside each test**
(`zipfile.ZipFile(io.BytesIO(), ...)`) rather than as a committed binary —
more conservative than even the LBNL fixture policy above, since GESL's
redistribution terms are unverified.
