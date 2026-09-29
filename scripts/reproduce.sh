#!/usr/bin/env bash
# Rebuild every published result from public CDC files.
set -euo pipefail
python -m equicvd.cli download
python -m equicvd.cli cohort
python -m equicvd.cli bench -B 200
python -m equicvd.cli sensitivity -B 200
