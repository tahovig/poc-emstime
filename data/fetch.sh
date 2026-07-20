#!/usr/bin/env bash
# Fetch a single raw file from the LBNL Open uPMU data portal.
# Usage: ./fetch.sh _LBNL_a6_bus1_LSTATE.gz
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p raw
curl -o "raw/${1}" "https://powerdata-download.lbl.gov/data/${1}"
